"""Local helper for the Call Tracker: enables the "Refresh calls" and "Save" buttons.

Run:  python3 serve.py
It opens http://127.0.0.1:8765 in your browser. Stop it with Ctrl+C.

Only reachable from this laptop (127.0.0.1). It serves this folder, runs
fetch_calls.py in the background when you click Refresh, and saves keywords.js.
"""
import datetime
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
HOST, PORT = "127.0.0.1", 8765
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

state = {"running": False, "started": None, "finished": None, "exit_code": None, "log": ""}
lock = threading.Lock()


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def run_fetch():
    """Run fetch_calls.py as a separate process and keep its output for the page."""
    try:
        p = subprocess.run([sys.executable, str(HERE / "fetch_calls.py")], cwd=HERE,
                           capture_output=True, text=True, timeout=900)
        code, log = p.returncode, p.stdout + p.stderr
    except Exception as e:
        code, log = -1, f"Could not run fetch_calls.py: {e}"
    with lock:
        state.update(running=False, finished=now(), exit_code=code, log=log)
    print(f"[refresh] finished with exit code {code}")


def write_keywords(data):
    clean = lambda xs: [str(x).strip()[:80] for x in xs if str(x).strip()]
    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ("keywords", "exclude")):
        raise ValueError("expected {keywords: [...], exclude: [...]}")
    settings = {"keywords": clean(data["keywords"]), "exclude": clean(data["exclude"])}
    (HERE / "keywords.js").write_text(
        "// My keywords. Edit them on the Call Tracker page (Keywords panel) and click Save,\n"
        "// or edit the lists below by hand. Both the page and fetch_calls.py read this file.\n"
        "window.CALL_TRACKER_SETTINGS = " + json.dumps(settings, indent=2, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    return settings


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # always serve the newest files
        super().end_headers()

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def trusted(self):
        """Only accept requests from this page, not from other websites open in the browser."""
        origin = self.headers.get("Origin")
        return (self.headers.get("Host") in ALLOWED_HOSTS and
                (origin is None or origin.split("//", 1)[-1] in ALLOWED_HOSTS))

    def do_GET(self):
        if self.path.split("?")[0] == "/api/status":
            if not self.trusted():
                return self.send_json({"error": "forbidden"}, 403)
            with lock:
                return self.send_json(state)
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if not self.trusted():
            return self.send_json({"error": "forbidden"}, 403)
        path = self.path.split("?")[0]
        if path == "/api/refresh":
            with lock:
                if not state["running"]:
                    state.update(running=True, started=now(), finished=None, exit_code=None, log="")
                    threading.Thread(target=run_fetch, daemon=True).start()
                    print("[refresh] started")
                return self.send_json(state)
        if path == "/api/keywords":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length > 100_000:
                    raise ValueError("too large")
                settings = write_keywords(json.loads(self.rfile.read(length)))
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)
            print(f"[keywords] saved {len(settings['keywords'])} keywords, {len(settings['exclude'])} hidden topics")
            return self.send_json({"ok": True, "settings": settings})
        return self.send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        pass   # keep the terminal quiet; refresh/save events are printed above


def main():
    sys.stdout.reconfigure(line_buffering=True)   # show messages right away
    url = f"http://{HOST}:{PORT}/"
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Port {PORT} is busy: the helper is probably already running. Open {url}")
        webbrowser.open(url)
        return
    print(f"Call Tracker helper running at {url}  (only on this laptop). Stop with Ctrl+C.")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
