---
description: 銘柄を一次資料から調べて、公開レポートに落とす
argument-hint: <銘柄名 or 証券コード>
---

# $ARGUMENTS を調べる

まず手順を出す:

```bash
python3 tool/kabu.py research <コード>
```

## 集める(この順に)

1. **一次資料** — 決算短信と決算説明資料を WebFetch で読む。**質疑応答要旨があれば必ず。**
   ニュースサイトの要約で代用しない
2. **期待側** — 市場コンセンサスと会社計画の差、決算翌日の株価反応
3. **利益の中身** — 一過性(資産売却益・保険金・還付)、市況・為替(在庫受払差・銅価等)、
   受注高、営業CF。数字が揃ったら:
   ```bash
   python3 tool/kabu.py decompose <増益額> --item "資産売却益=400" --item "為替=55" --prior <前年同期>
   ```
4. **株価指標** — 予想PER・PBR・配当利回り・52週レンジ内の位置・同業比較
   (株探 s.kabutan.jp / 松井 finance.matsui.co.jp)
5. **中期経営計画** — 目標値と進捗
6. **ニュース** — 報道・同業・マクロ

## 書く

```bash
python3 tool/kabu.py report new <コード> --name <銘柄名> --sector <セクター> \
  --price <株価> --asof <M/D> --verdict <評価> --summary "<1文>"
```

9つの節の TODO を埋める。**である調**、主語は会社、推奨語(買い/売り/狙い目)は使わない。
ポジション・取得単価・出口・ルールは**一切書かない**(友達に共有するため)。
数値が取れなければ「取得不可」と明記する。推測で埋めない。

「増益◯◯億のうち◯◯億は一過性/市況」まで書けて初めて分解したことになる。

## 出す

```bash
python3 tool/kabu.py portal && python3 tool/kabu.py check
```

検査を通ったら `python3 tool/kabu.py publish --push -m "<銘柄名>のレポートを追加"`。
ライト/ダーク両方でブラウザ確認してから渡す。
