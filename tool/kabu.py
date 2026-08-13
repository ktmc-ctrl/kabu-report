#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kabu — 株式相談ツール

  相談する   kabu brief / status / holdings / risk / ladder / morning
  記録する   kabu buy / sell / stop / price / note / prememo / watch / earnings
  調べる     kabu research / sweep / decompose
  レポート   kabu report / portal / check / render / publish

数字は全部このツールが記録から計算する。判断はしない。
使い方は tool/README.md を見る。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kabulib import (account, config, diary_html, perf_html, portal, privacy,  # noqa: E402
                     reports, research, rules, views)
from kabulib.fmt import c, heading  # noqa: E402
from kabulib.store import Store, StoreError, today  # noqa: E402


# ── 相談 ────────────────────────────────────────────────

def cmd_status(a):
    print(views.status(Store.load()))


def cmd_holdings(a):
    print(views.holdings(Store.load()))


def cmd_risk(a):
    print(views.risk(Store.load()))


def cmd_ladder(a):
    print(views.ladder(Store.load(), a.code))


def cmd_morning(a):
    store = Store.load()
    print(views.morning(store))
    if a.ok:
        touched = account.revive_stops(store, a.ok)
        store.add_journal(
            "✅ 朝の逆指値チェック",
            "証券口座の「(注文中)」を目で見て確認。生きていた: "
            + "・".join(h["name"] for h in touched),
            tags=["逆指値", "朝チェック"])
        store.save()
        print(c(f"\n  ✓ {len(touched)}銘柄の生存を記録した。", "green"))


def cmd_brief(a):
    print(views.brief(Store.load()))


# ── 記録 ────────────────────────────────────────────────

def cmd_buy(a):
    store = Store.load()
    h = account.buy(store, a.code, a.qty, a.price, name=a.name, frame=a.frame,
                    stop=a.stop, themes=a.theme, on=a.date, fee=a.fee,
                    force=a.force, skip_memo=a.no_memo, volatile=a.volatile)
    store.save()
    print(c(f"✓ {h['name']} {a.qty}株 @{a.price:,.1f} を記録。"
            f"保有 {h['qty']}株 / 平均取得 {h['cost']:,.2f}", "green"))
    print(views.status(store))


def cmd_sell(a):
    store = Store.load()
    r = account.sell(store, a.code, a.qty, a.price, on=a.date, fee=a.fee, reason=a.reason)
    store.save()
    pl = r["pl"]
    print(c(f"✓ {r['holding']['name']} {a.qty}株 @{a.price:,.1f} を決済。"
            f"確定 {pl:+,.0f}円", "green" if pl >= 0 else "red"))
    for w in r["warnings"]:
        print(c(f"  ! {w}", "yellow"))
    print(views.status(store))


def cmd_stop(a):
    store = Store.load()
    if a.check:
        print(views.morning(store))
        return
    price = None if a.remove else a.price
    if price is None and not a.remove:
        raise StoreError("価格を指定するか、外すなら --remove。")
    account.set_stop(store, a.code, price, on=a.date, expires=a.expires,
                     alive=not a.dead, note=a.note, force=a.force)
    store.save()
    print(views.ladder(store, a.code))
    print(views.risk(store))


def cmd_price(a):
    store = Store.load()
    pairs = []
    for item in a.pairs:
        if "=" not in item:
            raise StoreError(f"「{item}」は コード=価格 の形で。例: 7011=4256")
        code, value = item.split("=", 1)
        pairs.append((code.strip(), float(value.replace(",", ""))))
    updated = account.set_prices(store, pairs, on=a.date)
    store.save()
    for h in updated:
        print(f"  {h['name']}: {h['price']:,.1f}({rules.gain_pct(h)*100:+.2f}%)")
    print(views.status(store))


def cmd_frame(a):
    store = Store.load()
    h = account.set_frame(store, a.code, a.frame)
    store.save()
    print(c(f"✓ {h['name']} を {config.FRAMES[a.frame]} に変更。理由を日記に書き足すこと。", "yellow"))


def cmd_theme(a):
    store = Store.load()
    if not a.theme:
        from kabulib.fmt import finding_line
        print(heading("⑥ テーマ集中 — 1テーマは総資産の3〜4割まで"))
        found = rules.theme_check(store)
        if not found:
            print("  タグが付いていない。`kabu theme 5802 DC・AI` のように付ける。")
        for f in found:
            print(finding_line(f))
        return
    h = store.must_find(a.code)
    current = set(h.get("themes") or [])
    h["themes"] = sorted(current - set(a.theme) if a.remove else current | set(a.theme))
    store.save()
    print(c(f"✓ {h['name']}: {'・'.join(h['themes']) or '(なし)'}", "green"))
    from kabulib.fmt import finding_line
    for f in rules.theme_check(store):
        print(finding_line(f))


