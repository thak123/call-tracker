"""Part D: the weekly runner (weekly_refresh.py): log, summary of new calls, failures, scheduling help."""
import csv
import datetime
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).parent.parent
sys.path.insert(0, str(APP))
import weekly_refresh as wr  # noqa: E402

HEAD = ["id", "title", "funder", "eu", "source", "fit", "scope", "type", "deadline", "link", "amount", "who", "keywords"]


def row(id, title, deadline="2099-01-31", fit=3, funder="Test Fund"):
    return dict(id=id, title=title, funder=funder, eu="", source="HRZZ", fit=str(fit), scope="core", type="grant",
                deadline=deadline, link=f"https://example.com/{id}", amount="", who="staff", keywords="")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        w.writeheader()
        w.writerows(rows)


def fake_fetch(code=0, add=None, sleep=0):
    """A stand-in for fetch_calls.py: optionally waits, adds rows to live_calls.csv, exits with `code`."""
    adds = repr(add or [])
    return f'''import csv, pathlib, sys, time
time.sleep({sleep})
here = pathlib.Path(__file__).parent
rows = list(csv.DictReader(open(here / "live_calls.csv", encoding="utf-8"))) if (here / "live_calls.csv").exists() else []
rows += {adds}
with open(here / "live_calls.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames={HEAD!r}); w.writeheader(); w.writerows(rows)
print("fake search says hello")
{'print("PROBLEM: pretend the EU portal is down")' if code else ""}
sys.exit({code})
'''


class D1NewCalls(unittest.TestCase):
    TODAY = datetime.date(2026, 11, 24)

    def test_only_new_open_calls_count(self):
        old = [row("a", "Old open"), row("b", "Old closed", deadline="2000-01-01")]
        new = old + [row("c", "Brand new open"), row("d", "Brand new but closed", deadline="2000-01-01"),
                     row("e", "New with low fit", fit=0)]
        got = wr.new_open_calls(old, new, self.TODAY)
        self.assertEqual([c["id"] for c in got], ["c", "e"], "closed ones are not news; better fit comes first")

    def test_nothing_new(self):
        old = [row("a", "Old open")]
        self.assertEqual(wr.new_open_calls(old, old, self.TODAY), [])

    def test_summary_text(self):
        text = wr.summary_text(datetime.datetime(2026, 11, 30, 8, 0), 0, 480, 415,
                               [row("c", "Brand new open", fit=5, funder="Fund X")], first_run=False, problem="")
        for part in ("Monday 30 Nov 2026", "480 calls, 415 open", "New open calls since the last run: 1",
                     "[fit 5] Brand new open", "Fund X", "deadline 2099-01-31", "https://example.com/c"):
            self.assertIn(part, text)

    def test_summary_first_run_and_problem(self):
        first = wr.summary_text(datetime.datetime(2026, 11, 30, 8, 0), 0, 10, 5, [], first_run=True, problem="")
        self.assertIn("First run", first)
        bad = wr.summary_text(datetime.datetime(2026, 11, 30, 8, 0), 1, 10, 5, [], first_run=False, problem="PROBLEM: x")
        self.assertIn("PROBLEM", bad)


class D2Runner(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="ct-weekly-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def run_it(self, fetch_source, existing=None, extra=()):
        (self.dir / "fetch_calls.py").write_text(fetch_source)
        if existing is not None:
            write_csv(self.dir / "live_calls.csv", existing)
        return wr.main(["--dir", str(self.dir), *extra])

    def test_success_writes_log_and_summary_with_new_calls(self):
        code = self.run_it(fake_fetch(0, add=[row("n1", "A Fresh Call", fit=4)]), existing=[row("a", "Old open")])
        self.assertEqual(code, 0)
        summary = (self.dir / "weekly_summary.txt").read_text()
        self.assertIn("New open calls since the last run: 1", summary)
        self.assertIn("A Fresh Call", summary)
        log = (self.dir / "weekly_log.txt").read_text()
        self.assertIn("exit code 0", log)
        self.assertIn("fake search says hello", log)

    def test_second_run_appends_to_the_log(self):
        self.run_it(fake_fetch(0), existing=[row("a", "Old open")])
        self.run_it(fake_fetch(0))
        self.assertEqual((self.dir / "weekly_log.txt").read_text().count("exit code 0"), 2)

    def test_first_run_has_nothing_to_compare(self):
        self.run_it(fake_fetch(0, add=[row("n1", "A Fresh Call")]))
        self.assertIn("First run", (self.dir / "weekly_summary.txt").read_text())

    def test_failed_search_is_reported_and_exit_code_is_not_zero(self):
        code = self.run_it(fake_fetch(1), existing=[row("a", "Old open")])
        self.assertEqual(code, 1)
        self.assertIn("PROBLEM", (self.dir / "weekly_summary.txt").read_text())
        self.assertIn("exit code 1", (self.dir / "weekly_log.txt").read_text())
        self.assertTrue((self.dir / "live_calls.csv").exists(), "old results stay")

    def test_search_that_hangs_is_stopped(self):
        code = self.run_it(fake_fetch(0, sleep=30), existing=[row("a", "Old open")], extra=("--timeout", "1"))
        self.assertEqual(code, 2)
        self.assertIn("took longer than", (self.dir / "weekly_summary.txt").read_text())

    def test_log_does_not_grow_forever(self):
        (self.dir / "weekly_log.txt").write_text("x" * (wr.LOG_MAX + 50_000))
        self.run_it(fake_fetch(0), existing=[row("a", "Old open")])
        self.assertLess((self.dir / "weekly_log.txt").stat().st_size, wr.LOG_MAX)
        self.assertIn("exit code 0", (self.dir / "weekly_log.txt").read_text())


class D3Scheduling(unittest.TestCase):
    def test_how_to_schedule_has_exact_lines_for_this_folder(self):
        text = wr.how_to_schedule()
        self.assertIn(str(APP), text)
        self.assertIn(sys.executable, text)
        self.assertIn("0 8 * * 1", text)
        self.assertIn("Persistent=true", text)
        self.assertIn("systemctl --user enable --now", text)
        self.assertIn("nothing is installed", text.lower())


if __name__ == "__main__":
    unittest.main()
