from __future__ import annotations

import json
import logging
import os
import base64
import hmac
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from wsgiref.simple_server import make_server
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .cli import PROVIDERS, build_credentials, build_summarizer
from .extractor import TrafilaturaExtractor
from .fetcher import HttpxFetcher
from .writer import MarkdownPaperWriter, to_banglish

ROOT = Path(__file__).resolve().parent
UI = ROOT / "webui"
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def paper_display_title(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0:1]
    title = first_line[0].removeprefix("#").strip() if first_line else path.stem
    return to_banglish(title)


def run_job(job_id: str, options: dict) -> None:
    try:
        with LOCK:
            JOBS[job_id]["stage"] = "Fetching page"
        html = HttpxFetcher().fetch(options["url"])
        with LOCK:
            JOBS[job_id]["stage"] = "Extracting article"
        page = TrafilaturaExtractor().extract(html, options["url"])
        with LOCK:
            JOBS[job_id]["stage"] = "Generating analysis"
        summarizer = build_summarizer(
            options["provider"], options.get("model") or None,
            int(options.get("max_chars", 120000)),
            int(options.get("max_output_tokens", 2000)),
            build_credentials(None),
        )
        paper = summarizer.summarize(page)
        out_dir = Path(options.get("out_dir") or "papers").expanduser()
        result = MarkdownPaperWriter(out_dir).write(paper)
        with LOCK:
            JOBS[job_id].update(status="done", stage="Saved", path=str(result.resolve()), title=page.title)
    except (Exception, SystemExit) as exc:
        logging.exception("Web operation failed")
        with LOCK:
            JOBS[job_id].update(status="error", stage="Failed", error=str(exc))