def cmd_note(a):
    store = Store.load()
    store.add_journal(a.title, a.body or "", on=a.date, tags=a.tag or [])
    store.save()
    print(c(f"✓ 記録した: {a.title}", "green"))


def cmd_prememo(a):
    store = Store.load()
    fields = {}
    for key, label in account.MEMO_FIELDS:
        value = getattr(a, key, None)
        if not value:
            value = input(f"  {label}\n  > ").strip()
        fields[key] = value
    name = a.name or a.code
    memo = account.add_prememo(store, a.code, name, a.price, fields, on=a.date)
    store.save()
    print(c(f"\n✓ 買う前メモを記録: {name} @{a.price:,.1f}", "green"))
    print(c("  有効期限は「株価が5%動くか3営業日」。切れたら書き直してから注文する。", "dim"))
    if a.stop:
        findings = rules.size_check(store, a.code, name, a.qty or 0, a.price, a.stop, a.frame)
        print(heading("サイズ判定"))
        from kabulib.fmt import finding_line
        for f in findings:
            print(finding_line(f))
    return memo


def cmd_watch(a):
    store = Store.load()
    if a.remove:
        before = len(store.watchlist)
        store.watchlist[:] = [w for w in store.watchlist if w.get("code") != a.code]
        store.save()
        print(c(f"✓ {before - len(store.watchlist)}件を外した。", "green"))
        return
    store.watchlist[:] = [w for w in store.watchlist if w.get("code") != a.code]
    store.watchlist.append({"code": a.code, "name": a.name or a.code,
                            "trigger": a.trigger or "", "note": a.note or ""})
    store.save()
    print(c(f"✓ ウォッチに追加: {a.name or a.code}", "green"))


def cmd_earnings(a):
    store = Store.load()
    store.earnings[:] = [e for e in store.earnings
                         if not (e.get("code") == a.code and e.get("date") == a.date)]
    store.earnings.append({"date": a.date, "code": a.code,
                           "name": a.name or a.code, "note": a.note or ""})
    store.save()
    print(c(f"✓ 決算予定を記録: {a.date} {a.name or a.code}", "green"))


def cmd_account(a):
    store = Store.load()
    if a.cash is not None:
        store.cash = a.cash
    store.snapshot(a.date)
    store.save()
    print(views.status(store))


# ── 調べる ──────────────────────────────────────────────

def cmd_research(a):
    store = Store.load()
    h = None
    try:
        h = store.find(a.code)
    except StoreError:
        pass
    name = a.name or (h["name"] if h else a.code)
    print(research.checklist(name, a.code))
    if h:
        print(heading("この銘柄の記録"))
        print(f"  枠 {config.FRAMES.get(h.get('frame'), '—')} / {h['qty']}株 / "
              f"取得 {h['cost']:,.1f} / 現在値 {rules.current_price(h):,.1f} "
              f"({rules.gain_pct(h)*100:+.2f}%)")
        for key, label in (("thesis", "thesis"), ("invalidation", "話が別になる条件")):
            if h.get(key):
                print(f"  {label}: {h[key]}")


def cmd_sweep(a):
    store = Store.load()
    h = None
    try:
        h = store.find(a.code)
    except StoreError:
        pass
    print(research.sweep(a.name or (h["name"] if h else a.code)))


def cmd_decompose(a):
    items = []
    for item in a.item or []:
        if "=" not in item:
            raise StoreError(f"「{item}」は ラベル=金額 の形で。例: メタノール市況=99")
        label, value = item.split("=", 1)
        items.append((label.strip(), float(value.replace(",", ""))))
    print(research.decompose(a.total, items, unit=a.unit, prior=a.prior))


# ── レポート・ポータル ──────────────────────────────────

