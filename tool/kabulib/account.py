# -*- coding: utf-8 -*-
"""記録するコマンド——約定・逆指値・現在値・買う前メモ。

書き込みのたびにルールを当てる。⑩の切り下げ、⑤のサイズ超過、⑧のメモ無しは
既定で**止める**。押し切るときは --force が要り、その事実が日記に残る。
"""
from __future__ import annotations

from . import config, rules
from .fmt import c, pct, yen
from .store import Store, StoreError, today


def _avg_cost(qty_a: int, cost_a: float, qty_b: int, cost_b: float) -> float:
    """平均取得単価。証券会社の保有画面は丸めて表示されるので、内部では丸めない。"""
    return (qty_a * cost_a + qty_b * cost_b) / (qty_a + qty_b)


def _gate(findings: list, force: bool, what: str) -> list:
    """red があれば止める。--force なら通すが、押し切った事実を返して日記に残す。"""
    violations = [f for f in findings if f.is_violation]
    if violations and not force:
        lines = "\n".join(f"  ✗ [{f.rule}] {f.message}" + (f"\n      → {f.fix}" if f.fix else "")
                          for f in violations)
        raise StoreError(
            f"{what}はルールに引っかかる。\n{lines}\n"
            "  ルールを承知の上で通すなら --force。押し切った記録は日記に残る。"
        )
    return violations


# ── 買う ────────────────────────────────────────────────

def buy(store: Store, code: str, qty: int, price: float, *, name: str = "",
        frame: str = "long", stop: float | None = None, themes: list | None = None,
        on: str | None = None, fee: float = 0.0, force: bool = False,
        skip_memo: bool = False, volatile: bool = False) -> dict:
    on = on or today()
    if qty <= 0 or price <= 0:
        raise StoreError("株数と価格は正の数で。")
    if frame not in config.FRAMES:
        raise StoreError(f"枠は {'/'.join(config.FRAMES)} のどれか。")

    existing = store.find(code)
    name = name or (existing["name"] if existing else code)
    findings: list = []

    # ⑧ 買う前メモ — 無いなら止める
    memo = _open_memo(store, code)
    if memo is None and not skip_memo:
        findings.append(rules.Finding(
            "red", "⑧", code, name, "買う前メモがない",
            f"`kabu prememo {code}` で thesis・出口・リスク・承知点・話が別になる条件を先に書く"))
    elif memo is not None:
        expired = [f for f in rules.prememo_check(store) if f.code == code]
        findings.extend(expired)

    # ⑮ 買い増しならピラミッディングの条件を見る
    if existing:
        findings.extend(rules.pyramid_check(existing, qty))

    # ④⑤③-2 サイズ
    findings.extend(rules.size_check(store, code, name, qty, price, stop, frame))

    forced = _gate(findings, force, f"{name} {qty}株 @{price:,.1f} の買い")

    if existing:
        existing["cost"] = _avg_cost(existing["qty"], existing["cost"], qty, price)
        existing["qty"] += qty
        existing["adds"] = existing.get("adds", 0) + 1
        h = existing
    else:
        h = {
            "code": code, "name": name, "qty": qty, "cost": float(price),
            "frame": frame, "opened": on, "first_qty": qty, "adds": 0,
            "price": float(price), "price_asof": on,
            "themes": themes or [], "stop": None, "volatile": volatile,
        }
        if memo:
            h["thesis"] = memo.get("thesis", "")
            h["exit"] = memo.get("exit", "")
            h["invalidation"] = memo.get("invalidation", "")
        store.holdings.append(h)

    if themes:
        h["themes"] = sorted(set((h.get("themes") or []) + themes))
    if volatile:
        h["volatile"] = True
    h["price"] = float(price)
    h["price_asof"] = on
    h["high"] = max(h.get("high") or 0.0, float(price))

    store.cash -= qty * price + fee
    store.trades.append({
        "date": on, "code": code, "name": name, "side": "buy",
        "qty": qty, "price": float(price), "fee": fee, "pl": None,
        "frame": frame, "forced": bool(forced),
    })
    if memo:
        memo["used"] = True

    if stop is not None:
        set_stop(store, code, stop, on=on, note="買い付けと同時に設定", force=True)

    body = [f"{name} {qty}株を {price:,.1f} で取得。枠は{config.FRAMES[frame]}。"]
    if stop is not None:
        body.append(f"逆指値 {stop:,.1f}(発動時 {yen((stop - h['cost']) * h['qty'], True)}円)。")
    if forced:
        body.append("⚠️ ルール違反を --force で押し切った: "
                    + " / ".join(f"[{f.rule}] {f.message}" for f in forced))
    store.add_journal(f"🟢 買い: {name} {qty}株", "".join(body), on=on,
                      tags=["約定", "買い"], kind="trade")
    store.snapshot(on)
    return h


