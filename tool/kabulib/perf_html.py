# -*- coding: utf-8 -*-
"""private/performance.html を生成する(私的・共有禁止)。

日記が「今どうなっているか」なら、こちらは「どう積み上がってきたか」。
確定損益の累計・日別、口座資産の推移、決済1件ずつの記録。
"""
from __future__ import annotations

import html
from datetime import date

from . import rules
from .charts import bar_chart, line_chart
from .store import Store
from .theme import DIARY_CSS, document


def _yen(v, signed=False):
    if v is None:
        return "—"
    return f"{v:+,.0f}" if signed else f"{v:,.0f}"


def _cls(v):
    if v is None or v == 0:
        return ""
    return "up" if v > 0 else "down"


def build(store: Store, on: str | None = None) -> str:
    on = on or date.today().isoformat()
    closed = sorted([t for t in store.trades if t.get("pl") is not None],
                    key=lambda t: t["date"])
    real = sum(t["pl"] for t in closed)
    unreal = store.unrealized_total()
    wins = [t for t in closed if t["pl"] > 0]
    losses = [t for t in closed if t["pl"] < 0]

    parts = [
        "<h1>損益推移</h1>",
        f'<div class="subtitle">{on} 時点 ・ 記録から自動生成</div>',
        '<div class="private-banner"><b>🔒 私的ファイル — 共有禁止</b><br>'
        'ポジションと損益が入っている。公開するのはリポジトリ直下のレポートの方。</div>',
        f'''<div class="tiles">
  <div class="tile-k"><div class="label">確定損益</div>
    <div class="value {_cls(real)}">¥{_yen(real, True)}</div>
    <div class="note">{len(closed)}回の決済</div></div>
  <div class="tile-k"><div class="label">含み損益</div>
    <div class="value {_cls(unreal)}">¥{_yen(unreal, True)}</div>
    <div class="note">保有{len(store.holdings)}銘柄</div></div>
  <div class="tile-k"><div class="label">通算</div>
    <div class="value {_cls(real + unreal)}">¥{_yen(real + unreal, True)}</div>
    <div class="note">確定 + 含み</div></div>
  <div class="tile-k"><div class="label">勝率</div>
    <div class="value">{len(wins)/len(closed)*100:.0f}%</div>
    <div class="note">{len(wins)}勝 {len(losses)}敗</div></div>
</div>''' if closed else "",
    ]

    if closed:
        by_day: dict[str, float] = {}
        for t in closed:
            by_day[t["date"]] = by_day.get(t["date"], 0) + t["pl"]
        days = sorted(by_day)
        cum, running = [], 0.0
        for d in days:
            running += by_day[d]
            cum.append((d, running))

        parts.append('<div class="card"><h2>📈 確定損益の推移(累計)</h2>'
                     + line_chart(cum) + "</div>")
        parts.append('<div class="card"><h2>📉 日別の確定損益</h2>'
                     + bar_chart([(d, by_day[d]) for d in days]) + "</div>")

        avg_win = sum(t["pl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pl"] for t in losses) / len(losses) if losses else 0
        parts.append(f'''<div class="card"><h2>📐 勝ち負けの形</h2>
  <table>
    <tbody>
      <tr><td>平均利益</td><td class="num up">{_yen(avg_win, True)}</td>
          <td class="note-s">{len(wins)}件</td></tr>
      <tr><td>平均損失</td><td class="num down">{_yen(avg_loss, True)}</td>
          <td class="note-s">{len(losses)}件</td></tr>
      <tr><td>ペイオフレシオ</td>
          <td class="num">{abs(avg_win/avg_loss):.2f} : 1</td>
          <td class="note-s">平均利益 ÷ 平均損失</td></tr>
      <tr><td>最大の勝ち</td><td class="num up">{_yen(max((t["pl"] for t in closed), default=0), True)}</td><td></td></tr>
      <tr><td>最大の負け</td><td class="num down">{_yen(min((t["pl"] for t in closed), default=0), True)}</td><td></td></tr>
    </tbody>
  </table>
  <div class="note-s" style="margin-top:8px">逆指値で降りる運用なので、
  勝率より<b>ペイオフレシオ</b>の方が効く。負けを小さく揃えられているかを見る。</div>
</div>''' if avg_loss else "")

    snaps = store.data["account"]["snapshots"]
    if len(snaps) >= 2:
        # 通算(確定+含み)——0 起点が意味を持つので zero_based のまま
        parts.append(
            '<div class="card"><h2>📈 通算損益の推移(確定 + 含み)</h2>'
            + line_chart([(s["date"], s.get("unrealized", 0) + s.get("realized_cum", 0))
                          for s in snaps], "通算損益")
            + '<div class="note-s" style="margin-top:8px">'
              '確定損益と含み損益を足した、実際に増えた金額。'
              '0 の線からの距離がそのまま成果。</div></div>')
        # 含みだけの推移——日々の値動きがどう効いているか
        parts.append(
            '<div class="card"><h2>📊 含み損益の推移</h2>'
            + line_chart([(s["date"], s.get("unrealized", 0)) for s in snaps], "含み損益")
            + '<div class="note-s" style="margin-top:8px">'
              '保有中の評価損益。⑩で逆指値を上げても、この線自体は動かない——'
              '動くのは「確保できている下限」の方。</div></div>')
        # 口座資産は水準ではなく変化を見たいので 0 起点にしない。
        # 日記から補完したスナップショットは含み益しか分からず equity が無いので外す。
        eq = [(s["date"], s["equity"]) for s in snaps if s.get("equity") is not None]
        parts.append('<div class="card"><h2>💰 口座資産の推移</h2>'
                     + line_chart(eq, "口座資産", zero_based=False)
                     + '<div class="note-s" style="margin-top:8px">'
                       '記録を更新した日だけ点が打たれる。'
                       '毎日つけたいなら大引け後に <code class="tag">kabu price</code> を回す。</div></div>')

    if closed:
        def _cell(v, fmt="{:,.1f}"):
            """日記に数量・単価が残っていない取引がある。推測で埋めず「—」で出す。"""
            return fmt.format(v) if v is not None else "—"

        rows = "".join(
            f'<tr><td>{html.escape(t["date"])}</td><td><b>{html.escape(t["name"])}</b></td>'
            f'<td class="num">{_cell(t.get("qty"), "{:,.0f}")}</td>'
            f'<td class="num">{_cell(t.get("price"))}</td>'
            f'<td class="num {_cls(t["pl"])}">{_yen(t["pl"], True)}</td>'
            f'<td class="note-s">{html.escape(t.get("reason", ""))}</td></tr>'
            for t in reversed(closed))
        parts.append('<div class="card"><h2>🧾 決済の記録</h2><div class="scroll-x"><table>'
                     '<thead><tr><th>日付</th><th>銘柄</th><th class="num">株数</th>'
                     '<th class="num">単価</th><th class="num">損益</th><th>理由</th></tr></thead>'
                     f'<tbody>{rows}</tbody></table></div></div>')

    if store.holdings:
        rows = "".join(
            f'<tr><td><b>{html.escape(h["name"])}</b></td><td class="num">{h["qty"]}</td>'
            f'<td class="num">{h["cost"]:,.1f}</td>'
            f'<td class="num">{rules.current_price(h):,.1f}</td>'
            f'<td class="num {_cls(rules.unrealized(h))}">{_yen(rules.unrealized(h), True)}</td>'
            f'<td class="num {_cls(rules.unrealized(h))}">{rules.gain_pct(h)*100:+.2f}%</td></tr>'
            for h in sorted(store.holdings, key=lambda x: -rules.unrealized(x)))
        parts.append('<div class="card"><h2>📦 含み損益の内訳</h2><table>'
                     '<thead><tr><th>銘柄</th><th class="num">株数</th><th class="num">取得</th>'
                     '<th class="num">現在値</th><th class="num">損益</th><th class="num">率</th>'
                     "</tr></thead>" f"<tbody>{rows}</tbody></table></div>")

    return document("損益推移(私的)", "\n\n".join(p for p in parts if p), DIARY_CSS)
