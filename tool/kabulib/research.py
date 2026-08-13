# -*- coding: utf-8 -*-
"""調べるときの手順を、毎回同じ形で出す。

過去の事故から作られた手順なので、順番と「やらないこと」に意味がある。
・楽天: ニュース要約の「営業利益331億」を写して書いたが、原本は営業"損失"331億だった
・楽天: 急落を「急騰の反動」と書いたが、主因はコンセンサス比28.8%未達だった
・IHI: ヘッドラインの「+250%増益」の中身は、営業利益732億のうち400億が不動産売却益だった
"""
from __future__ import annotations

from dataclasses import dataclass

from .fmt import c, heading, pct, table

# ── 銘柄を調べるときの標準プロトコル ────────────────────

STEPS = [
    ("① 一次資料を読む",
     ["決算短信(PDF原本。ニュースの要約で代用しない)",
      "決算説明資料 — 質疑応答要旨があれば必ず読む",
      "セグメント別の内訳(どこが稼いだか)"],
     "会社が言っていないことは書かない。数字は原本から取る。"),
    ("② 期待側を取りに行く",
     ["市場コンセンサス(会社計画との差)",
      "決算翌日の株価反応(%と出来高)",
      "アナリストの目標株価レンジ"],
     "会社資料は「実績」しか教えない。売られた理由が中身なのか期待なのかは、"
     "コンセンサスと突き合わせないと分からない。"),
    ("③ 利益の中身を分解する",
     ["一過性(資産売却益・保険金・訴訟和解金・関税還付)",
      "市況・為替(在庫受払差・銅価・メタノール市況)",
      "受注高(重工・機械の場合)",
      "営業キャッシュ・フロー(利益についてきているか)"],
     "「増益◯◯億のうち◯◯億は一過性/市況」まで書けて初めて分解したことになる。"
     "`kabu decompose` を使う。"),
    ("④ 株価指標",
     ["予想PER・PBR・配当利回り",
      "52週レンジ内の位置(高値からの下落率・安値からの上昇率)",
      "同業比較"],
     "出典は株探(s.kabutan.jp)か松井(finance.matsui.co.jp)。"),
    ("⑤ 中期経営計画",
     ["目標値(ROE・利益・還元)と進捗", "注力領域", "未達なら差分の大きさ"], ""),
    ("⑥ ニュース",
     ["日経・Bloomberg・ロイター・株探",
      "同業・海外同業の動き(連鎖しているか)",
      "マクロ(為替・金利・政策)",
      "スカットルバット(OpenWork等の中の人の声)"],
     ""),
]

RULES = [
    "ニュースサイトの要約だけで書かない。会社の一次資料を読む。",
    "会社発表と市場コンセンサスを必ず突き合わせる。",
    "増益率は中身を分解する。一過性と実質を分ける。受注高と営業CFも見る。",
    "数値が取れなければ「取得不可」と明記する。推測で埋めない。",
    "訂正したら、レポートの更新履歴に「何をどう間違えたか」を残す。",
]

# ⑱ 保有が切られたときのニューススイープ(4方向)
SWEEP = [
    ("1. 報道", "日経・Bloomberg・ロイター・株探。会社が言わないこと"
                "(リストラ観測・当局調査・格下げ・空売りレポート)はここに出る"),
    ("2. セクター/競合", "同業の決算・海外同業の動き。"
                        "レーザーテック→信越、KOSPI→AI半導体、古河→電線の連鎖は全部これだった"),
    ("3. マクロ", "為替・金利・政策。銘柄のせいじゃない下げか、を切り分ける"),
    ("4. スカットルバット", "OpenWork等の中の人の声。thesisの生死は現場が先に知る"),
]


def checklist(name: str, code: str = "") -> str:
    label = f"{name}({code})" if code else name
    out = [heading(f"🔎 {label} を調べる — 標準プロトコル")]
    for title, items, note in STEPS:
        out.append(c(f"\n  {title}", "bold"))
        out.extend(f"    □ {i}" for i in items)
        if note:
            out.append(c(f"    {note}", "dim"))
    out.append(c("\n  絶対ルール(過去の失敗から)", "bold"))
    out.extend(f"    {i}. {r}" for i, r in enumerate(RULES, 1))
    out.append(c("\n  集め終わったら `kabu report new` で公開レポートの器を作る。", "dim"))
    return "\n".join(out)


