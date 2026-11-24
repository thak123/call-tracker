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
        everything, calls = calls, [c for c in calls if c["scope"] == "core"]
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
        calls = [c for c in calls if c["scope"] == "core"]
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


class B11OutsideMyField(unittest.TestCase):
    """Any source can mark a call as outside my field (scope "other"); job ads and notices are still dropped."""

    NOISE = ("radno mjesto", "državnu službu", "(m/ž)", "odobren", "obavijest", "savjetovanj", "radionic", "rezultat")

    def test_eufondovi_keeps_school_and_health_calls_as_other(self):
        calls, _ = run_source(fc.fetch_eufondovi)
        other = [c for c in calls if c["scope"] == "other"]
        self.assertGreater(len(other), 10, "the school/health/other calls are kept, not thrown away")
        self.assertEqual(len([c for c in calls if c["scope"] == "core"]), 9)
        for c in calls:
            self.assertFalse(any(n in c["title"].lower() for n in self.NOISE), c["title"])

    def test_devpost_keeps_hackathons_that_are_not_about_ai_as_other(self):
        calls, _ = run_source(fc.fetch_devpost)
        self.assertEqual(len([c for c in calls if c["scope"] == "core"]), 28)
        self.assertGreater(len([c for c in calls if c["scope"] == "other"]), 15)
        self.assertEqual(len({c["id"] for c in calls}), len(calls))

    def test_mzom_keeps_other_topics_but_drops_job_ads(self):
        calls, _ = run_source(fc.fetch_mzom)
        self.assertGreater(len([c for c in calls if c["scope"] == "other"]), 0, "calls about schools and minorities are kept as other")
        for c in calls:
            self.assertFalse(any(n in c["title"].lower() for n in ("radno mjesto", "državnu službu", "(m/ž)", "zapošljavanj")), c["title"])

    def test_one_per_call_prefers_core_over_other(self):
        mk = lambda scope: {"id": "x:1", "scope": scope, "deadline": D(2027, 1, 1), "title": "t"}
        self.assertEqual(fc.one_per_call([mk("other"), mk("core")])[0]["scope"], "core")

    def test_croatian_field_words_count_for_the_fit_score(self):
        f = lambda t: fc.fit_score({"title": t, "id": "x:1", "keywords": []})
        self.assertGreaterEqual(f("Natječaj za umjetnu inteligenciju u obrazovanju"), 2)
        self.assertGreaterEqual(f("Poziv za istraživanje hrvatskog jezika"), 2)
        self.assertGreaterEqual(f("Digitalne vještine građana"), 2)
        self.assertGreaterEqual(f("Strojno prevođenje i obrada govora"), 2)
        self.assertEqual(f("Javni poziv za dodjelu sredstava za sportaše"), 0)
        self.assertEqual(f("Poziv za poljoprivredna gospodarstva"), 0)