class Handler(BaseHTTPRequestHandler):
    server_version = "PaperScraperUI/1.0"

    def log_message(self, fmt, *args):
        logging.info("%s - %s", self.address_string(), fmt % args)

    def _json(self, value: dict, status: int = 200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = min(int(self.headers.get("Content-Length", "0")), 20000)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            configured = build_credentials(None)
            keys = {name: (name == "ollama" or bool(configured.get(name))) for name in PROVIDERS}
            self._json({"providers": list(PROVIDERS), "keys": keys, "out_dir": "papers"})
        elif parsed.path == "/api/papers":
            out_dir = Path("papers")
            files = sorted(out_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if out_dir.exists() else []
            self._json({"papers": [{"name": p.name, "title": paper_display_title(p), "path": str(p.resolve()), "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")} for p in files[:50]]})
        elif parsed.path.startswith("/api/papers/"):
            name = unquote(parsed.path.rsplit("/", 1)[-1])
            if Path(name).name != name or not name.endswith(".md"):
                return self._json({"error": "Invalid paper name"}, 400)
            path = Path("papers") / name
            if not path.is_file():
                return self._json({"error": "Paper not found"}, 404)
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            if parse_qs(parsed.query).get("download") == ["1"]:
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name, safe='')}")
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with LOCK:
                job = JOBS.get(job_id)
            self._json(job or {"error": "Unknown operation"}, 404 if job is None else 200)
        elif parsed.path in {"/", "/index.html", "/library", "/library/"}:
            self._file(UI / "index.html", "text/html; charset=utf-8")
        elif parsed.path in {"/style.css", "/app.js"}:
            name = parsed.path[1:]
            self._file(UI / name, "text/css; charset=utf-8" if name.endswith("css") else "text/javascript; charset=utf-8")
        else:
            self._json({"error": "Not found"}, 404)

    def _file(self, path: Path, content_type: str):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/keys":
            try:
                data = self._body()
                provider, key = data.get("provider"), data.get("key", "").strip()
                if provider not in PROVIDERS or provider == "ollama" or not key:
                    return self._json({"error": "Choose a provider and enter a key."}, 400)
                key_path = Path("keys.json")
                current = json.loads(key_path.read_text(encoding="utf-8")) if key_path.exists() else {}
                if not isinstance(current, dict):
                    return self._json({"error": "keys.json must contain a JSON object."}, 400)
                current[provider] = key
                key_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
                return self._json({"ok": True})
            except (OSError, json.JSONDecodeError) as exc:
                return self._json({"error": str(exc)}, 400)
        if self.path != "/api/run":
            return self._json({"error": "Not found"}, 404)
        try:
            data = self._body()
            url = data.get("url", "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                return self._json({"error": "Enter a valid http or https URL."}, 400)
            provider = data.get("provider", "anthropic")
            if provider not in PROVIDERS:
                return self._json({"error": "Unknown provider."}, 400)
            options = {**data, "url": url, "provider": provider}
            job_id = uuid.uuid4().hex
            with LOCK:
                JOBS[job_id] = {"status": "running", "stage": "Queued"}
            threading.Thread(target=run_job, args=(job_id, options), daemon=True).start()
            self._json({"id": job_id}, 202)
        except (ValueError, TypeError) as exc:
            self._json({"error": str(exc)}, 400)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    host = "127.0.0.1"
    port = int(os.getenv("PAPER_UI_PORT", "8765"))
    server = make_server(host, port, application)
    print(f"Paper Scraper UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Paper Scraper UI")
    finally:
        server.server_close()


def application(environ, start_response):
    """WSGI entry point for Passenger/cPanel and the local development server."""
    expected_user = os.getenv("PAPER_UI_USER", "")
    expected_password = os.getenv("PAPER_UI_PASSWORD", "")
    if expected_user or expected_password:
        supplied = environ.get("HTTP_AUTHORIZATION", "")
        try:
            scheme, encoded = supplied.split(" ", 1)
            username, password = base64.b64decode(encoded).decode("utf-8").split(":", 1)
        except (ValueError, UnicodeDecodeError):
            username = password = ""
            scheme = ""
        if (scheme.lower() != "basic"
                or not hmac.compare_digest(username, expected_user)
                or not hmac.compare_digest(password, expected_password)):
            body = b"Authentication required."
            start_response("401 Unauthorized", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body))), ("WWW-Authenticate", 'Basic realm="Paper Scraper"')])
            return [body]

    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    status, content_type, body = "200 OK", "text/plain; charset=utf-8", b""
    extra_headers = []

    def json_response(data, code=200):
        nonlocal status, content_type, body
        status = f"{code} { {200: 'OK', 202: 'Accepted', 400: 'Bad Request', 404: 'Not Found'}.get(code, 'Error') }"
        content_type = "application/json; charset=utf-8"
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    try:
        if method == "GET" and path in {"/", "/index.html", "/library", "/library/"}:
            content_type, body = "text/html; charset=utf-8", (UI / "index.html").read_bytes()
        elif method == "GET" and path in {"/style.css", "/app.js"}:
            filename = path.lstrip("/")
            content_type = "text/css; charset=utf-8" if filename.endswith(".css") else "text/javascript; charset=utf-8"
            body = (UI / filename).read_bytes()
        elif method == "GET" and path == "/api/config":
            configured = build_credentials(None)
            keys = {name: (name == "ollama" or bool(configured.get(name))) for name in PROVIDERS}
            json_response({"providers": list(PROVIDERS), "keys": keys, "out_dir": "papers"})
        elif method == "GET" and path == "/api/papers":
            out_dir = Path("papers")
            files = sorted(out_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if out_dir.exists() else []
            json_response({"papers": [{"name": p.name, "title": paper_display_title(p), "path": str(p.resolve()), "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")} for p in files[:50]]})
        elif method == "GET" and path.startswith("/api/papers/"):
            name = unquote(path.rsplit("/", 1)[-1])
            if Path(name).name != name or not name.endswith(".md"):
                json_response({"error": "Invalid paper name"}, 400)
            else:
                paper_path = Path("papers") / name
                if not paper_path.is_file():
                    json_response({"error": "Paper not found"}, 404)
                else:
                    content_type, body = "text/markdown; charset=utf-8", paper_path.read_bytes()
                    if parse_qs(environ.get("QUERY_STRING", "")).get("download") == ["1"]:
                        extra_headers.append(("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name, safe='')}"))
        elif method == "GET" and path.startswith("/api/jobs/"):
            with LOCK:
                job = JOBS.get(path.rsplit("/", 1)[-1])
            json_response(job or {"error": "Unknown operation"}, 200 if job else 404)
        elif method == "POST" and path in {"/api/run", "/api/keys"}:
            length = min(int(environ.get("CONTENT_LENGTH") or 0), 20000)
            data = json.loads(environ["wsgi.input"].read(length) or b"{}")
            if path == "/api/keys":
                provider, key = data.get("provider"), data.get("key", "").strip()
                if provider not in PROVIDERS or provider == "ollama" or not key:
                    json_response({"error": "Choose a provider and enter a key."}, 400)
                else:
                    key_path = Path("keys.json")
                    current = json.loads(key_path.read_text(encoding="utf-8")) if key_path.exists() else {}
                    if not isinstance(current, dict):
                        json_response({"error": "keys.json must contain a JSON object."}, 400)
                    else:
                        current[provider] = key
                        key_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
                        json_response({"ok": True})
            else:
                url = data.get("url", "").strip()
                parsed = urlparse(url)
                provider = data.get("provider", "anthropic")
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    json_response({"error": "Enter a valid http or https URL."}, 400)
                elif provider not in PROVIDERS:
                    json_response({"error": "Unknown provider."}, 400)
                else:
                    job_id = uuid.uuid4().hex
                    with LOCK:
                        JOBS[job_id] = {"status": "running", "stage": "Queued"}
                    threading.Thread(target=run_job, args=(job_id, {**data, "url": url, "provider": provider}), daemon=True).start()
                    json_response({"id": job_id}, 202)
        else:
            json_response({"error": "Not found"}, 404)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logging.exception("Request failed")
        json_response({"error": str(exc)}, 400)

    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body))), ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), *extra_headers])
    return [body]


if __name__ == "__main__":
    main()
