# -*- coding: utf-8 -*-
"""相談の土台になる「事実シート」。

判断はしない。相談するとき Claude が記憶や推測で数字を作らないよう、
口座・保有・逆指値・総リスク・集中度を、その場で計算して出す。
"""
from __future__ import annotations

from . import config, rules
from .fmt import c, finding_line, heading, pct, sign_color, table, yen
from .store import Store


def status(store: Store) -> str:
    eq = store.equity()
    unreal = store.unrealized_total()
    real = store.realized_total()
    mv = store.market_value()
    cost = sum(h["qty"] * h["cost"] for h in store.holdings)
    risk = rules.total_risk(store)

    out = [heading("口座")]
    rows = [
        ("口座資産", yen(eq), f"保有 {yen(mv)} + 現金 {yen(store.cash)}"),
        ("含み損益", c(yen(unreal, True), sign_color(unreal)),
         pct(unreal / cost) if cost else "—"),
        ("確定損益(通算)", c(yen(real, True), sign_color(real)),
         f"{len([t for t in store.trades if t.get('pl') is not None])}回の決済"),
        ("通算", c(yen(real + unreal, True), sign_color(real + unreal)), "確定 + 含み"),
        ("総リスク(⑫)", c(yen(risk.total, True), sign_color(risk.total)),
         f"総資産の{risk.pct*100:.2f}% ・ 上限6%まで {yen(risk.headroom)} の余地"),
    ]
    out.append(table(["", "", ""], rows, ["left", "right", "left"]))
    if risk.over_cap:
        out.append(c("  ⑫ 総リスクが上限6%を超えている。逆指値を上げるか株数を減らす。", "red"))
    if risk.uncovered:
        names = "・".join(h["name"] for h in risk.uncovered)
        out.append(c(f"  ⑨ 逆指値の無い銘柄: {names}", "red"))
    return "\n".join(out)


def holdings(store: Store) -> str:
    if not store.holdings:
        return "保有なし。"
    lads = sorted(rules.ladder_table(store), key=lambda l: -l.gain)
    rows = []
    for l in lads:
        h = store.must_find(l.code)
        frame = config.FRAMES.get(h.get("frame", "long"), "—")
        pl = rules.unrealized(h)
        if l.recommended is None:
            exit_col, locked = "逆指値なし", "—"
        else:
            exit_col = f"{l.recommended:,.0f}"
            if l.should_raise:
                exit_col = f"{l.current_stop:,.0f}→{l.recommended:,.0f}"
            elif l.distance is not None:
                exit_col += f" ({l.distance*100:.1f}%)"
            locked = c(yen(l.locked_after, True), sign_color(l.locked_after))
        rows.append((
            f"{h['name']} {h['qty']}", frame, f"{h['cost']:,.1f}", f"{l.price:,.1f}",
            c(yen(pl, True), sign_color(pl)), c(pct(l.gain), sign_color(pl)),
            exit_col, locked,
        ))
    out = [heading(f"保有 {len(store.holdings)}銘柄")]
    out.append(table(
        ["銘柄", "枠", "取得", "現在値", "損益", "率", "出口(⑩)", "発動時"],
        rows, ["left", "left", "right", "right", "right", "right", "left", "right"]))
    out.append(c("  出口の「A→B」は⑩の段に到達していて引き上げが要るという意味。"
                 "括弧内は現在値からの距離(守りたい帯は4〜10%)。", "dim"))
    return "\n".join(out)


