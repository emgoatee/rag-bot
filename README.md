# RAG Maker (Google AI File Search)

This project bootstraps a Retrieval-Augmented Generation (RAG) workflow that uses the **Google AI File Search** capability in the Gemini API to ground answers on your private documents. The repository contains reference code, configuration guidance, and scripts to manage file ingestion, monitor indexing, and issue grounded queries.

## Why Google AI File Search?

- **Managed RAG pipeline** – handles chunking, embeddings, vector search, and grounding out of the box.
- **Transparent answers** – every response can return citations to the exact passages retrieved.
- **Multi-modal ingest** – PDFs, Office docs, code, JSON, and more are supported with automatic parsing.
- **Same Gemini tooling** – integrates with `google-genai` client SDKs and Google AI Studio.

## High-Level Architecture

- **Data ingestion**: upload files into a File Search Store via the Gemini API.
- **Indexing phase**: Google processes the files (chunking + embedding); progress is polled until `READY`.
- **Grounded inference**: `generate_content` calls reference the File Search Store through the `file_search` tool to fetch relevant snippets, which the model uses to answer prompts.
- **Application layer**: a thin Python service exposes `/ask` and `/upload` endpoints to your front-end or automation.

```text
Client / UI ──► FastAPI service ──► Gemini File Search Store ──► Gemini Model
                      ▲                     │
                      └──── ingest scripts ─┘
```

## Repository Layout

```
.
├── README.md              # This guide
├── pyproject.toml         # Poetry-based Python environment (optional)
├── requirements.txt       # Alternative pip requirements
└── src/
    └── rag_maker/
        ├── __init__.py
        ├── config.py      # Settings loader for API keys and store IDs
        ├── file_search.py # Helpers to create stores, upload files, poll status
        └── service.py     # FastAPI app exposing upload & ask endpoints
```

## Prerequisites

1. **Gemini API access** with the File Search feature enabled.
2. **Python 3.10+** recommended.
3. `pip install google-genai fastapi uvicorn python-dotenv`.
4. An API key stored as `GOOGLE_AI_API_KEY` in `.env` or your shell.

> Sign up or check access via [Google AI Studio](https://aistudio.google.com/). Enable billing and confirm the “File Search” tool is visible in the Gemini dashboard.

## Configuration

Create an `.env` file (never commit API keys):

```
GOOGLE_AI_API_KEY=your-api-key
FILE_SEARCH_STORE_ID=stores/your-store-id   # Optional: populated after creation
GEMINI_MODEL=models/gemini-1.5-flash-002
MAX_CHUNKS=16
TEMPERATURE=0.3
```

You can either provision a File Search Store in Google AI Studio or create one with the helper in `file_search.py`. Store IDs look like `stores/abcd1234`.

## Usage

### 1. Set up environment

```bash
poetry install
# or
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Upload documents

```bash
python -m rag_maker.file_search ingest docs/*.pdf
```

This command uploads files, polls until processing is complete, and prints citation-ready document IDs.

### 3. Run the service

```bash
uvicorn rag_maker.service:app --reload
```

`POST /ask` with JSON `{"question": "What does the compliance policy say about audits?"}` to receive a grounded response and citations.

### 4. Direct scripted use

```bash
python -m rag_maker.file_search query "Summarize the onboarding policy"
```

### 5. Guided web interface

```bash
uvicorn rag_maker.service:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) for a step-by-step UI that walks you through uploading files, importing remote links, reviewing status, and chatting with grounded responses.

## Google Gemini API Notes (Nov 2025)

- **File Search APIs**
  - `client.file_search_stores.create(config={"display_name": "..."})`
  - `client.file_search_stores.upload_to_file_search_store(file="...", file_search_store_name=store.name)`
  - Poll the resulting long-running operation with `client.operations.get(operation)`
  - `client.file_search_stores.files.list(file_search_store_name=store.name)`
- **Grounded generation**
  - Provide a `GenerateContentConfig` with `tools=[{"file_search": {"file_search_store_names": [store.name]}}]`
  - Add a `system_instruction` that enforces citation usage.
  - Inspect `response.candidates[0].grounding_metadata` to extract sources and snippets.

The SDK returns structured status updates; expect states like `PROCESSING`, `READY`, or `FAILED`. Poll responsibly (e.g., exponential backoff).

## Testing

- Unit-test `file_search.py` with mocks for the Gemini client (see `tests/` scaffold to add).
- Consider contract tests if you have a non-production store.
- Manual smoke test: upload sample FAQ document and ask multi-step question expecting citations.

## Roadmap Ideas

- Add persistent storage (Postgres) for question/answer logs.
- Build front-end chat widget with streaming responses.
- Integrate Google Drive or Cloud Storage ingestion pipelines.
- Add auth + rate limiting to the FastAPI layer.

## References

- [Official Google AI File Search docs](https://ai.google.dev/gemini-api/docs/file-search)
- [Gemini API Python Client (`google-genai`)](https://pypi.org/project/google-genai/)
- [Gemini API Pricing](https://ai.google.dev/pricing)

Happy building! PRs welcome.


