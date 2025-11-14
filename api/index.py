"""
Vercel serverless function entry point for RAG Maker.
"""
import sys
from pathlib import Path

# Add the project root to Python path BEFORE any imports
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

# Now try to import dependencies and the app
try:
    from src.rag_maker.service import app
    # Vercel expects the ASGI app to be named 'app'
    # FastAPI is ASGI-compatible
except ImportError as e:
    # Dependencies not installed - create diagnostic response using basic FastAPI mock
    # We can't use real FastAPI since it's not installed, so create a minimal ASGI app

    import json

    async def app(scope, receive, send):
        """Minimal ASGI app that shows diagnostic info when dependencies aren't installed."""
        if scope['type'] == 'http':
            import os

            error_info = {
                "error": "Dependencies not installed - Vercel did not install requirements.txt",
                "import_error": str(e),
                "working_directory": os.getcwd(),
                "file_location": str(Path(__file__)),
                "python_path": sys.path,
                "api_directory_contents": os.listdir(Path(__file__).parent),
                "requirements_txt_exists": (Path(__file__).parent / "requirements.txt").exists(),
                "requirements_txt_content": (
                    (Path(__file__).parent / "requirements.txt").read_text()
                    if (Path(__file__).parent / "requirements.txt").exists()
                    else "NOT FOUND"
                ),
                "root_directory_contents": os.listdir(Path(__file__).parent.parent),
                "message": "Check Vercel build logs to see if Python dependencies were installed"
            }

            body = json.dumps(error_info, indent=2).encode()

            await send({
                'type': 'http.response.start',
                'status': 500,
                'headers': [[b'content-type', b'application/json']],
            })
            await send({
                'type': 'http.response.body',
                'body': body,
            })
