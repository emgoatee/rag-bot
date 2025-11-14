"""
Vercel serverless function entry point for RAG Maker.
"""
import sys
import traceback
from pathlib import Path

try:
    # Add the project root to Python path
    root = Path(__file__).parent.parent
    sys.path.insert(0, str(root))

    # Import the FastAPI app
    from src.rag_maker.service import app

    # Vercel expects the ASGI app to be named 'app'
    # FastAPI is ASGI-compatible

except Exception as e:
    # If import fails, create a minimal FastAPI app that shows the error
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    error_details = {
        "error": "Failed to initialize RAG Maker",
        "type": type(e).__name__,
        "message": str(e),
        "traceback": traceback.format_exc(),
        "python_path": sys.path,
        "working_directory": str(Path.cwd()),
        "file_location": str(Path(__file__)),
        "root_path": str(root) if 'root' in locals() else "not set"
    }

    @app.get("/")
    @app.post("/{path:path}")
    @app.get("/{path:path}")
    async def error_handler(path: str = ""):
        return JSONResponse(
            status_code=500,
            content=error_details
        )
