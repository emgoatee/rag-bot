"""Diagnostic endpoint that doesn't require any dependencies."""
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        api_dir = Path(__file__).parent
        root_dir = api_dir.parent

        try:
            api_contents = os.listdir(api_dir)
        except Exception as e:
            api_contents = f"Error: {e}"

        try:
            root_contents = os.listdir(root_dir)
        except Exception as e:
            root_contents = f"Error: {e}"

        try:
            req_file = api_dir / "requirements.txt"
            req_exists = req_file.exists()
            req_content = req_file.read_text() if req_exists else "NOT FOUND"
        except Exception as e:
            req_exists = False
            req_content = f"Error reading: {e}"

        info = {
            "status": "Dependencies NOT installed",
            "api_directory": str(api_dir),
            "api_directory_contents": api_contents,
            "root_directory": str(root_dir),
            "root_directory_contents": root_contents,
            "requirements_txt_exists": req_exists,
            "requirements_txt_path": str(api_dir / "requirements.txt"),
            "requirements_txt_content": req_content,
            "working_directory": os.getcwd(),
            "python_version": os.sys.version,
            "help": "If requirements.txt exists but dependencies aren't installed, check Vercel build logs"
        }

        body = json.dumps(info, indent=2).encode()

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(body)
