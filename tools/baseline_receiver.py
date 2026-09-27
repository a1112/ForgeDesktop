"""Temporary, loopback-only transfer of a public sampler and bounded benchmark report."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    sampler = Path(__file__).with_name('process_metrics.py').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != '/sampler.py':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(sampler)))
            self.end_headers()
            self.wfile.write(sampler)

        def do_POST(self):
            if self.path != '/report' or self.headers.get('Origin'):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4 * 1024 * 1024:
                    raise ValueError('report size')
                body = self.rfile.read(length)
                report = json.loads(body)
                if report.get('schemaVersion') != 1 or report.get('uid') != 1000:
                    raise ValueError('report identity')
                # Exactly one diagnostic result, never overwrite existing evidence.
                fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as output:
                    output.write(body)
            except (OSError, ValueError, TypeError, AttributeError):
                self.send_error(400)
                return
            self.send_response(201)
            self.send_header('Content-Length', '0')
            self.end_headers()

    HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
