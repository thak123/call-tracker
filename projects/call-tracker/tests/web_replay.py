"""Record real website answers once, then replay them in tests (no internet needed).

    python3 tests/web_replay.py record         # refresh ALL saved copies (needs internet)
    python3 tests/web_replay.py record --add   # keep the old copies, only record pages not saved yet
"""
import datetime
import gzip
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).parent
WEB = HERE / "fixtures" / "web"
INDEX = WEB / "index.json"
FIXED_TODAY = datetime.date(2026, 11, 24)
SETTINGS = HERE / "fixtures" / "keywords_test.js"


def url_of(req):
    return req.full_url if isinstance(req, urllib.request.Request) else str(req)


class FakeResponse(io.BytesIO):
    status = 200
    headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


@contextmanager
def replay(fail_hosts=()):
    """Answer every request from the saved copies. Hosts in fail_hosts act as if they were down."""
    index = json.loads(INDEX.read_text())
    real = urllib.request.urlopen

    def fake(req, timeout=None):
        url = url_of(req)
        if any(h in url for h in fail_hosts):
            raise urllib.error.URLError(f"pretend {url.split('/')[2]} is down")
        if url not in index:
            raise urllib.error.URLError(f"not in saved copies: {url}")
        return FakeResponse(gzip.decompress((WEB / index[url]).read_bytes()))
    urllib.request.urlopen = fake
    try:
        yield
    finally:
        urllib.request.urlopen = real


def load_fetch_calls():
    sys.path.insert(0, str(HERE.parent))
    import fetch_calls as fc
    fc.TODAY = FIXED_TODAY
    fc.SETTINGS = SETTINGS
    fc.MY_LIST = HERE / "fixtures" / "my_calls_test.csv"   # fixed list for the whole-run tests
    fc.EU_CACHE = None                                     # tests never read or write my real cache
    return fc


def record(add_only=False):
    fc = load_fetch_calls()
    WEB.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text()) if add_only and INDEX.exists() else {}
    real = urllib.request.urlopen

    def recording(req, timeout=None):
        url = url_of(req)
        if add_only and url in index:                      # already saved: use the saved copy
            return FakeResponse(gzip.decompress((WEB / index[url]).read_bytes()))
        with real(req, timeout=timeout) as r:
            body = r.read()
        name = hashlib.sha1(url.encode()).hexdigest()[:16] + ".gz"
        (WEB / name).write_bytes(gzip.compress(body))
        index[url] = name
        return FakeResponse(body)
    urllib.request.urlopen = recording
    try:
        keywords, _ = fc.load_settings()
        report = {"lines": [], "problems": [], "no_date": []}
        for f in (fc.fetch_eu, fc.fetch_hrzz, fc.fetch_eufondovi, fc.fetch_ampeu, fc.fetch_unizg, fc.fetch_mzom,
                  fc.fetch_uniri, fc.fetch_devpost, fc.fetch_eu_browse, fc.check_watch):
            f(keywords, report)
        eu_calls = fc.one_per_call(fc.fetch_eu_browse(keywords, report) + fc.fetch_eu(keywords, report))
        fc.enrich_eu(eu_calls, keywords, report)   # records the EU topic detail pages
    finally:
        urllib.request.urlopen = real
    INDEX.write_text(json.dumps(index, indent=1, ensure_ascii=False))
    print("\n".join(report["lines"]), "\nproblems:", report["problems"])
    print(f"Saved {len(index)} pages, {sum(p.stat().st_size for p in WEB.glob('*.gz')) // 1024} KB")


if __name__ == "__main__" and sys.argv[1:2] == ["record"]:
    record(add_only="--add" in sys.argv)
