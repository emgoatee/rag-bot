"""
Vercel serverless function entry point for RAG Maker.
"""
import sys
from pathlib import Path

# Add the project root to Python path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from src.rag_maker.service import app

# Vercel expects the ASGI app to be named 'app'
# FastAPI is ASGI-compatible
