# -*- coding: utf-8 -*-
"""private/trade_diary.html を JSON から生成する(私的・共有禁止)。

手で HTML を書き換えていた頃は、保有表の「出口」欄が空白のまま放置される
事故が起きた。ここでは保有・逆指値・総リスクは**必ず記録から描かれる**ので、
書き忘れという失敗の形が無くなる。
"""
from __future__ import annotations

import html
import re
from datetime import date

from . import config, rules
from .charts import bar_chart, line_chart
from .md import render as md_render
from .store import Store
from .theme import DIARY_CSS, document, private_nav

LEVEL_CLASS = {"red": "red", "yellow": "yellow", "green": "green"}
LEVEL_LABEL = {"red": "直す", "yellow": "見る", "green": "OK"}


def _yen(v, signed=False):
    if v is None:
        return "—"
    return f"{v:+,.0f}" if signed else f"{v:,.0f}"


def _cls(v):
    if v is None or v == 0:
        return ""
    return "up" if v > 0 else "down"


def build(store: Store, rulebook: str = "", on: str | None = None) -> str:
    on = on or date.today().isoformat()
    eq = store.equity()
    unreal = store.unrealized_total()
    real = store.realized_total()
    cost = sum(h["qty"] * h["cost"] for h in store.holdings)
    risk = rules.total_risk(store)
    findings = rules.morning_check(store, on)

    parts = [
        '<h1>トレード日記</h1>',
        f'<div class="subtitle">{on} 時点 ・ 記録から自動生成'
        '<br><span style="font-size:0.72rem">※数字はすべて「この口座」のもの。積立や銀行口座は別にある</span></div>',
        '<div class="private-banner"><b>🔒 私的ファイル — 共有禁止</b><br>'
        'ポジション・取得単価・逆指値・運用ルールが入っている。'
        'このファイルは <code class="tag">private/</code> にあり git の管理下にない。'
        '友達に見せるのは公開レポート(リポジトリ直下の *.html)の方。</div>',
    ]

    # ── 数字タイル ──────────────────────────────────────
    parts.append(f'''<div class="tiles">
  <div class="tile-k">
    <div class="label">口座資産</div>
    <div class="value">¥{_yen(eq)}</div>
    <div class="note">保有 {_yen(store.market_value())} + 現金 {_yen(store.cash)}</div>
  </div>
  <div class="tile-k">
    <div class="label">確定損益</div>
    <div class="value {_cls(real)}">¥{_yen(real, True)}</div>
    <div class="note">{len([t for t in store.trades if t.get("pl") is not None])}回の決済</div>
  </div>
  <div class="tile-k">
    <div class="label">含み損益</div>
    <div class="value {_cls(unreal)}">¥{_yen(unreal, True)}</div>
    <div class="note">{f"{unreal/cost*100:+.2f}%" if cost else "—"}</div>
  </div>
  <div class="tile-k">
    <div class="label">通算(確定+含み)</div>
    <div class="value {_cls(real + unreal)}">¥{_yen(real + unreal, True)}</div>
    <div class="note">確定 + 含み</div>
  </div>
</div>''')

    # ── 朝のチェック ────────────────────────────────────
    reds = [f for f in findings if f.level == "red"]
    yellows = [f for f in findings if f.level == "yellow"]
    card_class = "card task" if reds else "card"
    rows = []
    for f in reds + yellows:
        rows.append(
            f'<tr><td><span class="flag {LEVEL_CLASS[f.level]}">{LEVEL_LABEL[f.level]}</span></td>'
            f'<td>{html.escape(f.rule)}</td><td><b>{html.escape(f.name or "—")}</b></td>'
            f'<td>{html.escape(f.message)}'
            + (f'<br><span class="note-s">→ {html.escape(f.fix)}</span>' if f.fix else "")
            + "</td></tr>")
    if rows:
        parts.append(f'''<div class="{card_class}">
  <h2>☀️ 朝のチェック — 今すぐ直す {len(reds)}件 / 見ておく {len(yellows)}件</h2>
  <table><tbody>
{chr(10).join(rows)}
  </tbody></table>
  <div class="note-s" style="margin-top:8px">逆指値の毎朝チェックが1日の最初のタスク。
  <b>証券口座の「(注文中)」を実際に目で見て突き合わせること。</b>ここに出るのは記録の方で、実物ではない。</div>
</div>''')
    else:
        parts.append('<div class="card"><h2>☀️ 朝のチェック</h2>'
                     '<div class="body"><span class="up"><b>✓ 引っかかっているルールはゼロ。</b></span>'
                     'それでも証券口座の「(注文中)」は目で見て確認する。</div></div>')

    # ── 保有表 ──────────────────────────────────────────
    parts.append(_holdings_card(store, risk))

    # ── ⑩ 先に計算しておく段 ────────────────────────────
    parts.append(_ladder_card(store))

    # ── 損益チャート ────────────────────────────────────
    parts.append(_performance_card(store))

    # ── 日次ログ ────────────────────────────────────────
    parts.append(_journal_card(store))

    # ── 買う前メモ ──────────────────────────────────────
    open_memos = [m for m in store.prememos if not m.get("used")]
    if open_memos:
        items = []
        for m in reversed(open_memos):
            fields = "<br>".join(
                f"<b>{label}</b>: {html.escape(str(m.get(key, '')))}"
                for key, label in [("thesis", "thesis"), ("exit", "出口"), ("risk", "リスク"),
                                   ("accepted", "承知点"), ("invalidation", "話が別になる条件")])
            items.append(f'<div style="margin-bottom:10px"><b>{html.escape(m["name"])} '
                         f'@{m["price"]:,.1f}</b> <span class="note-s">{m["date"]}</span>'
                         f'<div class="body">{fields}</div></div>')
        parts.append('<div class="card"><h2>📝 未使用の買う前メモ</h2>'
                     + "".join(items)
                     + '<div class="note-s">有効期限は「株価が5%動くか3営業日」。'
                       '古いメモで買うのは、メモなしより危ない。</div></div>')

    # ── ウォッチリスト / 決算 ───────────────────────────
    if store.watchlist:
        rows = "".join(
            f'<tr><td><b>{html.escape(w.get("name", w.get("code", "")))}</b></td>'
            f'<td>{html.escape(w.get("trigger", ""))}</td>'
            f'<td>{html.escape(w.get("note", ""))}</td></tr>' for w in store.watchlist)
        parts.append('<div class="card"><h2>👀 ウォッチリスト</h2><table>'
                     '<thead><tr><th>銘柄</th><th>条件</th><th>メモ</th></tr></thead>'
                     f'<tbody>{rows}</tbody></table></div>')
    if store.earnings:
        rows = "".join(
            f'<tr><td><b>{html.escape(e.get("date", ""))}</b></td>'
            f'<td>{html.escape(e.get("name", ""))}</td>'
            f'<td>{html.escape(e.get("note", ""))}</td></tr>'
            for e in sorted(store.earnings, key=lambda x: x.get("date", "")))
        parts.append('<div class="card"><h2>📅 決算スケジュール</h2><table>'
                     '<thead><tr><th>日付</th><th>銘柄</th><th>立ち回り</th></tr></thead>'
                     f'<tbody>{rows}</tbody></table>'
                     '<div class="note-s" style="margin-top:8px">'
                     '<b>決算ギャップは逆指値で防げない。</b>−15%で寄り付けば、−5%の逆指値は'
                     '寄り付き価格で約定する。防ぐ方法は「持たない」か「量を減らす」だけ。</div></div>')

    # ── ルールブック ────────────────────────────────────
    if rulebook:
        parts.append('<div class="card"><details><summary>📕 ルールブック</summary>'
                     f'<div class="body">{md_render(rulebook)}</div></details>'
                     '<div class="note-s" style="margin-top:6px">原本は '
                     '<code class="tag">private/rulebook.md</code>。'
                     'ここはそれを描いているだけなので、直すなら向こうを直す。</div></div>')

    body = private_nav("trade_diary.html") + "\n\n" + "\n\n".join(parts)
    return document("トレード日記(私的)", body, DIARY_CSS)


