#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""既存の trade_diary.html を private/store.json + private/rulebook.md に取り込む。

一度だけ動かす道具。手書きの HTML が相手なので完璧には読めない——
保有表・口座の数字・ルールブックという**形が決まっている部分**だけを構造化し、
日次カードは本文をそのまま日記に移す。

  python3 tool/migrate.py ~/kabu/trade_diary.html --year 2026

取り込んだあとは `kabu render diary` で HTML を作り直せる。元ファイルは触らない。
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kabulib import config  # noqa: E402
from kabulib.store import Store  # noqa: E402

# 日記の略称 → 公開レポート側の正式名とコード。日記は略して書くので橋渡しが要る
ALIASES = {
    "三菱重": ("7011", "三菱重工業"), "任天堂": ("7974", "任天堂"),
    "東レ": ("3402", "東レ"), "信越化": ("4063", "信越化学工業"),
    "ソフトバンクG": ("9984", "ソフトバンクG"), "住友電工": ("5802", "住友電気工業"),
    "住友電": ("5802", "住友電気工業"), "トヨタ": ("7203", "トヨタ自動車"),
    "三菱UFJ": ("8306", "三菱UFJ FG"), "三井物産": ("8031", "三井物産"),
    "三井物": ("8031", "三井物産"), "三井住友FG": ("8316", "三井住友FG"),
    "ソニーG": ("6758", "ソニーグループ"), "イオン": ("8267", "イオン"),
    "きんでん": ("1944", "きんでん"), "みずほFG": ("8411", "みずほFG"),
    "三菱商事": ("8058", "三菱商事"), "三菱倉庫": ("9301", "三菱倉庫"),
    "NTT": ("9432", "NTT"), "楽天": ("4755", "楽天グループ"),
}
FRAME_OF = {"長期": "long", "スイング": "swing", "触らない枠": "hands_off"}
TAG_RE = re.compile(r"<[^>]+>")


def text_of(fragment: str) -> str:
    return html.unescape(TAG_RE.sub("", fragment)).strip()


def num(s: str) -> float | None:
    m = re.search(r"[-+−]?[\d,]+(?:\.\d+)?", s.replace("−", "-"))
    return float(m.group(0).replace(",", "").replace("−", "-")) if m else None


# ── 保有表 ──────────────────────────────────────────────

def parse_holdings(src: str) -> list:
    """「📊 保有◯銘柄」のカードにある表を読む。列は 銘柄/取得/損益/出口/発動時。"""
    card = re.search(r'<h2>📊\s*保有.*?</table>', src, re.S)
    if not card:
        return []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", card.group(0), re.S)
    out = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        if len(cells) < 5:
            continue
        name_cell = cells[0]
        m = re.search(r"<b>(.*?)</b>\s*([\d,]+)", name_cell, re.S)
        if not m:
            continue
        short = text_of(m.group(1))
        qty = int(m.group(2).replace(",", ""))
        code, name = ALIASES.get(short, ("", short))
        if not code:
            print(f"  ! 「{short}」のコードが分からない。ALIASES に足すか、あとで手で直す。")

        cost = num(text_of(cells[1]))
        pl = num(text_of(cells[2]).split("\n")[0])
        badge = text_of(re.search(r'class="badge[^"]*"[^>]*>(.*?)</span>', name_cell, re.S).group(1)
                        ) if 'class="badge' in name_cell else "長期"
        frame = FRAME_OF.get(badge.strip(), "long")

        exit_cell = cells[3]
        stop = None
        if "逆指値なし" not in text_of(exit_cell):
            b = re.search(r"<b>([\d,]+(?:\.\d+)?)</b>", exit_cell)
            if b:
                stop = float(b.group(1).replace(",", ""))
        # 出口の呼び方は3つだけ。表のセルには距離や注意書きも混ざるので拾い読みしない
        exit_text = text_of(exit_cell)
        kind = next((k for k in ("トレール", "損切り", "撤退") if k in exit_text), "")

        price = cost + pl / qty if (cost is not None and pl is not None and qty) else cost
        h = {
            "code": code or short, "name": name, "qty": qty, "cost": round(cost, 4),
            "frame": frame, "price": round(price, 2), "first_qty": qty, "adds": 0,
            "themes": [], "stop": None,
        }
        if stop is not None:
            h["stop"] = {"price": stop, "kind": kind or "トレール", "placed": "",
                         "expires": None, "alive": True, "exec": "成行"}
        out.append(h)
    return out


# ── 口座の数字 ──────────────────────────────────────────

def parse_account(src: str) -> dict:
    out = {}
    for label, key in (("口座資産", "equity"), ("確定損益", "realized"), ("含み損益", "unrealized")):
        # 値は「¥9,154,447」とも「+¥577,800」とも書かれている(符号が ¥ の前に来る)
        m = re.search(r'<div class="label">' + label + r'[^<]*</div>\s*'
                      r'<div class="value[^"]*">\s*([-+−]?)¥([\d,]+)</div>', src)
        if m:
            out[key] = num(m.group(1) + m.group(2))
    return out


# ── ルールブック ────────────────────────────────────────