def risk(store: Store) -> str:
    r = rules.total_risk(store)
    rows = []
    for line in r.lines:
        if line.pl is None:
            rows.append((line.name, f"{line.qty}", "—", c(line.reason, "dim"), ""))
            continue
        rows.append((line.name, f"{line.qty}", f"{line.stop:,.0f}",
                     c(yen(line.pl, True), sign_color(line.pl)),
                     "確保" if line.pl > 0 else ("±0" if line.pl == 0 else "")))
    out = [heading("⑫ 総リスク — 全部外れたらいくら失うか")]
    out.append(table(["銘柄", "株数", "逆指値", "発動時", ""], rows,
                     ["left", "right", "right", "right", "left"]))
    out.append("")
    out.append(f"  合計         {c(yen(r.total, True), sign_color(r.total))}"
               f"  (総資産 {yen(r.equity)} の {r.pct*100:.2f}%)")
    out.append(f"  上限6%       {yen(-r.cap)}")
    out.append(f"  余地         {c(yen(r.headroom), 'green' if r.headroom > 0 else 'red')}")
    if r.excluded:
        out.append(c("  ※ " + "・".join(h["name"] for h in r.excluded)
                     + " は触らない枠。意図的に逆指値なしなので合計に含めていない。", "dim"))
    if r.uncovered:
        out.append(c("  ✗ " + "・".join(h["name"] for h in r.uncovered)
                     + " は逆指値が無い。⑨違反で、この合計にも入っていない。", "red"))
    return "\n".join(out)


def ladder(store: Store, code: str | None = None) -> str:
    targets = [store.must_find(code)] if code else store.holdings
    out = []
    for h in targets:
        l = rules.ladder_for(h)
        out.append(heading(f"⑩ {h['name']}({h['code']}) — {config.FRAMES.get(h.get('frame'), '')}"))
        if not rules.needs_stop(h):
            out.append("  触らない枠。逆指値は置かない。撤退は価格ではなく論理で決める。")
            continue
        out.append(f"  取得 {h['cost']:,.1f} / 現在値 {l.price:,.1f} / "
                   f"{c(pct(l.gain), sign_color(l.gain))} → {c(l.step, 'bold')}")
        if l.current_stop is not None:
            out.append(f"  今の逆指値 {l.current_stop:,.0f}(発動時 "
                       f"{c(yen(l.locked, True), sign_color(l.locked))})")
        if l.should_raise:
            out.append(c(f"  → {l.recommended:,.0f} へ引き上げ。確保が "
                         f"{yen(l.locked, True)} → {yen(l.locked_after, True)} になる", "yellow"))
            out.append(c(f"     kabu stop {h['code']} {l.recommended:.0f}", "dim"))
        elif l.recommended is not None:
            out.append(f"  段の要求値は {l.ladder_stop:,.0f}。今の逆指値の方が上なので据え置き。")
        if l.distance is not None:
            mark = {"in": "green", "tight": "yellow", "wide": "yellow",
                    "initial": "dim", "none": "dim"}[l.band]
            out.append(f"  現在値からの距離 {c(pct(l.distance, 1, signed=False), mark)}"
                       f"(守りたい帯 {config.R10_BAND[0]*100:.0f}〜{config.R10_BAND[1]*100:.0f}%)")
        for n in l.notes:
            out.append(c(f"  ! {n}", "yellow"))

        out.append(c("\n  先に計算しておく段(株価がここまで来たら、逆指値はここ)", "dim"))
        rows = []
        for label, trigger, stop, dist in rules.ladder_preview(h):
            reached = "✓" if l.price >= trigger else " "
            rows.append((reached, label, f"{trigger:,.0f}", f"{stop:,.0f}",
                         f"{dist*100:.1f}%", yen((stop - h["cost"]) * h["qty"], True)))
        out.append(table(["", "段", "株価", "逆指値", "距離", "確保"], rows,
                         ["center", "left", "right", "right", "right", "right"]))
    return "\n".join(out)


def morning(store: Store) -> str:
    findings = rules.morning_check(store)
    reds = [f for f in findings if f.level == "red"]
    yellows = [f for f in findings if f.level == "yellow"]
    greens = [f for f in findings if f.level == "green"]

    out = [heading("☀️ 朝のチェック(⑨が1日の最初のタスク)")]
    if reds:
        out.append(c(f"\n  今すぐ直す — {len(reds)}件", "red"))
        out.extend(finding_line(f) for f in reds)
    if yellows:
        out.append(c(f"\n  見ておく — {len(yellows)}件", "yellow"))
        out.extend(finding_line(f) for f in yellows)
    if greens:
        out.append(c(f"\n  問題なし — {len(greens)}件", "green"))
        out.extend(finding_line(f) for f in greens)
    if not reds:
        out.append(c("\n  ✓ 逆指値は全部生きている。落ちているものはゼロ。", "green"))
    out.append(c("\n  ※ 証券口座の「(注文中)」を実際に目で見て突き合わせること。"
                 "このツールが見ているのは記録の方で、実物ではない。", "dim"))
    return "\n".join(out)