def sweep(name: str) -> str:
    """⑱ 逆指値が発動したとき、「相場のせい/銘柄のせい/話が別」の3択に落とすための手順。"""
    out = [heading(f"📰 {name} — ニューススイープ(4方向)")]
    for title, note in SWEEP:
        out.append(c(f"\n  {title}", "bold"))
        out.append(f"    {note}")
    out.append(c("\n  結論はこの3択で出す:", "bold"))
    out.append("    A. 相場のせい     → thesis は生きている。再エントリーの検証へ")
    out.append("    B. 銘柄のせい     → なぜを特定する。決算が理由なら初日に飛びつかない")
    out.append("    C. 話が別になった → 再エントリー禁止。thesis は死んだ")
    out.append(c("\n  会社公表は会社に都合のいい情報しか載らない。外から突き合わせるのがこの手順。", "dim"))
    return "\n".join(out)


# ── ⑰ 増益の分解 ───────────────────────────────────────

@dataclass
class Component:
    label: str
    amount: float
    kind: str      # oneoff(一過性) / market(市況・為替) / real(実質)


ONEOFF_HINTS = ["売却益", "保険金", "和解", "還付", "特別利益", "譲渡益", "受取"]
MARKET_HINTS = ["市況", "為替", "在庫", "銅価", "価格", "ナフサ", "メタノール", "円安"]


def classify(label: str) -> str:
    if any(h in label for h in ONEOFF_HINTS):
        return "oneoff"
    if any(h in label for h in MARKET_HINTS):
        return "market"
    return "real"


def decompose(total_delta: float, components: list, unit: str = "億円",
              prior: float | None = None) -> str:
    """増益額のうち、いくらが一過性・市況で、いくらが実質か。

    components は (ラベル, 金額) の並び。金額は増益への寄与(マイナスも可)。
    残余は実質として扱う——分解できなかった分を実質に寄せる方が、
    実質を過大評価しにくい。
    """
    comps = [Component(label, amount, classify(label)) for label, amount in components]
    explained = sum(cp.amount for cp in comps)
    residual = total_delta - explained

    rows = []
    for cp in comps:
        share = cp.amount / total_delta if total_delta else 0
        kind = {"oneoff": "一過性", "market": "市況・為替", "real": "実質"}[cp.kind]
        rows.append((cp.label, kind, f"{cp.amount:+,.1f}", f"{share*100:+.1f}%"))
    if abs(residual) > 1e-9:
        rows.append(("その他(残余)", "実質", f"{residual:+,.1f}",
                     f"{residual/total_delta*100:+.1f}%" if total_delta else "—"))

    oneoff = sum(cp.amount for cp in comps if cp.kind == "oneoff")
    market = sum(cp.amount for cp in comps if cp.kind == "market")
    real = total_delta - oneoff - market

    out = [heading(f"⑰ 増益 {total_delta:+,.1f}{unit} の分解")]
    out.append(table(["要因", "分類", f"金額({unit})", "増益に占める割合"], rows,
                     ["left", "left", "right", "right"]))
    out.append("")
    out.append(f"  一過性     {oneoff:+,.1f}{unit}"
               f"({oneoff/total_delta*100:+.1f}%)" if total_delta else "")
    out.append(f"  市況・為替 {market:+,.1f}{unit}"
               f"({market/total_delta*100:+.1f}%)" if total_delta else "")
    out.append(c(f"  実質       {real:+,.1f}{unit}"
                 f"({real/total_delta*100:+.1f}%)" if total_delta else "",
                 "green" if real > 0 else "red"))
    if prior:
        out.append("")
        out.append(f"  見かけの増益率 {total_delta/prior*100:+.1f}%"
                   f"  →  実質の増益率 {real/prior*100:+.1f}%"
                   f"(前年同期 {prior:,.1f}{unit})")
    out.append("")
    out.append(c("  レポートには「増益◯◯のうち◯◯は一過性/市況」の形で書く。", "dim"))
    out.append(c("  受注高と営業キャッシュ・フローも併せて見る——利益は出ていても現金が出ていく形がある。", "dim"))
    return "\n".join(x for x in out if x is not None)
