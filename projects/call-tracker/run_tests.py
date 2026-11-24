"""Run all Call Tracker tests:  python3 run_tests.py   (add --live to also check the real websites)

Part A  page workflows      tests/ui.test.mjs     (Chrome in a hidden window, via Node)
Part B  search script       tests/test_fetch.py   (saved website copies, no internet)
Part C  helper (serve.py)   tests/test_serve.py
Part D  weekly runner       tests/test_weekly.py
Part E  icon files          tests/test_assets.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
TESTS = HERE / "tests"


def run(title, cmd, env=None):
    print(f"\n=== {title} ===", flush=True)
    return subprocess.run(cmd, cwd=HERE, env=env).returncode == 0


def ensure_web_copies():
    """The saved website copies (tests/fixtures/web/*.gz) are not in Git. Re-create them when missing."""
    web = TESTS / "fixtures" / "web"
    if (web / "index.json").exists() and list(web.glob("*.gz")):
        return True
    print("\nSaved website copies are missing (they are not stored in Git). Recording them now from the real websites...")
    ok = run("Recording website copies", [sys.executable, str(TESTS / "web_replay.py"), "record"])
    if ok:
        print("\nRecorded today's pages. The websites change over time, so the exact call counts in"
              "\ntests/test_fetch.py may differ from today's pages: if Part B fails on a count, update the number.")
    return ok


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if (not only or "B" in only) and not ensure_web_copies():
        print("Could not record the website copies (no internet?). Part B needs them.")
        sys.exit(1)
    results = {}
    parts = {
        "A": ("Part A - page workflows", ["node", "--test", "--test-reporter=spec", str(TESTS / "ui.test.mjs")]),
        "B": ("Part B - search script", [sys.executable, "-m", "unittest", "-v", "tests.test_fetch"]),
        "C": ("Part C - helper", [sys.executable, "-m", "unittest", "-v", "tests.test_serve"]),
        "D": ("Part D - weekly runner", [sys.executable, "-m", "unittest", "-v", "tests.test_weekly"]),
        "E": ("Part E - icon files", [sys.executable, "-m", "unittest", "-v", "tests.test_assets"]),
    }
    for key, (title, cmd) in parts.items():
        if only and key not in only:
            continue
        test_file = TESTS / (Path(cmd[-1]).name if key == "A" else cmd[-1].split(".")[-1] + ".py")
        if not test_file.exists():
            print(f"\n=== {title} === (not written yet)")
            continue
        results[title] = run(title, cmd)
    if "--live" in sys.argv:
        results["Live check of real websites"] = run("Live check of real websites",
                                                     [sys.executable, str(TESTS / "live_check.py")])
    print("\n=== Summary ===")
    for title, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {title}")
    print(f"  Screenshots: {TESTS / 'screenshots'}")
    sys.exit(0 if results and all(results.values()) else 1)


if __name__ == "__main__":
    main()
