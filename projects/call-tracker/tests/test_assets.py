"""Part E: the website icon and favicon files, and that the page uses them."""
import re
import struct
import unittest
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

APP = Path(__file__).parent.parent
ICONS = APP / "icons"


def read_png(path):
    """Minimal PNG reader (8-bit RGBA or RGB): returns (width, height, channels, rows of pixel bytes)."""
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    pos, idat, w = 8, b"", None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8: pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ctype in (2, 6), f"unsupported PNG type {depth}/{ctype}"
        if kind == b"IDAT":
            idat += body
        pos += 12 + n
    ch = 4 if ctype == 6 else 3
    raw, stride, rows, prev = zlib.decompress(idat), w * ch, [], bytearray(w * ch)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    return w, h, ch, rows


def alpha(img, x, y):
    w, h, ch, rows = img
    return rows[y][x * ch + 3] if ch == 4 else 255


class E1Files(unittest.TestCase):
    def test_all_icon_files_exist(self):
        for name in ("favicon.svg", "favicon.ico", "favicon-32.png", "apple-touch-icon.png", "icon-512.png"):
            self.assertTrue((ICONS / name).is_file(), name)

    def test_svg_is_clean(self):
        text = (ICONS / "favicon.svg").read_text(encoding="utf-8")
        root = ET.fromstring(text)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.get("viewBox"), "0 0 64 64")
        self.assertIsNotNone(re.search(r"<title>.+</title>", text), "has a title for screen readers")
        self.assertNotIn("<script", text.lower())
        self.assertNotIn("http://", text.replace("http://www.w3.org/2000/svg", ""), "no outside references")
        self.assertLess(len(text), 4000, "a favicon should be tiny")

    def test_png_sizes(self):
        for name, size in (("favicon-32.png", 32), ("apple-touch-icon.png", 180), ("icon-512.png", 512)):
            w, h, *_ = read_png(ICONS / name)
            self.assertEqual((w, h), (size, size), name)

    def test_rounded_icons_are_transparent_in_the_corners_and_solid_in_the_middle(self):
        for name in ("favicon-32.png", "icon-512.png"):
            img = read_png(ICONS / name)
            w = img[0]
            self.assertEqual(alpha(img, 0, 0), 0, f"{name}: corner is transparent")
            self.assertEqual(alpha(img, w - 1, w - 1), 0)
            self.assertEqual(alpha(img, w // 2, w // 2), 255, f"{name}: centre is solid")

    def test_apple_icon_is_full_square_without_transparency(self):
        img = read_png(ICONS / "apple-touch-icon.png")
        for x, y in ((0, 0), (179, 0), (0, 179), (179, 179), (90, 90)):
            self.assertEqual(alpha(img, x, y), 255)

    def test_ico_has_three_sizes_in_png_format(self):
        data = (ICONS / "favicon.ico").read_bytes()
        reserved, kind, count = struct.unpack("<HHH", data[:6])
        self.assertEqual((reserved, kind, count), (0, 1, 3))
        sizes = []
        for i in range(count):
            w, h, _c, _r, _planes, _bits, length, offset = struct.unpack("<BBBBHHII", data[6 + 16 * i: 22 + 16 * i])
            sizes.append(w or 256)
            self.assertEqual(data[offset: offset + 8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(len(data) >= offset + length, True)
        self.assertEqual(sorted(sizes), [16, 32, 48])


class E2PageUsesThem(unittest.TestCase):
    html = (APP / "index.html").read_text(encoding="utf-8")

    def test_head_links_point_to_real_files(self):
        hrefs = re.findall(r'<link rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', self.html)
        self.assertGreaterEqual(len(hrefs), 4)
        for h in hrefs:
            self.assertTrue((APP / h).is_file(), h)
        self.assertIn('type="image/svg+xml"', self.html)
        self.assertRegex(self.html, r'<meta name="theme-color" content="#[0-9a-fA-F]{6}">')

    def test_header_shows_the_logo(self):
        self.assertRegex(self.html, r'<header>\s*<h1><img class="logo" src="icons/favicon.svg" alt=""')


if __name__ == "__main__":
    unittest.main()
