#!/usr/bin/env python3
"""Render a small WaveDrom-like JSON file to a standalone SVG.

GitHub does not render WaveDrom, so the timing diagrams in docs/timing are
kept as JSON sources (*.wave.json) and rendered to SVG with this script.

Supported wave characters (subset of WaveDrom):
  p   clock (one period per character)
  0 1 low / high
  x   unknown
  z   high impedance
  =   data segment; label taken from the "data" list in order
  .   extend previous state
  |   gap marker (drawn as a break on top of the previous state)

Usage:
  python3 tools/wave.py docs/timing/*.wave.json
"""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

CELL = 28        # width of one character
ROW_H = 30       # height of one signal row
SIG_H = 18       # height of the waveform inside a row
NAME_W = 190     # width of the name column
TOP = 34         # space for the title
FONT = "font-family='DejaVu Sans Mono, Menlo, monospace' font-size='12'"


def render(spec: dict) -> str:
    signals = [s for s in spec["signal"] if s]  # skip {} spacers
    n_cols = max(len(s.get("wave", "")) for s in signals)
    width = NAME_W + n_cols * CELL + 20
    height = TOP + len(signals) * ROW_H + 30
    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='white'/>",
    ]
    title = spec.get("title")
    if title:
        out.append(f"<text x='10' y='20' {FONT} font-weight='bold'>{escape(title)}</text>")

    # vertical grid
    for c in range(n_cols + 1):
        x = NAME_W + c * CELL
        out.append(f"<line x1='{x}' y1='{TOP - 6}' x2='{x}' y2='{height - 24}' "
                   "stroke='#eeeeee' stroke-width='1'/>")
        if c < n_cols:
            out.append(f"<text x='{x + CELL / 2}' y='{height - 10}' {FONT} fill='#999' "
                       f"text-anchor='middle'>{c}</text>")

    for row, sig in enumerate(signals):
        y0 = TOP + row * ROW_H
        hi, lo = y0 + 4, y0 + 4 + SIG_H
        mid = (hi + lo) / 2
        out.append(f"<text x='10' y='{mid + 4}' {FONT}>{escape(sig['name'])}</text>")
        wave = sig.get("wave", "")
        data = list(sig.get("data", []))
        state, prev_level = None, None
        seg_start = 0
        segments = []  # (state, start, end, label)
        for i, ch in enumerate(wave):
            if ch == "|":
                segments.append(("gap", i, i + 1, None))
                continue
            if ch == "." and state is not None:
                continue
            if state is not None:
                segments.append((state, seg_start, i, label))
            state, seg_start, label = ch, i, None
            if ch == "=":
                label = data.pop(0) if data else ""
        if state is not None:
            segments.append((state, seg_start, len(wave), label))

        for st, a, b, label in segments:
            xa, xb = NAME_W + a * CELL, NAME_W + b * CELL
            if st == "p":
                for k in range(a, b):
                    x = NAME_W + k * CELL
                    out.append(
                        f"<polyline points='{x},{lo} {x},{hi} {x + CELL / 2},{hi} "
                        f"{x + CELL / 2},{lo} {x + CELL},{lo}' fill='none' stroke='black'/>")
                prev_level = None
            elif st in "01":
                y = hi if st == "1" else lo
                if prev_level is not None and prev_level != y:
                    out.append(f"<line x1='{xa}' y1='{hi}' x2='{xa}' y2='{lo}' stroke='black'/>")
                out.append(f"<line x1='{xa}' y1='{y}' x2='{xb}' y2='{y}' stroke='black' "
                           "stroke-width='1.5'/>")
                prev_level = y
            elif st in "=x":
                fill = "#f2f2f2" if st == "x" else "#e3efff"
                out.append(
                    f"<polygon points='{xa},{mid} {xa + 4},{hi} {xb - 4},{hi} {xb},{mid} "
                    f"{xb - 4},{lo} {xa + 4},{lo}' fill='{fill}' stroke='black'/>")
                if st == "x":
                    out.append(f"<text x='{(xa + xb) / 2}' y='{mid + 4}' {FONT} fill='#888' "
                               "text-anchor='middle'>x</text>")
                elif label:
                    out.append(f"<text x='{(xa + xb) / 2}' y='{mid + 4}' {FONT} "
                               f"text-anchor='middle'>{escape(str(label))}</text>")
                prev_level = None
            elif st == "z":
                out.append(f"<line x1='{xa}' y1='{mid}' x2='{xb}' y2='{mid}' stroke='#3366cc'/>")
                prev_level = None
            elif st == "gap":
                out.append(f"<path d='M{xa + 10},{lo + 3} L{xa + 14},{hi - 3} M{xa + 15},{lo + 3} "
                           f"L{xa + 19},{hi - 3}' stroke='black' fill='none'/>")
    out.append("</svg>")
    return "\n".join(out)


def main(paths):
    for p in map(Path, paths):
        spec = json.loads(p.read_text(encoding="utf-8"))
        target = p.with_name(p.name.replace(".wave.json", ".svg"))
        target.write_text(render(spec), encoding="utf-8")
        print(f"{p} -> {target}")


if __name__ == "__main__":
    main(sys.argv[1:])
