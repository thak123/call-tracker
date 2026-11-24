"""Collect real funding calls from all my sources and save them as live_calls.csv.

Run:  python3 fetch_calls.py      (or click "Refresh calls" when the page runs via serve.py)
Writes live_calls.csv and live_calls.js; index.html shows the newest results by itself.

Sources (public data only, no personal data is sent):
  - EU Funding & Tenders Portal: searched with each of my keywords
  - HRZZ (Croatian Science Foundation): project calls and call news from hrzz.hr
  - eufondovi.gov.hr: research/innovation calls from EU funds in Croatia (incl. HAMAG-BICRO)
  - AMPEU: Erasmus+, CEEPUS, bilateral mobility and scholarship calls (ampeu.hr/natjecaji)
  - UNIZG: University of Zagreb "Otvoreni natječaji" research funding page
  - EU portal browse: ALL open/upcoming EU calls, each with a fit score for my topics (see fit_score)
  - Devpost: open AI/ML hackathons (for students)
  - my_calls.csv: calls I keep by hand (SemEval, WMT, ...: no data feed). Edit it in Excel, then Refresh.
  - MZOM: Ministry of Science calls (science & technology, international cooperation; no job ads)
  - UNIRI: University of Rijeka news about calls, scholarships and competitions (no job ads)
Left out on purpose: fondovieu.gov.hr (its terms forbid automated use), Zaklada Adris (not reachable).
My keywords and "not my topics" live in keywords.js (edit them on the page).
"""
import csv
import datetime
import html
import io
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
MY_LIST = HERE / "my_calls.csv"   # calls I add by hand (events without a data feed)
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
    return eu_post(f'"{text}"', page, size, {"bool": {"must": [{"terms": {"type": list(EU_TYPES)}}]}})


