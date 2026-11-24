"""Collect real funding calls from all my sources and save them as live_calls.csv.

Run:  python3 fetch_calls.py      (or click "Refresh calls" when the page runs via serve.py)
Writes live_calls.csv and live_calls.js; index.html shows the newest results by itself.

Sources (public data only, no personal data is sent):
  - EU Funding & Tenders Portal: searched with each of my keywords
  - HRZZ (Croatian Science Foundation): project calls and call news from hrzz.hr
  - eufondovi.gov.hr: research/innovation calls from EU funds in Croatia (incl. HAMAG-BICRO)
  - AMPEU: Erasmus+, CEEPUS, bilateral mobility and scholarship calls (ampeu.hr/natjecaji)
  - UNIZG: University of Zagreb "Otvoreni natječaji" research funding page
My keywords and "not my topics" live in keywords.js (edit them on the page).
"""
import csv
import datetime
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "live_calls.csv"
OUT_JS = HERE / "live_calls.js"   # same data, so the page can open it by itself
SETTINGS = HERE / "keywords.js"
TODAY = datetime.date.today()
KEEP_CLOSED_DAYS = 365   # closed calls from the last year go to "Check in the future"
UA = {"User-Agent": "call-tracker/1.0 (personal research tool)"}


def load_settings():
    """Read keywords and exclude words from keywords.js (a JSON object inside)."""
    text = SETTINGS.read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    clean = lambda xs: [x.strip() for x in xs if x.strip()]
    return clean(data.get("keywords", [])), clean(data.get("exclude", []))


def excluded_by(title, exclude):
    t = title.lower()
    return next((w for w in exclude if w.lower() in t), None)


def too_old(deadline):
    return deadline < TODAY - datetime.timedelta(days=KEEP_CLOSED_DAYS)


# ---------------------------------------------------------------- EU portal
EU_API = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
EU_PORTAL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
EU_TYPES = {"1": "grant", "2": "third-party call", "8": "grant"}   # 2 = tender, 8 = cascade funding


