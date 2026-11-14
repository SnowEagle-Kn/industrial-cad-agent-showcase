# -*- coding: utf-8 -*-
"""Generate the pre-built DEMO media with the Python standard library only.

The output is deterministic: no timestamps, no fonts, no third-party tools.
Run from the repository root:  python tools/build_demo_media.py
"""

import hashlib
import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONCEPT_DIR = os.path.join(ROOT, "examples", "concept_to_manufacturing")
DRAWING_DIR = os.path.join(ROOT, "examples", "drawing_to_deliverable")

BG = (247, 249, 252)
INK = (34, 49, 74)
ACCENT = (36, 110, 190)
SOFT = (120, 140, 168)
WHITE = (255, 255, 255)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


# ------------------------------------------------------------------ SVG
CONCEPT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="900" height="560" viewBox="0 0 900 560" role="img" aria-label="DEMO REPLAY concept preview, not for manufacturing">
  <rect width="900" height="560" fill="#f7f9fc"/>
  <rect x="12" y="12" width="876" height="536" fill="none" stroke="#22314a" stroke-width="2"/>
  <text x="40" y="54" font-family="sans-serif" font-size="26" font-weight="700" fill="#22314a">DEMO / REPLAY - CONCEPT PREVIEW</text>
  <text x="40" y="82" font-family="sans-serif" font-size="15" fill="#5a6a82">Synthetic sensor bracket - illustrative only - NOT FOR MANUFACTURING</text>
  <g stroke="#22314a" stroke-width="3" fill="none">
    <polygon points="250,330 470,250 690,330 470,410" fill="#dce8f7"/>
    <polygon points="250,330 250,290 470,210 470,250" fill="#c3d7ef"/>
    <polygon points="470,250 690,330 690,290 470,210" fill="#aec8e6"/>
  </g>
  <g fill="#246ebe">
    <circle cx="330" cy="330" r="14"/>
    <circle cx="610" cy="330" r="14"/>
  </g>
  <g stroke="#246ebe" stroke-width="3" fill="#f7f9fc">
    <rect x="410" y="276" width="120" height="64" rx="8"/>
  </g>
  <text x="430" y="316" font-family="sans-serif" font-size="16" fill="#22314a">SENSOR</text>
  <g stroke="#5a6a82" stroke-width="1.5" stroke-dasharray="6 5" fill="none">
    <line x1="250" y1="430" x2="690" y2="430"/>
    <line x1="250" y1="424" x2="250" y2="436"/>
    <line x1="690" y1="424" x2="690" y2="436"/>
    <line x1="250" y1="455" x2="470" y2="455"/>
    <line x1="250" y1="449" x2="250" y2="461"/>
    <line x1="470" y1="449" x2="470" y2="461"/>
  </g>
  <text x="430" y="422" font-family="sans-serif" font-size="15" fill="#5a6a82">envelope (demo)</text>
  <text x="330" y="447" font-family="sans-serif" font-size="15" fill="#5a6a82">hole pitch (demo)</text>
  <rect x="0" y="500" width="900" height="60" fill="#22314a"/>
  <text x="40" y="537" font-family="sans-serif" font-size="18" font-weight="700" fill="#ffffff">DEMO / REPLAY - SYNTHETIC FIXTURE - NOT FOR MANUFACTURING</text>
</svg>
"""

DRAWING_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="900" height="560" viewBox="0 0 900 560" role="img" aria-label="DEMO REPLAY drawing deliverable preview, not for manufacturing">
  <rect width="900" height="560" fill="#f7f9fc"/>
  <rect x="12" y="12" width="876" height="536" fill="none" stroke="#22314a" stroke-width="2"/>
  <text x="40" y="54" font-family="sans-serif" font-size="26" font-weight="700" fill="#22314a">DEMO / REPLAY - DELIVERABLE PREVIEW</text>
  <text x="40" y="82" font-family="sans-serif" font-size="15" fill="#5a6a82">Synthetic plate, self-made DXF fixture - illustrative only - NOT FOR MANUFACTURING</text>
  <g stroke="#22314a" stroke-width="3" fill="#eef4fc">
    <rect x="210" y="130" width="480" height="320"/>
  </g>
  <g stroke="#246ebe" stroke-width="3" fill="#f7f9fc">
    <circle cx="250" cy="170" r="18"/>
    <circle cx="650" cy="170" r="18"/>
    <circle cx="250" cy="410" r="18"/>
    <circle cx="650" cy="410" r="18"/>
  </g>
  <g stroke="#5a6a82" stroke-width="1.5" stroke-dasharray="6 5" fill="none">
    <line x1="210" y1="490" x2="690" y2="490"/>
    <line x1="210" y1="484" x2="210" y2="496"/>
    <line x1="690" y1="484" x2="690" y2="496"/>
    <line x1="140" y1="130" x2="140" y2="450"/>
    <line x1="134" y1="130" x2="146" y2="130"/>
    <line x1="134" y1="450" x2="146" y2="450"/>
  </g>
  <text x="410" y="482" font-family="sans-serif" font-size="15" fill="#5a6a82">120 (demo)</text>
  <text x="150" y="296" font-family="sans-serif" font-size="15" fill="#5a6a82">80 (demo)</text>
  <text x="380" y="300" font-family="sans-serif" font-size="16" fill="#22314a">4 x 6 mm through holes (demo)</text>
  <rect x="0" y="500" width="900" height="60" fill="#22314a"/>
  <text x="40" y="537" font-family="sans-serif" font-size="18" font-weight="700" fill="#ffffff">DEMO / REPLAY - SYNTHETIC FIXTURE - NOT FOR MANUFACTURING</text>
</svg>
"""