def eu_post(text, page, size, query, sort=None):
    query = json.dumps(query)
    b = uuid.uuid4().hex
    part = lambda name, value: (
        f'--{b}\r\nContent-Disposition: form-data; name="{name}"; filename="blob"\r\n'
        f"Content-Type: application/json\r\n\r\n{value}\r\n")
    body = (part("query", query) + part("languages", '["en"]')
            + (part("sort", json.dumps(sort)) if sort else "") + f"--{b}--\r\n").encode()
    params = urllib.parse.urlencode({"apiKey": "SEDIA", "text": text, "pageSize": size, "pageNumber": page})
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
    prog = {"HORIZON": "Horizon Europe", "ERC": "ERC", "DIGITAL": "Digital Europe", "EU4H": "EU4Health",
            "LIFE": "LIFE", "CREA": "Creative Europe", "ERASMUS": "Erasmus+", "CERV": "CERV", "MSCA": "MSCA"}.get(ident.split("-")[0], ident.split("-")[0])
    return {"id": "eu:" + ident, "title": title, "funder": "European Commission · " + prog, "eu": True, "source": "EU portal", "scope": "core",
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


# ---------------------------------------------------------------- fit score
# How well a call fits my research. Words in the title that point to my field count a little, my own keywords a lot,
# and EU programmes close to language/AI/humanities/digital get one point for being in the right area.
RELATED = [re.compile(p, re.I) for p in (
    r"\blanguage", r"linguist", r"\bspeech", r"\btext\b", r"\bdigital", r"\bdata\b", r"\bAI\b",
    r"artificial intelligence", r"machine learning", r"\blearning\b", r"educat", r"humanit", r"cultur",
    r"creativ", r"\bmedia\b", r"democra", r"disinformation", r"inclusi", r"multilingual", r"translat",
    r"heritage", r"open science", r"research infrastructure", r"\bskills\b", r"citizen")]
RELEVANT_PREFIXES = ("HORIZON-CL2", "HORIZON-CL4", "ERC", "HORIZON-MSCA", "DIGITAL", "HORIZON-WIDERA",
                     "HORIZON-EIC", "HORIZON-INFRA", "CREA", "ERASMUS")


def fit_score(c):
    score = 3 * len(c["keywords"])                                   # my keywords found in the call
    if any(r.search(c["title"]) for r in RELATED):
        score += 2                                                   # title words close to my field
    if c["id"].split(":", 1)[-1].upper().startswith(RELEVANT_PREFIXES):
        score += 1                                                   # EU programme close to my field
    return score


# ---------------------------------------------------------------- EU portal: browse everything
BROWSE_QUERY = {"bool": {"must": [{"terms": {"type": ["1", "8"]}}, {"terms": {"status": ["31094501", "31094502"]}}]}}


def fetch_eu_browse(keywords, report):
    """All open/upcoming EU grant calls (newest deadline first, stop when deadlines are in the past)."""
    calls, read = [], 0
    try:
        for page in range(1, 21):
            results = eu_post("***", page, 100, BROWSE_QUERY, {"field": "deadlineDate", "order": "DESC"})["results"]
            if not results:
                break
            read += len(results)
            for r in results:
                row = eu_row(r.get("metadata", {}))
                if row and row["deadline"] >= TODAY:
                    row.update(scope="browse", keywords=tags_for(row["title"], keywords))
                    calls.append(row)
            latest = [d[:10] for r in results for d in r.get("metadata", {}).get("deadlineDate") or []]
            if latest and max(latest) < TODAY.isoformat():
                break
    except Exception as e:
        if not read:
            report["problems"].append(f"EU browse: search failed ({e})")
            return []
    relevant = sum(fit_score(c) >= 1 for c in calls)
    report["lines"].append(f"  EU browse: {len(calls)} open/upcoming calls read, {relevant} fit my field (score 1 or more)")
    return calls


# ---------------------------------------------------------------- Devpost hackathons
DEVPOST = "https://devpost.com/api/hackathons?status[]=open&order_by=deadline&per_page=100&page={}"
MON = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def devpost_deadline(text):
    """'Nov 17 - 24, 2026' / 'Oct 17 - Nov 24, 2026' / 'Dec 28, 2026 - Jan 15, 2027' -> last day."""
    text = (text or "").strip()
    m = re.match(r"(?:([A-Z][a-z]{2}) )?(\d{1,2}), (\d{4})$", text.split(" - ")[-1].strip())
    if not m:
        return None
    month = m[1] or (re.match(r"([A-Z][a-z]{2})", text) or [None, None])[1]
    try:
        return datetime.date(int(m[3]), MON[month], int(m[2]))
    except (KeyError, ValueError):
        return None


def fetch_devpost(keywords, report):
    hackathons, total = [], None
    for page in range(1, 6):
        try:
            data = json.loads(get_text(DEVPOST.format(page)), strict=False)
        except Exception as e:
            if page == 1:
                report["problems"].append(f"Devpost: could not read devpost.com ({e})")
                return []
            break
        batch = data.get("hackathons", [])
        total = (data.get("meta") or {}).get("total_count", total)
        hackathons += batch
        if not batch or (total is not None and len(hackathons) >= total):
            break
    calls = []
    for h in hackathons:
        title = plain(h.get("title", ""))
        themes = [t.get("name", "") for t in h.get("themes", [])]
        if h.get("invite_only") or not (any("Machine Learning" in t or t == "Data" for t in themes)
                                        or any(r.search(title) for r in RELATED)):
            continue
        deadline = devpost_deadline(h.get("submission_period_dates"))
        if not deadline or too_old(deadline):
            continue
        prize = re.sub(r"^(\S{1,4})\s+(\d)", r"\1\2", plain(h.get("prize_amount") or ""))
        calls.append({"id": f"devpost:{h['id']}", "title": title, "funder": h.get("organization_name") or "Devpost host",
                      "eu": False, "source": "Devpost", "scope": "core", "type": "datathon", "deadline": deadline,
                      "link": h["url"].split("?")[0], "amount": prize if prize and prize != "$0" else "no prize listed",
                      "who": "students", "keywords": tags_for(title, keywords)})
    report["lines"].append(f"  Devpost: {len(calls)} open AI/data hackathons (of {len(hackathons)} open)")
    return calls


# ---------------------------------------------------------------- my own list (my_calls.csv)
def parse_any_date(text):
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text) or re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\.?$", text)
    if not m:
        return None
    y, mo, d = (int(m[1]), int(m[2]), int(m[3])) if len(m[1]) == 4 else (int(m[3]), int(m[2]), int(m[1]))
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def fetch_my_list(keywords, report):
    """Events with no data feed (SemEval, WMT, CLEF ...): I write them into my_calls.csv, with a date from the event's page."""
    if not MY_LIST.exists():
        return []
    text = MY_LIST.read_text(encoding="utf-8-sig")
    head = text.split("\n", 1)[0]
    rows = csv.DictReader(io.StringIO(text), delimiter=";" if head.count(";") > head.count(",") else ",")
    calls = []
    for i, r in enumerate(rows):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        line, title = i + 2, r.get("title", "")
        deadline = parse_any_date(r.get("deadline", ""))
        if not title or not deadline:
            why = "no title" if not title else f"date '{r.get('deadline', '')}' not understood: use 2027-01-31 or 31.1.2027"
            report["no_date"].append((f"my_calls.csv row {line}: {title or '(no title)'} ({why})", "my_calls.csv"))
            continue
        if too_old(deadline):
            continue
        mine = [k.strip() for k in re.split(r"[;|,]", r.get("keywords", "")) if k.strip()]
        calls.append({"id": f"my:{re.sub('[^a-z0-9]+', '-', title.lower()).strip('-')[:60]}:{deadline.isoformat()}",
                      "title": title, "funder": r.get("funder") or "my list", "eu": False, "source": "My list",
                      "scope": "core", "type": r.get("type") if r.get("type") in ("grant", "third-party call", "competition", "datathon") else "competition",
                      "deadline": deadline, "link": r.get("link") or MY_LIST.name, "amount": r.get("amount") or "see call page",
                      "who": r.get("who") or "staff;PhD",
                      "keywords": mine + [k for k in tags_for(title, keywords) if k not in mine]})
    report["lines"].append(f"  My list: {len(calls)} entries from {MY_LIST.name}")
    return calls


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
        tags = tags_for(title + " " + text, keywords)
        funder, eu = detect_funder(title, text, "HRZZ (Croatian Science Foundation)")
        calls.append({"id": f"hrzz:{p['id']}", "title": title, "funder": funder, "eu": eu, "source": "HRZZ",
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


def tags_for(text, keywords):
    """Only MY keywords (topics) that appear in the call text. Sources and funders are separate fields."""
    low = text.lower()
    return [k for k in keywords if k.lower() in low]


# Who pays: read from the call text. First match in the title wins, otherwise the earliest match in the text.
# (name, pattern, EU-funded?)
FUNDERS = [
    ("European Research Council (ERC)", r"\bERC\b|European Research Council|Europsk\w+ istraživačk\w+ vijeć", True),
    ("European Commission · MSCA", r"\bMSCA\b|Marie Sk\w+[- ]Curie", True),
    ("European Commission · Horizon Europe", r"Horizon Europe|Obzor\w* Europ\w*|\bHORIZON\b|Europsk\w+ inovacijsk\w+ vijeć|\bEIC\b", True),
    ("European Commission · Erasmus+", r"Erasmus\s*\+|\bErasmus\b", True),
    ("European Commission · Creative Europe", r"Creative Europe|Kreativn\w+ Europ", True),
    ("European Commission · Digital Europe", r"Digital Europe|Digitaln\w+ Europ|\bEDIH", True),
    ("Interreg (EU)", r"Interreg", True),
    ("EU funds · NPOO", r"\bNPOO\b|Nacionaln\w+ plan\w* oporavka", True),
    ("EU funds · ESF+", r"ESF\s*\+|Europsk\w+ socijaln\w+ fond", True),
    ("EU funds · EFRR", r"\bEFRR\b|\bERDF\b|Europsk\w+ fond\w* za regionalni razvoj", True),
    ("EU · STEP", r"\bSTEP\b", True),
    ("EU · COST", r"\bCOST\b", True),
    ("HRZZ (Croatian Science Foundation)", r"\bHRZZ\w*|Hrvatsk\w+ zaklad\w+ za znanost", False),
    ("HAMAG-BICRO", r"HAMAG", False),
    ("European Space Agency (ESA)", r"\bESA\b|Europsk\w+ svemirsk\w+ agencij", False),
    ("HAZU", r"\bHAZU\b|Hrvatsk\w+ akademij\w+ znanosti", False),
    ("Fulbright", r"Fulbright", False),
    ("DAAD", r"\bDAAD\b", False),
    ("YUFE alliance", r"\bYUFE", False),
    ("Foreign government scholarship", r"stipendij\w*\s+(?:\w+\s+){0,4}(?:Vlad\w+|Konfederacij\w+|Držav\w+|Republik\w+|Kraljevin\w+)", False),
    ("MZOM (Ministry of Science)", r"Ministarstv\w+ znanosti", False),
    ("AMPEU", r"\bAMPEU\b|Agencij\w+ za mobilnost", False),
    ("City of Rijeka / PGŽ", r"Grad\w* Rijek\w*|\bPGŽ|Primorsko-goransk", False),
]


def detect_funder(title, text, default, default_eu=False):
    """Return (funder, eu_funded) from the call's own words; fall back to the site it was found on."""
    for where in (title, text[:2000]):
        hits = [(m.start(), name, eu) for name, pat, eu in FUNDERS for m in [re.search(pat, where)] if m]
        if hits:
            _, name, eu = min(hits)
            return name, eu
    return default, default_eu


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
        funder, eu = detect_funder(title, text, "EU funds (Croatia)", True)
        calls.append({"id": f"euf:{p['id']}", "title": title, "funder": funder, "eu": eu, "source": "eufondovi",
                      "type": "grant", "deadline": deadline, "link": p["link"], "amount": "see call page",
                      "who": "staff", "keywords": tags_for(title + " " + text, keywords)})
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
        funder, eu = detect_funder(title, category, "AMPEU")
        calls.append({"id": "ampeu:" + href.rstrip("/").split("/")[-1], "title": title,
                      "funder": funder, "eu": eu, "source": "AMPEU",
                      "type": "grant", "deadline": deadline, "link": link, "amount": "see call page",
                      "who": "students;PhD" if scholarship else "staff;PhD",
                      "keywords": tags_for(title, keywords)})
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
        funder, eu = detect_funder(title, text, "University of Zagreb")
        calls.append({"id": "unizg:" + cid, "title": title, "funder": funder, "eu": eu, "source": "UNIZG",
                      "type": "grant", "deadline": deadline, "link": UNIZG_OPEN + "#" + cid,
                      "amount": "see call page", "who": "staff;PhD",
                      "keywords": tags_for(title + " " + text, keywords)})
    report["lines"].append(f"  UNIZG: {len(calls)} calls with a deadline"
                           + ("   (the open-calls page currently lists no recent call)" if not calls else ""))
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- MZOM
MZOM_LIST = "https://mzom.gov.hr/natjecaji-196/196?trazi=1&tip=&tip2=&tema=&datumod=&datumdo=&pojam=&page={}"
MZOM_PAGES = 8   # about 10 items per page, newest first: roughly the last 2-3 months
MZOM_KEEP = ("znanost i tehnologija", "međunarodna suradnja", "stranica", "visoko obrazovanje")
MZOM_SKIP = ("radno mjesto", "radnog mjesta", "učitelj", "lektor", "nabava", "konzultant", "rang-list",
             "obavijest", "pitanja i odgovori", "odluka", "razgovor", "ravnatelj")


def fetch_mzom(keywords, report):
    calls, no_date, seen = [], [], set()
    for n in range(1, MZOM_PAGES + 1):
        try:
            page = get_text(MZOM_LIST.format(n))
        except Exception as e:
            if n == 1:
                report["problems"].append(f"MZOM: could not read mzom.gov.hr ({e})")
                return []
            break
        items = re.findall(r"<div class='news_item'>(.*?)<span class='date'>([^<]*)</span>", page, re.S)
        if not items:
            break
        for body, meta in items:
            a = re.search(r"<a href='([^']+)'>\s*<span class='h3'>(.*?)</span>", body, re.S)
            if not a:
                continue
            href, title = a[1], plain(a[2])
            parts = [x.strip() for x in meta.split("|")]
            category = parts[-1].lower() if parts else ""
            info = plain(body[a.end():])
            if (href in seen or category not in MZOM_KEEP or "državnu službu" in (title + info).lower()
                    or any(w in title.lower() for w in MZOM_SKIP)):
                continue
            seen.add(href)
            m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", parts[0] if parts else "")
            published = datetime.date(int(m[3]), int(m[2]), int(m[1])) if m else TODAY
            link = urllib.parse.urljoin("https://mzom.gov.hr/", href)
            deadline = hrzz_deadline(info, published)
            if not deadline:
                no_date.append((title, link))
                continue
            if too_old(deadline):
                continue
            low = title.lower()
            calls.append({"id": "mzom:" + href.rstrip("/").split("/")[-1], "title": title,
                          "funder": detect_funder(title, info, "MZOM (Ministry of Science)")[0],
                          "eu": detect_funder(title, info, "MZOM (Ministry of Science)")[1], "source": "MZOM",
                          "type": "grant", "deadline": deadline, "link": link, "amount": "see call page",
                          "who": "students;PhD" if ("stipendij" in low or "studij" in low) else "staff;PhD",
                          "keywords": tags_for(title + " " + info, keywords)})
    report["lines"].append(f"  MZOM: {len(calls)} science/international calls with a deadline")
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- UNIRI
UNIRI_API = "https://uniri.hr/wp-json/wp/v2/vijesti"   # news; /natjecaj on uniri.hr holds job ads only
UNIRI_SEARCHES = ("poziv", "natječaj", "natjecanje", "stipendij", "thon")
UNIRI_CALL_WORDS = ("poziv", "natječaj", "natjecanj", "prijave", "stipendij", "thon")
UNIRI_SKIP = ("održan", "radionic", "posjet", "simpozij", "sastanak", "dan otvorenih", "peticij", "svečan",
              "ravnatelj", "sportaš", "studentskog zbora", "studentskim udrugama", "predavanj", "dobitnic",
              "zaključen", "završen", "uspjeh", "rang-list", "ćakula", "info-dan", "infodan", "najav")


def fetch_uniri(keywords, report):
    posts, failed = {}, None
    for term in UNIRI_SEARCHES:
        try:
            req = urllib.request.Request(UNIRI_API + "?" + urllib.parse.urlencode({
                "search": term, "per_page": 50, "_fields": "id,date,title,link,content",
                "after": (TODAY - datetime.timedelta(days=KEEP_CLOSED_DAYS + 60)).isoformat() + "T00:00:00"}), headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                for p in json.load(r):
                    posts[p["id"]] = p
        except Exception as e:
            failed = e
    if not posts and failed:
        report["problems"].append(f"UNIRI: could not read uniri.hr ({failed})")
        return []
    calls, no_date = [], []
    for p in posts.values():
        title = plain(p["title"]["rendered"])
        low = title.lower()
        if not any(w in low for w in UNIRI_CALL_WORDS) or any(w in low for w in UNIRI_SKIP + SKIP_TITLE):
            continue
        text = plain(p["content"]["rendered"])
        published = datetime.date.fromisoformat(p["date"][:10])
        deadline = hrzz_deadline(text, published)
        if not deadline:
            no_date.append((title, p["link"]))
            continue
        if too_old(deadline):
            continue
        both = (title + " " + text).lower()
        kind = "datathon" if ("thon" in low or "hackathon" in low or "datathon" in low) else "competition" if "natjecanj" in low else "grant"
        funder, eu = detect_funder(title, text, "University of Rijeka")
        calls.append({"id": f"uniri:{p['id']}", "title": title, "funder": funder, "eu": eu, "source": "UNIRI",
                      "type": kind, "deadline": deadline, "link": p["link"], "amount": "see call page",
                      "who": "students" if ("student" in both and "stipendij" in low) or kind != "grant" and "student" in both
                             else "staff;PhD",
                      "keywords": tags_for(title + " " + text, keywords)})
    report["lines"].append(f"  UNIRI: {len(calls)} calls/competitions with a deadline")
    report["no_date"] += no_date
    return calls


# ---------------------------------------------------------------- one card per call
def one_per_call(calls):
    """A call found twice (keyword search AND browsing) counts once. A call with several cut-off dates
    (the EU lists each as its own record) shows its NEXT cut-off: the one I can still act on."""
    def better(new, old):
        if new["scope"] != old["scope"]:
            return new["scope"] == "core"
        new_open, old_open = new["deadline"] >= TODAY, old["deadline"] >= TODAY
        if new_open and old_open:
            return new["deadline"] < old["deadline"]
        return new_open and not old_open
    best = {}
    for c in calls:
        c.setdefault("scope", "core")
        if c["id"] not in best or better(c, best[c["id"]]):
            best[c["id"]] = c
    return list(best.values())


# ---------------------------------------------------------------- duplicates across sources
GENERIC_CAPS = {"HRZZ", "EU", "MZOM", "AMPEU", "UNIRI", "UNIZG", "NPOO", "ESF", "EFRR", "COST"}


def norm(title):
    return re.sub(r"[^a-z0-9čćžšđ ]", "", title.lower())[:45]


def acronyms(title):
    return {w.strip("-") for w in re.findall(r"\b[A-ZČĆŽŠĐ][A-ZČĆŽŠĐ0-9-]{2,}", title)} - GENERIC_CAPS - {""}


def merge_duplicates(calls):
    """Same deadline + (same title start or same call acronym such as RAMP, DOK-2026) = one call."""
    out, merged = [], 0
    for c in calls:
        twin = next((o for o in out if o["deadline"] == c["deadline"] and
                     not (o["source"] == "EU portal" and c["source"] == "EU portal") and
                     (norm(o["title"]) == norm(c["title"]) or acronyms(o["title"]) & acronyms(c["title"]))), None)
        if twin:
            twin["keywords"] += [k for k in c["keywords"] if k not in twin["keywords"]]
            if c["source"] not in twin["source"]:
                twin["source"] += ", " + c["source"]
            merged += 1
        else:
            out.append(c)
    return out, merged


# ---------------------------------------------------------------- main
def main():
    keywords, exclude = load_settings()
    print(f"Keywords: {len(keywords)} · not my topics: {len(exclude)}  (from {SETTINGS.name})")
    report = {"lines": [], "problems": [], "no_date": []}
    all_calls = (fetch_eu(keywords, report) + fetch_hrzz(keywords, report) + fetch_eufondovi(keywords, report)
                 + fetch_ampeu(keywords, report) + fetch_unizg(keywords, report)
                 + fetch_mzom(keywords, report) + fetch_uniri(keywords, report)
                 + fetch_devpost(keywords, report) + fetch_eu_browse(keywords, report)
                 + fetch_my_list(keywords, report))

    all_calls = one_per_call(all_calls)
    all_calls, merged = merge_duplicates(all_calls)
    for c in all_calls:
        c["fit"] = fit_score(c)
    kept, left_out = [], []
    for c in all_calls:
        hit = excluded_by(c["title"], exclude)
        (left_out.append((hit, c)) if hit else kept.append(c))
    kept.sort(key=lambda c: c["deadline"])

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "funder", "eu", "source", "fit", "scope", "type", "deadline",
                                          "link", "amount", "who", "keywords"])
        w.writeheader()
        for c in kept:
            w.writerow({**c, "deadline": c["deadline"].isoformat(), "keywords": ";".join(c["keywords"]),
                        "eu": "yes" if c.get("eu") else ""})

    generated = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    OUT_JS.write_text("// Written by fetch_calls.py. Do not edit: run the script again instead.\n"
                      "window.LIVE_CALLS = " + json.dumps({"generated": generated,
                                                          "csv": OUT.read_text(encoding="utf-8")},
                                                         ensure_ascii=False) + ";\n", encoding="utf-8")

    print("\n".join(report["lines"]))
    if merged:
        print(f"  Merged {merged} duplicates (same call listed by two sources)")
    still_open = sum(c["deadline"] >= TODAY for c in kept)
    print(f"\nSaved {len(kept)} calls to {OUT.name} and {OUT_JS.name}: {still_open} open, {len(kept) - still_open} closed.")
    if left_out:
        shown = [(h, c) for h, c in left_out if c["scope"] == "core"]
        print(f"Left out {len(left_out)} calls on 'not my topics' ({len(left_out) - len(shown)} of them from EU browse):")
        for hit, c in shown:
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
