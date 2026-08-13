# -*- coding: utf-8 -*-
"""index.html(公開ポータル)の生成。

かつては全レポートを1ファイルに内包していたが、45銘柄を超えて 700KB 台まで
膨らんだため分割した。いまの index.html は**一覧だけ**を持ち、タイルは各銘柄の
個別ページ(リポジトリ直下の <code>XXXX_name.html</code>)への通常リンクになる。
一覧は「特集 / セクター別 / 割安・割高別」のタブ+カテゴリチップで、
一度に1カテゴリぶんだけ表示する(縦に伸びない)。
旧形式の共有リンク(<code>/#6866</code>)は index.html が個別ページへリダイレクトする。

ビルド時に crosslink.py で全レポート本文の銘柄名へ相互リンクも張る。

data/reports.json だけを見て組み立てる。不整合があれば生成せずに落とす——
「タイルが黙って消える」より、ビルドが止まる方がいい。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import config
from .crosslink import apply_all
from .reports import Library, ReportError
from .theme import BASE_CSS, PORTAL_CSS


def _tile(lib: Library, s: dict, show_sector: bool) -> str:
    vc = lib.bucket_class(s["verdict"])
    chip = (f'<span class="secchip">{html.escape(s["sector"])}</span>' if show_sector
            else f'<span class="vb {vc}">{html.escape(s["verdict"])}</span>')
    haystack = " ".join(str(s.get(k, "")) for k in
                        ("code", "name", "ticker", "sector", "verdict", "summary"))
    return f'''      <a class="tile" href="{html.escape(s["file"])}" data-q="{html.escape(haystack)}" aria-label="{html.escape(s["name"])}のレポートを開く">
        <div class="tile-top"><span class="tile-name">{html.escape(s["name"])}</span><span class="tile-code">{html.escape(s.get("ticker") or s["code"])}</span></div>
        <div class="tile-px">{html.escape(str(s.get("price", "—")))}<small>円 ・ {html.escape(str(s.get("asof", "")))}</small></div>
        <div style="margin-top:6px">{chip}</div>
        <div class="tile-sum">{html.escape(s.get("summary", ""))}</div>
        <div class="go">レポートを見る →</div>
      </a>'''


def build(lib: Library | None = None, public_dir: Path | None = None,
          out: Path | None = None) -> tuple[Path, int]:
    lib = lib or Library.load()
    public_dir = public_dir or config.PUBLIC
    out = out or config.PORTAL_OUT

    errors, warnings = lib.validate(public_dir)
    if errors:
        raise ReportError("ポータルを生成できない。先にこれを直す:\n"
                          + "\n".join(f"  ✗ {p}" for p in errors))
    for w in warnings:
        print(f"  ! {w}")

    n_linked = apply_all(lib.data, public_dir)
    if n_linked:
        print(f"  ✓ 銘柄名の相互リンクを更新({n_linked}ファイル)")

    # セクター別(チップで1セクターずつ表示)
    sec_blocks, sec_chips = [], []
    for sec in lib.sectors:
        tiles = [_tile(lib, s, False) for s in lib.stocks if s["sector"] == sec]
        if not tiles:
            continue
        esc = html.escape(sec)
        sec_chips.append(f'<button data-pick="{esc}" onclick="pick(\'sector\', this.dataset.pick)">{esc} <small>{len(tiles)}</small></button>')
        sec_blocks.append(
            f'    <div class="sec-block" data-name="{esc}">\n'
            f'    <div class="sector-h" data-group>{esc}</div>\n'
            f'    <div class="grid">\n' + "\n".join(tiles) + "\n    </div>\n    </div>")
    sector_pane = "\n".join(sec_blocks)
    sector_chips = "\n".join(sec_chips)

    # 割安・割高別(チップで1バケットずつ表示)
    val_blocks, val_chips = [], []
    for b in lib.buckets:
        tiles = [_tile(lib, s, True) for s in lib.stocks
                 if lib.verdicts.get(s["verdict"]) == b["name"]]
        if not tiles:
            continue
        esc = html.escape(b["name"])
        val_chips.append(f'<button data-pick="{esc}" onclick="pick(\'val\', this.dataset.pick)">{esc} <small>{len(tiles)}</small></button>')
        val_blocks.append(
            f'    <div class="sec-block" data-name="{esc}">\n'
            f'    <div class="sector-h val {b["class"]}" data-group>{esc} '
            f'<span class="cnt">{len(tiles)}銘柄</span></div>\n'
            f'    <div class="bdesc">{html.escape(b["desc"])}</div>\n'
            f'    <div class="grid">\n' + "\n".join(tiles) + "\n    </div>\n    </div>")
    val_pane = "\n".join(val_blocks)
    val_chips_html = "\n".join(val_chips)

    theme_banner = "\n".join(
        f'''  <a class="theme-btn" href="{html.escape(t["file"])}">
    <div class="tt">{html.escape(t["title"])}</div>
    <div class="td">{html.escape(t["desc"])}</div>
    <div class="tg">マップを開く →</div>
  </a>''' for t in lib.themes)

    # 旧形式リンク(#6866 / #theme-eff)→ 個別ページへのリダイレクト表
    files = {s["code"]: s["file"] for s in lib.stocks}
    files.update({t["id"]: t["file"] for t in lib.themes})

    title = lib.data.get("title", "📚 銘柄レポート ライブラリ")
    asof = lib.data.get("updated", "")
    n = len(lib.stocks)

    doc = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>銘柄レポート ライブラリ</title>
<style>{BASE_CSS}{PORTAL_CSS}</style>
</head>
<body class="viz-root">
<script>
/* 旧形式の共有リンク(全レポート内包時代の #ハッシュ)を個別ページへ流す */
var FILES = {json.dumps(files, ensure_ascii=False)};
function goLegacy() {{
  var id = location.hash.slice(1);
  if (id && FILES[id]) location.replace(FILES[id]);
}}
goLegacy();
window.addEventListener('hashchange', goLegacy);
</script>

<div class="topbar">
  <div class="brand">{html.escape(title)}</div>
</div>

<div class="subtitle">決算説明資料・中期経営計画・バリュエーションを1銘柄1ページに整理 ・ 全{n}銘柄{' ・ ' + html.escape(asof) + '時点' if asof else ''}</div>

  <label class="theme-lead" for="q" style="margin-top:2px">さがす</label>
  <input class="search" id="q" type="search" placeholder="銘柄名・コード・セクター・キーワード" oninput="filter(this.value)" autocomplete="off">

  <div class="seg" role="tablist" aria-label="表示の切り替え">
    <button id="tab-sector" class="on" role="tab" aria-selected="true" onclick="setGroup('sector')">セクター別</button>
    <button id="tab-val" role="tab" aria-selected="false" onclick="setGroup('val')">割安・割高別</button>
    <button id="tab-themes" role="tab" aria-selected="false" onclick="setGroup('themes')">特集 <small>{len(lib.themes)}</small></button>
  </div>

  <div id="grp-sector">
    <div class="chips" id="chips-sector">
{sector_chips}
    </div>
{sector_pane}
  </div>

  <div id="grp-val" style="display:none">
    <div class="chips" id="chips-val">
{val_chips_html}
    </div>
{val_pane}
  </div>

  <div id="grp-themes" style="display:none">
{theme_banner}
  </div>

  <div class="empty" id="empty">該当なし。</div>

  <div class="card" style="margin-top:16px">
    <div class="body" style="font-size:0.74rem">
      各レポートは<b>会社が公表した決算短信・決算説明資料(一次資料)</b>を読み込んだうえで、①最新決算と利益の質(一過性要因の分解) ②通期見通しと変動要因 ③バリュエーション(PER・PBR・52週レンジ内の位置) ④中期経営計画と今後のテーマ ⑤環境要因 ⑥リスク要因、の順に整理している。決算発表や大きなニュースの都度、更新履歴を残しながら改訂する。<br>
      <span class="note-s">※タイル上のバッジは各レポート内のバリュエーション評価を要約したもの。{config.DISCLAIMER}</span>
    </div>
  </div>

  <div class="foot">
    株価は各レポート記載時点の終値等。バリュエーション評価は予想PER・PBR・52週レンジ内の位置に基づく相対的な整理であり、将来の株価を示唆するものではありません。<br>
    出典は各レポート末尾の「更新履歴」に記載。
  </div>

<script>
var GROUP = 'sector';
var PICK = {{ sector: null, val: null }};

function setGroup(g) {{
  GROUP = g;
  ['sector', 'val', 'themes'].forEach(function (k) {{
    document.getElementById('grp-' + k).style.display = (k === g) ? '' : 'none';
    var t = document.getElementById('tab-' + k);
    t.classList.toggle('on', k === g);
    t.setAttribute('aria-selected', k === g);
  }});
  applyPick();
}}

function pick(group, name) {{
  PICK[group] = name;
  applyPick();
}}

function applyPick() {{
  ['sector', 'val'].forEach(function (group) {{
    var pane = document.getElementById('grp-' + group);
    var chips = document.getElementById('chips-' + group).querySelectorAll('button');
    if (!PICK[group] && chips.length) PICK[group] = chips[0].dataset.pick;
    for (var i = 0; i < chips.length; i++)
      chips[i].classList.toggle('on', chips[i].dataset.pick === PICK[group]);
    var blocks = pane.querySelectorAll('.sec-block');
    for (var j = 0; j < blocks.length; j++)
      blocks[j].style.display = (blocks[j].dataset.name === PICK[group]) ? '' : 'none';
  }});
}}

function filter(q) {{
  q = (q || '').trim().toLowerCase();
  var searching = !!q;
  document.body.classList.toggle('searching', searching);
  if (!searching) {{
    // 検索解除: タイルを全部戻して、タブ+チップの表示に復帰
    var all = document.querySelectorAll('.tile');
    for (var i = 0; i < all.length; i++) all[i].style.display = '';
    document.getElementById('empty').style.display = 'none';
    setGroup(GROUP);
    return;
  }}
  // 検索中: セクター別ペインを全セクター表示にして、その中を絞り込む
  document.getElementById('grp-sector').style.display = '';
  document.getElementById('grp-val').style.display = 'none';
  document.getElementById('grp-themes').style.display = 'none';
  var hits = 0;
  var blocks = document.querySelectorAll('#grp-sector .sec-block');
  for (var b = 0; b < blocks.length; b++) {{
    var tiles = blocks[b].querySelectorAll('.tile'), vis = 0;
    for (var i = 0; i < tiles.length; i++) {{
      var ok = tiles[i].getAttribute('data-q').toLowerCase().indexOf(q) >= 0;
      tiles[i].style.display = ok ? '' : 'none';
      if (ok) vis++;
    }}
    blocks[b].style.display = vis ? '' : 'none';
    hits += vis;
  }}
  document.getElementById('empty').style.display = hits === 0 ? 'block' : 'none';
}}

applyPick();
</script>

</body>
</html>
'''
    out.write_text(doc, encoding="utf-8")
    return out, n
