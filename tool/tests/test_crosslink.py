# -*- coding: utf-8 -*-
"""銘柄名の相互リンク(crosslink)の検査。誤リンクと二重リンクを出さないこと。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kabulib.crosslink import linkify, targets_of  # noqa: E402

LIB = {"stocks": [
    {"code": "8267", "name": "イオン", "file": "8267_aeon.html"},
    {"code": "9432", "name": "NTT", "file": "9432_ntt.html"},
    {"code": "9434", "name": "ソフトバンク", "file": "9434_softbank_kk.html"},
    {"code": "9984", "name": "ソフトバンクG", "file": "9984_softbankg.html"},
    {"code": "6508", "name": "明電舎", "file": "6508_meidensha.html"},
    {"code": "3402", "name": "東レ", "file": "3402_toray.html"},
], "themes": []}
T = targets_of(LIB)


class 相互リンク(unittest.TestCase):
    def test_銘柄名にリンクが付く(self):
        out = linkify("<p>明電舎が増産する。</p>", T, "9432")
        self.assertIn('<a class="xref" href="6508_meidensha.html">明電舎</a>', out)

    def test_コード付きは丸ごと1リンク(self):
        out = linkify("<p>明電舎[6508]と比べる。</p>", T, "9432")
        self.assertIn('>明電舎[6508]</a>', out)
        self.assertEqual(out.count("<a "), 1)

    def test_裸の角括弧コードにもリンク(self):
        out = linkify("<p>重電では[6508]が先行。</p>", T, "9432")
        self.assertIn('>[6508]</a>', out)

    def test_自分自身にはリンクしない(self):
        out = linkify("<p>明電舎の受注。</p>", T, "6508")
        self.assertNotIn("<a", out)

    def test_カタカナ語の途中は誤リンクしない(self):
        out = linkify("<p>リチウムイオン電池を検査する。</p>", T, "6508")
        self.assertNotIn("<a", out)

    def test_英字の連続は誤リンクしない(self):
        out = linkify("<p>NTTデータの案件。</p>", T, "6508")
        self.assertNotIn("<a", out)
        out2 = linkify("<p>通信の本命はNTTである。</p>", T, "6508")
        self.assertIn('>NTT</a>', out2)

    def test_長い表記が優先される(self):
        out = linkify("<p>ソフトバンクGとソフトバンクは別銘柄。</p>", T, "6508")
        self.assertIn('href="9984_softbankg.html">ソフトバンクG</a>', out)
        self.assertIn('href="9434_softbank_kk.html">ソフトバンク</a>', out)

    def test_既存リンクの中は触らない_冪等(self):
        src = "<p>明電舎とダイヘン。</p>"
        once = linkify(src, T, "9432")
        twice = linkify(once, T, "9432")
        self.assertEqual(once, twice)

    def test_タグ属性は触らない(self):
        out = linkify('<img alt="明電舎の工場">', T, "9432")
        self.assertNotIn("<a", out)

    def test_title_とスタイルは触らない(self):
        out = linkify("<title>明電舎</title><style>.a{}</style>", T, "9432")
        self.assertNotIn("<a", out)
