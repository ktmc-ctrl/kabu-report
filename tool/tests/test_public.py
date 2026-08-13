# -*- coding: utf-8 -*-
"""公開側のテスト——プライバシー検査とレポートの整合性。

ここが通らないうちは公開しない。誤検知(決算分析の普通の文章を私的情報と
言ってしまう)も、見逃し(本当の混入を通してしまう)も、どちらも困る。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kabulib import config, privacy, reports  # noqa: E402

FAKE = Path("dummy.html")


def labels(text: str) -> set:
    return {f.label for f in privacy.scan_text(FAKE, text, style=False)}


class TestPrivacyCatchesLeaks(unittest.TestCase):
    """混入は必ず拾う"""

    def test_逆指値(self):
        self.assertIn("ポジション運用の用語(逆指値)", labels("逆指値を4,017へ引き上げた。"))

    def test_枠の名前(self):
        self.assertIn("内部の枠の名前", labels("この銘柄は長期枠で持っている。"))

    def test_コア9(self):
        self.assertIn("内部の枠の名前(コア9)", labels("コア9の再エントリー条件。"))

    def test_取得単価(self):
        self.assertIn("取得価格に関する記述", labels("取得単価は3,540円。"))

    def test_ルール番号(self):
        self.assertIn("内部ルール番号(丸数字)", labels("ルール⑩により切り下げは禁止。"))
        self.assertIn("内部ルール番号(丸数字)", labels("⑨で逆指値の生存を確認する。"))

    def test_個人名(self):
        self.assertIn("個人名", labels("みっちーの判断で買った。"))

    def test_口座の状態(self):
        self.assertIn("口座の状態", labels("口座資産は9,154,447円。"))

    def test_文脈つきの建値と含み益(self):
        self.assertIn("取得価格に関する記述", labels("逆指値を建値まで引き上げる。"))
        self.assertIn("ポジションの損益", labels("保有株の含み益は+508,600円。"))


class TestPrivacyIgnoresNormalProse(unittest.TestCase):
    """決算分析の普通の文章は通す"""

    def test_箇条書きの丸数字(self):
        self.assertEqual(labels("①次世代市場 ②炭素繊維複合材料 ③水処理"), set())

    def test_商品市況の建値(self):
        self.assertEqual(labels("Q1平均銅建値2,220円/kg・通期前提2,227円/kg。"), set())

    def test_会社の含み益(self):
        self.assertEqual(labels("Arm・OpenAIへの資産集中、含み益に対する税負担。"), set())

    def test_コア営業利益率(self):
        self.assertEqual(labels("営業利益率7.5%(コア9.1%)"), set())

    def test_実際の公開レポートは全部きれい(self):
        dirty = [f for f in privacy.scan() if f.is_leak]
        self.assertEqual(
            [], dirty,
            "公開物に混入がある:\n" + "\n".join(
                f"  {f.path.name}:{f.line} {f.label} — {f.excerpt}" for f in dirty))


class TestLibrary(unittest.TestCase):
    """data/reports.json とレポート本体の対応"""

    def setUp(self):
        self.lib = reports.Library.load()

    def test_実データに不整合がない(self):
        errors, _ = self.lib.validate()
        self.assertEqual([], errors, "\n" + "\n".join(errors))

    def test_未登録のverdictはエラーになる(self):
        # 旧 build_portal.py ではタイルが黙って消えていた失敗
        self.lib.stocks[0] = dict(self.lib.stocks[0], verdict="謎の評価")
        errors, _ = self.lib.validate()
        self.assertTrue(any("verdicts に未登録" in e for e in errors))

    def test_未登録のセクターはエラーになる(self):
        self.lib.stocks[0] = dict(self.lib.stocks[0], sector="新セクター")
        errors, _ = self.lib.validate()
        self.assertTrue(any("sectors に未登録" in e for e in errors))

    def test_verdictから色を引ける(self):
        self.assertEqual(self.lib.bucket_class("割安圏"), "lo")
        self.assertEqual(self.lib.bucket_class("割高圏"), "hi")
        self.assertEqual(self.lib.bucket_class("中立"), "mid")

    def test_全銘柄のverdictが登録済み(self):
        for s in self.lib.stocks:
            self.assertIn(s["verdict"], self.lib.verdicts, s["name"])


class TestReportFileChecks(unittest.TestCase):
    """ポータルに取り込んだときに壊れる書き方を見つける"""

    def _write(self, tmp: Path, head: str = "", body: str = "") -> Path:
        p = tmp / "t.html"
        p.write_text(f"<html><head><style>{head}</style></head>"
                     f"<body class='viz-root'>{body}"
                     f"<div>{config.DISCLAIMER}</div></body></html>", encoding="utf-8")
        return p

    def test_headの独自CSSはエラー(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = self._write(Path(d), head=".mybox { color: red; }")
            errors, _ = reports.check_report_file(p, "テスト")
            self.assertTrue(any("<head>" in e for e in errors))

    def test_headの共通CSSの写しは通す(self):
        import tempfile
        from kabulib.theme import BASE_CSS
        with tempfile.TemporaryDirectory() as d:
            p = self._write(Path(d), head=BASE_CSS)
            errors, _ = reports.check_report_file(p, "テスト")
            self.assertEqual([], errors)

    def test_bodyの要素セレクタはエラー(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = self._write(Path(d), body="<style>table { font-size: 2rem; }</style>")
            errors, _ = reports.check_report_file(p, "テスト")
            self.assertTrue(any("要素セレクタ" in e for e in errors))

    def test_bodyのスコープ済みCSSは通す(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = self._write(Path(d), body="<style>.tmap table { font-size: 2rem; }</style>")
            errors, _ = reports.check_report_file(p, "テスト")
            self.assertEqual([], errors)

    def test_免責がないとエラー(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.html"
            p.write_text("<html><head></head><body>本文</body></html>", encoding="utf-8")
            errors, _ = reports.check_report_file(p, "テスト")
            self.assertTrue(any("免責" in e for e in errors))


class TestGitignore(unittest.TestCase):
    def test_privateは無視されている(self):
        text = (config.ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("private/", text)

    def test_privateがgitの管理下に入っていない(self):
        self.assertEqual([], privacy.tracked_private_files())


if __name__ == "__main__":
    unittest.main()
