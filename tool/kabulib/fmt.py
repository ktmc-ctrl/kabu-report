# -*- coding: utf-8 -*-
"""端末表示の小道具。全角を2桁として数える幅計算つき。"""
from __future__ import annotations

import os
import sys
import unicodedata

_NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()

C = {
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m",
}
LEVEL_MARK = {"red": ("✗", "red"), "yellow": ("!", "yellow"), "green": ("✓", "green")}


def c(text: str, color: str) -> str:
    if _NO_COLOR or color not in C:
        return text
    return f"{C[color]}{text}{C['off']}"


def width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s: str, n: int, align: str = "left") -> str:
    gap = max(0, n - width(s))
    if align == "right":
        return " " * gap + s
    if align == "center":
        return " " * (gap // 2) + s + " " * (gap - gap // 2)
    return s + " " * gap


def yen(v: float | None, signed: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v:+,.0f}" if signed else f"{v:,.0f}"


def pct(v: float | None, digits: int = 2, signed: bool = True) -> str:
    if v is None:
        return "—"
    return f"{v*100:+.{digits}f}%" if signed else f"{v*100:.{digits}f}%"


def sign_color(v: float | None) -> str:
    if v is None:
        return "dim"
    return "green" if v > 0 else ("red" if v < 0 else "dim")


def table(headers: list, rows: list, aligns: list | None = None) -> str:
    """罫線なしの等幅テーブル。色コードは幅計算から除くため、装飾前の文字列を渡すこと。"""
    aligns = aligns or ["left"] * len(headers)
    cols = [max(width(str(headers[i])), *(width(str(r[i])) for r in rows)) if rows
            else width(str(headers[i])) for i in range(len(headers))]
    out = ["  ".join(c(pad(str(h), cols[i], aligns[i]), "dim") for i, h in enumerate(headers))]
    out.append(c("─" * (sum(cols) + 2 * (len(cols) - 1)), "dim"))
    for r in rows:
        out.append("  ".join(pad(str(v), cols[i], aligns[i]) for i, v in enumerate(r)))
    return "\n".join(out)


def heading(text: str) -> str:
    return "\n" + c(text, "bold")


def finding_line(f) -> str:
    mark, color = LEVEL_MARK.get(f.level, ("·", "dim"))
    who = f.name or f.code or "—"
    head = f"{c(mark, color)} {c(f'[{f.rule}]', 'dim')} {who}"
    line = f"  {head}  {f.message}"
    if f.fix:
        line += "\n" + " " * 6 + c(f"→ {f.fix}", "dim")
    return line
