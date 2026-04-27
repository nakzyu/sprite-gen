#!/usr/bin/env python3
"""Pad all <char>_<action>.png files in a sheets dir so frames share a common
cell size.

Default (per-character): every action of one character padded to that
character's max(w) x max(h). Different characters can have different cells.
Use this when each character has its own animation set in your engine.

--global: every sheet across all characters padded to the GLOBAL max(w) x
max(h). Use this when you want a single uniform cell size across the entire
roster (one atlas, simpler import).

Feet stay centered horizontally, character stays bottom-aligned.

Usage:
  normalize_sheets.py [--sheets-dir DIR] [--global] [--cell W H]
"""
import argparse
import re
from pathlib import Path
from PIL import Image
from collections import defaultdict

PAT = re.compile(r"^([^_]+)_([^_]+)\.png$")


def pad_save(p, max_w, max_h, prefix=""):
    img = Image.open(p).convert("RGBA")
    w, h = img.size
    if (w, h) == (max_w, max_h):
        print(f"  {prefix}{p.name}: already {w}x{h}")
        return
    if w <= max_w and h <= max_h:
        canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        pad_x = (max_w - w) // 2
        pad_y = max_h - h
        canvas.paste(img, (pad_x, pad_y), img)
        canvas.save(p)
        print(f"  {prefix}{p.name}: {w}x{h} -> {max_w}x{max_h}")
        return
    # Clip: src overflows target. Keep bottom-aligned, center horizontally.
    canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    sx_off = (w - max_w) // 2 if w > max_w else 0
    sy_off = (h - max_h) if h > max_h else 0
    crop = img.crop((sx_off, sy_off, sx_off + min(w, max_w),
                     sy_off + min(h, max_h)))
    px_off = (max_w - crop.size[0]) // 2
    py_off = max_h - crop.size[1]
    canvas.paste(crop, (px_off, py_off), crop)
    canvas.save(p)
    print(f"  {prefix}{p.name}: {w}x{h} -> {max_w}x{max_h} [CLIPPED]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets-dir", default="./sprites/sheets")
    ap.add_argument("--global", dest="global_norm", action="store_true",
                    help="Pad every sheet to the GLOBAL max cell across all "
                         "characters (uniform roster). Default is per-char.")
    ap.add_argument("--cell", nargs=2, type=int, metavar=("W", "H"),
                    help="Force every sheet to exact W x H. Clips any "
                         "overflow (warns). Implies --global.")
    a = ap.parse_args()
    sheets = Path(a.sheets_dir)

    paths = []
    by_char = defaultdict(list)
    for p in sorted(sheets.glob("*.png")):
        m = PAT.match(p.name)
        if m:
            by_char[m.group(1)].append((m.group(2), p))
            paths.append(p)

    if a.cell:
        max_w, max_h = a.cell
        print(f"\n=== FORCED cell {max_w}x{max_h} (clips overflow) ===")
        for p in paths:
            pad_save(p, max_w, max_h)
        return

    if a.global_norm:
        sizes = [Image.open(p).size for p in paths]
        max_w = max(s[0] for s in sizes)
        max_h = max(s[1] for s in sizes)
        print(f"\n=== GLOBAL -> cell {max_w}x{max_h} ===")
        for p in paths:
            pad_save(p, max_w, max_h)
        return

    for char, actions in by_char.items():
        sizes = [Image.open(p).size for _, p in actions]
        max_w = max(s[0] for s in sizes)
        max_h = max(s[1] for s in sizes)
        print(f"\n=== {char} -> cell {max_w}x{max_h} ===")
        for action, p in actions:
            pad_save(p, max_w, max_h, prefix=f"{action}: ")


if __name__ == "__main__":
    main()
