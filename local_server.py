import http.server
import socketserver
import json
import os
import sqlite3
from db_client import SupabaseDBClient

PORT = 5000

class EchoLocalHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/like":
            self._handle_increment("likes")
        elif self.path == "/api/play":
            self._handle_increment("plays")
        else:
            self.send_error(404, "Not Found")

    def _handle_increment(self, field):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
            row_id = data.get("row_id")
            if not row_id:
                raise ValueError("Missing row_id")

            db = SupabaseDBClient(env='local')
            success = False
            if field == "likes":
                success = db.increment_likes(row_id)
            else:
                success = db.increment_plays(row_id)

            if success:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_error(500, "Database Update Failed")
        except Exception as e:
            self.send_error(400, str(e))

if __name__ == "__main__":
    handler = EchoLocalHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"[Echo Server] Serving locally at http://localhost:{PORT}")
        print(f"[Echo Server] Ready to handle local Likes and Plays.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Echo Server] Shutting down.")
            httpd.shutdown()
