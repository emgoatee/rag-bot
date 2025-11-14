"""Diagnostic endpoint that doesn't require any dependencies."""
import json
import os
import sys
from pathlib import Path


def handler(event, context):
    """Vercel serverless function handler."""
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
        "status": "Diagnostic Info",
        "message": "If you see this, the function is working but dependencies may not be installed",
        "api_directory": str(api_dir),
        "api_directory_contents": api_contents,
        "root_directory": str(root_dir),
        "root_directory_contents": root_contents,
        "requirements_txt_exists": req_exists,
        "requirements_txt_path": str(api_dir / "requirements.txt"),
        "requirements_txt_content": req_content,
        "working_directory": os.getcwd(),
        "python_version": sys.version,
        "python_path": sys.path,
    }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(info, indent=2)
    }
