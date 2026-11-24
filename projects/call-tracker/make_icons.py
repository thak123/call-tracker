"""Draw the Call Tracker icon and make every size of it.

    python3 make_icons.py

Writes into icons/:  favicon.svg  favicon.ico (16, 32, 48)  favicon-32.png  apple-touch-icon.png (180)  icon-512.png
The picture: a calendar page with a highlighted deadline day. Change the colours below and run again.
Needs Chrome or Chromium (it draws the PNG sizes); nothing else to install, nothing goes online.
"""
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "icons"

# ---- colours ---------------------------------------------------------------
BG_TOP, BG_BOTTOM = "#3a78c2", "#1d4373"   # the rounded square (the site's blue)
HEADER = "#eb6834"                         # calendar top bar (the "third-party call" orange of the cards)
PAGE = "#ffffff"
DAY = "#c9d7ec"                            # ordinary days
DEADLINE = "#eda100"                       # the highlighted deadline day (the "datathon" yellow)
# ----------------------------------------------------------------------------


def svg(rounded=True):
    r = 14 if rounded else 0
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img">
  <title>Call Tracker</title>
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/></linearGradient></defs>
  <rect width="64" height="64" rx="{r}" fill="url(#g)"/>
  <rect x="21" y="9" width="5" height="12" rx="2.5" fill="{PAGE}"/>
  <rect x="38" y="9" width="5" height="12" rx="2.5" fill="{PAGE}"/>
  <rect x="11" y="15" width="42" height="38" rx="6" fill="{PAGE}"/>
  <path d="M11 21a6 6 0 0 1 6-6h30a6 6 0 0 1 6 6v7H11z" fill="{HEADER}"/>
  <g fill="{DAY}"><rect x="17" y="34" width="7" height="7" rx="2"/><rect x="28.5" y="34" width="7" height="7" rx="2"/><rect x="40" y="34" width="7" height="7" rx="2"/>
  <rect x="17" y="44" width="7" height="7" rx="2"/><rect x="28.5" y="44" width="7" height="7" rx="2"/></g>
  <circle cx="43.5" cy="47.5" r="6.5" fill="{DEADLINE}"/>
</svg>
"""


def find_chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    for path in ("/snap/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if Path(path).exists():
            return path
    sys.exit("Chrome or Chromium not found: install one, or use the SVG only.")


def render_png(svg_text, size, target, transparent=True):
    """Draw the SVG at size x size with Chrome (hidden window) and save a PNG."""
    tmp = Path(tempfile.mkdtemp(prefix="ct-icons-"))
    try:
        (tmp / "i.svg").write_text(svg_text, encoding="utf-8")
        (tmp / "p.html").write_text(
            f'<html><body style="margin:0;background:transparent"><img src="i.svg" width="{size}" height="{size}" style="display:block"></body></html>')
        shot = tmp / "shot.png"
        subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size},{size}",
                        f"--user-data-dir={tmp / 'profile'}", "--default-background-color=" + ("00000000" if transparent else "FFFFFFFF"),
                        f"--screenshot={shot}", (tmp / "p.html").as_uri()], check=True, capture_output=True, timeout=60)
        shutil.copy(shot, target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_ico(pngs, target):
    """An .ico file that holds PNG pictures (supported everywhere today)."""
    images = [Path(p).read_bytes() for p in pngs]
    sizes = [16, 32, 48]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for size, data in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    Path(target).write_bytes(head + entries + b"".join(images))


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "favicon.svg").write_text(svg(True), encoding="utf-8")
    render_png(svg(True), 32, OUT / "favicon-32.png")
    render_png(svg(True), 512, OUT / "icon-512.png")
    render_png(svg(False), 180, OUT / "apple-touch-icon.png", transparent=False)   # phones round the corners themselves
    tmp = Path(tempfile.mkdtemp(prefix="ct-ico-"))
    try:
        small = []
        for s in (16, 32, 48):
            render_png(svg(True), s, tmp / f"{s}.png")
            small.append(tmp / f"{s}.png")
        make_ico(small, OUT / "favicon.ico")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("Icons written to", OUT)
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name:22} {f.stat().st_size:>7} bytes")


if __name__ == "__main__":
    main()