def cmd_report(a):
    lib = reports.Library.load()
    if a.action == "list":
        print(heading(f"公開レポート {len(lib.stocks)}銘柄 ・ 特集 {len(lib.themes)}本"))
        from kabulib.fmt import table
        rows = [(s["code"], s["name"], s["sector"], s["verdict"],
                 str(s.get("price", "")), str(s.get("asof", "")), s["file"])
                for s in lib.stocks]
        print(table(["コード", "銘柄", "セクター", "評価", "株価", "更新", "ファイル"], rows))
        return

    if a.action == "new":
        if not a.name:
            raise StoreError("--name で銘柄名を。")
        slug = a.slug or a.name
        path = config.PUBLIC / f"{a.code}_{slug}.html"
        if path.exists() and not a.force:
            raise StoreError(f"{path.name} はもうある。上書きするなら --force。")
        path.write_text(reports.scaffold(a.code, a.name, a.ticker or a.code,
                                         a.price or "—", a.asof or today()),
                        encoding="utf-8")
        lib.upsert(a.code, name=a.name, ticker=a.ticker or a.code,
                   sector=a.sector, price=a.price or "—", asof=a.asof or _md(today()),
                   verdict=a.verdict or "中立", summary=a.summary or "", file=path.name)
        lib.save()
        print(c(f"✓ {path.name} を作成。9つの節の TODO を一次資料から埋める。", "green"))
        print(c(f"  メタは {config.REPORTS_FILE.relative_to(config.ROOT)} に登録済み。", "dim"))
        print(research.checklist(a.name, a.code))
        return

    if a.action == "set":
        if lib.find(a.code) is None:
            raise StoreError(f"{a.code} は未登録。先に `kabu report new`。")
        lib.upsert(a.code, name=a.name, ticker=a.ticker, sector=a.sector,
                   price=a.price, asof=a.asof, verdict=a.verdict,
                   summary=a.summary, file=a.file)
        errors, _ = lib.validate()
        lib.save()
        print(c(f"✓ {a.code} のメタを更新。", "green"))
        for p in errors:
            print(c(f"  ✗ {p}", "red"))


def cmd_portal(a):
    lib = reports.Library.load()
    if a.asof:
        lib.data["updated"] = a.asof
        lib.save()
    out, n = portal.build(lib)
    print(c(f"✓ {out.relative_to(config.ROOT)} を生成({n}銘柄 ・ "
            f"{len(lib.themes)}特集 ・ {out.stat().st_size:,}バイト)", "green"))


def cmd_check(a):
    errors, warnings = reports.Library.load().validate()
    findings = privacy.scan()
    leaks = [f for f in findings if f.is_leak]
    styles = [f for f in findings if f.kind == "style"]

    print(heading("メタデータの整合性"))
    if errors:
        for p in errors:
            print(c(f"  ✗ {p}", "red"))
    else:
        print(c("  ✓ verdict・セクター・ファイルの対応に抜けなし。", "green"))
    if warnings and not a.quiet:
        for w in warnings:
            print(c(f"  ! {w}", "yellow"))

    print(heading("プライバシー(公開物に私的情報が出ていないか)"))
    if leaks:
        for f in leaks:
            where = f.path.relative_to(config.ROOT)
            loc = f"{where}:{f.line}" if f.line else str(where)
            print(c(f"  ✗ {loc}  {f.label}", "red"))
            if f.excerpt:
                print(c(f"      {f.excerpt}", "dim"))
    else:
        print(c("  ✓ 公開物にポジション情報・内部ルール名の混入なし。", "green"))

    if styles and not a.quiet:
        print(heading("文体(公開レポートはである調・推奨語を使わない)"))
        for f in styles:
            print(c(f"  ! {f.path.relative_to(config.ROOT)}:{f.line}  {f.label}", "yellow"))
            print(c(f"      {f.excerpt}", "dim"))

    if errors or leaks:
        sys.exit(1)


def cmd_render(a):
    store = Store.load()
    rulebook_path = config.PRIVATE / "rulebook.md"
    rulebook = rulebook_path.read_text(encoding="utf-8") if rulebook_path.exists() else ""
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    made = []
    if a.what in ("diary", "all"):
        config.DIARY_OUT.write_text(diary_html.build(store, rulebook), encoding="utf-8")
        made.append(config.DIARY_OUT)
    if a.what in ("performance", "perf", "all"):
        config.PERF_OUT.write_text(perf_html.build(store), encoding="utf-8")
        made.append(config.PERF_OUT)
    for p in made:
        print(c(f"✓ {p.relative_to(config.ROOT)}({p.stat().st_size:,}バイト)", "green"))
    print(c("  private/ は git の管理下にない。共有しない。", "dim"))


