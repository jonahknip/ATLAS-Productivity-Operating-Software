"""
Simple static file server for ATLAS Web UI.
Can be deployed to Railway as a separate service.
"""

import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 3000))
DIRECTORY = Path(__file__).parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def end_headers(self):
        # Add CORS headers for API requests
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()


if __name__ == "__main__":
    print(f"ATLAS Web UI server starting on port {PORT}")
    print(f"Serving files from: {DIRECTORY}")
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    httpd.serve_forever()
