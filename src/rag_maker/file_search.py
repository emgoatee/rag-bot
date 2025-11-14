from __future__ import annotations

import argparse
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, List, Optional

from google import genai
from google.genai import types

from .config import Settings, get_settings

POLL_SECONDS = 5


class FileSearchManager:
    """Convenience wrapper around the Gemini File Search APIs."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.api_key:
            raise ValueError(
                "GOOGLE_AI_API_KEY environment variable is required. "
                "Get your API key from https://aistudio.google.com/apikey"
            )
        self.client = genai.Client(api_key=self.settings.api_key)
        self._stores_api = getattr(self.client, "file_search_stores", None)
        self._file_search_api = getattr(self.client, "file_search", None)
        self._operations_api = getattr(self.client, "operations", None)

    # --- store management -------------------------------------------------

    def list_stores(self):
        """List all available file search stores."""
        if self._stores_api:
            try:
                return list(self._stores_api.list())
            except Exception:
                return []
        return []

    def create_store(self, display_name: str = "RAG Maker Store") -> str:
        """Create a new file search store with the given display name."""
        if self._stores_api:
            store = self._stores_api.create(config={"display_name": display_name})
        elif self._file_search_api and hasattr(self._file_search_api, "create_store"):
            store = self._file_search_api.create_store(display_name=display_name)
        else:  # pragma: no cover - unexpected SDK shape
            raise RuntimeError("File Search API not available in client.")

        store_name = getattr(store, "name", None) or store["name"]
        return store_name

    def get_store(self, store_id: str):
        """Get details for a specific store."""
        if self._stores_api:
            try:
                return self._stores_api.get(name=store_id)
            except Exception:
                return None
        return None

    def ensure_store(self, display_name: str = "RAG Maker Store") -> str:
        """Return an existing store id or create a new store."""

        if self.settings.file_search_store:
            return self.settings.file_search_store

        # Try to get an existing store first
        stores = self.list_stores()
        if stores:
            # Return the first available store
            first_store = stores[0]
            return getattr(first_store, "name", None) or first_store.get("name")

        # Create a new store if none exist
        return self.create_store(display_name)

    def list_files(self, store: Optional[str] = None):
        store_id = store or self.ensure_store()
        if self._stores_api and hasattr(self._stores_api, "files"):
            files_endpoint = getattr(self._stores_api, "files")
            return list(files_endpoint.list(file_search_store_name=store_id))
        if self._file_search_api and hasattr(self._file_search_api, "list_files"):
            return list(self._file_search_api.list_files(store=store_id))
        return []

    # --- ingestion --------------------------------------------------------

    def upload_files(
        self,
        paths: Iterable[Path],
        store: Optional[str] = None,
        wait: bool = True,
        display_names: Optional[Iterable[str]] = None,
    ) -> List[types.Operation]:
        """Upload local files to File Search and optionally block until ready."""

        store_id = store or self.ensure_store()
        uploaded: List[types.Operation] = []
        paths_list = list(paths)
        display_list = list(display_names) if display_names else [None] * len(paths_list)

        if display_names and len(display_list) != len(paths_list):
            raise ValueError("display_names length must match paths length.")

        for idx, path in enumerate(paths_list):
            path = Path(path).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(path)

            display_name = display_list[idx] or path.name
            if self._stores_api and hasattr(self._stores_api, "upload_to_file_search_store"):
                operation = self._stores_api.upload_to_file_search_store(
                    file=str(path),
                    file_search_store_name=store_id,
                    config={"display_name": display_name},
                )
            elif self._file_search_api and hasattr(self._file_search_api, "upload_file"):
                operation = self._file_search_api.upload_file(store=store_id, path=str(path))
            else:  # pragma: no cover - unexpected SDK shape
                raise RuntimeError("Upload API not available in client.")

            uploaded.append(operation)

        if wait:
            for idx, operation in enumerate(uploaded):
                uploaded[idx] = self.wait_until_ready(operation)

        return uploaded

    def wait_until_ready(self, operation: types.Operation) -> types.Operation:
        current = operation
        while True:
            done = getattr(current, "done", None)
            if done or (isinstance(current, dict) and current.get("done")):
                break
            time.sleep(POLL_SECONDS)
            if self._operations_api and hasattr(self._operations_api, "get"):
                current = self._operations_api.get(operation=current)
            else:
                current = self.client.operations.get(current)

        if isinstance(current, dict):
            if current.get("error"):
                raise RuntimeError(str(current["error"]))
        else:
            error = getattr(current, "error", None)
            if error and getattr(error, "code", 0):
                raise RuntimeError(str(error))

        return current

    def get_operation_status(self, name: str):
        if self._operations_api and hasattr(self._operations_api, "get"):
            try:
                placeholder = SimpleNamespace(name=name)
                return self._operations_api.get(operation=placeholder)
            except AttributeError:
                try:
                    return self._operations_api.get(operation=name)
                except AttributeError:
                    pass
            except Exception:
                pass
        try:
            return self.client.operations.get(name)
        except Exception:
            rest_name = name.replace("/upload/operations/", "/operations/")
            url = f"https://generativelanguage.googleapis.com/v1beta/{rest_name}"
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params={"key": self.settings.api_key})
                response.raise_for_status()
                return response.json()

    def get_document_metadata(self, document_path: str):
        if not document_path:
            return None

        if self._stores_api and hasattr(self._stores_api, "documents"):
            documents_api = getattr(self._stores_api, "documents")
            try:
                return documents_api.get(name=document_path)
            except Exception:
                pass

        url = f"https://generativelanguage.googleapis.com/v1beta/{document_path}"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params={"key": self.settings.api_key})
            response.raise_for_status()
            return response.json()

    # --- querying ---------------------------------------------------------

    def _to_contents(self, question: str):
        part_cls = getattr(types, "Part", None)
        content_cls = getattr(types, "Content", None)
        if part_cls and content_cls:
            part = part_cls(text=question)
            return [content_cls(role="user", parts=[part])]
        return [{"role": "user", "parts": [{"text": question}]}]

    def _build_tool_config(self, store_id: str):
        if self._stores_api:
            payload = {"file_search_store_names": [store_id]}
        else:
            payload = {"store": store_id}

        file_search_cls = getattr(types, "FileSearchToolConfig", None)
        tool_cls = getattr(types, "Tool", None)

        if file_search_cls:
            fs_config = file_search_cls(**payload)
            if tool_cls:
                return tool_cls(file_search=fs_config)
            return {"file_search": fs_config}

        if tool_cls:
            return tool_cls(file_search=payload)

        return {"file_search": payload}

    def _build_generate_config(self, tool, temperature: float):
        generate_config_cls = getattr(types, "GenerateContentConfig", None)
        if generate_config_cls:
            return generate_config_cls(
                tools=[tool],
                temperature=temperature,
                system_instruction=(
                    "Answer concisely using the provided search results. "
                    "Always cite sources when relevant."
                ),
            )
        return {
            "tools": [tool],
            "temperature": temperature,
            "system_instruction": (
                "Answer concisely using the provided search results. "
                "Always cite sources when relevant."
            ),
        }

    def ask(
        self,
        question: str,
        store: Optional[str] = None,
        max_chunks: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """Submit a grounded question to Gemini using File Search."""

        store_id = store or self.ensure_store()
        max_chunks = max_chunks or self.settings.max_chunks
        temperature = temperature if temperature is not None else self.settings.temperature

        tool = self._build_tool_config(store_id)
        config = self._build_generate_config(tool, temperature)

        response = self.client.models.generate_content(
            model=self.settings.model,
            contents=self._to_contents(question),
            config=config,
        )

        return response


# --------------------------------------------------------------------------- #
# CLI entry points


def _ingest_command(args: argparse.Namespace) -> None:
    manager = FileSearchManager()
    store = manager.ensure_store(display_name=args.display_name)
    operations = manager.upload_files(args.paths, store=store, wait=not args.no_wait)
    for op in operations:
        response = getattr(op, "response", None) or op.get("response")
        file_name = None
        if isinstance(response, dict):
            file_name = response.get("file", {}).get("name") or response.get("name")
        elif response is not None:
            file_name = getattr(response, "name", None)
        print(f"Uploaded: {file_name or op}")


def _query_command(args: argparse.Namespace) -> None:
    manager = FileSearchManager()
    response = manager.ask(args.question, max_chunks=args.max_chunks, temperature=args.temperature)
    print(getattr(response, "text", str(response)))
    candidate = response.candidates[0]
    grounding = (
        getattr(candidate, "grounding_metadata", None)
        or getattr(candidate, "groundingMetadata", None)
    )
    if grounding:
        chunks = (
            getattr(grounding, "grounding_chunks", None)
            or getattr(grounding, "groundingChunks", None)
            or (grounding.get("grounding_chunks") if isinstance(grounding, dict) else None)
            or (grounding.get("groundingChunks") if isinstance(grounding, dict) else None)
            or []
        )
        if chunks:
            print("--- Citations ---")
            for chunk in chunks:
                if isinstance(chunk, dict):
                    chunk_id = chunk.get("chunk_reference") or chunk.get("id")
                    title = chunk.get("title") or chunk.get("display_name")
                    uri = chunk.get("uri")
                else:
                    chunk_id = getattr(chunk, "chunk_reference", None) or getattr(chunk, "id", None)
                    title = getattr(chunk, "title", None) or getattr(chunk, "display_name", None)
                    uri = getattr(chunk, "uri", None)
                print(f"- {title or chunk_id}: {uri or ''}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with Google AI File Search.")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Upload files into the File Search store.")
    ingest.add_argument("paths", nargs="+", type=Path)
    ingest.add_argument("--display-name", default="RAG Maker Store")
    ingest.add_argument("--no-wait", action="store_true", help="Do not wait for processing.")
    ingest.set_defaults(func=_ingest_command)

    query = sub.add_parser("query", help="Ask a grounded question.")
    query.add_argument("question")
    query.add_argument("--max-chunks", type=int)
    query.add_argument("--temperature", type=float)
    query.set_defaults(func=_query_command)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

