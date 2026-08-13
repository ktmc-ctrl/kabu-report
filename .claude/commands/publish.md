---
description: ポータルを生成して、プライバシー検査を通してから公開する
allowed-tools: Bash(python3 tool/kabu.py:*), Bash(git status:*), Bash(git diff:*)
---

## 検査

!`python3 tool/kabu.py check`

## やること

1. 上の検査に**✗ が1つでもあれば公開しない。** 直してからやり直す
   - メタの不整合 → `data/reports.json`(verdict / sector の登録漏れ)
   - プライバシー → 公開ファイルからその行を消す。私的な話は `private/` へ
   - 文体の指摘 → である調に直す。推奨語は使わない
2. 通ったら公開する:
   ```bash
   python3 tool/kabu.py publish --push -m "<何を更新したか>"
   ```
3. HTML を大きく変えたなら、その前にライト/ダーク両方でブラウザ確認する

`publish` は 生成 → 検査 → commit → push を1本で通す。**検査に落ちたら commit しない。**

$ARGUMENTS