# ── 売る ────────────────────────────────────────────────

def sell(store: Store, code: str, qty: int, price: float, *, on: str | None = None,
         fee: float = 0.0, reason: str = "") -> dict:
    on = on or today()
    h = store.must_find(code)
    if qty <= 0:
        raise StoreError("株数は正の数で。")
    if qty > h["qty"]:
        raise StoreError(f"{h['name']}は{h['qty']}株しか持っていない。")

    pl = (price - h["cost"]) * qty - fee
    h["qty"] -= qty
    store.cash += qty * price - fee
    # 最高到達値をトレードに残す。「+5%に触れて建値で終わった」型を後から実測するため(9/1追加)
    peak = max(h.get("high") or h["cost"], float(price))
    store.trades.append({
        "date": on, "code": h["code"], "name": h["name"], "side": "sell",
        "qty": qty, "price": float(price), "fee": fee, "pl": round(pl, 1),
        "reason": reason,
        "peak": peak, "peak_pct": round((peak - h["cost"]) / h["cost"], 4),
    })

    body = [f"{h['name']} {qty}株を {price:,.1f} で決済。確定 {yen(pl, True)}円"
            f"({pct((price - h['cost']) / h['cost'])})。"]
    if reason:
        body.append(f"理由: {reason}。")
    result = {"holding": h, "pl": pl, "closed": h["qty"] == 0, "warnings": []}

    if h["qty"] == 0:
        store.holdings.remove(h)
        if h.get("frame") == "long":
            # ⑱ コア銘柄は発動=撤退ではなく、現金化して再検証に入る合図
            result["warnings"].append(
                "⑱ 長期枠。切られた値段は忘れる。再エントリーは "
                "①ニューススイープ → ②thesisの生死 → ③底打ち/押し目の確認 → ④新しい買う前メモ の順。"
                "「話が別になる条件」が出ていたら再エントリー禁止")
            body.append("全株決済。⑱の再検証待ちへ。")
    else:
        # ⑯ 一部売却で残りの逆指値まで取り消されることがある
        result["warnings"].append(
            f"⑯ 残り{h['qty']}株。**証券口座の「(注文中)」を今すぐ見る。**"
            "一部売却で残りの逆指値まで取り消されることがある")
        if rules.has_stop(h):
            h["stop"]["alive"] = False
            h["stop"]["note"] = "一部売却により要確認(⑯)"
            body.append(f"残り{h['qty']}株の逆指値は「要確認」に落とした。実物を見て復帰させる。")

    if reason:
        result["warnings"].append("⑬ 下げが理由なら「なぜ」を先に。決算が理由なら初日に飛びつかない")

    store.add_journal(f"🔴 売り: {h['name']} {qty}株", "".join(body), on=on,
                      tags=["約定", "売り"], kind="trade")
    store.snapshot(on)
    return result


# ── 逆指値 ──────────────────────────────────────────────

def set_stop(store: Store, code: str, price: float | None, *, on: str | None = None,
             expires: str | None = None, alive: bool = True, execution: str = "成行",
             note: str = "", force: bool = False, kind: str = "") -> dict:
    """⑩ 切り下げは拒否する。上げるのは自由、下げるには --force が要る。"""
    on = on or today()
    h = store.must_find(code)

    if price is None:                      # 逆指値を外す(触らない枠へ移すときなど)
        if rules.needs_stop(h) and not force:
            raise StoreError(
                f"{h['name']}は{config.FRAMES[h.get('frame', 'long')]}。逆指値を外すと出口がなくなる(⑨)。"
                "触らない枠に移すなら `kabu frame` を先に。押し切るなら --force。")
        h["stop"] = None
        store.add_journal(f"逆指値を外した: {h['name']}", note or "—", on=on, tags=["逆指値"])
        return h

    old = rules.stop_price(h)
    if old is not None and price < old and not force:
        raise StoreError(
            f"⑩ 切り下げは禁止。{h['name']}の逆指値は今 {old:,.1f}。{price:,.1f} へは下げられない。\n"
            "  株価が下がってバンドから外れて見えても、上向きなら待てば戻る。\n"
            "  本当に下げるなら --force(押し切った記録が日記に残る)。")

    lowered = old is not None and price < old
    h["stop"] = {
        "price": float(price), "kind": kind or _stop_kind(h, price),
        "placed": on, "expires": expires, "alive": alive,
        "exec": execution, "note": note,
    }

    lad = rules.ladder_for(h)
    body = [f"{h['name']} の逆指値を "]
    body.append(f"{old:,.1f} → {price:,.1f}" if old is not None else f"{price:,.1f} に設定")
    body.append(f"。発動時 {yen(lad.locked_after, True)}円")
    if lad.distance is not None:
        body.append(f"、現在値から {pct(lad.distance, 1, signed=False)}")
    body.append("。")
    if lowered:
        body.append("⚠️ ⑩の切り下げ禁止を --force で押し切った。")
    if note:
        body.append(note)
    store.add_journal(f"🪜 逆指値: {h['name']} {price:,.1f}", "".join(body), on=on,
                      tags=["逆指値"], kind="stop")
    return h