class B2bBrowseAndDevpost(unittest.TestCase):
    def test_eu_browse_lists_all_open_calls_with_fit(self):
        calls, report = run_source(fc.fetch_eu_browse)
        self.assertGreater(len(calls), 400)
        self.assertTrue(all(c["scope"] == "browse" and c["eu"] and c["deadline"] >= fc.TODAY for c in calls))
        ai_learning = next(c for c in calls if "effective use of artificial intelligence in learning" in c["title"])
        self.assertGreaterEqual(fc.fit_score(ai_learning), 3)
        self.assertIn("fit my field", report["lines"][0])
        self.assertEqual(report["problems"], [])

    def test_one_card_per_call_with_the_next_cutoff(self):
        calls, _ = run_source(fc.fetch_eu_browse)
        picked = fc.one_per_call(calls)
        self.assertEqual(len({c["id"] for c in picked}), len(picked))
        self.assertLess(len(picked), len(calls), "repeated records were reduced")
        cerv = [c for c in calls if c["id"] == "eu:CERV-2024-CITIZENS-VALUES"]
        self.assertGreater(len(cerv), 1)
        self.assertEqual(next(c for c in picked if c["id"] == "eu:CERV-2024-CITIZENS-VALUES")["deadline"],
                         min(c["deadline"] for c in cerv), "earliest upcoming cut-off wins")

    def test_keyword_search_result_wins_over_browse(self):
        mk = lambda scope, dl: {"id": "eu:X", "scope": scope, "deadline": dl, "title": "t"}
        out = fc.one_per_call([mk("browse", D(2027, 1, 1)), mk("core", D(2027, 3, 1))])
        self.assertEqual((len(out), out[0]["scope"]), (1, "core"))
        out = fc.one_per_call([mk("core", D(2026, 10, 1)), mk("core", D(2027, 3, 1)), mk("core", D(2027, 2, 1))])
        self.assertEqual(out[0]["deadline"], D(2027, 2, 1), "an upcoming cut-off beats a passed one")

    def test_eu_browse_failure_is_reported(self):
        calls, report = run_source(fc.fetch_eu_browse, fail_hosts=("api.tech.ec.europa.eu",))
        self.assertEqual(calls, [])
        self.assertIn("EU browse: search failed", report["problems"][0])

    def test_devpost(self):
        calls, report = run_source(fc.fetch_devpost)
        calls = [c for c in calls if c["scope"] == "core"]
        self.assertEqual(len(calls), 28)
        self.assertTrue(all(c["type"] == "datathon" and c["who"] == "students" and c["source"] == "Devpost" for c in calls))
        self.assertTrue(all(c["link"].startswith("https://") and "?" not in c["link"] for c in calls))
        self.assertTrue(all(c["deadline"] >= fc.TODAY for c in calls))
        self.assertFalse(any(c["amount"].startswith("$ ") for c in calls), "prize written like $700")
        self.assertEqual(report["problems"], [])

    def test_devpost_failure_is_reported(self):
        calls, report = run_source(fc.fetch_devpost, fail_hosts=("devpost.com",))
        self.assertEqual(calls, [])
        self.assertIn("Devpost: could not read", report["problems"][0])


class B1cFitAndDevpostDates(unittest.TestCase):
    def call(self, title, ident="x:1", keywords=()):
        return {"title": title, "id": ident, "keywords": list(keywords)}

    def test_fit_scores(self):
        self.assertEqual(fc.fit_score(self.call("Road bridge maintenance")), 0)
        self.assertEqual(fc.fit_score(self.call("Digital skills for citizens")), 2, "related words in the title")
        self.assertEqual(fc.fit_score(self.call("Road bridge maintenance", "eu:HORIZON-CL4-2027-01")), 1, "programme close to my field")
        self.assertEqual(fc.fit_score(self.call("NLP for Croatian", keywords=["natural language processing"])), 3, "one of my keywords")
        self.assertEqual(fc.fit_score(self.call("Language AI", "eu:ERC-2027-ADG", ["artificial intelligence", "multilingual"])), 9)

    def test_devpost_date_formats(self):
        d = fc.devpost_deadline
        self.assertEqual(d("Nov 24, 2026"), D(2026, 11, 24))
        self.assertEqual(d("Nov 17 - 24, 2026"), D(2026, 11, 24))
        self.assertEqual(d("Oct 17 - Nov 24, 2026"), D(2026, 11, 24))
        self.assertEqual(d("Dec 28, 2026 - Jan 15, 2027"), D(2027, 1, 15))
        self.assertIsNone(d("Coming soon"))
        self.assertIsNone(d(None))


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

    def test_two_different_eu_calls_are_never_merged(self):
        out, merged = fc.merge_duplicates([
            self.call("Support for SME innovation", D(2027, 9, 23), "EU portal"),
            self.call("Training for SME advisers", D(2027, 9, 23), "EU portal")])
        self.assertEqual((len(out), merged), (2, 0))

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
        self.assertIn("from EU browse", out)

    def test_csv_and_js_hold_the_same_calls(self):
        tmp, out, _ = self.run_main()
        rows = list(csv.DictReader(open(tmp / "live_calls.csv", encoding="utf-8")))
        js = (tmp / "live_calls.js").read_text(encoding="utf-8")
        data = json.loads(js[js.index("{"): js.rindex("}") + 1])
        self.assertEqual(data["csv"], (tmp / "live_calls.csv").read_text(encoding="utf-8"))
        self.assertEqual(list(rows[0].keys()), ["id", "title", "funder", "eu", "source", "fit", "scope", "type",
                                                "deadline", "link", "amount", "who", "keywords", "opens", "about", "mode", "location"])
        self.assertTrue({"core", "browse", "other"} <= {r["scope"] for r in rows})
        mine = [r for r in rows if r["source"] == "My list"]
        self.assertEqual([r["title"] for r in mine], ["Test Shared Task"], "my hand-kept list is part of the results")
        browse = [r for r in rows if r["scope"] == "browse"]
        self.assertTrue(any(int(r["fit"]) >= 1 for r in browse) and any(int(r["fit"]) == 0 for r in browse))
        self.assertTrue(all(r["fit"].isdigit() for r in rows))
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