def brief(store: Store) -> str:
    """相談を始める前に読む事実シート。装飾なしで、そのまま文脈に置ける形にする。"""
    eq = store.equity()
    r = rules.total_risk(store)
    unreal = store.unrealized_total()
    real = store.realized_total()
    lines = [
        "# 口座の事実(このツールが記録から計算した値。推測は含まない)",
        "",
        f"- 口座資産 {eq:,.0f}円(保有 {store.market_value():,.0f} + 現金 {store.cash:,.0f})",
        f"- 含み損益 {unreal:+,.0f}円 / 確定損益 通算 {real:+,.0f}円 / 合計 {real+unreal:+,.0f}円",
        f"- ⑫総リスク(全逆指値が同時発動) {r.total:+,.0f}円 = 総資産の{r.pct*100:.2f}%"
        f"(上限6%={r.cap:,.0f}円、余地 {r.headroom:,.0f}円)",
        f"- 保有 {len(store.holdings)}銘柄",
        "",
        "## 保有",
        "",
        "| 銘柄 | 枠 | 株数 | 取得 | 現在値 | 損益 | 率 | 逆指値 | 距離 | 発動時 | ⑩の段 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for l in sorted(rules.ladder_table(store), key=lambda x: -x.gain):
        h = store.must_find(l.code)
        pl = rules.unrealized(h)
        stop = f"{l.current_stop:,.0f}" if l.current_stop is not None else "なし"
        dist = f"{l.distance*100:.1f}%" if l.distance is not None else "—"
        locked = f"{l.locked:+,.0f}" if l.locked is not None else "—"
        step = l.step + ("(要引き上げ→%s)" % f"{l.recommended:,.0f}" if l.should_raise else "")
        lines.append(
            f"| {h['name']} | {config.FRAMES.get(h.get('frame'), '')} | {h['qty']} | "
            f"{h['cost']:,.1f} | {l.price:,.1f} | {pl:+,.0f} | {l.gain*100:+.2f}% | "
            f"{stop} | {dist} | {locked} | {step} |")

    themes = store.themes()
    if themes:
        lines += ["", "## テーマ集中(⑥ 1テーマは総資産の3〜4割まで)", ""]
        for theme, hs in sorted(themes.items(), key=lambda kv: -sum(
                x["qty"] * rules.current_price(x) for x in kv[1])):
            v = sum(x["qty"] * rules.current_price(x) for x in hs)
            lines.append(f"- {theme}: {v:,.0f}円({v/eq*100:.1f}%)"
                         f" — {'・'.join(x['name'] for x in hs)}")

    findings = rules.morning_check(store)
    reds = [f for f in findings if f.level == "red"]
    yellows = [f for f in findings if f.level == "yellow"]
    lines += ["", "## いま引っかかっているルール", ""]
    if not reds and not yellows:
        lines.append("- なし")
    for f in reds:
        lines.append(f"- **違反 [{f.rule}] {f.name}**: {f.message}" + (f" → {f.fix}" if f.fix else ""))
    for f in yellows:
        lines.append(f"- 注意 [{f.rule}] {f.name}: {f.message}" + (f" → {f.fix}" if f.fix else ""))

    watch = [w for w in store.watchlist]
    if watch:
        lines += ["", "## ウォッチリスト", ""]
        for w in watch:
            lines.append(f"- {w.get('name', w.get('code'))}: {w.get('trigger', '')}"
                         + (f" — {w['note']}" if w.get("note") else ""))

    if store.earnings:
        lines += ["", "## 決算スケジュール", ""]
        for e in sorted(store.earnings, key=lambda x: x.get("date", "")):
            lines.append(f"- {e.get('date')} {e.get('name')}: {e.get('note', '')}")

    recent = store.journal[:5]
    if recent:
        lines += ["", "## 直近の記録", ""]
        for e in recent:
            lines.append(f"- {e['date']} {e['title']}")
    return "\n".join(lines)
