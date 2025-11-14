"""Simple test endpoint to verify dependencies are installed."""
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Try importing the dependencies
            import fastapi
            import google.genai
            import pydantic

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"""Dependencies installed successfully!

FastAPI version: {fastapi.__version__}
Google GenAI available: Yes
Pydantic available: Yes

This means requirements.txt is working!
""".encode())
        except ImportError as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Import error: {e}\n\nDependencies are NOT installed!".encode())
