#!/usr/bin/env python3
"""Builds docs/banner/banner.html: the ASCII header for the README.

Render it to PNG with headless Chrome:
  chrome --headless=new --force-device-scale-factor=2 --window-size=1280,400 \
         --screenshot=docs/banner.png docs/banner/banner.html
"""
import html
import os
import random

random.seed(11)
FONT = {  # 5x7 pixel letters
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}
CW, CH = 3, 2          # characters per font pixel (wide, tall)
W, H = 150, 26          # canvas in characters
DENSE = "@%#&8$"
LIGHT = ".:-=+*"


def letters(text):
    rows = [""] * 7
    for ch in text:
        for i, r in enumerate(FONT[ch]):
            rows[i] += r + "0"
    return rows


grid = [[(" ", None)] * W for _ in range(H)]
for y in range(H):
    for x in range(W):
        if random.random() < 0.035:
            grid[y][x] = (random.choice("..·*+"), "#3a3a40" if random.random() < .7 else "#6b6b73")

bits = letters("AGENT HQ")
bw, bh = len(bits[0]) * CW, 7 * CH
ox, oy = (W - bw) // 2, 5
for py, row in enumerate(bits):
    for px, b in enumerate(row):
        if b != "1":
            continue
        for dy in range(CH):
            for dx in range(CW):
                x, y = ox + px * CW + dx, oy + py * CH + dy
                t = (x - ox) / bw                       # left to right: amber -> coral
                light = 0.55 + 0.45 * (1 - dy / CH) - 0.15 * t + random.uniform(-.1, .1)
                col = ["#8c3f28", "#b85538", "#D97757", "#e8946f", "#f2b48e"][
                    max(0, min(4, int(light * 5)))]
                grid[y][x] = (random.choice(DENSE if light > .55 else LIGHT + DENSE), col)
        # soft shadow one row below each pixel block
        sy = oy + py * CH + CH
        for dx in range(CW):
            x = ox + px * CW + dx + 1
            if sy < H and grid[sy][x][1] in (None, "#3a3a40", "#6b6b73"):
                grid[sy][x] = (random.choice(".:"), "#4a2a20")

# a small task board drawn in box characters under the title
board = [
    "┌─ todo ──────────┐ ┌─ doing ─────────┐ ┌─ review ────────┐ ┌─ done ──────────┐",
    "│ ▢ pricing page  │ │ ▶ client portal │ │ ? android crash │ │ ✓ invoices      │",
    "│ ▢ steam demo    │ │ ▶ rope physics  │ │ ? docs switcher │ │ ✓ pg backups    │",
    "└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘",
]
def colorize(line, i):
    res = ""
    for ch in line:
        col = "#5c5c63"
        if ch == "▶":
            col = "#6E8CFF"
        elif ch == "✓":
            col = "#3CCB7F"
        elif ch == "?":
            col = "#A78BFA"
        elif ch.isalpha():
            col = "#B6B6BB" if i in (1, 2) else "#85858C"
        res += f'<span style="color:{col}">{html.escape(ch)}</span>'
    return res


board_html = "\n".join(colorize(l, i) for i, l in enumerate(board))

out = []
for row in grid:
    line, cur, buf = "", None, ""
    for ch, col in row:
        if col != cur:
            if buf:
                line += f'<span style="color:{cur}">{html.escape(buf)}</span>' if cur else html.escape(buf)
            cur, buf = col, ""
        buf += ch
    if buf:
        line += f'<span style="color:{cur}">{html.escape(buf)}</span>' if cur else html.escape(buf)
    out.append(line)

page = f"""<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;background:#0B0B0C;width:1280px;height:400px;overflow:hidden}}
body{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px}}
pre{{margin:0;padding:0;font:700 14.2px/10px ui-monospace,Menlo,monospace;letter-spacing:-.2px}}
pre.board{{font:500 14px/18px ui-monospace,Menlo,monospace;letter-spacing:0}}
.tag{{color:#85858C;font:500 15px ui-monospace,Menlo,monospace;letter-spacing:.04em}}
</style><pre>{chr(10).join(out)}</pre><pre class="board">{board_html}</pre>
<div class="tag">memory · tasks · dashboard for Claude Code agents</div>"""
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "banner.html"), "w") as f:
    f.write(page)
print("banner.html written")