def eu_search(text, page, size=100):
    """One page of results from the EU search (exact phrase, calls/tenders only)."""
    query = json.dumps({"bool": {"must": [{"terms": {"type": list(EU_TYPES)}}]}})
    b = uuid.uuid4().hex
    part = lambda name, value: (
        f'--{b}\r\nContent-Disposition: form-data; name="{name}"; filename="blob"\r\n'
        f"Content-Type: application/json\r\n\r\n{value}\r\n")
    body = (part("query", query) + part("languages", '["en"]') + f"--{b}--\r\n").encode()
    params = urllib.parse.urlencode({"apiKey": "SEDIA", "text": f'"{text}"',
                                     "pageSize": size, "pageNumber": page})
    req = urllib.request.Request(f"{EU_API}?{params}", data=body,
                                 headers={**UA, "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def eu_first(meta, key, default=""):
    v = meta.get(key)
    return (v[0] if isinstance(v, list) and v else v) or default


def eu_row(meta):
    ident, title = eu_first(meta, "identifier"), eu_first(meta, "title")
    dates = sorted(datetime.date.fromisoformat(d[:10]) for d in meta.get("deadlineDate") or [])
    if not ident or not title or not dates:
        return None   # FAQ pages, news etc. have no call number or deadline
    upcoming = [d for d in dates if d >= TODAY]
    deadline = upcoming[0] if upcoming else dates[-1]   # next deadline, else the last one
    if too_old(deadline):
        return None
    return {"id": "eu:" + ident, "title": title, "funder": "European Commission · " + ident.split("-")[0],
            "type": EU_TYPES.get(eu_first(meta, "type"), "grant"), "deadline": deadline,
            "link": EU_PORTAL + ident, "amount": "see call page", "who": "staff;PhD", "keywords": []}


def fetch_eu(keywords, report):
    calls = {}
    for kw in keywords:
        try:
            first_page = eu_search(kw, 1)
            results, total, page = first_page["results"], first_page["totalResults"], 2
            while len(results) < min(total, 1000):
                more = eu_search(kw, page)["results"]
                if not more:
                    break
                results += more
                page += 1
        except Exception as e:   # network down, API changed, ...
            report["problems"].append(f'EU "{kw}": search failed ({e})')
            continue
        found = 0
        for r in results:
            row = eu_row(r.get("metadata", {}))
            if not row:
                continue
            row = calls.setdefault(row["id"], row)   # same call found twice -> one row
            if kw not in row["keywords"]:
                row["keywords"].append(kw)
                found += 1
        report["lines"].append(f'  EU "{kw}": {found} calls' + ("   (none right now)" if not found else ""))
    return list(calls.values())


# ---------------------------------------------------------------- HRZZ
HRZZ_API = "https://hrzz.hr/wp-json/wp/v2/posts"
HRZZ_CATEGORIES = {39: "Natječaji za projekte", 49: "Novosti"}   # 38 = job ads, left out
CALL_WORDS = ("natječaj", "natjecaj", "poziv", "call", "prijav")
SKIP_TITLE = ("rezultat", "zatvoren", "(m/ž)", "priopćenje", "odluka")
MONTHS = {"siječnja": 1, "veljače": 2, "ožujka": 3, "travnja": 4, "svibnja": 5, "lipnja": 6,
          "srpnja": 7, "kolovoza": 8, "rujna": 9, "listopada": 10, "studenoga": 11, "studenog": 11,
          "prosinca": 12}
DATE_WORDS = re.compile(r"(\d{1,2})\.\s*(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?", re.I)
DATE_NUM = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")
DEADLINE_HINT = re.compile(r"\brok\w*|\bdo\s+(?=\d)|najkasnije|zaključ\w*", re.I)


def hrzz_get(params):
    req = urllib.request.Request(HRZZ_API + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def hrzz_deadline(text, published):
    """Find the deadline in Croatian text: dates written shortly after 'rok', 'do', 'najkasnije'."""
    dates = []
    for hint in DEADLINE_HINT.finditer(text):
        window = text[hint.start(): hint.end() + 90]
        for m in DATE_WORDS.finditer(window):
            day, month = int(m.group(1)), MONTHS[m.group(2).lower()]
            year = int(m.group(3)) if m.group(3) else published.year + (month < published.month)
            dates.append((year, month, day))
        for m in DATE_NUM.finditer(window):
            dates.append((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    found = set()
    for y, mo, d in dates:
        try:
            dt = datetime.date(y, mo, d)
        except ValueError:
            continue
        if dt >= published - datetime.timedelta(days=30):   # ignore old dates mentioned in passing
            found.add(dt)
    if not found:
        return None
    upcoming = sorted(d for d in found if d >= TODAY)
    return upcoming[0] if upcoming else max(found)


def fetch_hrzz(keywords, report):
    try:
        posts = []
        for page in (1, 2):
            posts += hrzz_get({"categories": ",".join(map(str, HRZZ_CATEGORIES)), "per_page": 100,
                               "page": page, "_fields": "id,date,title,link,categories,content",
                               "after": (TODAY - datetime.timedelta(days=KEEP_CLOSED_DAYS + 60)).isoformat() + "T00:00:00"})
            if len(posts) < 100 * page:
                break
    except Exception as e:
        # WordPress answers "page out of range" with an error; only a failure on page 1 is a problem
        if not posts:
            report["problems"].append(f"HRZZ: could not read hrzz.hr ({e})")
            return []
    calls, no_date = [], []
    for p in posts:
        title = plain(p["title"]["rendered"])
        low = title.lower()
        if any(s in low for s in SKIP_TITLE):
            continue
        if 39 not in p["categories"] and not any(w in low for w in CALL_WORDS):
            continue   # general news that is not about a call
        published = datetime.date.fromisoformat(p["date"][:10])
        text = plain(p["content"]["rendered"])
        deadline = hrzz_deadline(text, published)
        if not deadline:
            no_date.append((title, p["link"]))
            continue
        if too_old(deadline):
            continue
        tags = ["HRZZ"] + [k for k in keywords if k.lower() in (title + " " + text).lower()]
        calls.append({"id": f"hrzz:{p['id']}", "title": title, "funder": "HRZZ (Croatian Science Foundation)",
                      "type": "grant", "deadline": deadline, "link": p["link"],
                      "amount": "see call page", "who": "staff;PhD", "keywords": tags})
    report["lines"].append(f"  HRZZ: {len(calls)} calls with a deadline")
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- shared helpers for Croatian sites
def get_text(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def tags_for(text, keywords, source):
    low = text.lower()
    return [source] + [k for k in keywords if k.lower() in low]


# ---------------------------------------------------------------- eufondovi.gov.hr
EUF_API = "https://eufondovi.gov.hr/wp-json/wp/v2/posts"
# Only calls that concern research, innovation or higher education (the portal also has calls for schools, health ...)
RESEARCH_WORDS = ("istraživ", "znanstven", "znanost", "inovacij", "visoko obrazovanj", "visokih učilišta",
                  "sveučiliš", "obzor europa", "horizon", "doktor", "edih", "umjetn")
EUF_SKIP = ("odobren", "izmjen", "škol", "vrtić", "predškol", "strukovn",   # results, amendments, schools
            "obavijest", "savjetovanj", "radionic", "vijeća mladih", "uvrštavanje na listu")   # notices, consultations


def fetch_eufondovi(keywords, report):
    try:
        posts = []
        for page in (1, 2, 3):
            req = urllib.request.Request(EUF_API + "?" + urllib.parse.urlencode({
                "search": "poziv", "per_page": 100, "page": page,
                "_fields": "id,date,title,link,content",
                "after": (TODAY - datetime.timedelta(days=KEEP_CLOSED_DAYS + 60)).isoformat() + "T00:00:00"}), headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                batch = json.load(r)
            posts += batch
            if len(batch) < 100:
                break
    except Exception as e:
        if not posts:
            report["problems"].append(f"eufondovi: could not read eufondovi.gov.hr ({e})")
            return []
    calls, no_date, skipped = [], [], 0
    for p in posts:
        title = plain(p["title"]["rendered"])
        low = title.lower()
        if not any(w in low for w in ("poziv", "natječaj")) or any(s in low for s in SKIP_TITLE + EUF_SKIP):
            continue
        text = plain(p["content"]["rendered"])
        if not any(w in (title + " " + text[:1500]).lower() for w in RESEARCH_WORDS):
            skipped += 1
            continue
        published = datetime.date.fromisoformat(p["date"][:10])
        deadline = hrzz_deadline(text, published)
        if not deadline:
            no_date.append((title, p["link"]))
            continue
        if too_old(deadline):
            continue
        calls.append({"id": f"euf:{p['id']}", "title": title, "funder": "EU fondovi Hrvatska (eufondovi.gov.hr)",
                      "type": "grant", "deadline": deadline, "link": p["link"], "amount": "see call page",
                      "who": "staff", "keywords": tags_for(title + " " + text, keywords, "eufondovi")})
    report["lines"].append(f"  eufondovi: {len(calls)} research/innovation calls with a deadline "
                           f"({skipped} other calls skipped: schools, health, ...)")
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- AMPEU
AMPEU = "https://www.ampeu.hr"
AMPEU_SKIP = ("zapošljavanj", "stručnjak", "konferencij", "trening", "radionic")


def fetch_ampeu(keywords, report):
    try:
        page = get_text(AMPEU + "/natjecaji")
    except Exception as e:
        report["problems"].append(f"AMPEU: could not read ampeu.hr ({e})")
        return []
    items = re.findall(r'<div class="newsListItem">\s*<a href="([^"]+)".*?</a>', page, re.S)
    blocks = re.findall(r'<div class="newsListItem">(.*?)</a>', page, re.S)
    field = lambda b, cls: plain((re.search(rf'class="{cls}">(.*?)</div>', b, re.S) or [None, ""])[1])
    calls, no_date = [], []
    for href, b in zip(items, blocks):
        title, category = field(b, "newsListItemTitle"), field(b, "newsListItemCategory")
        published_s, info = field(b, "newsListItemDate"), field(b, "newsListItemInfo")
        if not title or any(s in title.lower() for s in AMPEU_SKIP):
            continue
        link = urllib.parse.urljoin(AMPEU, href)
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", published_s)
        published = datetime.date(int(m[3]), int(m[2]), int(m[1])) if m else TODAY
        deadline = None
        m = re.search(r"Rok:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", info)
        if m:
            deadline = datetime.date(int(m[3]), int(m[2]), int(m[1]))
        elif "PROŠAO" not in info.upper():   # "VIŠE ROKOVA" (several deadlines): read the call page
            try:
                deadline = hrzz_deadline(plain(get_text(link)), published)
            except Exception:
                deadline = None
        if not deadline:
            if "PROŠAO" not in info.upper() and (TODAY - published).days < KEEP_CLOSED_DAYS:
                no_date.append((title, link))
            continue
        if too_old(deadline):
            continue
        scholarship = "stipendij" in title.lower()
        calls.append({"id": "ampeu:" + href.rstrip("/").split("/")[-1], "title": title,
                      "funder": f"AMPEU · {category}" if category else "AMPEU",
                      "type": "grant", "deadline": deadline, "link": link, "amount": "see call page",
                      "who": "students;PhD" if scholarship else "staff;PhD",
                      "keywords": tags_for(title, keywords, "AMPEU") + (["mobility"] if "mobilnost" in category.lower() else [])})
    report["lines"].append(f"  AMPEU: {len(calls)} calls with a deadline")
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- UNIZG
UNIZG_OPEN = "https://www.unizg.hr/istrazivanje/istrazivanje-i-inovacije/financiranje-istrazivanja/otvoreni-natjecaji/"


def fetch_unizg(keywords, report):
    try:
        page = get_text(UNIZG_OPEN)
    except Exception as e:
        report["problems"].append(f"UNIZG: could not read unizg.hr ({e})")
        return []
    calls, no_date = [], []
    # each call is a content block that starts with an <h1> title
    for cid, block in re.findall(r'<div id="(c\d+)" class="csc-default">(.*?)(?=<div id="c\d+" class="csc-default">|<div class="col-)', page, re.S):
        h1 = re.search(r"<h1>(.*?)</h1>", block, re.S)
        if not h1:
            continue
        title, text = plain(h1[1]), plain(block)
        if title.lower().startswith("popis dokumentacije"):
            continue
        m = re.search(r"(\d{1,2})\.\s*(" + "|".join(MONTHS) + r")\s+(\d{4})", text, re.I)
        published = datetime.date(int(m[3]), MONTHS[m[2].lower()], int(m[1])) if m else TODAY
        deadline = hrzz_deadline(text, published)
        if not deadline:
            no_date.append((title, UNIZG_OPEN))
            continue
        if too_old(deadline):
            continue
        calls.append({"id": "unizg:" + cid, "title": title, "funder": "University of Zagreb",
                      "type": "grant", "deadline": deadline, "link": UNIZG_OPEN + "#" + cid,
                      "amount": "see call page", "who": "staff;PhD",
                      "keywords": tags_for(title + " " + text, keywords, "UNIZG")})
    report["lines"].append(f"  UNIZG: {len(calls)} calls with a deadline"
                           + ("   (the open-calls page currently lists no recent call)" if not calls else ""))
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- main
def main():
    keywords, exclude = load_settings()
    print(f"Keywords: {len(keywords)} · not my topics: {len(exclude)}  (from {SETTINGS.name})")
    report = {"lines": [], "problems": [], "no_date": []}
    all_calls = (fetch_eu(keywords, report) + fetch_hrzz(keywords, report) + fetch_eufondovi(keywords, report)
                 + fetch_ampeu(keywords, report) + fetch_unizg(keywords, report))

    kept, left_out = [], []
    for c in all_calls:
        hit = excluded_by(c["title"], exclude)
        (left_out.append((hit, c)) if hit else kept.append(c))
    kept.sort(key=lambda c: c["deadline"])

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "funder", "type", "deadline",
                                          "link", "amount", "who", "keywords"])
        w.writeheader()
        for c in kept:
            w.writerow({**c, "deadline": c["deadline"].isoformat(), "keywords": ";".join(c["keywords"])})

    generated = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    OUT_JS.write_text("// Written by fetch_calls.py. Do not edit: run the script again instead.\n"
                      "window.LIVE_CALLS = " + json.dumps({"generated": generated,
                                                          "csv": OUT.read_text(encoding="utf-8")},
                                                         ensure_ascii=False) + ";\n", encoding="utf-8")

    print("\n".join(report["lines"]))
    still_open = sum(c["deadline"] >= TODAY for c in kept)
    print(f"\nSaved {len(kept)} calls to {OUT.name} and {OUT_JS.name}: {still_open} open, {len(kept) - still_open} closed.")
    if left_out:
        print(f"Left out {len(left_out)} calls on 'not my topics':")
        for hit, c in left_out:
            print(f"  - [{hit}] {c['title'][:80]}")
    if report["no_date"]:
        print(f"Check by hand ({len(report['no_date'])} posts without a clear deadline):")
        for t, link in report["no_date"]:
            print(f"  - {t[:70]}  {link}")
    for p in report["problems"]:
        print("PROBLEM:", p)
    if report["problems"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
