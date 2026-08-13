# 銘柄レポート ライブラリ

日本株の個別銘柄レポートと、テーマ特集をまとめた静的サイトです。

**公開URL**: https://ktmc-ctrl.github.io/kabu-report/

---

## 収録内容

- **個別銘柄 27社** — 決算・バリュエーション・中期経営計画を1銘柄1ページに整理
- **特集 5本**
  - 🏢 データセンター 全体マップ — 電力・冷却・回線
  - ⚡ 電力 全体マップ — 需要・発電・送配電
  - 💳 フィンテック 全体マップ — 決済・証券・銀行・SaaS
  - 🗺 半導体・データセンター 素材サプライチェーン マップ
  - ⚗️ 日本の化学メーカー 比較 — 信越化学はどこに立っているか

トップページ (`index.html`) は全レポートを内包した1ファイル完結版です。
ボタンで銘柄・特集を切り替えられ、「セクター別」「割安・割高別」の2通りで並べ替えでき、
銘柄名・コード・キーワードで絞り込めます。

個別ファイルにも直接アクセスできます。

```
https://ktmc-ctrl.github.io/kabu-report/4063_shinetsu.html
https://ktmc-ctrl.github.io/kabu-report/theme_datacenter.html
```

---

## 各レポートの構成

会社が公表した決算短信・決算説明資料(一次資料)を読み込んだうえで、以下の順に整理しています。

1. 最新決算と利益の質(一過性要因の分解)
2. 通期見通しと変動要因
3. バリュエーション(PER・PBR・52週レンジ内の位置)
4. 中期経営計画と今後のテーマ
5. 環境要因(為替・金利・関税)
6. リスク要因

数値は各ページの「更新履歴」に記載した作成時点のものです。

---

## サイトの作り方

サイトは `tool/` の **kabu** で生成しています。レポートのメタデータは
`data/reports.json` の1箇所にまとまっていて、そこから `index.html` が組み上がります。

```bash
python3 tool/kabu.py report new 6367 --name ダイキン工業 --sector 重工・機械・自動車
python3 tool/kabu.py portal      # index.html を生成
python3 tool/kabu.py check       # 整合性とプライバシーの検査
python3 tool/kabu.py publish --push -m "レポートを更新"
```

`check` は、未登録の評価区分やセクター(タイルが表示されなくなる)、
ポータルに取り込むと効かなくなる CSS の書き方、免責文の欠落を検出します。
検査に落ちると `publish` は commit しません。

コマンドの一覧とデータ構造は [`tool/README.md`](tool/README.md) にあります。

### ローカルで確認する

```bash
python3 -m http.server 8000
# → http://localhost:8000/
```

### テスト

```bash
python3 -m unittest discover -s tool/tests
```

---

## GitHub Pages

`.nojekyll` を置いてあるので Jekyll による変換は走りません。
**Settings → Pages** で Source を `Deploy from a branch`、Branch を `main` / `/ (root)`
にしてあります。push すると数分で反映されます。

---

## 注意

- 本レポートは公開情報の整理であり、投資勧誘・投資助言を目的とするものではありません
- 投資判断はご自身の責任で行ってください
- リポジトリを Public にすると、URL を知っている人は誰でも閲覧できます
