from __future__ import annotations

import asyncio
import mimetypes
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from .file_search import FileSearchManager

app = FastAPI(title="RAG Maker", version="0.2.0")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web"

if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="ui-assets")


def get_manager() -> FileSearchManager:
    return FileSearchManager()


async def _download_remote_bytes(url: str, timeout: float = 60.0) -> tuple[int, bytes, str]:
    """Fetch remote content using stdlib so we avoid optional deps."""

    def _fetch() -> tuple[int, bytes, str]:
        req = Request(url, headers={"User-Agent": "RAG-Maker/1.0"})
        with urlopen(req, timeout=timeout) as response:
            status = response.getcode() or 500
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
        return status, data, content_type

    return await asyncio.to_thread(_fetch)


class AskRequest(BaseModel):
    question: str
    max_chunks: Optional[int] = None
    temperature: Optional[float] = None
    store_id: Optional[str] = None


class CreateStoreRequest(BaseModel):
    display_name: str


class AskResponse(BaseModel):
    answer: str
    citations: List[dict]


class UrlUploadRequest(BaseModel):
    url: HttpUrl
    display_name: Optional[str] = None


def _coalesce(obj: Any, *keys: str) -> Optional[Any]:
    for key in keys:
        if isinstance(obj, dict):
            if key in obj and obj[key] is not None:
                return obj[key]
        elif hasattr(obj, key):
            value = getattr(obj, key)
            if value is not None:
                return value
    return None


def _serialize_operation(operation: Any, fallback_name: Optional[str] = None) -> Dict[str, Any]:
    response = _coalesce(operation, "response", "result")
    document_name = _coalesce(response, "document_name", "documentName", "name")
    parent = _coalesce(response, "parent", "file_search_store_name", "fileSearchStoreName")
    display_name = _coalesce(response, "display_name", "displayName") or fallback_name
    done = bool(
        _coalesce(operation, "done")
        or (isinstance(operation, dict) and operation.get("done"))
    )
    error_obj = _coalesce(operation, "error")
    error_msg = None
    if error_obj:
        if isinstance(error_obj, dict):
            error_msg = error_obj.get("message") or str(error_obj)
        else:
            error_msg = str(error_obj)

    return {
        "operation": _coalesce(operation, "name"),
        "document_name": document_name,
        "display_name": display_name
        or (Path(document_name).name if document_name else None)
        or fallback_name,
        "store": parent,
        "done": done,
        "error": error_msg,
    }


def _serialize_file(file_obj: Any) -> Dict[str, Any]:
    return {
        "name": _coalesce(file_obj, "name"),
        "display_name": _coalesce(file_obj, "display_name", "displayName"),
        "state": _coalesce(file_obj, "state"),
        "size_bytes": _coalesce(file_obj, "size_bytes", "sizeBytes"),
        "chunk_count": _coalesce(file_obj, "chunk_count", "chunkCount"),
        "create_time": _coalesce(file_obj, "create_time", "createTime"),
        "update_time": _coalesce(file_obj, "update_time", "updateTime"),
    }


def _serialize_store(store_obj: Any) -> Dict[str, Any]:
    return {
        "name": _coalesce(store_obj, "name"),
        "display_name": _coalesce(store_obj, "display_name", "displayName"),
        "create_time": _coalesce(store_obj, "create_time", "createTime"),
        "update_time": _coalesce(store_obj, "update_time", "updateTime"),
    }


@app.get("/", include_in_schema=False)
async def ui_root():
    if WEB_DIR.exists():
        return FileResponse(WEB_DIR / "index.html")
    return {"status": "RAG Maker API ready"}