def _holdings_card(store: Store, risk) -> str:
    if not store.holdings:
        return '<div class="card"><h2>📊 保有</h2><div class="body">保有なし。</div></div>'

    rows = []
    for lad in sorted(rules.ladder_table(store), key=lambda x: -x.gain):
        h = store.must_find(lad.code)
        pl = rules.unrealized(h)
        frame = h.get("frame", "long")
        row_class = ""
        if frame == "hands_off":
            row_class = ' class="pink-row"'
        elif lad.locked is not None and lad.locked > 0:
            row_class = ' class="ok-row"'
        badge = {"long": '<span class="badge ok">長期</span>',
                 "swing": '<span class="badge">スイング</span>',
                 "hands_off": '<span class="badge" style="color:var(--accent-pink);'
                              'border-color:var(--accent-pink)">触らない枠</span>'}[frame]

        if lad.recommended is None:
            exit_cell = "<b>逆指値なし</b><br><span class='note-s'>論理で撤退</span>"
            locked_cell = "—"
        else:
            kind = (h.get("stop") or {}).get("kind", "")
            exit_cell = f"{kind}<b>{lad.current_stop:,.0f}</b>" if lad.current_stop else "<b>未設定</b>"
            if lad.should_raise:
                exit_cell += (f'<br><span class="warn" style="font-size:0.64rem">'
                              f'<b>→{lad.recommended:,.0f}へ</b></span>')
            elif lad.distance is not None:
                note = "(バンド下限)" if lad.band == "tight" else ("(深すぎ)" if lad.band == "wide" else "")
                exit_cell += (f'<br><span class="note-s">距離{lad.distance*100:.1f}%'
                              f'{note}</span>')
            locked_cell = (f'<span class="{_cls(lad.locked)}">{_yen(lad.locked, True)}</span>')
            if lad.locked is not None and lad.locked > 0:
                locked_cell = f"確保<br><b class='up'>{_yen(lad.locked, True)}</b>"
                if lad.should_raise:
                    locked_cell += f"<br><span class='note-s'>→{_yen(lad.locked_after, True)}</span>"

        rows.append(
            f'<tr{row_class}><td><b>{html.escape(h["name"])}</b> {h["qty"]}<br>{badge}</td>'
            f'<td class="num">{h["cost"]:,.1f}</td>'
            f'<td class="num">{lad.price:,.1f}</td>'
            f'<td class="num {_cls(pl)}">{_yen(pl, True)}<br><b>{lad.gain*100:+.2f}%</b></td>'
            f'<td>{exit_cell}</td><td class="num">{locked_cell}</td></tr>')

    risk_line = " / ".join(
        f'{html.escape(l.name)}<span class="{_cls(l.pl)}">{_yen(l.pl, True)}</span>'
        for l in risk.lines if l.pl is not None)
    extra = []
    if risk.excluded:
        extra.append("<b>⚠️ " + "・".join(html.escape(h["name"]) for h in risk.excluded)
                     + " は意図的に逆指値なし(触らない枠)。</b>上のリスク計算には含めていない。")
    if risk.uncovered:
        extra.append('<span class="down"><b>✗ '
                     + "・".join(html.escape(h["name"]) for h in risk.uncovered)
                     + " は逆指値が無い。出口ゼロ。</b></span>")
    themes = [f for f in rules.theme_check(store) if f.level in ("red", "yellow")]
    for f in themes:
        extra.append(f'<span class="warn"><b>⚠️ {html.escape(f.message)}</b></span>')

    return f'''<div class="card">
  <h2>📊 保有{len(store.holdings)}銘柄</h2>
  <div class="scroll-x"><table>
    <thead><tr><th>銘柄</th><th class="num">取得</th><th class="num">現在値</th>
    <th class="num">損益</th><th>出口</th><th class="num">発動時</th></tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table></div>
  <div class="note-s" style="margin-top:8px"><b>📊 総リスク(全部外れたらいくら失うか):</b><br>
  {risk_line}<br>= <b class="{_cls(risk.total)}">{_yen(risk.total, True)}</b>
  (口座資産の{risk.pct*100:.2f}%)。上限6%({_yen(risk.cap)})まで{_yen(risk.headroom)}の余地。
  {"<br><br>" + "<br><br>".join(extra) if extra else ""}</div>
</div>'''


