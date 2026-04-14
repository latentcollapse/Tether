#!/usr/bin/env python3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


HOST = "127.0.0.1"
PORT = 9876


class PingHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {"raw": raw.decode("utf-8", errors="replace")}

        subject = payload.get("subject", "<no subject>")
        sender = payload.get("from", "<unknown>")
        handle = payload.get("handle", "<no handle>")
        print(
            f"[tether-ping] from={sender} subject={subject} handle={handle}",
            flush=True,
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    print(f"[tether-ping] listening on http://{HOST}:{PORT}", flush=True)
    HTTPServer((HOST, PORT), PingHandler).serve_forever()
