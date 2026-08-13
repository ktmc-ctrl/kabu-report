---
description: 朝のチェック。逆指値の生存確認と、引き上げが要る段の洗い出し
allowed-tools: Bash(python3 tool/kabu.py:*)
---

!`python3 tool/kabu.py morning`

## やること

1. **「今すぐ直す」があれば、まずそれを伝える。** 他の話は後
2. 逆指値の引き上げが要る銘柄は、**引き上げ後の確保額と総リスクの変化**まで言う
3. みっちーに、証券口座の「(注文中)」を実際に見てもらう。
   **GMOクリック証券の逆指値は期限切れで消えることが多発している。**
   ここに出るのは記録の方で、実物ではない
4. 確認できたら `python3 tool/kabu.py morning --ok <コード> <コード> ...` で生存を記録する
5. 実際に逆指値を動かしたら `python3 tool/kabu.py stop <コード> <価格>` で記録する

$ARGUMENTS
