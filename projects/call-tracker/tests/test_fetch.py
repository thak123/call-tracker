"""Part B: the search script (fetch_calls.py), on saved website copies with a fixed date (24 Nov 2026)."""
import contextlib
import csv
import datetime
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.web_replay import replay, load_fetch_calls

fc = load_fetch_calls()
D = datetime.date


def run_source(fetch, fail_hosts=()):
    keywords, _ = fc.load_settings()
    report = {"lines": [], "problems": [], "no_date": []}
    with replay(fail_hosts):
        calls = fetch(keywords, report)
    return calls, report


def titles(calls):
    return [c["title"] for c in calls]


class B1DeadlineReader(unittest.TestCase):
    """Croatian dates in call texts."""

    def check(self, text, published, expected):
        self.assertEqual(fc.hrzz_deadline(text, published), expected, text)

    def test_month_names(self):
        self.check("s rokom prijave 25. veljače 2027. godine", D(2026, 11, 11), D(2027, 2, 25))

    def test_do_with_date(self):
        self.check("trajat će od 1. rujna do 17. studenoga 2026.", D(2026, 7, 15), D(2026, 11, 17))

    def test_numeric_date(self):
        self.check("s rokom za prijavu 27. 4. 2026. do 13 sati", D(2026, 3, 1), D(2026, 4, 27))

    def test_missing_year_means_next_year(self):
        self.check("Rok: 15. siječnja", D(2026, 11, 5), D(2027, 1, 15))

    def test_impossible_date_ignored(self):
        self.check("rok prijave 31. veljače 2027.", D(2026, 11, 1), None)

    def test_old_dates_ignored(self):
        self.check("rok je bio 1. ožujka 2020.", D(2026, 11, 1), None)

    def test_next_upcoming_deadline_chosen(self):
        self.check("Rok za pretprijavu: 11. siječnja 2027. Rok za drugu fazu: 16. lipnja 2027.",
                   D(2026, 11, 5), D(2027, 1, 11))

    def test_all_passed_gives_latest(self):
        self.check("Rok za pretprijave je 16. studenoga 2026. najkasnije do 23. studenoga 2026.",
                   D(2026, 10, 20), D(2026, 11, 23))

    def test_no_date(self):
        self.check("Prijave su otvorene. Više informacija uskoro.", D(2026, 11, 1), None)


class B1bFunderAndKeywords(unittest.TestCase):
    def test_funder_from_title(self):
        self.assertEqual(fc.detect_funder("Otvoren je poziv ERC Consolidator Grant", "", "University of Rijeka"),
                         ("European Research Council (ERC)", True))
        self.assertEqual(fc.detect_funder("Program „Fulbright Specialist“ u 2027.", "", "AMPEU"), ("Fulbright", False))
        self.assertEqual(fc.detect_funder("Natječaj za stipendije Švicarske Konfederacije", "", "AMPEU"),
                         ("Foreign government scholarship", False))

    def test_funder_from_text_when_title_is_vague(self):
        self.assertEqual(fc.detect_funder("Otvoren novi natječaj", "Hrvatska zaklada za znanost raspisala je DOK-2026", "UNIRI"),
                         ("HRZZ (Croatian Science Foundation)", False))

    def test_fallback_is_the_source(self):
        self.assertEqual(fc.detect_funder("Raspisan natječaj Fonda Sizif", "nagrade studentima", "University of Rijeka"),
                         ("University of Rijeka", False))

    def test_keywords_are_only_topics(self):
        tags = fc.tags_for("HRZZ i MZOM: poziv za umjetna inteligencija i NLP", ["umjetna inteligencija", "speech"])
        self.assertEqual(tags, ["umjetna inteligencija"])


class B2Sources(unittest.TestCase):
    """Each source on its saved pages: right number of calls, and the non-calls are left out."""

    def test_eu_portal(self):
        calls, report = run_source(fc.fetch_eu)
        self.assertEqual(len(calls), 16)
        self.assertTrue(all(c["eu"] and c["source"] == "EU portal" for c in calls))
        self.assertTrue(all(c["link"].startswith(fc.EU_PORTAL) for c in calls))
        self.assertIn("Artificial Intelligence for Cybersecurity applications", titles(calls))
        self.assertEqual(report["problems"], [])

    def test_hrzz(self):
        calls, _ = run_source(fc.fetch_hrzz)
        self.assertEqual(len(calls), 4)
        self.assertFalse(any("(m/ž)" in t for t in titles(calls)), "job ads left out")
        sbep = next(c for c in calls if "SBEP" in c["title"])
        self.assertEqual(sbep["deadline"], D(2026, 11, 23))

    def test_eufondovi(self):
        calls, _ = run_source(fc.fetch_eufondovi)
        self.assertEqual(len(calls), 9)
        for word in ("škol", "odobren", "izmjen", "obavijest"):
            self.assertFalse(any(word in t.lower() for t in titles(calls)), f"'{word}' left out")
        inov = next(c for c in calls if "Inovacije procesa" in c["title"])
        self.assertEqual(inov["deadline"], D(2026, 12, 31))

    def test_ampeu(self):
        calls, _ = run_source(fc.fetch_ampeu)
        self.assertEqual(len(calls), 5)
        by_title = {c["title"]: c for c in calls}
        fulbright = next(c for t, c in by_title.items() if "Fulbright" in t)
        self.assertEqual((fulbright["deadline"], fulbright["funder"]), (D(2027, 1, 31), "Fulbright"))
        swiss = next(c for t, c in by_title.items() if "Švicarske" in t)
        self.assertEqual((swiss["deadline"], swiss["who"]), (D(2026, 11, 30), "students;PhD"))
        self.assertFalse(any("zapošljavanj" in t.lower() for t in by_title), "job ads left out")

    def test_unizg(self):
        calls, report = run_source(fc.fetch_unizg)
        self.assertEqual(calls, [])
        self.assertIn("no recent call", report["lines"][0])

    def test_mzom(self):
        calls, _ = run_source(fc.fetch_mzom)
        self.assertEqual(len(calls), 25)
        for word in ("lektor", "učitelj", "radno mjesto", "nabava", "rang-list"):
            self.assertFalse(any(word in t.lower() for t in titles(calls)), f"'{word}' left out")
        esa = next(c for c in calls if "ESA" in c["title"])
        self.assertEqual(esa["funder"], "European Space Agency (ESA)")

    def test_uniri(self):
        calls, _ = run_source(fc.fetch_uniri)
        self.assertEqual(len(calls), 27)
        for word in ("dobitnic", "završen", "zaključen", "održan"):
            self.assertFalse(any(word in t.lower() for t in titles(calls)), f"'{word}' left out")
        erc = next(c for c in calls if "ERC" in c["title"])
        self.assertEqual((erc["funder"], erc["eu"]), ("European Research Council (ERC)", True))
        yufethon = next(c for c in calls if "YUFEthon" in c["title"])
        self.assertEqual(yufethon["type"], "datathon")
        for c in calls:
            self.assertNotIn("UNIRI", c["keywords"], "source is not a keyword")


