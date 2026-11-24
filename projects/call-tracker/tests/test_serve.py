"""Part C: the local helper (serve.py), started in a test folder with a fake search and its own port."""
import http.client
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

APP = Path(__file__).parent.parent
FIX = Path(__file__).parent / "fixtures"

FAKE_SEARCH = '''import pathlib, time
here = pathlib.Path(__file__).parent
n = here / "runs.txt"
n.write_text(str(int(n.read_text()) + 1 if n.exists() else 1))
time.sleep(1.5)
print("fake search done")
'''


class Helper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="ct-helper-"))
        for f in ("serve.py", "index.html"):
            shutil.copy(APP / f, cls.dir / f)
        shutil.copy(FIX / "site" / "keywords.js", cls.dir / "keywords.js")
        (cls.dir / "fetch_calls.py").write_text(FAKE_SEARCH)
        cls.port = random.randint(19000, 19900)
        cls.proc = cls.start()
        for _ in range(50):
            try:
                cls.request("GET", "/")
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def start(cls):
        return subprocess.Popen([sys.executable, str(cls.dir / "serve.py"), "--no-browser"],
                                env={**os.environ, "CT_PORT": str(cls.port)},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.proc.kill()
        cls.proc.wait()
        shutil.rmtree(cls.dir, True)

    @classmethod
    def request(cls, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=10)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        data = r.read().decode("utf-8", "replace")
        c.close()
        return r.status, data

    # C1
    def test_c1_serves_the_page(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("<title>Call Tracker</title>", body)

    def test_c1_port_busy_gives_friendly_message(self):
        second = subprocess.run([sys.executable, str(self.dir / "serve.py"), "--no-browser"],
                                env={**os.environ, "CT_PORT": str(self.port), "BROWSER": "true"},
                                capture_output=True, text=True, timeout=20)
        self.assertIn("is busy", second.stdout)

    # C2
    def test_c2_other_websites_are_refused(self):
        status, _ = self.request("POST", "/api/refresh", headers={"Origin": "https://evil.example.com"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/keywords", body="{}", headers={"Origin": "https://evil.example.com"})
        self.assertEqual(status, 403)

    def test_c2_wrong_host_is_refused(self):
        status, _ = self.request("GET", "/api/status", headers={"Host": f"attacker.example:{self.port}"})
        self.assertEqual(status, 403)

    # C3
    def test_c3_keywords_bad_data_refused(self):
        for body in ("not json", json.dumps({"keywords": "nlp"}), json.dumps([1, 2])):
            status, _ = self.request("POST", "/api/keywords", body=body, headers={"Content-Type": "application/json"})
            self.assertEqual(status, 400, body)

    def test_c3_keywords_saved_and_readable_by_the_script(self):
        settings = {"keywords": ["machine translation", "  ", "speech"], "exclude": ["climate"]}
        status, body = self.request("POST", "/api/keywords", body=json.dumps(settings),
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(status, 200, body)
        text = (self.dir / "keywords.js").read_text(encoding="utf-8")
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        self.assertEqual(data, {"keywords": ["machine translation", "speech"], "exclude": ["climate"]})

    # C4
    def test_c4_second_refresh_click_does_not_start_a_second_search(self):
        (self.dir / "runs.txt").unlink(missing_ok=True)
        _, first = self.request("POST", "/api/refresh")
        _, second = self.request("POST", "/api/refresh")
        self.assertTrue(json.loads(first)["running"])
        self.assertEqual(json.loads(first)["started"], json.loads(second)["started"])
        for _ in range(60):
            if not json.loads(self.request("GET", "/api/status")[1])["running"]:
                break
            time.sleep(0.1)
        st = json.loads(self.request("GET", "/api/status")[1])
        self.assertEqual((st["running"], st["exit_code"]), (False, 0))
        self.assertIn("fake search done", st["log"])
        self.assertEqual((self.dir / "runs.txt").read_text(), "1", "the search ran exactly once")


if __name__ == "__main__":
    unittest.main()
