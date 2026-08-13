# -*- coding: utf-8 -*-
"""private/store.json の読み書き。

このファイルにはポジション情報が入る。**公開リポジトリに commit しない**
(private/ は .gitignore 済み)。書き込みは一時ファイル経由の原子的置換で、
毎回 1 世代前を private/backups/ に残す。
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path

from . import config

SCHEMA_VERSION = 1

EMPTY = {
    "version": SCHEMA_VERSION,
    # realized_opening: 移行前にすでに確定していた損益。個々の約定は残っていないので
    # 1つの数字として持ち、通算の計算にだけ足す(勝率・ペイオフには入れない)
    "account": {"cash": 0, "realized_opening": 0, "snapshots": []},
    "holdings": [],
    "trades": [],
    "journal": [],
    "prememos": [],
    "watchlist": [],
    "earnings": [],
}


class StoreError(Exception):
    """ルール違反や不整合。CLI はこれを捕まえて 1 行で表示する。"""


class Store:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path

    # ── 入出力 ──────────────────────────────────────────
    @classmethod
    def load(cls, path: Path | None = None) -> "Store":
        path = path or config.STORE_FILE
        if not path.exists():
            return cls(json.loads(json.dumps(EMPTY)), path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version", 1)
        if version > SCHEMA_VERSION:
            raise StoreError(
                f"store.json のバージョンが新しすぎる (v{version} > v{SCHEMA_VERSION})。ツールを更新して。"
            )
        for key, default in EMPTY.items():
            data.setdefault(key, json.loads(json.dumps(default)))
        return cls(data, path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            backups = self.path.parent / "backups"
            backups.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.path, backups / f"store-{stamp}.json")
            _prune_backups(backups, keep=30)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)  # ポジション情報なので本人のみ

    # ── 口座 ────────────────────────────────────────────
    @property
    def cash(self) -> float:
        return float(self.data["account"].get("cash", 0))

    @cash.setter
    def cash(self, v: float) -> None:
        self.data["account"]["cash"] = round(float(v))

    def market_value(self) -> float:
        """保有の時価合計。現在値が未設定の銘柄は取得単価で評価する。"""
        return sum(h["qty"] * (h.get("price") or h["cost"]) for h in self.holdings)

    def equity(self) -> float:
        """口座資産 = 保有時価 + 現金余力。⑤⑫のパーセンテージはすべてこれが分母。"""
        return self.market_value() + self.cash

    def realized_total(self) -> float:
        """確定損益の通算。移行前の分(realized_opening)も足す。"""
        return (float(self.data["account"].get("realized_opening") or 0)
                + sum(t.get("pl") or 0 for t in self.trades))

    def unrealized_total(self) -> float:
        return sum(
            h["qty"] * ((h.get("price") or h["cost"]) - h["cost"]) for h in self.holdings
        )

    # ── コレクション ────────────────────────────────────
    @property
    def holdings(self) -> list:
        return self.data["holdings"]

    @property
    def trades(self) -> list:
        return self.data["trades"]

    @property
    def journal(self) -> list:
        return self.data["journal"]

    @property
    def prememos(self) -> list:
        return self.data["prememos"]

    @property
    def watchlist(self) -> list:
        return self.data["watchlist"]

    @property
    def earnings(self) -> list:
        return self.data["earnings"]

    # ── 検索 ────────────────────────────────────────────
    def find(self, key: str) -> dict | None:
        """証券コードでも銘柄名でも引ける。名前は部分一致(1件に絞れたときだけ)。"""
        key = key.strip()
        for h in self.holdings:
            if h["code"] == key:
                return h
        exact = [h for h in self.holdings if h["name"] == key]
        if len(exact) == 1:
            return exact[0]
        partial = [h for h in self.holdings if key and key in h["name"]]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            names = "・".join(h["name"] for h in partial)
            raise StoreError(f"「{key}」は {names} のどれ? 証券コードで指定して。")
        return None

    def must_find(self, key: str) -> dict:
        h = self.find(key)
        if h is None:
            raise StoreError(f"「{key}」は保有にない。`kabu holdings` で確認して。")
        return h

    def themes(self) -> dict:
        """テーマ名 → 保有のリスト。⑥の集中チェックで使う。"""
        out: dict[str, list] = {}
        for h in self.holdings:
            for t in h.get("themes") or []:
                out.setdefault(t, []).append(h)
        return out

    # ── 追記 ────────────────────────────────────────────
    def add_journal(self, title: str, body: str, on: str | None = None,
                    tags: list | None = None, kind: str = "note") -> dict:
        entry = {
            "date": on or today(),
            "kind": kind,
            "title": title,
            "body": body,
            "tags": tags or [],
        }
        self.journal.append(entry)
        self.journal.sort(key=lambda e: e["date"], reverse=True)
        return entry

    def snapshot(self, on: str | None = None) -> dict:
        """その日の口座状態を1件記録する。同じ日付は上書き(大引けの値を正とする)。"""
        snap = {
            "date": on or today(),
            "equity": round(self.equity()),
            "cash": round(self.cash),
            "market_value": round(self.market_value()),
            "unrealized": round(self.unrealized_total()),
            "realized_cum": round(self.realized_total()),
        }
        snaps = self.data["account"]["snapshots"]
        snaps[:] = [s for s in snaps if s["date"] != snap["date"]]
        snaps.append(snap)
        snaps.sort(key=lambda s: s["date"])
        return snap


def today() -> str:
    return date.today().isoformat()


def _prune_backups(directory: Path, keep: int) -> None:
    files = sorted(directory.glob("store-*.json"))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)
