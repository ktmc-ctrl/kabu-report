# -*- coding: utf-8 -*-
"""損益レポートの集計。performance.html の材料をここで作る。

perf_html.py は「見せ方」だけを持ち、数字の作り方はこちらに置く。
テストから直接呼べるようにするためでもある(HTML を経由せずに検算できる)。
"""
from __future__ import annotations

import csv
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path

from . import config, rules
from .store import Store

# ⑩の帯。デイトレ(同日)を独立させているのは、⑩がそもそも翌日以降を前提にしているため。
BANDS = [
    ("同日(デイトレ)", lambda d: d == 0),
    ("1〜3日", lambda d: 0 < d <= 3),
    ("4〜10日", lambda d: 3 < d <= 10),
    ("11〜30日", lambda d: 10 < d <= 30),
    ("31日〜", lambda d: d > 30),
]


def _executions_file() -> Path | None:
    """約定履歴 CSV。証券口座から突合したもので、保有期間の計算に要る。

    store.json の trades は「決済の記録」が中心で買いの日付が揃わないため、
    保有期間だけはこの CSV を正とする。無ければ保有期間の分析は出さない。
    """
    found = sorted(config.PRIVATE.glob("executions_*.csv"))
    return found[-1] if found else None


def holding_periods() -> dict | None:
    """保有期間の帯ごとの成績。約定履歴が無ければ None。

    損益は移動平均法(証券会社と同じ)、保有日数は FIFO で数える。
    この2つは別の目的の計算なので、わざと別の方式を使っている。
    """
    path = _executions_file()
    if not path:
        return None

    rows = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["dt"] = datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M")
            r["qty"] = int(r["qty"])
            r["price"] = float(r["price"])
            rows.append(r)
    rows.sort(key=lambda r: r["dt"])

    avg: dict[str, float] = defaultdict(float)
    pos: dict[str, int] = defaultdict(int)
    lots: dict[str, deque] = defaultdict(deque)
    sells = []
    for r in rows:
        c = r["code"]
        if r["side"] == "買":
            avg[c] = (avg[c] * pos[c] + r["price"] * r["qty"]) / (pos[c] + r["qty"])
            pos[c] += r["qty"]
            lots[c].append([r["dt"], r["qty"]])
            continue
        pl = (r["price"] - avg[c]) * r["qty"]
        pos[c] -= r["qty"]
        need, weighted = r["qty"], 0.0
        while need > 0 and lots[c]:
            d0, q = lots[c][0]
            take = min(q, need)
            weighted += (r["dt"].date() - d0.date()).days * take
            q -= take
            need -= take
            if q == 0:
                lots[c].popleft()
            else:
                lots[c][0][1] = q
        sells.append({"date": r["dt"].date(), "name": r["name"], "qty": r["qty"],
                      "pl": pl, "days": weighted / r["qty"]})

    if not sells:
        return None

    out = []
    for label, hit in BANDS:
        g = [s for s in sells if hit(s["days"])]
        if not g:
            continue
        out.append({
            "label": label, "n": len(g),
            "win": sum(1 for s in g if s["pl"] > 0),
            "lose": sum(1 for s in g if s["pl"] < 0),
            "total": sum(s["pl"] for s in g),
            "avg": sum(s["pl"] for s in g) / len(g),
        })
    days = sorted(s["days"] for s in sells)
    return {
        "bands": out,
        "n": len(sells),
        "total": sum(s["pl"] for s in sells),
        "avg_days": sum(days) / len(days),
        "median_days": days[len(days) // 2],
        "source": path.name,
    }


def by_symbol(store: Store) -> list[dict]:
    """銘柄ごとの確定損益。何で勝って何で負けたかを一覧にする。"""
    agg: dict[str, dict] = {}
    for t in store.trades:
        if t.get("pl") is None:
            continue
        a = agg.setdefault(t["code"], {"code": t["code"], "name": t["name"],
                                       "pl": 0.0, "n": 0, "win": 0})
        a["pl"] += t["pl"]
        a["n"] += 1
        if t["pl"] > 0:
            a["win"] += 1
    return sorted(agg.values(), key=lambda a: -a["pl"])


def protection(store: Store) -> dict:
    """含み益のうち、逆指値でいくら確保できているか。

    ⑩を上げる目的そのものなので、達成度を1つの数字で見せる。
    触らない枠は逆指値を置かない設計なので、母数から外して別建てで示す。
    """
    unreal = locked = hands_off = 0.0
    lines = []
    for h in store.holdings:
        u = rules.unrealized(h)
        unreal += u
        if not rules.needs_stop(h):
            hands_off += u
            lines.append({"name": h["name"], "unreal": u, "locked": None})
            continue
        stop = rules.stop_price(h)
        l = (stop - h["cost"]) * h["qty"] if stop is not None else 0.0
        locked += l
        lines.append({"name": h["name"], "unreal": u, "locked": l})
    return {
        "unrealized": unreal, "locked": locked, "open": unreal - locked,
        "hands_off": hands_off,
        "pct": (locked / unreal * 100) if unreal else 0.0,
        "lines": sorted(lines, key=lambda x: -x["unreal"]),
    }


def monthly(store: Store) -> list[tuple[str, float, int]]:
    """月ごとの確定損益。(月, 損益, 決済件数)"""
    agg: dict[str, list] = {}
    for t in store.trades:
        if t.get("pl") is None:
            continue
        m = t["date"][:7]
        a = agg.setdefault(m, [0.0, 0])
        a[0] += t["pl"]
        a[1] += 1
    return [(m, v[0], v[1]) for m, v in sorted(agg.items())]


def equity_curve(store: Store) -> list[dict]:
    """口座の推移。スナップショットのうち値が入っているものだけ。"""
    return [s for s in store.data["account"]["snapshots"]
            if s.get("unrealized") is not None]