def _ladder_card(store: Store) -> str:
    blocks = []
    for h in store.holdings:
        if not rules.needs_stop(h):
            continue
        lad = rules.ladder_for(h)
        rows = []
        for label, trigger, stop, dist in rules.ladder_preview(h):
            reached = "✓" if lad.price >= trigger else ""
            locked = (stop - h["cost"]) * h["qty"]
            rows.append(f'<tr><td class="num">{reached}</td><td>{html.escape(label)}</td>'
                        f'<td class="num">{trigger:,.0f}</td><td class="num"><b>{stop:,.0f}</b></td>'
                        f'<td class="num">{dist*100:.1f}%</td>'
                        f'<td class="num {_cls(locked)}">{_yen(locked, True)}</td></tr>')
        blocks.append(
            f'<details><summary>{html.escape(h["name"])} '
            f'<span class="note-s">取得{h["cost"]:,.1f} ・ 現在{lad.price:,.1f} ・ '
            f'{lad.gain*100:+.2f}% ・ {html.escape(lad.step)}</span></summary>'
            '<div class="body"><table><thead><tr><th></th><th>段</th>'
            '<th class="num">株価</th><th class="num">逆指値</th>'
            '<th class="num">距離</th><th class="num">確保</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>')
    if not blocks:
        return ""
    return ('<div class="card"><h2>🪜 先に計算しておく段</h2>'
            + "".join(blocks)
            + '<div class="note-s" style="margin-top:8px">左が「その株価に来たら」、右が「そこに置く逆指値」。'
              '<b>切り下げは絶対にしない。</b>決めているのは分数ではなく「現在値から何%下に置くか」で、'
              f'守りたいのは{config.R10_BAND[0]*100:.0f}〜{config.R10_BAND[1]*100:.0f}%の帯。'
              '値動きの荒い銘柄は計算値ではなく直近の押し安値の下を優先する。</div></div>')


