# -*- coding: utf-8 -*-
"""index.html(公開ポータル)の生成。全レポートを内包した1ファイルにする。

data/reports.json だけを見て組み立てる。不整合があれば生成せずに落とす——
「タイルが黙って消える」より、ビルドが止まる方がいい。
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import config
from .reports import BODY_RE, Library, ReportError
from .theme import BASE_CSS, PORTAL_CSS


def _body_of(path: Path) -> str:
    m = BODY_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        raise ReportError(f"{path.name}: <body> が見つからない。")
    return m.group(1).strip()


def _tile(lib: Library, s: dict, show_sector: bool) -> str:
    vc = lib.bucket_class(s["verdict"])
    chip = (f'<span class="secchip">{html.escape(s["sector"])}</span>' if show_sector
            else f'<span class="vb {vc}">{html.escape(s["verdict"])}</span>')
    haystack = " ".join(str(s.get(k, "")) for k in
                        ("code", "name", "ticker", "sector", "verdict", "summary"))
    return f'''      <button class="tile" data-q="{html.escape(haystack)}" onclick="show('{s["code"]}')" aria-label="{html.escape(s["name"])}のレポートを開く">
        <div class="tile-top"><span class="tile-name">{html.escape(s["name"])}</span><span class="tile-code">{html.escape(s.get("ticker") or s["code"])}</span></div>
        <div class="tile-px">{html.escape(str(s.get("price", "—")))}<small>円 ・ {html.escape(str(s.get("asof", "")))}</small></div>
        <div style="margin-top:6px">{chip}</div>
        <div class="tile-sum">{html.escape(s.get("summary", ""))}</div>
        <div class="go">レポートを見る →</div>
      </button>'''


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

    bodies = {t["id"]: _body_of(public_dir / t["file"]) for t in lib.themes}
    bodies.update({s["code"]: _body_of(public_dir / s["file"]) for s in lib.stocks})

    # セクター別
    sections = []
    for sec in lib.sectors:
        tiles = [_tile(lib, s, False) for s in lib.stocks if s["sector"] == sec]
        if not tiles:
            continue
        sections.append(f'    <div class="sector-h" data-group>{html.escape(sec)}</div>\n'
                        f'    <div class="grid">\n' + "\n".join(tiles) + "\n    </div>")
    sector_grid = "\n".join(sections)

    # 割安・割高別
    vsections = []
    for b in lib.buckets:
        tiles = [_tile(lib, s, True) for s in lib.stocks
                 if lib.verdicts.get(s["verdict"]) == b["name"]]
        if not tiles:
            continue
        vsections.append(
            f'    <div class="sector-h val {b["class"]}" data-group>{html.escape(b["name"])} '
            f'<span class="cnt">{len(tiles)}銘柄</span></div>\n'
            f'    <div class="bdesc">{html.escape(b["desc"])}</div>\n'
            f'    <div class="grid">\n' + "\n".join(tiles) + "\n    </div>")
    val_grid = "\n".join(vsections)

    theme_banner = "\n".join(
        f'''  <button class="theme-btn" onclick="show('{t["id"]}')">
    <div class="tt">{html.escape(t["title"])}</div>
    <div class="td">{html.escape(t["desc"])}</div>
    <div class="tg">マップを開く →</div>
  </button>''' for t in lib.themes)

    views = "\n\n".join(
        f'<div class="view" id="v-{s["code"]}">\n{bodies[s["code"]]}\n</div>'
        for s in lib.stocks)
    views += "\n\n" + "\n\n".join(
        f'<div class="view" id="v-{t["id"]}">\n{bodies[t["id"]]}\n</div>' for t in lib.themes)

    names = {s["code"]: f'{s["name"]} [{s.get("ticker") or s["code"]}]' for s in lib.stocks}
    names.update({t["id"]: t["title"] for t in lib.themes})

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

<div class="topbar">
  <button class="btn-back" onclick="show('home')">← 一覧に戻る</button>
  <div class="brand" id="brand">{html.escape(title)}</div>
</div>

<div class="view active" id="v-home">
  <div class="subtitle">決算説明資料・中期経営計画・バリュエーションを1銘柄1ページに整理 ・ 全{n}銘柄{' ・ ' + html.escape(asof) + '時点' if asof else ''}</div>

  <div class="card">
    <div class="body" style="font-size:0.78rem">
      各レポートは<b>会社が公表した決算短信・決算説明資料(一次資料)</b>を読み込んだうえで、①最新決算と利益の質(一過性要因の分解) ②通期見通しと変動要因 ③バリュエーション(PER・PBR・52週レンジ内の位置) ④中期経営計画と今後のテーマ ⑤環境要因(為替・金利・関税) ⑥リスク要因、の順に整理している。決算発表や大きなニュースの都度、更新履歴を残しながら改訂する。<br>
      <span class="note-s">※タイル上のバッジは各レポート内のバリュエーション評価を要約したもの。{config.DISCLAIMER}</span>
    </div>
  </div>

  <div class="theme-lead">特集</div>
{theme_banner}

  <label class="theme-lead" for="q">さがす</label>
  <input class="search" id="q" type="search" placeholder="銘柄名・コード・セクター・キーワード" oninput="filter(this.value)" autocomplete="off">

  <div class="seg" role="tablist" aria-label="グループ分けの切り替え">
    <button id="tab-sector" class="on" role="tab" aria-selected="true" onclick="setGroup('sector')">セクター別</button>
    <button id="tab-val" role="tab" aria-selected="false" onclick="setGroup('val')">割安・割高別</button>
  </div>

  <div id="grp-sector">
{sector_grid}
  </div>

  <div id="grp-val" style="display:none">
{val_grid}
  </div>

  <div class="empty" id="empty">該当なし。</div>

  <div class="foot">
    株価は各レポート記載時点の終値等。バリュエーション評価は予想PER・PBR・52週レンジ内の位置に基づく相対的な整理であり、将来の株価を示唆するものではありません。<br>
    出典は各レポート末尾の「更新履歴」に記載。
  </div>
</div>

{views}

<script>
var NAMES = {json.dumps(names, ensure_ascii=False)};
var HOME = {json.dumps(title, ensure_ascii=False)};
function show(id) {{
  var vs = document.querySelectorAll('.view');
  for (var i=0;i<vs.length;i++) vs[i].classList.remove('active');
  var t = document.getElementById('v-'+id);
  if (!t) {{ t = document.getElementById('v-home'); id='home'; }}
  t.classList.add('active');
  document.body.classList.toggle('detail', id !== 'home');
  document.getElementById('brand').textContent = id==='home' ? HOME : NAMES[id];
  window.scrollTo(0,0);
  if (location.hash !== '#'+id) history.replaceState(null,'','#'+id);
}}
function setGroup(g) {{
  var isSec = (g !== 'val');
  document.getElementById('grp-sector').style.display = isSec ? '' : 'none';
  document.getElementById('grp-val').style.display = isSec ? 'none' : '';
  var ts = document.getElementById('tab-sector'), tv = document.getElementById('tab-val');
  ts.classList.toggle('on', isSec); tv.classList.toggle('on', !isSec);
  ts.setAttribute('aria-selected', isSec); tv.setAttribute('aria-selected', !isSec);
}}
function filter(q) {{
  q = (q||'').trim().toLowerCase();
  var tiles = document.querySelectorAll('#v-home .tile'), hits = 0;
  for (var i=0;i<tiles.length;i++) {{
    var ok = !q || tiles[i].getAttribute('data-q').toLowerCase().indexOf(q) >= 0;
    tiles[i].style.display = ok ? '' : 'none';
    if (ok) hits++;
  }}
  // 中身が全部隠れた見出しと、その直後のグリッドも畳む
  var groups = document.querySelectorAll('#v-home [data-group]');
  for (var j=0;j<groups.length;j++) {{
    var grid = groups[j].nextElementSibling;
    while (grid && !grid.classList.contains('grid')) grid = grid.nextElementSibling;
    var visible = grid ? grid.querySelectorAll('.tile:not([style*="none"])').length : 0;
    groups[j].style.display = visible ? '' : 'none';
    var between = groups[j].nextElementSibling;
    while (between && between !== grid) {{ between.style.display = visible ? '' : 'none'; between = between.nextElementSibling; }}
    if (grid) grid.style.display = visible ? '' : 'none';
  }}
  document.getElementById('empty').style.display = (q && hits===0) ? 'block' : 'none';
}}
window.addEventListener('hashchange', function(){{ show(location.hash.slice(1)||'home'); }});
if (location.hash.length>1) show(location.hash.slice(1));
</script>

</body>
</html>
'''
    out.write_text(doc, encoding="utf-8")
    return out, n