@app.get("/stores")
async def list_stores(manager: FileSearchManager = Depends(get_manager)):
    """List all available file search stores."""
    try:
        stores = manager.list_stores()
        return {"stores": [_serialize_store(store) for store in stores]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/stores")
async def create_store(
    payload: CreateStoreRequest,
    manager: FileSearchManager = Depends(get_manager),
):
    """Create a new file search store."""
    try:
        store_id = manager.create_store(display_name=payload.display_name)
        store = manager.get_store(store_id)
        if store:
            return {"store": _serialize_store(store)}
        return {"store": {"name": store_id, "display_name": payload.display_name}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/stores/{store_id:path}")
async def get_store(
    store_id: str,
    manager: FileSearchManager = Depends(get_manager),
):
    """Get details for a specific store."""
    try:
        store = manager.get_store(store_id)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        return {"store": _serialize_store(store)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    store_id: Optional[str] = None,
    manager: FileSearchManager = Depends(get_manager),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    temp_paths: List[Path] = []
    display_names: List[str] = []
    try:
        for file in files:
            original_name = file.filename or "document"
            suffix = Path(original_name).suffix or ".tmp"
            handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            contents = await file.read()
            handle.write(contents)
            handle.flush()
            handle.close()
            temp_paths.append(Path(handle.name))
            display_names.append(original_name)

        uploaded = manager.upload_files(temp_paths, store=store_id, wait=False, display_names=display_names)
        serialized = [
            _serialize_operation(op, fallback_name=display_names[idx])
            for idx, op in enumerate(uploaded)
        ]
        return {"uploaded": serialized}
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()


@app.post("/upload-url")
async def upload_url(
    payload: UrlUploadRequest,
    store_id: Optional[str] = None,
    manager: FileSearchManager = Depends(get_manager),
):
    temp_dir: Optional[Path] = None
    try:
        try:
            status, body, content_type = await _download_remote_bytes(str(payload.url))
        except URLError as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download remote file: {exc}") from exc
        if status != 200:
            raise HTTPException(status_code=status, detail="Failed to download remote file.")

        parsed = urlparse(str(payload.url))
        candidate_name = payload.display_name or Path(parsed.path).name or "remote-document"
        content_type = (content_type or "").split(";")[0]
        suffix = Path(candidate_name).suffix
        if not suffix:
            guess = mimetypes.guess_extension(content_type or "")
            if guess:
                candidate_name += guess

        temp_dir = Path(tempfile.mkdtemp())
        target = temp_dir / candidate_name
        target.write_bytes(body)

        uploaded = manager.upload_files([target], store=store_id, wait=False, display_names=[candidate_name])
        return {"uploaded": [_serialize_operation(uploaded[0], fallback_name=candidate_name)]}
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/files")
async def list_files(
    store_id: Optional[str] = None,
    manager: FileSearchManager = Depends(get_manager),
):
    try:
        files = manager.list_files(store=store_id)
    except Exception as exc:  # pragma: no cover - surface error
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"files": [_serialize_file(item) for item in files]}


class OperationStatusResponse(BaseModel):
    done: bool
    error: Optional[str] = None
    document_name: Optional[str] = None
    display_name: Optional[str] = None
    store: Optional[str] = None


@app.get("/operation-status", response_model=OperationStatusResponse)
async def operation_status(
    name: str,
    manager: FileSearchManager = Depends(get_manager),
):
    try:
        operation = manager.get_operation_status(name)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    serialized = _serialize_operation(operation)
    done = serialized.get("done", False)
    error = serialized.get("error")
    response = _coalesce(operation, "response", "result")
    display_name = serialized.get("display_name")
    store = serialized.get("store")
    document_name = _coalesce(response, "document_name", "documentName", "name")
    if document_name and store and not document_name.startswith("fileSearchStores/"):
        document_name = f"fileSearchStores/{store}/documents/{document_name}"

    return OperationStatusResponse(
        done=done,
        error=error,
        document_name=document_name,
        display_name=display_name,
        store=store,
    )


@app.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    manager: FileSearchManager = Depends(get_manager),
):
    try:
        response = manager.ask(
            payload.question,
            store=payload.store_id,
            max_chunks=payload.max_chunks,
            temperature=payload.temperature,
        )
    except Exception as exc:  # pragma: no cover - surface to client
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    candidate = response.candidates[0]
    text = getattr(response, "text", None)
    if not text:
        parts = getattr(candidate.content, "parts", [])
        if parts:
            text = getattr(parts[0], "text", None) or str(parts[0])
    if not text:
        raise HTTPException(status_code=502, detail="No content in response.")

    grounding = getattr(candidate, "grounding_metadata", None) or getattr(candidate, "groundingMetadata", None)
    citations: List[Dict[str, Any]] = []
    doc_meta_cache: Dict[str, Any] = {}
    seen_citations = set()
    if grounding:
        chunks = (
            getattr(grounding, "grounding_chunks", None)
            or getattr(grounding, "groundingChunks", None)
            or (grounding.get("grounding_chunks") if isinstance(grounding, dict) else None)
            or (grounding.get("groundingChunks") if isinstance(grounding, dict) else None)
            or []
        )
        for chunk in chunks:
            chunk_dict = {}
            if isinstance(chunk, dict):
                chunk_dict = chunk
            else:
                chunk_dict = {
                    "chunk_reference": getattr(chunk, "chunk_reference", None) or getattr(chunk, "id", None),
                    "id": getattr(chunk, "id", None),
                    "title": getattr(chunk, "title", None) or getattr(chunk, "display_name", None),
                    "display_name": getattr(chunk, "display_name", None),
                    "uri": getattr(chunk, "uri", None),
                    "snippet": getattr(chunk, "snippet", None),
                    "segment": getattr(chunk, "segment", None),
                    "retrieved_context": getattr(chunk, "retrieved_context", None),
                }

            chunk_ref = chunk_dict.get("chunk_reference") or chunk_dict.get("id")
            segment = chunk_dict.get("segment") or {}
            if segment and not isinstance(segment, dict):
                segment = {
                    "title": getattr(segment, "title", None),
                    "text": getattr(segment, "text", None),
                    "snippet": getattr(segment, "snippet", None),
                    "uri": getattr(segment, "uri", None),
                }

            retrieved_context = chunk_dict.get("retrieved_context") or {}
            if retrieved_context and not isinstance(retrieved_context, dict):
                retrieved_context = {
                    "text": getattr(retrieved_context, "text", None),
                    "title": getattr(retrieved_context, "title", None),
                    "uri": getattr(retrieved_context, "uri", None),
                }

            snippet = chunk_dict.get("snippet")
            if not snippet and segment:
                snippet = segment.get("snippet") or segment.get("text")
            if not snippet and retrieved_context:
                snippet = retrieved_context.get("text")

            if snippet and len(snippet) > 500:
                snippet = snippet[:497].rstrip() + "..."

            chunk_title = (
                chunk_dict.get("title")
                or chunk_dict.get("display_name")
                or segment.get("title")
                or retrieved_context.get("title")
            )
            uri = chunk_dict.get("uri") or segment.get("uri") or retrieved_context.get("uri")

            document_path = None
            if chunk_ref:
                document_path = chunk_ref.split("#", 1)[0]

            document_display_name = None
            document_uri = None
            document_error = None
            if document_path and document_path not in doc_meta_cache:
                try:
                    doc_meta_cache[document_path] = manager.get_document_metadata(document_path)
                except Exception as meta_exc:  # pragma: no cover - surface to client
                    doc_meta_cache[document_path] = {"error": str(meta_exc)}

            meta = doc_meta_cache.get(document_path) if document_path else None
            if isinstance(meta, dict):
                document_display_name = meta.get("displayName") or meta.get("title")
                document_uri = meta.get("uri")
                document_error = meta.get("error")
            else:
                document_display_name = document_display_name or retrieved_context.get("title")
                document_uri = document_uri or retrieved_context.get("uri")

            dedupe_key = (document_path, snippet, document_display_name)
            if dedupe_key in seen_citations:
                continue
            seen_citations.add(dedupe_key)

            citations.append(
                {
                    "id": chunk_ref or chunk_dict.get("id"),
                    "title": chunk_title,
                    "uri": uri or document_uri,
                    "snippet": snippet,
                    "chunk_reference": chunk_ref,
                    "document_path": document_path,
                    "document_display_name": document_display_name,
                    "document_uri": document_uri,
                    "document_error": document_error,
                }
            )

    return AskResponse(answer=text, citations=citations)