def _performance_card(store: Store) -> str:
    closed = [t for t in store.trades if t.get("pl") is not None]
    if not closed:
        return ""
    by_day: dict[str, float] = {}
    for t in closed:
        by_day[t["date"]] = by_day.get(t["date"], 0) + t["pl"]
    days = sorted(by_day)
    cum, running = [], 0.0
    for d in days:
        running += by_day[d]
        cum.append((d, running))

    parts = ['<div class="card"><h2>📈 確定損益の推移(累計)</h2>',
             line_chart(cum), "</div>",
             '<div class="card"><h2>📉 日別の確定損益</h2>',
             bar_chart([(d, by_day[d]) for d in days]), "</div>"]
    return "\n".join(parts)


def _journal_card(store: Store) -> str:
    if not store.journal:
        return ""
    cards = []
    for e in store.journal[:60]:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span> ' for t in e.get("tags", []))
        body = e.get("body", "")
        if not re.search(r"<[a-z]", body, re.I):
            body = md_render(body)
        cards.append(f'<div style="border-bottom:1px solid var(--grid);padding:10px 0">'
                     f'<div><b>{html.escape(e["title"])}</b> '
                     f'<span class="note-s">{html.escape(e["date"])}</span> {tags}</div>'
                     f'<div class="body">{body}</div></div>')
    more = ("" if len(store.journal) <= 60
            else f'<div class="note-s" style="margin-top:8px">他 {len(store.journal)-60} 件は '
                 '<code class="tag">private/store.json</code> に。</div>')
    return ('<div class="card"><h2>🗒 日次ログ</h2>' + "".join(cards) + more + "</div>")
