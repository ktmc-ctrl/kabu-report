# 銘柄レポート ライブラリ

日本株の個別銘柄レポートと、テーマ特集をまとめた静的サイトです。

**公開URL**: `https://<ユーザー名>.github.io/kabu-reports/`

---

## 収録内容

- **個別銘柄 27社** — 決算・バリュエーション・中期経営計画を1銘柄1ページに整理
- **特集 3本**
  - 🏢 データセンター 全体マップ — 電力・冷却・回線
  - 🗺 半導体・データセンター 素材サプライチェーン マップ
  - ⚗️ 日本の化学メーカー 比較 — 信越化学はどこに立っているか

トップページ (`index.html`) は全レポートを内包した1ファイル完結版です。
ボタンで銘柄・特集を切り替えられ、「セクター別」「割安・割高別」の2通りで並べ替えできます。

個別ファイルにも直接アクセスできます。

```
https://<ユーザー名>.github.io/kabu-reports/4063_shinetsu.html
https://<ユーザー名>.github.io/kabu-reports/theme_datacenter.html
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

## GitHub Pages で公開する手順

1. GitHub で新しいリポジトリを作る(例: `kabu-reports`、Public)
2. このフォルダを push する

   ```bash
   git remote add origin https://github.com/<ユーザー名>/kabu-reports.git
   git branch -M main
   git push -u origin main
   ```

3. リポジトリの **Settings → Pages** を開く
4. **Source** を `Deploy from a branch`、**Branch** を `main` / `/ (root)` に設定して Save
5. 1〜2分待つと `https://<ユーザー名>.github.io/kabu-reports/` が公開される

`.nojekyll` を置いてあるので、Jekyll による変換は走りません。

### 更新するとき

```bash
git add -A
git commit -m "レポートを更新"
git push
```

push するだけで公開ページに反映されます。

---

## 注意

- 本レポートは公開情報の整理であり、投資勧誘・投資助言を目的とするものではありません
- 投資判断はご自身の責任で行ってください
- リポジトリを Public にすると、URL を知っている人は誰でも閲覧できます