def parse_rulebook(src: str) -> str:
    m = re.search(r"<summary>📕\s*ルールブック.*?</summary>(.*?)</details>", src, re.S)
    if not m:
        return ""
    body = m.group(1)
    items = re.findall(r"<li>(.*?)</li>", body, re.S)
    lines = ["# ルールブック", "",
             "trade_diary.html から取り込んだ原本。直すならこのファイルを直す",
             "(`kabu render diary` が読んで日記に描く)。", ""]
    for item in items:
        text = item
        text = re.sub(r"<br\s*/?>", "\n  ", text)
        text = re.sub(r"<hr[^>]*>", "\n  ---\n  ", text)
        text = re.sub(r"</?b>", "**", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"\*\*\s*\*\*", "", text)
        chunks = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not chunks:
            continue
        lines.append(f"- {chunks[0]}")
        lines.extend(f"  {ln}" for ln in chunks[1:])
        lines.append("")
    return "\n".join(lines)


# ── 日次カード ──────────────────────────────────────────

def parse_journal(src: str, year: int) -> list:
    """カードを1件=1記録として移す。日付は見出しから拾い、無ければ空にする。"""
    skip = ("保有", "ルールブック", "確定損益の推移", "日別の確定損益", "今日の記録",
            "日次ログ", "ウォッチリスト", "決算スケジュール")
    # カードは入れ子の <div> を含むので閉じタグでは切れない。
    # 次のカードが始まる位置までを1件とみなす。
    starts = [m.start() for m in re.finditer(r'<div class="card[^"]*"[^>]*>', src)]
    end = src.find("</body>")
    bounds = [(s, starts[i + 1] if i + 1 < len(starts) else end)
              for i, s in enumerate(starts)]
    out = []
    for start, stop in bounds:
        block = src[start:stop]
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        if not h2:
            continue
        title = text_of(h2.group(1))
        if any(s in title for s in skip):
            continue
        body = block[h2.end():].strip()
        d = re.search(r"(\d{1,2})/(\d{1,2})", title) or re.search(r"(\d{1,2})/(\d{1,2})", body[:200])
        date = f"{year}-{int(d.group(1)):02d}-{int(d.group(2)):02d}" if d else ""
        out.append({"date": date, "kind": "imported", "title": title,
                    "body": body, "tags": ["移行"]})
    dated = [e for e in out if e["date"]]
    fallback = max((e["date"] for e in dated), default=f"{year}-01-01")
    for e in out:
        if not e["date"]:
            e["date"] = fallback
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


# ── 実行 ────────────────────────────────────────────────

def _migrate_claude_md(src: Path) -> None:
    """旧 CLAUDE.md を CLAUDE.local.md(非公開)へ移す。

    口座の状態は store.json が正になるので、その節だけ落とす——
    2箇所に数字があると必ずどちらかが古くなる。
    """
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"\n##\s*口座の状態.*?(?=\n##\s|\Z)", "\n", text, flags=re.S)
    out = config.ROOT / "CLAUDE.local.md"
    out.write_text(
        "<!-- 非公開(.gitignore 済み)。口調と運用の指示。\n"
        "     口座の状態は private/store.json が正——`kabu brief` で読む。\n"
        "     公開側の手順は CLAUDE.md の方に書いてある。 -->\n\n"
        + text.strip() + "\n", encoding="utf-8")
    print(f"  → {out}(口座の状態の節は落とした。store.json が正)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("diary", type=Path, help="既存の trade_diary.html")
    ap.add_argument("--year", type=int, default=2026, help="日記の日付に補う年")
    ap.add_argument("--claude-md", type=Path,
                    help="旧ワークスペースの CLAUDE.md。口調と運用の指示を "
                         "CLAUDE.local.md(非公開)へ移す")
    ap.add_argument("--no-journal", action="store_true", help="日次カードは移さない")
    ap.add_argument("--force", action="store_true", help="既存の store.json を上書きする")
    a = ap.parse_args()

    src = a.diary.read_text(encoding="utf-8")
    if config.STORE_FILE.exists() and not a.force:
        sys.exit(f"✗ {config.STORE_FILE} がもうある。上書きするなら --force。")

    store = Store.load()
    store.holdings[:] = parse_holdings(src)
    acct = parse_account(src)
    mv = store.market_value()
    if acct.get("equity"):
        store.cash = acct["equity"] - mv
    store.data["account"]["realized_opening"] = acct.get("realized", 0)

    rulebook = parse_rulebook(src)
    if rulebook:
        config.PRIVATE.mkdir(parents=True, exist_ok=True)
        (config.PRIVATE / "rulebook.md").write_text(rulebook, encoding="utf-8")

    if not a.no_journal:
        store.journal[:] = parse_journal(src, a.year)

    if a.claude_md:
        _migrate_claude_md(a.claude_md)

    store.snapshot()
    store.save()

    print(f"✓ 保有 {len(store.holdings)}銘柄 / 日記 {len(store.journal)}件 を取り込んだ")
    print(f"  口座資産 {store.equity():,.0f}(保有 {mv:,.0f} + 現金 {store.cash:,.0f})")
    print(f"  含み損益 {store.unrealized_total():+,.0f}")
    if acct.get("unrealized") and abs(store.unrealized_total() - acct["unrealized"]) > 100:
        print(f"  ! 日記の含み損益 {acct['unrealized']:+,.0f} と合わない。取得単価か株数を確認して。")
    print(f"  → {config.STORE_FILE}")
    print("  次: kabu morning で引っかかりを見て、kabu render diary で日記を作り直す。")
    print("  ⚠️ 逆指値の期限・執行方法は日記に書かれていないので入っていない。"
          "証券口座を見て `kabu stop` で補う。")


if __name__ == "__main__":
    main()
