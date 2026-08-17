# -*- coding: utf-8 -*-
"""private/performance.html を生成する(私的・共有禁止)。

日記が「今どうなっているか」なら、こちらは「どう積み上がってきたか」。
確定損益の累計・日別、口座資産の推移、決済1件ずつの記録。
"""
from __future__ import annotations

import html
from datetime import date

from . import perf_stats, rules
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

    # ── ⑩の達成度 ────────────────────────────────────
    # 含み益のうち逆指値でいくら確保できているか。⑩を上げる目的そのもの。
    p = perf_stats.protection(store)
    if p["unrealized"] > 0:
        lw = max(1.5, min(98.0, p["locked"] / p["unrealized"] * 100)) if p["locked"] > 0 else 0.0
        # 帯が細いと数字が入らないので、10%未満のときはラベルを出さない(額は下の文に書く)
        bars = ""
        if lw:
            bars += (f'<div class="locked" style="width:{lw:.1f}%">'
                     + (f'確保 {p["locked"]:,.0f}' if lw >= 10 else "") + "</div>")
        bars += f'<div class="open" style="width:{100-lw:.1f}%">まだ守れていない {p["open"]:,.0f}</div>'

        def _prot_cells(l):
            """発動時の損益と、含み益に対する達成度。

            逆指値が取得単価より下にある銘柄は発動時がマイナス=まだ1円も
            確保できていない。ここを「確保」と呼ぶと嘘になるので言葉を分ける。
            """
            if l["locked"] is None:
                return '<td class="num">—</td><td class="note-s">触らない枠(逆指値なし)</td>'
            cell = f'<td class="num {_cls(l["locked"])}">{_yen(l["locked"], True)}</td>'
            if l["locked"] > 0 and l["unreal"] > 0:
                w = max(0, min(100, l["locked"] / l["unreal"] * 100))
                return cell + (f'<td><div class="hb"><div class="track">'
                               f'<div class="fill" style="width:{w:.0f}%"></div></div>'
                               f'<span class="note-s">{w:.0f}%</span></div></td>')
            return cell + '<td class="note-s">まだ確保ゼロ</td>'

        rows = "".join(
            f'<tr><td>{html.escape(l["name"])}</td>'
            f'<td class="num {_cls(l["unreal"])}">{_yen(l["unreal"], True)}</td>'
            + _prot_cells(l) + "</tr>"
            for l in p["lines"])
        parts.append(f'''<div class="card"><h2>🔒 含み益のうち、確保できている額</h2>
  <div class="legend"><span><i style="background:var(--pos)"></i>逆指値で確保 {_yen(p["locked"], True)}</span>
    <span><i style="background:var(--baseline)"></i>まだ守れていない {_yen(p["open"], True)}</span></div>
  <div class="stack">{bars}</div>
  <div class="note-s">含み益 {_yen(p["unrealized"], True)} のうち <b>{p["pct"]:.1f}%</b>。
  逆指値を引き上げると、この青が右へ伸びる。<br>
  「発動時」は<b>その逆指値で切られたときの損益</b>。マイナスの銘柄は逆指値がまだ取得単価より下にあり、
  1円も確保できていない状態(⑩の第1段)。触らない枠(ソフトバンクG)は逆指値を置かない設計なので対象外。</div>
  <div class="scroll-x" style="margin-top:10px"><table>
    <thead><tr><th>銘柄</th><th class="num">含み益</th><th class="num">発動時</th><th>達成度</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
</div>''')

    # ── 保有期間別 ────────────────────────────────────
    hp = perf_stats.holding_periods()
    if hp:
        best = max(hp["bands"], key=lambda b: b["total"])
        mx = max(abs(b["total"]) for b in hp["bands"]) or 1
        hi = ' class="ok-row"'          # f-string の中に引用符を入れられないので外に出す
        rows = "".join(
            f'<tr{hi if b is best else ""}><td>{html.escape(b["label"])}</td>'
            f'<td class="num">{b["n"]}</td>'
            f'<td class="num note-s">{b["win"]}勝{b["lose"]}敗</td>'
            f'<td class="num {_cls(b["total"])}">{_yen(b["total"], True)}</td>'
            f'<td class="num {_cls(b["avg"])}">{_yen(b["avg"], True)}</td>'
            f'<td><div class="hb"><div class="track"><div class="fill'
            f'{"" if b["total"] >= 0 else " neg"}" '
            f'style="width:{abs(b["total"]) / mx * 100:.0f}%"></div></div></div></td></tr>'
            for b in hp["bands"])
        parts.append(f'''<div class="card"><h2>⏱ 保有期間ごとの成績</h2>
  <div class="scroll-x"><table>
    <thead><tr><th>持った期間</th><th class="num">件数</th><th class="num">勝敗</th>
      <th class="num">合計</th><th class="num">平均</th><th>大きさ</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <div class="note-s" style="margin-top:8px">
    平均保有 <b>{hp["avg_days"]:.1f}日</b> ・ 中央値 <b>{hp["median_days"]:.1f}日</b>
    ({hp["n"]}件の決済、損益は移動平均法・日数はFIFOで算出)。<br>
    いちばん稼いだ帯は <b>{html.escape(best["label"])}</b> で {_yen(best["total"], True)}。
    <b>同日(デイトレ)の成績</b>は、⑩のラダーが翌日以降を前提にしていることと合わせて読む。
    出典は <code class="tag">{html.escape(hp["source"])}</code>(証券口座の約定履歴)。
  </div>
</div>''')

    # ── 銘柄別 ────────────────────────────────────────
    sym = perf_stats.by_symbol(store)
    if sym:
        mx = max(abs(a["pl"]) for a in sym) or 1
        rows = "".join(
            f'<tr><td><b>{html.escape(a["name"])}</b> <span class="note-s">{a["code"]}</span></td>'
            f'<td class="num note-s">{a["n"]}回 {a["win"]}勝</td>'
            f'<td class="num {_cls(a["pl"])}">{_yen(a["pl"], True)}</td>'
            f'<td><div class="hb"><div class="track"><div class="fill'
            f'{"" if a["pl"] >= 0 else " neg"}" '
            f'style="width:{abs(a["pl"]) / mx * 100:.0f}%"></div></div></div></td></tr>'
            for a in sym)
        parts.append(f'''<div class="card"><h2>🏷 銘柄ごとの確定損益</h2>
  <div class="scroll-x"><table>
    <thead><tr><th>銘柄</th><th class="num">決済</th><th class="num">損益</th><th>大きさ</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <div class="note-s" style="margin-top:8px">決済済みのみ。いま保有している分は含まない。</div>
</div>''')

    # ── 月別 ──────────────────────────────────────────
    mon = perf_stats.monthly(store)
    if len(mon) >= 2:
        parts.append('<div class="card"><h2>📅 月ごとの確定損益</h2>'
                     + bar_chart([(m, v) for m, v, _ in mon], "月別")
                     + '<div class="note-s" style="margin-top:8px">'
                     + " ・ ".join(f'{m}: {_yen(v, True)}({n}件)' for m, v, n in mon)
                     + "</div></div>")

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
