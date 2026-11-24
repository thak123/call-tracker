"""Weekly refresh for the Call Tracker: run the search, keep a log, write a short "what is new" summary.

    python3 weekly_refresh.py                      run now (this is what the schedule calls)
    python3 weekly_refresh.py --how-to-schedule    print the exact lines to set up "every Monday"

Files it writes (all in this folder):
    weekly_log.txt       what the search printed, run after run (kept to a reasonable size)
    weekly_summary.txt   the last run in a few lines: counts, problems, new open calls
Exit code: 0 = fine, 1 = the search reported a problem, 2 = the search took too long and was stopped.
"""
import argparse
import csv
import datetime
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
LOG_MAX = 400_000          # bytes; older log lines are dropped past this
TIMEOUT_SECONDS = 30 * 60  # the real search takes about 2 minutes
TOP_NEW = 15


def read_rows(path):
    if not Path(path).exists():
        return None
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def new_open_calls(old_rows, new_rows, today):
    """Calls that were not in the last results, are still open, best fit first."""
    seen = {r["id"] for r in old_rows}
    fresh = [r for r in new_rows if r["id"] not in seen and r["deadline"] >= today.isoformat()]
    return sorted(fresh, key=lambda r: (-int(r.get("fit") or 0), r["deadline"]))


def summary_text(now, code, total, open_count, new, first_run, problem, alerts=()):
    lines = [f"Call Tracker weekly refresh: {now.strftime('%A %d %b %Y, %H:%M')}"]
    if code == 0:
        lines.append(f"Search finished OK: {total} calls, {open_count} open.")
    else:
        lines.append(f"Search had a problem (exit code {code}). The results below are from the last good data.")
        if problem:
            lines.append(problem)
    if first_run:
        lines.append("First run: nothing to compare with yet.")
    else:
        lines.append(f"New open calls since the last run: {len(new)}")
        for i, c in enumerate(new[:TOP_NEW], 1):
            lines.append(f"  {i}. [fit {c.get('fit') or 0}] {c['title']}")
            lines.append(f"     {c['funder']} · deadline {c['deadline']}")
            lines.append(f"     {c['link']}")
        if len(new) > TOP_NEW:
            lines.append(f"  ... and {len(new) - TOP_NEW} more: open index.html to see them (they carry a NEW badge).")
    if alerts:
        lines.append("Needs a look (a new call may be open, or a source may have stopped working):")
        lines += [f"  {a}" for a in alerts]
    lines.append("Open index.html to look at everything.")
    return "\n".join(lines) + "\n"


def append_log(path, text):
    path = Path(path)
    old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    full = old + text
    if len(full.encode("utf-8")) > LOG_MAX:
        full = full[-(LOG_MAX // 2):]
        full = full[full.find("\n=== ") + 1:] if "\n=== " in full else full   # start at a whole entry
    path.write_text(full, encoding="utf-8")


def how_to_schedule():
    folder, py = HERE, sys.executable
    return f"""How to run the refresh every Monday morning (nothing is installed by this program: you choose one option and run it yourself)

OPTION 1: cron (simple; it only runs if the computer is on at that time)
  1. In a terminal type:  crontab -e
  2. Add this line at the end, then save:

     0 8 * * 1 cd "{folder}" && "{py}" weekly_refresh.py >> weekly_cron.log 2>&1

  (0 8 * * 1 = every Monday at 08:00)

OPTION 2: systemd timer (better for a laptop: if it was off on Monday, it runs when you switch it on)
  1. mkdir -p ~/.config/systemd/user
  2. Create ~/.config/systemd/user/call-tracker.service with:

     [Unit]
     Description=Call Tracker weekly refresh
     [Service]
     Type=oneshot
     WorkingDirectory={folder}
     ExecStart="{py}" weekly_refresh.py

  3. Create ~/.config/systemd/user/call-tracker.timer with:

     [Unit]
     Description=Call Tracker every Monday
     [Timer]
     OnCalendar=Mon *-*-* 08:00:00
     Persistent=true
     [Install]
     WantedBy=timers.target

  4. Then run:  systemctl --user enable --now call-tracker.timer
  5. Check it:  systemctl --user list-timers

To stop: remove the cron line, or run  systemctl --user disable --now call-tracker.timer

After each run, read {folder / 'weekly_summary.txt'} to see what is new, or just open index.html (new calls carry a NEW badge).
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(HERE), help="folder with fetch_calls.py and live_calls.csv (default: this folder)")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS, help="seconds before the search is stopped")
    ap.add_argument("--how-to-schedule", action="store_true", help="print the lines for cron or a systemd timer")
    args = ap.parse_args(argv)
    if args.how_to_schedule:
        print(how_to_schedule())
        return 0

    folder = Path(args.dir)
    results = folder / "live_calls.csv"
    before = read_rows(results)
    now = datetime.datetime.now()
    problem, alerts = "", []
    try:
        run = subprocess.run([sys.executable, str(folder / "fetch_calls.py")], cwd=folder,
                             capture_output=True, text=True, timeout=args.timeout)
        code, output = run.returncode, run.stdout + run.stderr
        problem = "\n".join(l for l in output.splitlines() if "PROBLEM" in l)
        alerts = [l for l in output.splitlines() if l.startswith(("WATCH ALERT", "SOURCE WARNING"))]
    except subprocess.TimeoutExpired:
        code, output = 2, ""
        problem = f"The search took longer than {args.timeout} seconds and was stopped."
    append_log(folder / "weekly_log.txt", f"\n=== {now.strftime('%Y-%m-%d %H:%M')} exit code {code} ===\n{output or problem}\n")

    after = read_rows(results) or []
    new = new_open_calls(before or [], after, now.date()) if before is not None else []
    open_count = sum(r["deadline"] >= now.date().isoformat() for r in after)
    text = summary_text(now, code, len(after), open_count, new, first_run=before is None, problem=problem, alerts=alerts)
    (folder / "weekly_summary.txt").write_text(text, encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
