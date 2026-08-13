# -*- coding: utf-8 -*-
"""ルールブック(全19条)のうち、数値で判定できるものを機械化する。

手計算していたもの——⑩のラダー、⑫の総リスク、バンドの距離、④⑤のサイズ——を
ここに集約する。判断そのものはしない。**事実と、ルールが要求する数値**だけを返す。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .store import Store


# ── 共通の小道具 ────────────────────────────────────────

def tick_floor(price: float) -> float:
    """逆指値を呼値に丸める。切り上げると逆指値が浅くなるので必ず切り捨てる。"""
    if price < 1000:
        return int(price * 10) / 10
    return float(int(price))


def current_price(h: dict) -> float:
    """現在値。未取得なら取得単価で代用する(損益ゼロとして扱われる)。"""
    return float(h.get("price") or h["cost"])


def gain_pct(h: dict) -> float:
    return (current_price(h) - h["cost"]) / h["cost"]


def unrealized(h: dict) -> float:
    return (current_price(h) - h["cost"]) * h["qty"]


def has_stop(h: dict) -> bool:
    s = h.get("stop")
    return bool(s and s.get("price") and s.get("alive", True))


def stop_price(h: dict) -> float | None:
    return float(h["stop"]["price"]) if has_stop(h) else None


def needs_stop(h: dict) -> bool:
    """触らない枠(③-2)は逆指値を置かない。それ以外は⑨で必須。"""
    return h.get("frame") not in config.NO_STOP_FRAMES


@dataclass
class Finding:
    """チェックの結果1件。level は red(違反) / yellow(注意) / green(良好)。"""
    level: str
    rule: str
    code: str
    name: str
    message: str
    fix: str = ""

    @property
    def is_violation(self) -> bool:
        return self.level == "red"


# ── ⑩ トレーリング逆指値(5段ラダー)──────────────────

@dataclass
class Ladder:
    code: str
    name: str
    cost: float
    price: float
    qty: int
    gain: float                  # 含み益率
    step: str                    # 到達している段の名前
    ladder_stop: float | None    # その段が要求する逆指値(第1段は None)
    current_stop: float | None
    recommended: float | None    # 実際に置くべき値 = max(今の逆指値, 段の要求値)
    distance: float | None       # 現在値から何%下か
    band: str                    # in / tight / wide / none
    locked: float | None         # 発動したときの損益
    locked_after: float | None   # 推奨に引き上げた後の損益
    notes: list = field(default_factory=list)

    @property
    def should_raise(self) -> bool:
        return (
            self.recommended is not None
            and self.current_stop is not None
            and self.recommended > self.current_stop
        )


def ladder_for(h: dict) -> Ladder:
    """1銘柄の⑩ラダーを計算する。切り下げは絶対にしないので、推奨は必ず現行以上。"""
    cost, price, qty = h["cost"], current_price(h), h["qty"]
    g = gain_pct(h)
    cur = stop_price(h)

    step, target = "第1段 損切り", None
    for threshold, fraction, label in config.R10_LADDER:
        if g >= threshold:
            step = label
            target = tick_floor(cost + (price - cost) * fraction)
            break

    if target is None and cur is None and needs_stop(h):
        # まだ第1段。逆指値が無いならデフォルト(−5%)を提示する
        target = tick_floor(cost * (1 - config.R10_INITIAL_STOP))

    if not needs_stop(h):
        recommended = None
    elif cur is None:
        recommended = target
    elif target is None:
        recommended = cur
    else:
        recommended = max(cur, target)   # 切り下げ禁止

    distance = (price - recommended) / price if recommended else None
    lo, hi = config.R10_BAND
    trailing = target is not None and g >= config.R10_LADDER[-1][0]
    if distance is None:
        band = "none"
    elif not trailing:
        # 第1段は「直近安値の下、または −5%」。4〜10%の帯はトレールに入ってからの話
        band = "initial"
    elif distance < lo:
        band = "tight"
    elif distance > hi:
        band = "wide"
    else:
        band = "in"

    notes = []
    if band == "tight":
        notes.append(
            f"現在値から{distance*100:.1f}%——バンド下限{lo*100:.0f}%より浅い。"
            "株価が上がればバンドは戻る。慌てて切り下げない"
        )
    elif band == "wide":
        notes.append(f"現在値から{distance*100:.1f}%——{hi*100:.0f}%より深い。利益を返しすぎ")
    if h.get("volatile"):
        notes.append("値動きが荒い銘柄。計算値ではなく直近の押し安値の下を優先する")

    return Ladder(
        code=h["code"], name=h["name"], cost=cost, price=price, qty=qty, gain=g,
        step=step, ladder_stop=target, current_stop=cur, recommended=recommended,
        distance=distance, band=band,
        locked=(cur - cost) * qty if cur is not None else None,
        locked_after=(recommended - cost) * qty if recommended is not None else None,
        notes=notes,
    )


def ladder_table(store: Store) -> list[Ladder]:
    return [ladder_for(h) for h in store.holdings]


def ladder_preview(h: dict) -> list[tuple]:
    """「株価がここまで来たら、逆指値はここ」を先に計算しておく表。"""
    cost = h["cost"]
    rows = []
    for threshold, fraction, label in sorted(config.R10_LADDER):
        trigger = cost * (1 + threshold)
        stop = tick_floor(cost + (trigger - cost) * fraction)
        rows.append((label, trigger, stop, (trigger - stop) / trigger))
    return rows


# ── ⑫ 総リスク上限 ─────────────────────────────────────

@dataclass
class RiskLine:
    code: str
    name: str
    qty: int
    cost: float
    stop: float | None
    pl: float | None        # 発動したときの損益。None = 逆指値なし
    counted: bool           # ⑫の合計に含めるか
    reason: str = ""


@dataclass
class RiskReport:
    lines: list
    total: float            # 全逆指値が同時発動したときの合計損益
    equity: float
    cap: float              # 総資産の6%
    headroom: float         # あと何円リスクを取れるか
    uncovered: list         # 逆指値が無い(⑨違反の)銘柄
    excluded: list          # 触らない枠。意図的に除外

    @property
    def pct(self) -> float:
        return abs(self.total) / self.equity if self.equity else 0.0

    @property
    def over_cap(self) -> bool:
        return self.total < -self.cap


def total_risk(store: Store) -> RiskReport:
    """⑫「全部外れたらいくら失うか」。触らない枠は逆指値を置かないので除外する。"""
    lines, uncovered, excluded = [], [], []
    total = 0.0
    for h in store.holdings:
        sp = stop_price(h)
        if not needs_stop(h):
            lines.append(RiskLine(h["code"], h["name"], h["qty"], h["cost"], sp, None,
                                  False, "触らない枠(逆指値なし・論理で撤退)"))
            excluded.append(h)
            continue
        if sp is None:
            lines.append(RiskLine(h["code"], h["name"], h["qty"], h["cost"], None, None,
                                  False, "逆指値なし——⑨違反"))
            uncovered.append(h)
            continue
        pl = (sp - h["cost"]) * h["qty"]
        total += pl
        lines.append(RiskLine(h["code"], h["name"], h["qty"], h["cost"], sp, pl, True))

    lines.sort(key=lambda r: (r.pl is None, r.pl or 0))
    equity = store.equity()
    cap = equity * config.R12_TOTAL_RISK_MAX
    return RiskReport(lines, total, equity, cap, cap + total, uncovered, excluded)


# ── ④⑤ サイズ ─────────────────────────────────────────

def size_check(store: Store, code: str, name: str, qty: int, price: float,
               stop: float | None, frame: str) -> list[Finding]:
    """買う前のサイズ判定。⑤(失う額)が本命で、④(使う額)はその代わりの上限。"""
    out = []
    equity = store.equity()
    if equity <= 0:
        return [Finding("yellow", "④⑤", code, name, "口座資産が未設定。`kabu account --cash` を先に")]

    amount = qty * price
    existing = store.find(code)
    total_amount = amount + (existing["qty"] * existing["cost"] if existing else 0)

    # ⑤ 1回で失う額を総資産の1.5%に固定する(損切りが置けるならこちらを優先)
    if stop is not None:
        risk = (price - stop) * qty
        limit = equity * config.R5_RISK_PER_TRADE
        pct = risk / equity
        if risk > limit:
            shares = int(limit / (price - stop)) if price > stop else 0
            out.append(Finding(
                "red", "⑤", code, name,
                f"1回のリスク {risk:,.0f}円({pct*100:.2f}%)が上限 {limit:,.0f}円(1.5%)を超える",
                f"{shares}株までなら収まる。株数を減らすか、逆指値を上げる",
            ))
        else:
            out.append(Finding(
                "green", "⑤", code, name,
                f"1回のリスク {risk:,.0f}円({pct*100:.2f}%)——上限 {limit:,.0f}円の内側",
            ))
    else:
        # 損切りが置けない/不明確 → ④の金額上限がデフォルトになる
        if frame == "swing" and amount > config.R4_SWING_PROBE_MAX_YEN:
            out.append(Finding("red", "④", code, name,
                               f"スイングの打診買いは{config.R4_SWING_PROBE_MAX_YEN:,}円まで(今回 {amount:,.0f}円)"))
        if frame == "long" and amount > equity * config.R4_LONG_ONE_SHOT:
            out.append(Finding("red", "④", code, name,
                               f"長期枠の1回は総資産の7%={equity*config.R4_LONG_ONE_SHOT:,.0f}円まで(今回 {amount:,.0f}円)"))
        out.append(Finding("yellow", "⑤", code, name,
                           "逆指値が未定。⑤(失う額)で測れないので④の金額上限で判定した",
                           "先に損切りの位置を決める"))

    # ④ 1銘柄の上限15%は常に適用
    single_cap = equity * config.R4_SINGLE_NAME_MAX
    if total_amount > single_cap:
        out.append(Finding("red", "④", code, name,
                           f"1銘柄で {total_amount:,.0f}円=総資産の{total_amount/equity*100:.1f}%。上限15%({single_cap:,.0f}円)超過"))

    # ③-2 触らない枠は「−50%になっても触らずにいられる額」に限る
    if frame == "hands_off":
        cap = equity * config.R3_HANDS_OFF_MAX
        level = "red" if total_amount > cap else "green"
        out.append(Finding(level, "③-2", code, name,
                           f"触らない枠 {total_amount:,.0f}円(総資産の{total_amount/equity*100:.1f}%)。"
                           f"目安上限は3%={cap:,.0f}円",
                           "−50%になっても触らずにいられる額か、買う前に自分に問う" if level == "red" else ""))

    # 現金余力
    if amount > store.cash:
        out.append(Finding("red", "—", code, name,
                           f"現金余力 {store.cash:,.0f}円では {amount:,.0f}円は買えない"))
    return out


# ── ⑥ テーマ集中 ───────────────────────────────────────

def theme_check(store: Store) -> list[Finding]:
    equity = store.equity()
    out = []
    if equity <= 0:
        return out
    for theme, holdings in sorted(store.themes().items()):
        value = sum(h["qty"] * current_price(h) for h in holdings)
        share = value / equity
        names = "・".join(h["name"] for h in holdings)
        if share >= config.R6_THEME_MAX:
            out.append(Finding("red", "⑥", "", theme,
                               f"{theme} が総資産の{share*100:.1f}%({len(holdings)}銘柄: {names})。上限は3〜4割",
                               "一つの出来事で全部同時に効く。減らすか、これ以上足さない"))
        elif share >= config.R6_THEME_WARN:
            out.append(Finding("yellow", "⑥", "", theme,
                               f"{theme} が総資産の{share*100:.1f}%({len(holdings)}銘柄: {names})。3〜4割の帯に入った"))
        elif len(holdings) >= 3 or (len(holdings) >= 2 and share >= 0.15):
            # 金額が上限に届いていなくても、同じ船に乗っている数は事実として出す。
            # 一つの出来事で同時に効く——それが分かっていることが目的
            out.append(Finding("yellow", "⑥", "", theme,
                               f"{theme} に{len(holdings)}銘柄({names})。金額は{share*100:.1f}%だが同じ船に乗っている"))
    return out


# ── ⑮ ピラミッディング ─────────────────────────────────

def pyramid_check(h: dict, add_qty: int) -> list[Finding]:
    out = []
    g = gain_pct(h)
    if g < config.R15_MIN_GAIN:
        out.append(Finding("red", "⑮", h["code"], h["name"],
                           f"含み益 {g*100:+.2f}% は +{config.R15_MIN_GAIN*100:.0f}% 未満。"
                           f"{'下がってからの買い増しはナンピン' if g < 0 else 'ノイズを超えた証拠がまだない'}"))
    adds = h.get("adds", 0)
    if adds >= config.R15_MAX_ADDS:
        out.append(Finding("red", "⑮", h["code"], h["name"],
                           f"追加はすでに{adds}回。上限は{config.R15_MAX_ADDS}回"))
    first_qty = h.get("first_qty") or h["qty"]
    if add_qty > first_qty:
        out.append(Finding("red", "⑮", h["code"], h["name"],
                           f"追加は第1回と同じ株数まで({first_qty}株)。今回{add_qty}株"))
    if not out:
        out.append(Finding("green", "⑮", h["code"], h["name"],
                           f"含み益 {g*100:+.2f}%・追加{adds}回目——条件を満たす"))
    out.append(Finding("yellow", "⑮", h["code"], h["name"],
                       "追加後は逆指値を新しい平均取得単価の下へ引き上げる(追加でリスクを増やさない)"))
    return out


# ── ⑨ 毎朝の逆指値チェック + 全体点検 ──────────────────

def morning_check(store: Store, on: str | None = None) -> list[Finding]:
    """1日の最初のタスク。逆指値の生存・段の到達・バンド・総リスクを一度に見る。"""
    from .store import today
    on = on or today()
    out: list[Finding] = []

    for h in store.holdings:
        code, name = h["code"], h["name"]
        if not needs_stop(h):
            out.append(Finding("green", "③-2", code, name, "触らない枠。逆指値なしが意図どおり"))
            continue
        s = h.get("stop") or {}
        if not s.get("price"):
            out.append(Finding("red", "⑨", code, name, "逆指値が未設定——出口がない",
                               f"`kabu stop {code} <価格>` で入れる"))
            continue
        if not s.get("alive", True):
            out.append(Finding("red", "⑨", code, name, "逆指値が落ちている(注文中→0)",
                               f"再発注して `kabu stop {code} {s['price']:.0f} --alive` で戻す"))
            continue
        expires = s.get("expires")
        if expires and expires <= on:
            out.append(Finding("red", "⑨", code, name,
                               f"逆指値の期限が {expires} で切れている",
                               "期限は「無期限」で入れ直す。GMOクリック証券は期限切れで消えることが多発している"))
        elif expires:
            out.append(Finding("yellow", "⑨", code, name, f"逆指値の期限が {expires}。無期限に直しておく"))
        if s.get("exec") and s["exec"] != "成行":
            out.append(Finding("red", "⑨", code, name,
                               f"執行方法が「{s['exec']}」。指値だとギャップで売れ残る",
                               "必ず成行にする"))

        lad = ladder_for(h)
        if lad.should_raise:
            out.append(Finding("yellow", "⑩", code, name,
                               f"{lad.step}に到達。逆指値 {lad.current_stop:,.0f} → "
                               f"{lad.recommended:,.0f} へ引き上げ("
                               f"確保 {lad.locked:+,.0f} → {lad.locked_after:+,.0f})",
                               f"`kabu stop {code} {lad.recommended:.0f}`"))
        elif lad.band in ("tight", "wide"):
            out.append(Finding("yellow", "⑩", code, name, lad.notes[0] if lad.notes else ""))
        elif lad.band == "initial":
            out.append(Finding("green", "⑨", code, name,
                               f"逆指値 {lad.current_stop:,.0f}(距離 {lad.distance*100:.1f}%)"
                               f"——生存。{lad.step}なのでバンドの対象外"))
        else:
            out.append(Finding("green", "⑨⑩", code, name,
                               f"逆指値 {lad.current_stop:,.0f}(距離 {lad.distance*100:.1f}%)——生存・バンド内"))

    risk = total_risk(store)
    if risk.over_cap:
        out.append(Finding("red", "⑫", "", "総リスク",
                           f"全発動で {risk.total:+,.0f}円(総資産の{risk.pct*100:.2f}%)。上限6%={risk.cap:,.0f}円を超過",
                           "逆指値を引き上げるか、株数を減らす"))
    else:
        out.append(Finding("green", "⑫", "", "総リスク",
                           f"全発動で {risk.total:+,.0f}円(総資産の{risk.pct*100:.2f}%)。"
                           f"上限6%={risk.cap:,.0f}円まで {risk.headroom:,.0f}円の余地"))

    out.extend(theme_check(store))
    out.extend(prememo_check(store))
    return out


# ── ⑧ 買う前メモの鮮度 ─────────────────────────────────

def prememo_check(store: Store) -> list[Finding]:
    """メモの有効期限は「株価が5%動くか3営業日」。古いメモで買うのはメモなしより危ない。"""
    from datetime import date as _date
    out = []
    for m in store.prememos:
        if m.get("used"):
            continue
        code = m.get("code", "")
        name = m.get("name", code)
        try:
            age = (_date.today() - _date.fromisoformat(m["date"])).days
        except (KeyError, ValueError):
            continue
        h = store.find(code) if code else None
        px = (h and h.get("price")) or m.get("price")
        moved = abs(px - m["price"]) / m["price"] if px and m.get("price") else 0.0
        if age > config.R8_MEMO_DAYS or moved > config.R8_MEMO_MOVE:
            why = []
            if age > config.R8_MEMO_DAYS:
                why.append(f"{age}日前")
            if moved > config.R8_MEMO_MOVE:
                why.append(f"株価が{moved*100:.1f}%動いた")
            out.append(Finding("red", "⑧", code, name,
                               f"買う前メモが期限切れ({'・'.join(why)})",
                               "書き直してから注文する"))
    return out