def write_svg(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content.encode("utf-8"))


# ------------------------------------------------------------------ PNG
FONT = {
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
}
WATERMARK_TEXT = "DEMO / REPLAY"


def _new_canvas(width, height, color):
    return bytearray(bytes(color) * (width * height)), width, height


def _set(pixels, width, x, y, color):
    if x < 0 or y < 0:
        return
    offset = (y * width + x) * 3
    if offset + 3 > len(pixels):
        return
    pixels[offset:offset + 3] = bytes(color)


def fill_rect(pixels, width, x0, y0, x1, y1, color):
    for y in range(y0, y1):
        for x in range(x0, x1):
            _set(pixels, width, x, y, color)


def rect_outline(pixels, width, x0, y0, x1, y1, color, thickness=2):
    for offset in range(thickness):
        for x in range(x0 + offset, x1 - offset):
            _set(pixels, width, x, y0 + offset, color)
            _set(pixels, width, x, y1 - 1 - offset, color)
        for y in range(y0 + offset, y1 - offset):
            _set(pixels, width, x0 + offset, y, color)
            _set(pixels, width, x1 - 1 - offset, y, color)


def circle_outline(pixels, width, cx, cy, radius, color, thickness=2):
    for offset in range(thickness):
        rr = radius - offset
        steps = max(24, rr * 8)
        for step in range(steps):
            angle = 2.0 * math.pi * step / steps
            x = int(round(cx + rr * math.cos(angle)))
            y = int(round(cy + rr * math.sin(angle)))
            _set(pixels, width, x, y, color)


def draw_text(pixels, width, x, y, text, color, scale=4, spacing=1):
    cursor = x
    for char in text:
        glyph = FONT.get(char, FONT[" "])
        for row_index, row in enumerate(glyph):
            for col_index, bit in enumerate(row):
                if bit == "1":
                    fill_rect(pixels, width,
                              cursor + col_index * scale,
                              y + row_index * scale,
                              cursor + (col_index + 1) * scale,
                              y + (row_index + 1) * scale, color)
        cursor += (5 + spacing) * scale


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path, pixels, width, height):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * width * 3:(y + 1) * width * 3])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    text_title = b"Title\x00DEMO REPLAY preview"
    text_comment = (b"Comment\x00DEMO / REPLAY - SYNTHETIC FIXTURE - "
                    b"NOT FOR MANUFACTURING")
    payload = (b"\x89PNG\r\n\x1a\n"
               + _chunk(b"IHDR", ihdr)
               + _chunk(b"tEXt", text_title)
               + _chunk(b"tEXt", text_comment)
               + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
               + _chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)


def concept_png(width=640, height=400):
    pixels, w, _ = _new_canvas(width, height, BG)
    rect_outline(pixels, w, 10, 10, width - 10, height - 10, INK, 2)
    # isometric-ish plate: three offset rectangles
    fill_rect(pixels, w, 150, 110, 490, 260, (220, 232, 247))
    rect_outline(pixels, w, 150, 110, 490, 260, INK, 2)
    fill_rect(pixels, w, 130, 90, 470, 110, (195, 215, 239))
    rect_outline(pixels, w, 130, 90, 470, 110, INK, 2)
    fill_rect(pixels, w, 470, 110, 510, 260, (174, 200, 230))
    rect_outline(pixels, w, 470, 110, 510, 260, INK, 2)
    circle_outline(pixels, w, 200, 190, 12, ACCENT, 3)
    circle_outline(pixels, w, 440, 190, 12, ACCENT, 3)
    fill_rect(pixels, w, 290, 150, 370, 220, (238, 244, 252))
    rect_outline(pixels, w, 290, 150, 370, 220, ACCENT, 2)
    fill_rect(pixels, w, 0, 330, width, 400, INK)
    draw_text(pixels, w, 40, 350, WATERMARK_TEXT, WHITE, 4, 1)
    return pixels, width, height


def drawing_png(width=640, height=400):
    pixels, w, _ = _new_canvas(width, height, BG)
    rect_outline(pixels, w, 10, 10, width - 10, height - 10, INK, 2)
    fill_rect(pixels, w, 110, 70, 530, 280, (238, 244, 252))
    rect_outline(pixels, w, 110, 70, 530, 280, INK, 3)
    for cx, cy in ((150, 110), (490, 110), (150, 240), (490, 240)):
        circle_outline(pixels, w, cx, cy, 16, ACCENT, 3)
    fill_rect(pixels, w, 0, 330, width, 400, INK)
    draw_text(pixels, w, 40, 350, WATERMARK_TEXT, WHITE, 4, 1)
    return pixels, width, height


def main():
    write_svg(os.path.join(CONCEPT_DIR, "concept-preview-2d.svg"), CONCEPT_SVG)
    write_svg(os.path.join(DRAWING_DIR, "deliverable-preview-2d.svg"), DRAWING_SVG)
    pixels, width, height = concept_png()
    write_png(os.path.join(CONCEPT_DIR, "concept-preview-3d.png"), pixels, width, height)
    pixels, width, height = drawing_png()
    write_png(os.path.join(DRAWING_DIR, "deliverable-preview-3d.png"), pixels, width, height)
    for path in (
            os.path.join(CONCEPT_DIR, "concept-preview-2d.svg"),
            os.path.join(CONCEPT_DIR, "concept-preview-3d.png"),
            os.path.join(DRAWING_DIR, "deliverable-preview-2d.svg"),
            os.path.join(DRAWING_DIR, "deliverable-preview-3d.png")):
        print("%s  %s  %d" % (_sha256(path), path, os.path.getsize(path)))


if __name__ == "__main__":
    main()
