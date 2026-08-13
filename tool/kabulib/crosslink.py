# -*- coding: utf-8 -*-
"""レポート本文の銘柄名を、その銘柄の個別ページへの自動リンクにする。

`kabu portal` のビルド時に全公開レポートへ適用する。設計方針:

- **冪等**: 既に <a>...</a> の中にあるテキストは触らない。何度ビルドしても同じ結果
- **誤リンクを出さないことを優先**: カタカナ語の途中(「リチウムイオン」の「イオン」)や
  英字の連続(「NTTデータ」の「NTT」)にはリンクしない。裸の4桁数字は年号と
  紛れるので、[6508] のような角括弧つき、または銘柄名の直後の (6508) だけをリンクする
- 自分自身のページへは張らない
"""
from __future__ import annotations

import html
import re
from pathlib import Path

# 本文中の表記ゆれ → 銘柄コード。reports.json の正式名は自動で対象になるので、
# ここには略称・別表記だけを足す。
ALIASES = {
    "三菱重工": "7011",
    "トヨタ": "7203",
    "ソニーG": "6758",
    "スクエニ": "9684",
    "スクウェア・エニックス": "9684",
    "信越化学": "4063",
    "住友電工": "5802",
    "古河電工": "5801",
    "三井金属": "5706",
    "キオクシア": "285A",
    "SBG": "9984",
    "ソフトバンクグループ": "9984",
    "三菱UFJ": "8306",
    "三菱UFJフィナンシャル・グループ": "8306",
    "楽天G": "4755",
    "みずほ銀行": "8411",
    "フェローテックHD": "6890",
    "フェローテックホールディングス": "6890",
    "東京応化工業": "4186",
    "レゾナック・ホールディングス": "4004",
}

_KATA = "ァ-ヶーA-Za-z0-9"
_TOKEN = "\x00{}\x00"

# リンクを張らない領域(中身ごと読み飛ばす)
_SKIP_RE = re.compile(r"<a\b.*?</a>|<(title|style|script)\b.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def _surface_pattern(surface: str) -> re.Pattern:
    """表記1つぶんの正規表現。カタカナ・英数の途中にはマッチさせない。"""
    esc = re.escape(surface)
    pre = f"(?<![{_KATA}])" if re.match(f"[{_KATA}]", surface) else ""
    post = f"(?![{_KATA}])" if re.search(f"[{_KATA}]$", surface) else ""
    # 「明電舎[6508]」「明電舎 (6508)」のようにコードが続く場合は丸ごと1リンクにする
    return re.compile(f"{pre}{esc}(?:\\s*[\\[(][0-9A-Z]{{4,5}}[)\\]])?{post}")


def targets_of(lib_data: dict) -> list[tuple[str, str, str]]:
    """(表記, コード, ファイル) のリスト。長い表記から先にマッチさせる。"""
    files = {s["code"]: s["file"] for s in lib_data["stocks"]}
    out = []
    for s in lib_data["stocks"]:
        out.append((s["name"], s["code"], s["file"]))
    for surface, code in ALIASES.items():
        if code in files:
            out.append((surface, code, files[code]))
    # 銘柄名は長い表記から先に。裸コード [6508] は名前より**後**に処理する
    # (先に置換すると「明電舎[6508]」が2つのリンクに分断される)
    out.sort(key=lambda t: len(t[0]), reverse=True)
    out += [(f"[{code}]", code, f) for code, f in files.items()]
    return out


def linkify(src: str, targets: list[tuple[str, str, str]], self_code: str) -> str:
    """1ファイルぶんの HTML に相互リンクを張る。"""
    # 1) スキップ領域を退避
    saved: list[str] = []

    def _save(m: re.Match) -> str:
        saved.append(m.group(0))
        return _TOKEN.format(f"S{len(saved) - 1}")

    work = _SKIP_RE.sub(_save, src)

    # 2) タグも退避(属性値の中の銘柄名を触らないため)
    def _save_tag(m: re.Match) -> str:
        saved.append(m.group(0))
        return _TOKEN.format(f"S{len(saved) - 1}")

    work = _TAG_RE.sub(_save_tag, work)

    # 3) テキストだけになったところで、長い表記から順に置換
    links: list[str] = []
    for surface, code, file in targets:
        if code == self_code:
            continue

        def _link(m: re.Match, _file=file) -> str:
            links.append(f'<a class="xref" href="{html.escape(_file)}">{m.group(0)}</a>')
            return _TOKEN.format(f"L{len(links) - 1}")

        work = _surface_pattern(surface).sub(_link, work)

    # 4) 復元(リンク→スキップ領域の順)
    for i, l in enumerate(links):
        work = work.replace(_TOKEN.format(f"L{i}"), l)
    for i, s in enumerate(saved):
        work = work.replace(_TOKEN.format(f"S{i}"), s)
    return work


def apply_all(lib_data: dict, public_dir: Path) -> int:
    """全公開レポート(銘柄+特集)に相互リンクを張る。書き換えたファイル数を返す。"""
    targets = targets_of(lib_data)
    changed = 0
    pages = [(s["file"], s["code"]) for s in lib_data["stocks"]]
    pages += [(t["file"], "") for t in lib_data["themes"]]
    for file, self_code in pages:
        p = public_dir / file
        src = p.read_text(encoding="utf-8")
        out = linkify(src, targets, self_code)
        if out != src:
            p.write_text(out, encoding="utf-8")
            changed += 1
    return changed