def cmd_publish(a):
    lib = reports.Library.load()
    if a.asof:
        lib.data["updated"] = a.asof
        lib.save()
    out, n = portal.build(lib)
    print(c(f"✓ ポータルを生成({n}銘柄)", "green"))

    findings = [f for f in privacy.scan() if f.is_leak]
    if findings:
        print(c("\n✗ 公開できない。私的情報が混ざっている:", "red"))
        for f in findings:
            print(c(f"  {f.path.relative_to(config.ROOT)}:{f.line}  {f.label}", "red"))
            if f.excerpt:
                print(c(f"    {f.excerpt}", "dim"))
        sys.exit(1)
    print(c("✓ プライバシー検査を通過", "green"))

    if a.no_commit:
        print(c("  --no-commit なのでここまで。", "dim"))
        return
    message = a.message or "レポートを更新"
    for cmd in (["git", "-C", str(config.ROOT), "add", "-A"],
                ["git", "-C", str(config.ROOT), "commit", "-m", message]):
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0 and "nothing to commit" not in res.stdout:
            print(c(f"✗ {' '.join(cmd[-2:])} が失敗:\n{res.stdout}{res.stderr}", "red"))
            sys.exit(1)
    print(c(f"✓ commit: {message}", "green"))
    if a.push:
        res = subprocess.run(["git", "-C", str(config.ROOT), "push"],
                             capture_output=True, text=True, check=False)
        print(c("✓ push 完了" if res.returncode == 0
                else f"✗ push 失敗:\n{res.stderr}", "green" if res.returncode == 0 else "red"))


def cmd_init(a):
    config.PRIVATE.mkdir(parents=True, exist_ok=True)
    store = Store.load()
    if a.cash is not None:
        store.cash = a.cash
    store.save()
    rulebook = config.PRIVATE / "rulebook.md"
    if not rulebook.exists():
        template = config.ROOT / "tool" / "templates" / "rulebook.md"
        rulebook.write_text(template.read_text(encoding="utf-8") if template.exists()
                            else "# ルールブック\n\n", encoding="utf-8")
    print(c(f"✓ {config.STORE_FILE.relative_to(config.ROOT)} と "
            f"{rulebook.relative_to(config.ROOT)} を用意した。", "green"))
    print(c("  次: kabu buy でポジションを入れるか、tool/migrate.py で既存の日記から取り込む。", "dim"))


def _md(iso: str) -> str:
    """2026-08-13 → 8/13(タイルの表示用)。"""
    y, m, d = iso.split("-")
    return f"{int(m)}/{int(d)}"