class B4Duplicates(unittest.TestCase):
    def call(self, title, deadline, source):
        return {"title": title, "deadline": deadline, "source": source, "keywords": [source.lower()]}

    def test_same_acronym_and_deadline_merge(self):
        out, merged = fc.merge_duplicates([
            self.call("Poziv na dostavu projektnih prijedloga u sklopu RAMP poziva 2027.", D(2027, 2, 15), "MZOM"),
            self.call("Otvoren poziv u okviru RAMP-a", D(2027, 2, 15), "UNIRI")])
        self.assertEqual((len(out), merged, out[0]["source"]), (1, 1, "MZOM, UNIRI"))

    def test_same_title_merge(self):
        out, merged = fc.merge_duplicates([
            self.call("Natječaj za stipendije Švicarske Konfederacije", D(2026, 11, 30), "AMPEU"),
            self.call("Natječaj za stipendije Švicarske Konfederacije", D(2026, 11, 30), "MZOM")])
        self.assertEqual(merged, 1)

    def test_different_deadline_not_merged(self):
        out, merged = fc.merge_duplicates([
            self.call("RAMP poziv 2027.", D(2027, 2, 15), "MZOM"), self.call("RAMP poziv 2028.", D(2028, 2, 15), "MZOM")])
        self.assertEqual((len(out), merged), (2, 0))


class B3B5B6WholeRun(unittest.TestCase):
    """The whole script: not-my-topics, output files, and a broken source."""

    def run_main(self, fail_hosts=()):
        tmp = Path(tempfile.mkdtemp(prefix="ct-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        old = fc.OUT, fc.OUT_JS
        fc.OUT, fc.OUT_JS = tmp / "live_calls.csv", tmp / "live_calls.js"
        out, code = io.StringIO(), 0
        try:
            with replay(fail_hosts), contextlib.redirect_stdout(out):
                try:
                    fc.main()
                except SystemExit as e:
                    code = e.code
        finally:
            fc.OUT, fc.OUT_JS = old
        return tmp, out.getvalue(), code

    def test_not_my_topics_left_out_and_listed(self):
        tmp, out, code = self.run_main()
        self.assertEqual(code, 0)
        rows = list(csv.DictReader(open(tmp / "live_calls.csv", encoding="utf-8")))
        _, exclude = fc.load_settings()
        for r in rows:
            self.assertFalse(any(w in r["title"].lower() for w in exclude), r["title"])
        self.assertIn("Left out", out)
        self.assertIn("[climate]", out)

    def test_csv_and_js_hold_the_same_calls(self):
        tmp, out, _ = self.run_main()
        rows = list(csv.DictReader(open(tmp / "live_calls.csv", encoding="utf-8")))
        js = (tmp / "live_calls.js").read_text(encoding="utf-8")
        data = json.loads(js[js.index("{"): js.rindex("}") + 1])
        self.assertEqual(data["csv"], (tmp / "live_calls.csv").read_text(encoding="utf-8"))
        self.assertEqual(list(rows[0].keys()), ["id", "title", "funder", "eu", "source", "type", "deadline",
                                                "link", "amount", "who", "keywords"])
        self.assertGreater(len(rows), 50)
        self.assertEqual(len({r["id"] for r in rows}), len(rows), "no duplicate ids")
        self.assertIn("Merged", out)

    def test_broken_source_is_reported_and_others_still_work(self):
        tmp, out, code = self.run_main(fail_hosts=("ampeu.hr",))
        self.assertEqual(code, 1)
        self.assertIn("PROBLEM: AMPEU: could not read ampeu.hr", out)
        rows = list(csv.DictReader(open(tmp / "live_calls.csv", encoding="utf-8")))
        self.assertTrue(any(r["source"].startswith("HRZZ") for r in rows), "other sources still saved")
        self.assertFalse(any(r["source"] == "AMPEU" for r in rows))


if __name__ == "__main__":
    unittest.main()
