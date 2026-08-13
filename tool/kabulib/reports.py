# -*- coding: utf-8 -*-
"""公開レポートのメタデータ(data/reports.json)と、レポートの雛形生成・検査。

旧 build_portal.py では META / FILES / THEMES / SECTOR_ORDER / BUCKET_OF を
手で揃える必要があり、揃っていないと**黙ってタイルが消えた**。ここでは
それを JSON 1本にまとめ、不整合はビルド前に例外で落とす。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

SCHEMA_VERSION = 1

DEFAULT_VERDICTS = {
    "割安圏": "割安", "割安寄り": "割安",
    "中立": "中立",
    "やや割高": "割高", "割高圏": "割高",
    "市況次第": "評価難", "PER非適用": "評価難",
}
DEFAULT_BUCKETS = [
    {"name": "割安", "class": "lo",
     "desc": "予想PER・PBRが過去比/同業比で低位、または資産価値対比のディスカウントが大きい"},
    {"name": "中立", "class": "mid",
     "desc": "指標面に大きな歪みはなく、業績見通しとおおむね整合的な水準"},
    {"name": "割高", "class": "hi",
     "desc": "指標が過去比・同業比で高位。将来の成長期待の織り込みが進んでいる"},
    {"name": "評価難", "class": "mid",
     "desc": "利益が市況変動や黒字化途上にあり、PERによる評価が機能しにくい"},
]


class ReportError(Exception):
    pass


@dataclass
class Library:
    data: dict
    path: Path

    # ── 入出力 ──────────────────────────────────────────
    @classmethod
    def load(cls, path: Path | None = None) -> "Library":
        path = path or config.REPORTS_FILE
        if not path.exists():
            return cls({"version": SCHEMA_VERSION, "title": "📚 銘柄レポート ライブラリ",
                        "sectors": [], "verdicts": dict(DEFAULT_VERDICTS),
                        "buckets": [dict(b) for b in DEFAULT_BUCKETS],
                        "stocks": [], "themes": []}, path)
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
            f.write("\n")

    # ── アクセサ ────────────────────────────────────────
    @property
    def stocks(self) -> list:
        return self.data["stocks"]

    @property
    def themes(self) -> list:
        return self.data["themes"]

    @property
    def sectors(self) -> list:
        return self.data["sectors"]

    @property
    def verdicts(self) -> dict:
        return self.data.get("verdicts") or dict(DEFAULT_VERDICTS)

    @property
    def buckets(self) -> list:
        return self.data.get("buckets") or [dict(b) for b in DEFAULT_BUCKETS]

    def bucket_class(self, verdict: str) -> str:
        """タイルのバッジ色。verdict → バケット → 色 と辿るので、色の付け忘れが起きない。"""
        bucket = self.verdicts.get(verdict)
        for b in self.buckets:
            if b["name"] == bucket:
                return b["class"]
        return "mid"

    def find(self, code: str) -> dict | None:
        for s in self.stocks:
            if s["code"] == code:
                return s
        return None

    def upsert(self, code: str, **fields) -> dict:
        s = self.find(code)
        if s is None:
            s = {"code": code}
            self.stocks.append(s)
        s.update({k: v for k, v in fields.items() if v is not None})
        return s

    # ── 検査 ────────────────────────────────────────────
    def validate(self, public_dir: Path | None = None) -> tuple:
        """旧 build_portal.py で「黙って壊れた」3つを、ビルド前の判定にする。

        (errors, warnings) を返す。errors があるとポータルは生成しない。
        """
        public_dir = public_dir or config.PUBLIC
        errors, warnings = [], []

        for s in self.stocks:
            where = f"{s.get('name', s['code'])}({s['code']})"
            # 落とし穴1: verdict が verdicts 表に無いと、割安・割高別ビューから黙って消える
            if s.get("verdict") not in self.verdicts:
                errors.append(
                    f"{where}: verdict「{s.get('verdict')}」が verdicts に未登録。"
                    f"割安・割高別ビューから黙って消える。登録済み: {'/'.join(self.verdicts)}")
            # 落とし穴3: sectors に無いセクターは描画されない
            if s.get("sector") not in self.sectors:
                errors.append(
                    f"{where}: セクター「{s.get('sector')}」が sectors に未登録。"
                    "セクター別ビューに出ない。")
            f = public_dir / s.get("file", "")
            if not s.get("file") or not f.exists():
                errors.append(f"{where}: レポート本体 {s.get('file')} が無い。")
                continue
            e, w = check_report_file(f, where)
            errors += e
            warnings += w

        for t in self.themes:
            f = public_dir / t.get("file", "")
            if not f.exists():
                errors.append(f"特集 {t.get('title')}: {t.get('file')} が無い。")
            else:
                e, w = check_report_file(f, t.get("title", t.get("file")))
                errors += e
                warnings += w

        seen = set()
        for s in self.stocks:
            if s["code"] in seen:
                errors.append(f"コード {s['code']} が重複している。")
            seen.add(s["code"])
        return errors, warnings


BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.S | re.I)
HEAD_RE = re.compile(r"<head[^>]*>(.*?)</head>", re.S | re.I)
STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)


def css_selectors(css: str) -> set:
    """CSS からセレクタ文字列を取り出す。コメントと at-rule の前置きは落とす。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@[a-zA-Z-]+[^{;]*\{", "{", css)   # @media 等は中身だけ見る
    out = set()
    for chunk in re.findall(r"([^{}]+)\{[^{}]*\}", css):
        for part in chunk.split(","):
            part = re.sub(r"\s+", " ", part).strip()
            if part and not part.startswith(("@", "%")) and not part[0].isdigit():
                out.add(part)
    return out


def _shared_selectors() -> set:
    from .theme import BASE_CSS, PORTAL_CSS
    return css_selectors(BASE_CSS + PORTAL_CSS)


def check_report_file(path: Path, where: str) -> tuple:
    """個別レポート1本の検査。ポータルに取り込んだときに壊れる書き方を見つける。"""
    errors, warnings = [], []
    src = path.read_text(encoding="utf-8")

    body_m = BODY_RE.search(src)
    if not body_m:
        return [f"{where}: <body> が見つからない。ポータルに取り込めない。"], []
    body = body_m.group(1)

    # 落とし穴2: ポータルは <body> の中身しか取り込まない。<head> の <style> は捨てられる。
    # 共通CSSの写しなら捨てられて構わない——問題は**独自の**CSSが <head> にある場合。
    head = HEAD_RE.search(src)
    if head:
        shared = _shared_selectors()
        custom = set()
        for m in STYLE_RE.finditer(head.group(1)):
            custom |= css_selectors(m.group(1)) - shared
        if custom:
            sample = "、".join(sorted(custom)[:6])
            errors.append(
                f"{where}: <head> の <style> に共通CSSに無いセレクタがある({sample})。"
                "ポータルは <body> の中身しか取り込まないので、この指定は捨てられて"
                "レイアウトが崩れる。<style> を <body> の中に移し、"
                "ラッパークラス(.tmap / .chem のような)で名前空間を切る。")

    # <body> 内の <style> — 全レポートが同じ文書に同居するのでスコープが要る
    for m in STYLE_RE.finditer(body):
        bare, wide = set(), set()
        for sel in css_selectors(m.group(1)):
            # ダークモードの :root:where(...) 前置きは付いていて構わない。
            # 効く範囲を決めるのは「独自のクラスが入っているか」の方。
            classes = set(re.findall(r"\.(?!viz-root)[A-Za-z][\w-]*", sel))
            if classes:
                continue
            (wide if ".viz-root" in sel or sel.startswith(("*", ":root")) else bare).add(sel)
        if bare:
            errors.append(
                f"{where}: <body> 内の CSS にスコープの無い要素セレクタがある"
                f"({'、'.join(sorted(bare)[:6])})。ポータルでは全レポートの CSS が"
                "同じ文書に同居するので、他のレポートのカードまで巻き込んで崩れる。")
        if wide:
            warnings.append(
                f"{where}: <body> 内の CSS が .viz-root 直下など広い範囲を指している"
                f"({'、'.join(sorted(wide)[:3])})。クラス名がたまたま衝突しないから"
                "今は動いているだけ。専用のラッパークラスに寄せておく方が安全。")

    if config.DISCLAIMER not in src:
        errors.append(f"{where}: 末尾の免責文が無い。公開レポートには必ず入れる。")
    return errors, warnings


# ── 雛形 ────────────────────────────────────────────────

SECTIONS = [
    ("サマリー", True,
     "枠線付きカードで3〜5行。「何が起きたか」「利益の質」「今どう評価されているか」。"),
    ("最新決算", True,
     "売上・営業(事業)利益・純利益の表(前年同期比つき)+セグメント表。"
     "直後に必ず利益の中身の分解——資産売却益・関税還付・在庫受払差・為替・市況を切り分け、"
     "「増益◯◯億のうち◯◯億は一過性/市況」まで書く。"),
    ("通期見通しと変動要因", False,
     "会社計画・進捗率・上方修正の有無。市場コンセンサスとの差があれば必ず併記。"),
    ("バリュエーション・株価の文脈", True,
     "予想PER・PBR・配当利回り・52週レンジ内の位置(高値からの下落率/安値からの上昇率)・"
     "同業比較。決算翌日の株価反応も。ここの結論がメタの verdict と一致していること。"),
    ("中期経営計画・今後のテーマ", False, "目標値(ROE・利益・還元)と進捗、注力領域。"),
    ("株主還元", False, "配当方針・自社株買い(発行済比・消却の有無)。"),
    ("環境要因", False, "為替前提、金利、関税、原料・市況。"),
    ("リスク要因(注視点)", False, "箇条書き3〜6本。強気材料の裏返しを必ず1本入れる。"),
    ("更新履歴", True, "作成日・出典URL(決算短信/説明資料/株価)・訂正時は何をどう間違えたか。"),
]


def scaffold(code: str, name: str, ticker: str = "", price: str = "—",
             asof: str = "") -> str:
    """公開レポートの器を作る。中身は一次資料を読んでから埋める。

    共通クラス(.card / h2 / table / .num / .up / .down / .warn / .note / .tag)だけで書く。
    独自 CSS が要るときは <body> の中に <style> を置き、必ずラッパークラスで囲う。
    """
    ticker = ticker or code
    cards = [f"""<div class="head">
  <div>
    <h1>{name} <span class="note">[{ticker}]</span></h1>
    <div class="subtitle">決算・バリュエーション・中期経営計画の整理{' ・ ' + asof if asof else ''}</div>
  </div>
  <div class="px"><div class="v">{price}</div><div class="note">円</div></div>
</div>"""]

    for i, (title, required, guide) in enumerate(SECTIONS, 1):
        mark = "" if required else '<span class="tag">任意</span> '
        cards.append(f"""<div class="card">
  <h2>{i}. {title}</h2>
  <div class="body">
    {mark}<!-- TODO: {guide} -->
  </div>
</div>""")

    cards.append(f'<div class="note-s">{config.DISCLAIMER}</div>')
    from .theme import document
    return document(f"{name}({ticker}) レポート", "\n\n".join(cards))
