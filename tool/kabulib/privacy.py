# -*- coding: utf-8 -*-
"""公開物に私的情報が混ざっていないかを検査する。

2層構造の境目を、規律ではなく検査で守る。
  私的(共有禁止) … private/ の日記・損益。ポジション・取得単価・ルール
  公開(友達と共有) … リポジトリ直下の *.html と data/。決算分析のみ
公開側にポジション情報や内部ルール名が出ていたら、それは事故。
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import config

# 丸数字は公開レポートでも箇条書きの番号として普通に使う。
# 内部ルール番号かどうかは、近くに運用の語があるかで見分ける。
RULE_VOCAB = (
    "ルール|逆指値|損切り|建値|トレール|枠|再エントリー|総リスク|買う前メモ|"
    "ナンピン|ピラミッディング|押し目|底打ち|ラダー|撤退ライン"
)
CONTEXT_WINDOW = 16

# 公開側に出てはいけないもの。これらは決算分析の文章には現れない
LEAK_PATTERNS = [
    (r"コア\s*9(?![.\d%])", "内部の枠の名前(コア9)"),
    (r"(長期枠|スイング枠|触らない枠)", "内部の枠の名前"),
    (r"逆指値", "ポジション運用の用語(逆指値)"),
    (r"(取得単価|平均取得)", "取得価格に関する記述"),
    (r"損切り", "ポジション運用の用語(損切り)"),
    (r"(トレーリング|トレール)", "ポジション運用の用語(トレール)"),
    (r"(口座資産|現金余力)", "口座の状態"),
    (r"(みっちー|俊納みちひろ)", "個人名"),
    (r"kutsunamichihiro", "個人のメールアドレス"),
    (r"買う前メモ", "内部の手順名"),
    (r"総リスク", "内部のリスク管理用語"),
]

# これらは決算分析にも出てくる語なので、自分のポジションの話をしている
# ときだけ拾う。「銅建値2,220円/kg」「含み益に対する税負担」は誤検知にしない。
POSITION_VOCAB = "逆指値|取得単価|保有株|ポジション|建玉|株数|損切り|口座"
CONTEXTUAL_PATTERNS = [
    (r"建値", "取得価格に関する記述"),
    (r"(含み益|含み損)", "ポジションの損益"),
    (r"証券口座", "口座の状態"),
]

# 公開レポートの文体ルール(である調・推奨語を使わない)
STYLE_PATTERNS = [
    (r"(?<![一-龥ぁ-んァ-ヶ])(狙い目|買い時|売り時|仕込み|要注目)", "推奨語。公開レポートでは使わない"),
    (r"(おすすめ|オススメ|推奨銘柄)", "推奨語。公開レポートでは使わない"),
    (r"(だと思う|でしょう|しましょう|ですね)", "である調から外れている"),
]

SKIP_DIRS = {".git", "private", "node_modules", "tool", ".claude"}
# 運用の指示書。公開レポートではなく作業のための文書なので検査の対象外。
# CLAUDE.local.md は .gitignore 済みでそもそも公開されない。
SKIP_FILES = {"CLAUDE.md", "CLAUDE.local.md"}


@dataclass
class Leak:
    path: Path
    line: int
    kind: str          # leak / style / missing
    label: str
    excerpt: str

    @property
    def is_leak(self) -> bool:
        return self.kind in ("leak", "missing")


def scan_text(path: Path, text: str, style: bool = True) -> list:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for pattern, label in LEAK_PATTERNS:
            m = re.search(pattern, line)
            if m:
                out.append(Leak(path, i, "leak", label, _excerpt(line, m)))
        m = _near(line, r"[①-⑳]", RULE_VOCAB)
        if m:
            out.append(Leak(path, i, "leak", "内部ルール番号(丸数字)", _excerpt(line, m)))
        for pattern, label in CONTEXTUAL_PATTERNS:
            m = _near(line, pattern, POSITION_VOCAB)
            if m:
                out.append(Leak(path, i, "leak", label, _excerpt(line, m)))
        if style:
            for pattern, label in STYLE_PATTERNS:
                m = re.search(pattern, line)
                if m:
                    out.append(Leak(path, i, "style", label, _excerpt(line, m)))
    return out


def _near(line: str, pattern: str, vocab: str):
    """pattern の前後に vocab の語があるときだけ一致を返す。

    公開レポートの「①次世代市場 ②炭素繊維」のような箇条書きや、
    「銅建値2,220円/kg」は見逃す。「ルール⑰」「逆指値を建値へ」だけを拾う。
    """
    for m in re.finditer(pattern, line):
        lo = max(0, m.start() - CONTEXT_WINDOW)
        if re.search(vocab, line[lo:m.end() + CONTEXT_WINDOW]):
            return m
    return None


def _excerpt(line: str, m: re.Match, span: int = 34) -> str:
    start = max(0, m.start() - span)
    end = min(len(line), m.end() + span)
    return ("…" if start else "") + line[start:end].strip() + ("…" if end < len(line) else "")


def public_files(root: Path | None = None) -> list:
    root = root or config.PUBLIC
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.name in SKIP_FILES:
            continue
        if p.suffix.lower() in (".html", ".md", ".json", ".txt", ".css", ".js"):
            out.append(p)
    return out


def scan(root: Path | None = None) -> list:
    root = root or config.PUBLIC
    findings = []
    for p in public_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        # 免責は公開レポート(直下の *.html)にだけ要求する
        style = p.suffix.lower() == ".html"
        findings.extend(scan_text(p, text, style=style))
        if style and p.parent == root and p.name != "index.html":
            if config.DISCLAIMER not in text:
                findings.append(Leak(p, 0, "missing", "末尾の免責文が無い", ""))
    findings.extend(tracked_private_files(root))
    return findings


def tracked_private_files(root: Path | None = None) -> list:
    """private/ が誤って git の管理下に入っていないか。ここが最後の砦。"""
    root = root or config.PUBLIC
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", "private"],
            capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in res.stdout.splitlines():
        if line.strip():
            out.append(Leak(root / line.strip(), 0, "leak",
                            "private/ のファイルが git の管理下に入っている", line.strip()))
    return out