def _stop_kind(h: dict, price: float) -> str:
    """逆指値の性格。取得単価より上なら「利益の確保」、下なら「損切り」。"""
    if price >= h["cost"]:
        return "トレール"
    return "損切り" if h.get("frame") == "swing" else "撤退"


def revive_stops(store: Store, codes: list, on: str | None = None) -> list:
    """⑨ 朝のチェックで「生きていた」ことを記録する。"""
    on = on or today()
    touched = []
    for code in codes:
        h = store.must_find(code)
        if not rules.needs_stop(h):
            continue
        if not h.get("stop"):
            raise StoreError(f"{h['name']}には逆指値そのものが無い。先に `kabu stop` で入れる。")
        h["stop"]["alive"] = True
        h["stop"]["checked"] = on
        h["stop"].pop("note", None)
        touched.append(h)
    return touched


# ── 現在値 ──────────────────────────────────────────────

def set_prices(store: Store, pairs: list, on: str | None = None) -> list:
    """(コード, 価格) の並びで現在値を更新する。約定履歴・大引けの値を正とする。"""
    on = on or today()
    out = []
    for code, price in pairs:
        h = store.must_find(code)
        h["price"] = float(price)
        h["price_asof"] = on
        # 最高到達値。「+5%に触れたのに獲れなかった」を後から数えるための記録(9/1追加)
        h["high"] = max(h.get("high") or h["cost"], float(price))
        out.append(h)
    if out:
        store.snapshot(on)
    return out


# ── 枠 ──────────────────────────────────────────────────

def set_frame(store: Store, code: str, frame: str, on: str | None = None) -> dict:
    """① 枠はあとから変更禁止。変えるなら理由が日記に残る。"""
    h = store.must_find(code)
    if frame not in config.FRAMES:
        raise StoreError(f"枠は {'/'.join(config.FRAMES)} のどれか。")
    old = h.get("frame")
    h["frame"] = frame
    store.add_journal(
        f"⚠️ 枠の変更: {h['name']} {config.FRAMES.get(old, old)} → {config.FRAMES[frame]}",
        "①「枠はあとから変更禁止」に触れる操作。変えた理由をここに書き足しておくこと。",
        on=on or today(), tags=["枠"])
    return h


# ── ⑧ 買う前メモ ───────────────────────────────────────

MEMO_FIELDS = [
    ("thesis", "thesis(なぜ上がると考えるか)"),
    ("exit", "出口(どこで降りるか——逆指値の位置)"),
    ("risk", "リスク(何が起きたら負けるか)"),
    ("accepted", "承知点(承知の上で受け入れる不利)"),
    ("invalidation", "話が別になる条件(これが出たら thesis は死ぬ)"),
]


def add_prememo(store: Store, code: str, name: str, price: float, fields: dict,
                on: str | None = None) -> dict:
    missing = [label for key, label in MEMO_FIELDS if not fields.get(key)]
    if missing:
        raise StoreError("買う前メモに空欄がある: " + " / ".join(missing))
    memo = {"date": on or today(), "code": code, "name": name,
            "price": float(price), "used": False}
    memo.update({k: fields[k] for k, _ in MEMO_FIELDS})
    store.prememos.append(memo)
    store.add_journal(
        f"📝 買う前メモ: {name} @{price:,.1f}",
        "<br>".join(f"<b>{label}</b>: {fields[key]}" for key, label in MEMO_FIELDS),
        on=on, tags=["買う前メモ"], kind="memo")
    return memo


def _open_memo(store: Store, code: str) -> dict | None:
    for m in reversed(store.prememos):
        if m.get("code") == code and not m.get("used"):
            return m
    return None
