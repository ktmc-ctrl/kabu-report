# -*- coding: utf-8 -*-
"""kabu の中身。

  config   ルールの数値の唯一の定義
  store    private/store.json の読み書き
  rules    ⑨⑩⑫④⑤⑥⑧⑮ の判定(判断はしない。数値を返すだけ)
  account  書き込み。ルールを当ててから記録する
  views    端末表示 / 相談用の事実シート
  research 調べる手順と⑰の分解
  reports  公開レポートのメタと検査
  portal   index.html の生成
  privacy  公開物に私的情報が混ざっていないかの検査
  theme    共通CSSの唯一の定義
  charts   依存なしのSVGチャート
  md       必要な分だけの Markdown → HTML
  diary_html / perf_html   私的HTMLの生成
  fmt      端末の書式

入口は tool/kabu.py。
"""
