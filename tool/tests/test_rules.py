# -*- coding: utf-8 -*-
"""ルール計算のテスト。

期待値は日記(2026/8/13 大引け)で手計算した数字をそのまま使う。
手でやっていたことと同じ答えが出ることが、このツールの唯一の要件。

  python3 -m unittest discover -s tool/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kabulib import config, rules  # noqa: E402
from kabulib.store import Store, StoreError  # noqa: E402
from kabulib import account  # noqa: E402


def holding(code, name, qty, cost, price, stop=None, frame="long", **extra):
    h = {"code": code, "name": name, "qty": qty, "cost": cost, "price": price,
         "frame": frame, "themes": [], "stop": None, "first_qty": qty, "adds": 0}
    if stop is not None:
        h["stop"] = {"price": stop, "kind": "トレール", "alive": True, "exec": "成行",
                     "expires": None, "placed": ""}
    h.update(extra)
    return h


def store_with(holdings, cash=655_247):
    s = Store.load(Path("/nonexistent/store.json"))
    s.holdings[:] = holdings
    s.cash = cash
    return s


# 日記の保有13銘柄(2026/8/13 大引け)
DIARY = [
    holding("7011", "三菱重工業", 200, 3540, 4256, 3894),
    holding("7974", "任天堂", 100, 7087, 8325, 7992),
    holding("3402", "東レ", 300, 1211, 1355, 1293),
    holding("4063", "信越化学工業", 100, 5939, 6378, 5939),
    holding("9984", "ソフトバンクG", 100, 5191, 5575, None, frame="hands_off"),
    holding("5802", "住友電気工業", 200, 2179, 2334.5, 2179),
    holding("7203", "トヨタ自動車", 200, 2896, 2985, 2650),
    holding("8306", "三菱UFJ FG", 300, 3613, 3709, 3425, frame="swing"),
    holding("8031", "三井物産", 100, 4770, 4894, 4300),
    holding("8316", "三井住友FG", 100, 6825, 6969, 6480, frame="swing"),
    holding("6758", "ソニーグループ", 200, 3647, 3700, 3380),
    holding("8267", "イオン", 300, 1385, 1396, 1316, frame="swing"),
    holding("1944", "きんでん", 100, 6943, 6920, 6400),
]


class TestLadder(unittest.TestCase):
    """⑩ トレーリング逆指値(5段ラダー)"""

    def test_三菱重の第4段は日記と同じ4017になる(self):
        # 取得3,540 / 現在4,256(+20.22%)→ +15%段(2/3): 3540 + 716×2/3 = 4,017
        lad = rules.ladder_for(DIARY[0])
        self.assertEqual(lad.step, "第4段 +15%(2/3)")
        self.assertEqual(lad.recommended, 4017)
        self.assertTrue(lad.should_raise)
        self.assertEqual(lad.locked, 70_800)          # 現行3,894での確保
        self.assertEqual(lad.locked_after, 95_400)    # 4,017に上げた後

    def test_段の分数(self):
        cost, price = 1000.0, 1300.0                  # +30% → 第5段(3/4)
        self.assertEqual(rules.ladder_for(holding("x", "x", 100, cost, price)).ladder_stop,
                         1000 + 300 * 0.75)
        for price, fraction in ((1200.0, 2 / 3), (1120.0, 0.5)):
            h = holding("x", "x", 100, cost, price)
            self.assertAlmostEqual(rules.ladder_for(h).ladder_stop,
                                   rules.tick_floor(cost + (price - cost) * fraction))

    def test_第6段と第7段の分数(self):
        # 2026-08-14 改訂: 3/4 で打ち止めだと含み益が伸びるほど距離が開き、
        # +67% あたりで 4〜10% の帯から外れる。+40%→4/5、+60%→5/6 を追加した
        cost = 1000.0
        lad = rules.ladder_for(holding("x", "x", 100, cost, 1450.0))   # +45%
        self.assertEqual(lad.step, "第6段 +40%(4/5)")
        self.assertEqual(lad.ladder_stop, rules.tick_floor(cost + 450 * 0.8))
        lad = rules.ladder_for(holding("x", "x", 100, cost, 1700.0))   # +70%
        self.assertEqual(lad.step, "第7段 +60%(5/6)")
        self.assertEqual(lad.ladder_stop, rules.tick_floor(cost + 700 * 5 / 6))
        # 第7段でも距離は帯の中に収まる(10%を超えない)
        self.assertLessEqual(lad.distance, 0.10)

    def test_第2段は建値ちょうど(self):
        lad = rules.ladder_for(holding("x", "x", 100, 1000, 1060))   # +6%
        self.assertEqual(lad.step, "第2段 +5%(建値)")
        self.assertEqual(lad.ladder_stop, 1000)

    def test_段が上がっても現行の逆指値より下には落とさない(self):
        # 任天堂は段の要求値(7,911)より高い7,992が入っている。据え置きが正しい
        lad = rules.ladder_for(DIARY[1])
        self.assertLess(lad.ladder_stop, lad.current_stop)
        self.assertEqual(lad.recommended, 7992)
        self.assertFalse(lad.should_raise)

    def test_バンドの距離が日記と一致する(self):
        self.assertAlmostEqual(rules.ladder_for(DIARY[1]).distance, 0.040, places=3)
        self.assertAlmostEqual(rules.ladder_for(DIARY[2]).distance, 0.046, places=3)

    def test_第1段はバンドの対象外(self):
        # トヨタは+3.07%でまだ第1段。距離11.2%でもバンド違反にはしない
        self.assertEqual(rules.ladder_for(DIARY[6]).band, "initial")

    def test_触らない枠には逆指値を出さない(self):
        lad = rules.ladder_for(DIARY[4])
        self.assertIsNone(lad.recommended)
        self.assertEqual(lad.band, "none")

    def test_呼値は切り捨てる(self):
        # 切り上げると逆指値が浅くなる。1円未満は落とす
        self.assertEqual(rules.tick_floor(4017.33), 4017)
        self.assertEqual(rules.tick_floor(158.97), 158.9)


class TestTotalRisk(unittest.TestCase):
    """⑫ 総リスク上限"""

    def setUp(self):
        self.store = store_with(list(DIARY))

    def test_口座資産が日記と一致する(self):
        self.assertEqual(round(self.store.equity()), 9_154_447)
        self.assertEqual(round(self.store.market_value()), 8_499_200)
        self.assertEqual(round(self.store.unrealized_total()), 508_600)

    def test_合計と余地が日記と一致する(self):
        r = rules.total_risk(self.store)
        self.assertEqual(round(r.total), -129_600)
        self.assertAlmostEqual(r.pct, 0.0142, places=4)
        self.assertFalse(r.over_cap)
        self.assertEqual(round(r.headroom), 419_667)

    def test_触らない枠は合計に入れない(self):
        r = rules.total_risk(self.store)
        self.assertEqual([h["name"] for h in r.excluded], ["ソフトバンクG"])
        self.assertNotIn("ソフトバンクG", [l.name for l in r.lines if l.counted])

    def test_逆指値のない長期枠は未カバーとして出る(self):
        store = store_with([holding("x", "テスト", 100, 1000, 1000)])
        r = rules.total_risk(store)
        self.assertEqual([h["name"] for h in r.uncovered], ["テスト"])

    def test_上限を超えたら違反になる(self):
        store = store_with([holding("x", "テスト", 1000, 1000, 1000, 500)], cash=0)
        self.assertTrue(rules.total_risk(store).over_cap)


class TestMorning(unittest.TestCase):
    """⑨ 毎朝の逆指値チェック"""

    def test_日記の状態では引き上げ1件だけが残る(self):
        found = rules.morning_check(store_with(list(DIARY)))
        self.assertEqual([f for f in found if f.level == "red"], [])
        raises = [f for f in found if f.rule == "⑩" and "引き上げ" in f.message]
        self.assertEqual([f.name for f in raises], ["三菱重工業"])

    def test_逆指値が落ちていたら違反(self):
        h = holding("x", "テスト", 100, 1000, 1000, 950)
        h["stop"]["alive"] = False
        found = rules.morning_check(store_with([h]))
        self.assertTrue(any(f.rule == "⑨" and f.is_violation for f in found))

    def test_期限切れは違反(self):
        h = holding("x", "テスト", 100, 1000, 1000, 950)
        h["stop"]["expires"] = "2020-01-01"
        found = rules.morning_check(store_with([h]))
        self.assertTrue(any("期限" in f.message and f.is_violation for f in found))

    def test_指値執行は違反(self):
        h = holding("x", "テスト", 100, 1000, 1000, 950)
        h["stop"]["exec"] = "指値"
        found = rules.morning_check(store_with([h]))
        self.assertTrue(any("成行" in f.fix for f in found if f.is_violation))


class TestSize(unittest.TestCase):
    """④⑤ サイズ"""

    def setUp(self):
        self.store = store_with(list(DIARY))

    def test_リスクが1_5パーセントを超えたら止める(self):
        # 口座915万 → 上限約13.7万。1株あたり500円のリスクで500株 = 25万
        found = rules.size_check(self.store, "x", "テスト", 500, 5000, 4500, "long")
        self.assertTrue(any(f.rule == "⑤" and f.is_violation for f in found))

    def test_リスクが収まっていれば通る(self):
        found = rules.size_check(self.store, "x", "テスト", 100, 5000, 4800, "long")
        self.assertFalse(any(f.is_violation for f in found))

    def test_1銘柄15パーセント超は違反(self):
        found = rules.size_check(self.store, "x", "テスト", 400, 5000, 4990, "long")
        self.assertTrue(any(f.rule == "④" and "15%" in f.message for f in found))

    def test_触らない枠は3パーセントが目安(self):
        found = rules.size_check(self.store, "x", "テスト", 100, 5000, None, "hands_off")
        self.assertTrue(any(f.rule == "③-2" for f in found))


class TestThemes(unittest.TestCase):
    """⑥ テーマ集中"""

    def test_同じ船に乗っている数を出す(self):
        holdings = list(DIARY)
        for h in holdings:
            if h["name"] in ("三菱重工業", "信越化学工業", "住友電気工業", "きんでん"):
                h["themes"] = ["DC・AI"]
        found = rules.theme_check(store_with(holdings))
        self.assertEqual(len(found), 1)
        self.assertIn("4銘柄", found[0].message)

    def test_4割を超えたら違反(self):
        h = holding("x", "テスト", 1000, 5000, 5000, 4900)
        h["themes"] = ["集中"]
        found = rules.theme_check(store_with([h], cash=0))
        self.assertTrue(found[0].is_violation)


class TestStopWrites(unittest.TestCase):
    """書き込み時にルールを当てる"""

    def setUp(self):
        self.store = store_with([holding("7011", "三菱重工業", 200, 3540, 4256, 3894)])

    def test_切り下げは拒否される(self):
        with self.assertRaises(StoreError) as ctx:
            account.set_stop(self.store, "7011", 3800)
        self.assertIn("切り下げ", str(ctx.exception))

    def test_forceなら通るが日記に残る(self):
        account.set_stop(self.store, "7011", 3800, force=True)
        self.assertEqual(rules.stop_price(self.store.holdings[0]), 3800)
        self.assertIn("押し切った", self.store.journal[0]["body"])

    def test_引き上げは通る(self):
        account.set_stop(self.store, "7011", 4017)
        self.assertEqual(rules.stop_price(self.store.holdings[0]), 4017)

    def test_長期枠の逆指値は外せない(self):
        with self.assertRaises(StoreError):
            account.set_stop(self.store, "7011", None)

    def test_買う前メモがないと買えない(self):
        with self.assertRaises(StoreError) as ctx:
            account.buy(self.store, "9999", 100, 1000, name="テスト")
        self.assertIn("買う前メモ", str(ctx.exception))

    def test_一部売却したら残りの逆指値を要確認に落とす(self):
        result = account.sell(self.store, "7011", 100, 4300)
        self.assertFalse(self.store.holdings[0]["stop"]["alive"])
        self.assertTrue(any("⑯" in w for w in result["warnings"]))

    def test_平均取得単価は丸めずに持つ(self):
        account.buy(self.store, "7011", 100, 4300, skip_memo=True, force=True)
        h = self.store.holdings[0]
        self.assertEqual(h["qty"], 300)
        self.assertAlmostEqual(h["cost"], (200 * 3540 + 100 * 4300) / 300)


class TestPyramid(unittest.TestCase):
    """⑮ ピラミッディング"""

    def test_プラス5パーセント未満は禁止(self):
        h = holding("x", "テスト", 100, 1000, 1020)
        self.assertTrue(any(f.is_violation for f in rules.pyramid_check(h, 100)))

    def test_下がってからの買い増しはナンピンと言う(self):
        h = holding("x", "テスト", 100, 1000, 900)
        msgs = [f.message for f in rules.pyramid_check(h, 100) if f.is_violation]
        self.assertTrue(any("ナンピン" in m for m in msgs))

    def test_条件を満たせば通る(self):
        h = holding("x", "テスト", 100, 1000, 1100)
        self.assertFalse(any(f.is_violation for f in rules.pyramid_check(h, 100)))

    def test_第1回より多い株数は禁止(self):
        h = holding("x", "テスト", 100, 1000, 1100)
        self.assertTrue(any(f.is_violation for f in rules.pyramid_check(h, 200)))


class TestPrememo(unittest.TestCase):
    """⑧ 買う前メモの鮮度"""

    def test_5パーセント動いたら期限切れ(self):
        store = store_with([holding("x", "テスト", 100, 1000, 1100)])
        store.prememos.append({"date": _today(), "code": "x",
                               "name": "テスト", "price": 1000.0, "used": False})
        found = rules.prememo_check(store)
        self.assertTrue(any("株価が" in f.message for f in found))

    def test_使ったメモは見ない(self):
        store = store_with([holding("x", "テスト", 100, 1000, 1100)])
        store.prememos.append({"date": "2020-01-01", "code": "x", "name": "テスト",
                               "price": 1000.0, "used": True})
        self.assertEqual(rules.prememo_check(store), [])


def _today():
    from datetime import date
    return date.today().isoformat()


if __name__ == "__main__":
    unittest.main()


class 最高到達値の記録(unittest.TestCase):
    """9/1追加。「+5%に触れたのに獲れなかった」型を後から実測するための high / peak。"""

    def _store(self):
        s = Store.load(Path("/nonexistent/store.json"))
        s.cash = 10_000_000
        return s

    def test_価格更新で最高値が伸び_下落では戻らない(self):
        from kabulib import account
        s = self._store()
        account.buy(s, "9999", 100, 1000.0, name="テスト", frame="swing",
                    stop=950.0, skip_memo=True, force=True)
        h = s.must_find("9999")
        self.assertEqual(h["high"], 1000.0)
        account.set_prices(s, [("9999", 1080.0)])
        self.assertEqual(h["high"], 1080.0)
        account.set_prices(s, [("9999", 1010.0)])
        self.assertEqual(h["high"], 1080.0)  # 切り下がらない

    def test_決済トレードにpeakが残る(self):
        from kabulib import account
        s = self._store()
        account.buy(s, "9999", 100, 1000.0, name="テスト", frame="swing",
                    stop=950.0, skip_memo=True, force=True)
        account.set_prices(s, [("9999", 1070.0)])   # +7%まで行って
        account.set_prices(s, [("9999", 1000.0)])
        account.sell(s, "9999", 100, 1001.0, reason="建値撤退のテスト")
        t = s.trades[-1]
        self.assertEqual(t["peak"], 1070.0)
        self.assertAlmostEqual(t["peak_pct"], 0.07)