# ── パーサ ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kabu", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<コマンド>")

    def add(name, func, help_):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(func=func)
        return s

    # 相談
    add("status", cmd_status, "口座の要約")
    add("holdings", cmd_holdings, "保有一覧(⑩の段とバンド判定つき)")
    add("risk", cmd_risk, "⑫ 総リスク — 全部外れたらいくら失うか")
    s = add("ladder", cmd_ladder, "⑩ トレーリング逆指値の段を計算")
    s.add_argument("code", nargs="?", help="省略すると全銘柄")
    s = add("morning", cmd_morning, "☀️ 朝のチェック(⑨が1日の最初のタスク)")
    s.add_argument("--ok", nargs="*", metavar="コード", help="生存を確認できた銘柄を記録")
    add("brief", cmd_brief, "相談用の事実シート(Markdown)")

    # 記録
    s = add("buy", cmd_buy, "買いを記録(④⑤⑧⑮を当てる)")
    s.add_argument("code"); s.add_argument("qty", type=int); s.add_argument("price", type=float)
    s.add_argument("--name", default=""); s.add_argument("--frame", default="long",
                                                         choices=list(config.FRAMES))
    s.add_argument("--stop", type=float, help="同時に置く逆指値")
    s.add_argument("--theme", action="append", help="⑥の集中判定に使う。複数可")
    s.add_argument("--date"); s.add_argument("--fee", type=float, default=0.0)
    s.add_argument("--volatile", action="store_true", help="値動きが荒い(⑩で押し安値を優先)")
    s.add_argument("--no-memo", action="store_true", help="⑧の買う前メモ無しで通す")
    s.add_argument("--force", action="store_true", help="ルール違反を承知で押し切る")

    s = add("sell", cmd_sell, "決済を記録(⑯⑱の確認つき)")
    s.add_argument("code"); s.add_argument("qty", type=int); s.add_argument("price", type=float)
    s.add_argument("--date"); s.add_argument("--fee", type=float, default=0.0)
    s.add_argument("--reason", default="")

    s = add("stop", cmd_stop, "逆指値の設定・引き上げ(⑩ 切り下げは拒否)")
    s.add_argument("code", nargs="?"); s.add_argument("price", nargs="?", type=float)
    s.add_argument("--check", action="store_true", help="⑨の生存チェックだけ")
    s.add_argument("--remove", action="store_true"); s.add_argument("--dead", action="store_true",
                                                                    help="落ちている状態で記録")
    s.add_argument("--expires", help="期限。無期限が原則なので普通は指定しない")
    s.add_argument("--note", default=""); s.add_argument("--date")
    s.add_argument("--force", action="store_true", help="切り下げを承知で押し切る")

    s = add("price", cmd_price, "現在値を更新(コード=価格 を並べる)")
    s.add_argument("pairs", nargs="+", metavar="コード=価格"); s.add_argument("--date")

    s = add("frame", cmd_frame, "① 枠の変更(原則禁止。記録が残る)")
    s.add_argument("code"); s.add_argument("frame", choices=list(config.FRAMES))

    s = add("theme", cmd_theme, "⑥ 保有にテーマのタグを付ける(引数なしで集中度を見る)")
    s.add_argument("code", nargs="?"); s.add_argument("theme", nargs="*")
    s.add_argument("--remove", action="store_true")

    s = add("note", cmd_note, "日記に記録を足す")
    s.add_argument("title"); s.add_argument("body", nargs="?", default="")
    s.add_argument("--tag", action="append"); s.add_argument("--date")

    s = add("prememo", cmd_prememo, "⑧ 買う前メモ(未記入は対話で聞く)")
    s.add_argument("code"); s.add_argument("price", type=float)
    s.add_argument("--name"); s.add_argument("--qty", type=int); s.add_argument("--stop", type=float)
    s.add_argument("--frame", default="long", choices=list(config.FRAMES))
    s.add_argument("--date")
    for key, label in account.MEMO_FIELDS:
        s.add_argument(f"--{key}", help=label)

    s = add("watch", cmd_watch, "ウォッチリスト")
    s.add_argument("code"); s.add_argument("--name"); s.add_argument("--trigger")
    s.add_argument("--note"); s.add_argument("--remove", action="store_true")

    s = add("earnings", cmd_earnings, "決算予定を記録")
    s.add_argument("date"); s.add_argument("code"); s.add_argument("--name"); s.add_argument("--note")

    s = add("account", cmd_account, "現金余力の更新とスナップショット")
    s.add_argument("--cash", type=float); s.add_argument("--date")

    # 調べる
    s = add("research", cmd_research, "🔎 銘柄を調べる標準プロトコル")
    s.add_argument("code"); s.add_argument("--name")
    s = add("sweep", cmd_sweep, "📰 ⑱ ニューススイープ(切られたときの4方向)")
    s.add_argument("code"); s.add_argument("--name")
    s = add("decompose", cmd_decompose, "⑰ 増益の中身を一過性・市況・実質に分解")
    s.add_argument("total", type=float, help="増益額")
    s.add_argument("--item", action="append", metavar="ラベル=金額")
    s.add_argument("--prior", type=float, help="前年同期の利益(実質増益率を出す)")
    s.add_argument("--unit", default="億円")

    # レポート
    s = add("report", cmd_report, "公開レポートの雛形生成とメタ更新")
    s.add_argument("action", choices=["new", "set", "list"])
    s.add_argument("code", nargs="?", default="")
    s.add_argument("--name"); s.add_argument("--ticker"); s.add_argument("--sector")
    s.add_argument("--price"); s.add_argument("--asof"); s.add_argument("--verdict")
    s.add_argument("--summary"); s.add_argument("--file"); s.add_argument("--slug")
    s.add_argument("--force", action="store_true")

    s = add("portal", cmd_portal, "index.html を生成")
    s.add_argument("--asof", help="トップに出す「◯◯時点」")

    s = add("check", cmd_check, "🔒 プライバシー検査 + メタ整合性検査")
    s.add_argument("--quiet", action="store_true", help="文体の指摘を省く")

    s = add("render", cmd_render, "私的HTML(日記・損益)を生成")
    s.add_argument("what", nargs="?", default="all",
                   choices=["diary", "performance", "perf", "all"])

    s = add("publish", cmd_publish, "ポータル生成 → 検査 → commit")
    s.add_argument("-m", "--message"); s.add_argument("--asof")
    s.add_argument("--push", action="store_true"); s.add_argument("--no-commit", action="store_true")

    s = add("init", cmd_init, "private/ を用意する")
    s.add_argument("--cash", type=float)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (StoreError, reports.ReportError) as e:
        print(c(f"\n✗ {e}", "red"), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)


if __name__ == "__main__":
    main()
