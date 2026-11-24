"""Optional online check (python3 run_tests.py --live): asks each real website once, with my real keywords,
and reports whether every source still answers. Writes no files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import fetch_calls as fc  # noqa: E402

keywords, _ = fc.load_settings()
report = {"lines": [], "problems": [], "no_date": []}
for fetch in (fc.fetch_eu, fc.fetch_hrzz, fc.fetch_eufondovi, fc.fetch_ampeu, fc.fetch_unizg, fc.fetch_mzom, fc.fetch_uniri,
              fc.fetch_devpost, fc.fetch_eu_browse, fc.check_watch):
    fetch(keywords, report)
print("\n".join(line for line in report["lines"] if "(none right now)" not in line))
for p in report["problems"]:
    print("PROBLEM:", p)
print("All sources answered." if not report["problems"] else "Some sources failed: see PROBLEM lines.")
sys.exit(1 if report["problems"] else 0)
