# -*- coding: utf-8 -*-
"""必要な分だけの Markdown → HTML。ルールブックとメモを素のテキストで持つために使う。

対応: 見出し(##/###)・箇条書き(-/1.)・**太字**・`コード`・水平線・段落・改行。
表やリンク記法は使わない前提。凝った記法が要るなら HTML を直接書く。
"""
from __future__ import annotations

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+?)`")
_MARK = re.compile(r"==(.+?)==")


def inline(text: str) -> str:
    out = html.escape(text)
    out = _CODE.sub(r'<code class="tag">\1</code>', out)
    out = _BOLD.sub(r"<b>\1</b>", out)
    out = _MARK.sub(r'<span class="warn">\1</span>', out)
    return out


def render(src: str) -> str:
    lines = src.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    list_stack: list[str] = []

    def close_lists(depth: int = 0) -> None:
        while len(list_stack) > depth:
            out.append(f"</{list_stack.pop()}>")

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_lists()
            continue
        if line.startswith("---"):
            close_lists()
            out.append('<hr class="sep">')
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            close_lists()
            level = min(len(m.group(1)) + 1, 4)   # # → h2(h1 はページ見出し用に空けておく)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            indent, marker, body = m.group(1), m.group(2), m.group(3)
            depth = len(indent) // 2 + 1
            tag = "ol" if marker[0].isdigit() else "ul"
            if depth > len(list_stack):
                while len(list_stack) < depth:
                    out.append(f"<{tag}>")
                    list_stack.append(tag)
            else:
                close_lists(depth)
                if not list_stack:
                    out.append(f"<{tag}>")
                    list_stack.append(tag)
            out.append(f"<li>{inline(body)}</li>")
            continue
        close_lists()
        out.append(f'<p class="body">{inline(line)}</p>')

    close_lists()
    return "\n".join(out)