class B7MyList(unittest.TestCase):
    """Calls I add by hand in my_calls.csv (events without a data feed, like SemEval or WMT)."""

    def run_list(self, content):
        tmp = Path(tempfile.mkdtemp(prefix="ct-mylist-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "my.csv").write_text(content, encoding="utf-8")
        old = fc.MY_LIST
        fc.MY_LIST = tmp / "my.csv"
        try:
            return run_source(fc.fetch_my_list)
        finally:
            fc.MY_LIST = old

    HEAD = "title,type,deadline,link,funder,who,keywords,amount\n"

    def test_good_rows(self):
        calls, report = self.run_list(self.HEAD +
            "Shared Task One,competition,2027-01-31,https://example.com/1,Some Society,staff;PhD;students,machine translation;multilingual,\n"
            "Shared Task Two,,15.1.2027,https://example.com/2,,,,€500\n")
        self.assertEqual(len(calls), 2)
        one, two = calls
        self.assertEqual((one["deadline"], one["source"], one["scope"], one["eu"]), (D(2027, 1, 31), "My list", "core", False))
        self.assertEqual((one["funder"], one["who"], one["type"]), ("Some Society", "staff;PhD;students", "competition"))
        self.assertEqual(one["keywords"], ["machine translation", "multilingual"])
        self.assertEqual((two["deadline"], two["type"], two["who"], two["amount"]), (D(2027, 1, 15), "competition", "staff;PhD", "€500"))
        self.assertTrue(one["id"].startswith("my:") and one["id"] != two["id"])
        self.assertEqual(report["no_date"], [])

    def test_my_keywords_found_in_the_title_are_added(self):
        calls, _ = self.run_list(self.HEAD + "Multilingual speech benchmark,datathon,2027-02-01,https://example.com,,,,\n")
        self.assertEqual(calls[0]["keywords"], ["multilingual"])
        self.assertEqual(calls[0]["type"], "datathon")

    def test_bad_rows_are_reported_not_hidden(self):
        calls, report = self.run_list(self.HEAD +
            "Good,competition,2027-01-31,https://example.com,,,,\n"
            "Bad Date,competition,sometime in spring,https://example.com,,,,\n"
            ",competition,2027-01-31,https://example.com,,,,\n")
        self.assertEqual([c["title"] for c in calls], ["Good"])
        self.assertEqual(len(report["no_date"]), 2)
        self.assertIn("row 3", report["no_date"][0][0]); self.assertIn("Bad Date", report["no_date"][0][0])
        self.assertIn("row 4", report["no_date"][1][0])

    def test_european_excel_file_with_semicolons(self):
        calls, _ = self.run_list("﻿title;type;deadline;link;funder;who;keywords;amount\n"
                                 "Euro Task;competition;3.12.2026.;https://example.com;Fund;staff;multilingual;\n")
        self.assertEqual((len(calls), calls[0]["deadline"]), (1, D(2026, 12, 3)))

    def test_old_entries_are_dropped_and_missing_file_is_fine(self):
        calls, _ = self.run_list(self.HEAD + "Ancient,competition,2024-01-31,https://example.com,,,,\n")
        self.assertEqual(calls, [])
        old = fc.MY_LIST
        fc.MY_LIST = Path("/nonexistent/my_calls.csv")
        try:
            self.assertEqual(run_source(fc.fetch_my_list)[0], [])
        finally:
            fc.MY_LIST = old

    def test_my_real_list_has_no_typos(self):
        old = fc.MY_LIST
        fc.MY_LIST = fc.HERE / "my_calls.csv"
        try:
            calls, report = run_source(fc.fetch_my_list)
        finally:
            fc.MY_LIST = old
        self.assertEqual(report["no_date"], [], "every row of my_calls.csv has a title and a date")
        self.assertGreaterEqual(len(calls), 3)
        for c in calls:
            self.assertTrue(c["link"].startswith("https://"), c["title"])


class B8Watch(unittest.TestCase):
    """Pages that announce a call later (COST Open Call): flag it when the 'closed' notice disappears."""

    def run_watch(self, fail_hosts=(), page_text=None):
        keywords, _ = fc.load_settings()
        report = {"lines": [], "problems": [], "no_date": []}
        old = fc.get_text
        if page_text is not None:
            fc.get_text = lambda url: page_text
        try:
            with replay(fail_hosts):
                fc.check_watch(keywords, report)
        finally:
            fc.get_text = old
        return report

    def test_closed_page_gives_no_alert(self):
        report = self.run_watch()
        self.assertEqual(report.get("alerts", []), [])
        self.assertIn("COST Open Call: still closed", report["lines"][0])
        self.assertEqual(report["problems"], [])

    def test_alert_when_the_closed_notice_is_gone(self):
        report = self.run_watch(page_text="<p>The COST Open Call 2027 is open. Submit your proposal by 29 October 2027.</p>")
        self.assertEqual(len(report["alerts"]), 1)
        name, url = report["alerts"][0]
        self.assertEqual(name, "COST Open Call")
        self.assertTrue(url.startswith("https://www.cost.eu/"))
        self.assertIn("may be open", report["lines"][0])

    def test_site_down_is_a_problem_not_an_alert(self):
        report = self.run_watch(fail_hosts=("cost.eu",))
        self.assertEqual(report.get("alerts", []), [])
        self.assertIn("Watch COST Open Call: could not read", report["problems"][0])

    def test_whole_run_prints_alert_and_keeps_going(self):
        out = io.StringIO()
        old = fc.get_text
        real = old
        fc.get_text = lambda url: "<p>Open call is open now</p>" if "cost.eu" in url else real(url)
        tmp = Path(tempfile.mkdtemp(prefix="ct-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        saved = fc.OUT, fc.OUT_JS
        fc.OUT, fc.OUT_JS = tmp / "live_calls.csv", tmp / "live_calls.js"
        try:
            with replay(), contextlib.redirect_stdout(out):
                try:
                    fc.main()
                except SystemExit:
                    pass
        finally:
            fc.get_text = old
            fc.OUT, fc.OUT_JS = saved
        self.assertIn("WATCH ALERT: COST Open Call", out.getvalue())
        self.assertTrue((tmp / "live_calls.csv").exists())


class B9SourceHealth(unittest.TestCase):
    """The Sources panel: how many calls each source gave, and whether it needs a look."""

    def test_judge_source(self):
        j = fc.judge_source
        self.assertEqual(j("X", 5, 5, "")["status"], "ok")
        self.assertEqual(j("X", 0, 0, "")["status"], "ok", "a source that was always empty is fine")
        self.assertEqual(j("X", 0, 2, "")["status"], "ok", "small sources may be empty")
        w = j("X", 0, 5, "")
        self.assertEqual(w["status"], "warn"); self.assertIn("found 0 calls, last time 5", w["message"])
        self.assertEqual(j("X", 3, 20, "")["status"], "warn", "far fewer than last time")
        self.assertEqual(j("X", 12, 20, "")["status"], "ok", "somewhat fewer is normal")
        p = j("X", 0, 5, "could not read x.org (timeout)")
        self.assertEqual((p["status"], p["message"]), ("problem", "could not read x.org (timeout)"))
        self.assertEqual(j("X", 4, None, "")["status"], "ok", "first run: nothing to compare with")

    def run_main(self, fail_hosts=(), previous=None):
        tmp = Path(tempfile.mkdtemp(prefix="ct-health-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        old = fc.OUT, fc.OUT_JS
        fc.OUT, fc.OUT_JS = tmp / "live_calls.csv", tmp / "live_calls.js"
        if previous is not None:
            fc.OUT_JS.write_text("window.LIVE_CALLS = " + json.dumps({"generated": "x", "csv": "", "sources": previous}) + ";\n")
        out = io.StringIO()
        try:
            with replay(fail_hosts), contextlib.redirect_stdout(out):
                try:
                    fc.main()
                except SystemExit:
                    pass
        finally:
            fc.OUT, fc.OUT_JS = old
        js = (tmp / "live_calls.js").read_text(encoding="utf-8")
        return json.loads(js[js.index("{"): js.rindex("}") + 1]), out.getvalue()

    def test_every_source_is_listed_with_count_and_status(self):
        data, out = self.run_main()
        by = {s["name"]: s for s in data["sources"]}
        for name in ("EU portal: my keywords", "EU portal: all open calls", "HRZZ", "eufondovi", "AMPEU", "UNIZG",
                     "MZOM", "UNIRI", "Devpost", "My list"):
            self.assertIn(name, by)
        self.assertEqual(by["AMPEU"]["count"], 5)
        self.assertEqual(by["AMPEU"]["status"], "ok")
        self.assertTrue(by["AMPEU"]["url"].startswith("https://"))
        self.assertEqual(by["UNIZG"]["count"], 0)
        self.assertEqual(by["Watch: COST Open Call"]["status"], "ok")
        self.assertTrue(all({"name", "status", "count", "message", "url"} <= set(s) for s in data["sources"]))

    def test_failed_source_is_marked_and_others_are_fine(self):
        data, out = self.run_main(fail_hosts=("ampeu.hr",))
        by = {s["name"]: s for s in data["sources"]}
        self.assertEqual(by["AMPEU"]["status"], "problem")
        self.assertIn("could not read ampeu.hr", by["AMPEU"]["message"])
        self.assertEqual(by["HRZZ"]["status"], "ok")

    def test_a_source_that_went_quiet_is_flagged_against_the_last_run(self):
        data, out = self.run_main(previous=[{"name": "AMPEU", "count": 12}, {"name": "HRZZ", "count": 4}])
        by = {s["name"]: s for s in data["sources"]}
        self.assertEqual(by["AMPEU"]["status"], "ok", "5 of 12 is fine")
        data, out = self.run_main(previous=[{"name": "AMPEU", "count": 40}])
        by = {s["name"]: s for s in data["sources"]}
        self.assertEqual(by["AMPEU"]["status"], "warn")
        self.assertIn("last time 40", by["AMPEU"]["message"])
        self.assertIn("SOURCE WARNING: AMPEU", out)


class B10EuDetails(unittest.TestCase):
    """Description, budget and opening date of EU topics (from the portal's own details files)."""

    SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "eu_topic_sample.json").read_text(encoding="utf-8"))["TopicDetails"]

    def test_parse_a_real_topic(self):
        info = fc.parse_topic_details(self.SAMPLE, "HORIZON-CL2-2027-01-TRANSFO-05", D(2026, 11, 24))
        self.assertEqual(info["amount"], "€3–4M per project · ~3 grants")
        self.assertEqual(info["opens"], "2027-05-13")
        self.assertLessEqual(len(info["about"]), 301)
        self.assertNotIn("<", info["about"])
        self.assertTrue(info["about"].strip())
        self.assertIn("artificial intelligence", info["text"].lower())

    def test_amount_formats(self):
        f = fc.format_amount
        self.assertEqual(f(14_000_000, 14_000_000, 3, 42_000_000), "€14M per project · ~3 grants")
        self.assertEqual(f(3_000_000, 3_300_000, 3, 10_000_000), "€3–3.3M per project · ~3 grants")
        self.assertEqual(f(0, 0, 373, 594_100_000), "€594M in total · ~373 grants")
        self.assertEqual(f(500_000, 500_000, 0, 0), "€0.5M per project")
        self.assertEqual(f(0, 0, 0, 0), "")

    def test_opening_date_only_when_in_the_future(self):
        d = json.loads(json.dumps(self.SAMPLE))
        self.assertEqual(fc.parse_topic_details(d, "HORIZON-CL2-2027-01-TRANSFO-05", D(2027, 6, 1))["opens"], "", "already open")

    def test_record_without_budget_is_fine(self):
        d = {"identifier": "X", "description": "<p>Scope:</p><p>Only text here.</p>", "budgetOverviewJSONItem": {"budgetTopicActionMap": {}}, "actions": []}
        info = fc.parse_topic_details(d, "X", D(2026, 11, 24))
        self.assertEqual((info["amount"], info["opens"]), ("", ""))
        self.assertEqual(info["about"], "Only text here.")

    def test_description_keywords_count_less_than_title_keywords(self):
        base = {"title": "Plain title", "id": "eu:X", "keywords": ["multilingual", "artificial intelligence"], "desc_only": ["artificial intelligence"]}
        self.assertEqual(fc.fit_score(base), 3 + 2, "one keyword in the title (3), one only in the description (2)")

    def enrich(self, calls, fail_hosts=(), cache=None):
        keywords, _ = fc.load_settings()
        report = {"lines": [], "problems": [], "no_date": []}
        old = fc.EU_CACHE
        fc.EU_CACHE = cache
        try:
            with replay(fail_hosts):
                fc.enrich_eu(calls, keywords, report)
        finally:
            fc.EU_CACHE = old
        return report

    def browse_calls(self):
        calls, _ = run_source(fc.fetch_eu_browse)
        return fc.one_per_call(calls)

    def test_enrich_adds_about_amount_opens_and_description_keywords(self):
        calls = self.browse_calls()
        report = self.enrich(calls)
        with_about = [c for c in calls if c.get("about")]
        self.assertGreater(len(with_about), len(calls) * 0.8, "most EU calls got a description")
        self.assertTrue(any(c["amount"] != "see call page" for c in calls), "amounts filled in")
        self.assertTrue(any(c.get("opens") for c in calls), "some calls are not open yet")
        self.assertTrue(any(c.get("desc_only") for c in calls), "keywords found in descriptions")
        self.assertIn("EU details:", report["lines"][0])
        for c in calls:
            if c.get("desc_only"):
                self.assertTrue(set(c["desc_only"]) <= set(c["keywords"]))

    def test_failures_are_counted_and_the_calls_stay(self):
        calls = self.browse_calls()
        n = len(calls)
        report = self.enrich(calls, fail_hosts=("topicDetails",))
        self.assertEqual(len(calls), n)
        self.assertFalse(any(c.get("about") for c in calls))
        self.assertIn("failed", report["lines"][0])

    def test_cache_is_used_the_second_time(self):
        tmp = Path(tempfile.mkdtemp(prefix="ct-cache-")); self.addCleanup(shutil.rmtree, tmp, True)
        cache = tmp / "eu_details_cache.json"
        first = self.browse_calls()[:20]
        self.enrich(first, cache=cache)
        self.assertTrue(cache.exists())
        second = self.browse_calls()[:20]
        report = self.enrich(second, fail_hosts=("topicDetails",), cache=cache)   # network "down": answers come from the cache
        self.assertEqual([c.get("about") for c in second], [c.get("about") for c in first])
        self.assertIn("from the saved copy", report["lines"][0])


class B12HackathonPlace(unittest.TestCase):
    """Where a hackathon takes place: online or in person (with the venue as Devpost writes it)."""

    def test_place_of(self):
        f = fc.place_of
        self.assertEqual(f({"icon": "globe", "location": "Online"}), ("online", ""))
        self.assertEqual(f({"icon": "map-marker-alt", "location": "REMOTE"}), ("online", ""), "'remote' means online")
        self.assertEqual(f({"icon": "map-marker-alt", "location": "Durham University, Entrepreneurs Durham"}),
                         ("in person", "Durham University, Entrepreneurs Durham"))
        self.assertEqual(f({"icon": "map-marker-alt", "location": "OJone Building, Bengaluru. "}), ("in person", "OJone Building, Bengaluru"))
        self.assertEqual(f({"icon": "globe", "location": "Virtual / Worldwide"}), ("online", ""), "a globe icon means online")
        self.assertEqual(f(None), ("", ""))
        self.assertEqual(f({}), ("", ""))

    def test_devpost_rows_carry_the_place(self):
        calls, _ = run_source(fc.fetch_devpost)
        modes = {c["mode"] for c in calls}
        self.assertEqual(modes, {"online", "in person"})
        online = [c for c in calls if c["mode"] == "online"]
        in_person = [c for c in calls if c["mode"] == "in person"]
        self.assertGreater(len(online), 40)
        self.assertGreater(len(in_person), 0)
        self.assertTrue(all(c["location"] for c in in_person), "a venue for every in-person event")
        self.assertTrue(all(c["location"] == "" for c in online))

    def test_other_sources_do_not_claim_a_place(self):
        calls, _ = run_source(fc.fetch_hrzz)
        self.assertTrue(all(c.get("mode", "") == "" for c in calls))
