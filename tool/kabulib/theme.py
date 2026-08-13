# -*- coding: utf-8 -*-
"""HTML の共通スタイル。公開ポータルと私的レポートで同じトークンを使う。

色は dataviz の検証済みパレット(青 #2a78d6 / 赤 #e34948 系)。
ライト/ダークの両方で成立させるため、**色の定義はすべて :root と
prefers-color-scheme の対で書く**。片方にしか無い色を作らない。
"""

BASE_CSS = """
  :root { color-scheme: light dark; }
  .viz-root {
    color-scheme: light;
    --surface-1: #fcfcfb; --surface-2: #f2f1ec; --page: #f9f9f7;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #898781;
    --grid: #e1e0d9; --baseline: #c3c2b7; --border: rgba(11,11,11,0.10);
    --pos: #2a78d6; --neg: #e34948; --alt: #eb6834; --aqua: #1baf7a;
    --good-text: #006300; --warn: #c77f00; --accent-pink: #e87ba4;
    --shadow: 0 1px 2px rgba(11,11,11,0.05), 0 4px 12px rgba(11,11,11,0.06);
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --surface-1: #1a1a19; --surface-2: #232322; --page: #0d0d0d;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #898781;
      --grid: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,0.10);
      --pos: #3987e5; --neg: #e66767; --alt: #d95926; --aqua: #199e70;
      --good-text: #0ca30c; --warn: #e0a030; --accent-pink: #d55181;
      --shadow: 0 1px 2px rgba(0,0,0,0.4), 0 4px 14px rgba(0,0,0,0.35);
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body.viz-root {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page); color: var(--text-primary);
    padding: 16px; max-width: 860px; margin: 0 auto; line-height: 1.65;
    font-variant-numeric: tabular-nums;
    -webkit-text-size-adjust: 100%;
  }
  h1 { font-size: 1.15rem; margin-bottom: 2px; }
  .subtitle { color: var(--text-secondary); font-size: 0.76rem; margin-bottom: 14px; }
  .card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 12px; }
  h2 { font-size: 0.92rem; margin-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
  th { text-align: left; color: var(--text-muted); font-weight: 600; padding: 5px 4px; border-bottom: 1px solid var(--baseline); }
  td { padding: 6px 4px; border-bottom: 1px solid var(--grid); vertical-align: top; }
  th.num, td.num { text-align: right; }
  .up { color: var(--good-text); } .down { color: var(--neg); } .warn { color: var(--warn); }
  .badge { display: inline-block; font-size: 0.66rem; border-radius: 6px; padding: 1px 6px; border: 1px solid var(--border); white-space: nowrap; color: var(--text-muted); }
  .badge.ok { color: var(--good-text); } .badge.ng { color: var(--neg); }
  .body { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.8; }
  .body b { color: var(--text-primary); }
  .note-s { font-size: 0.7rem; color: var(--text-muted); }
  .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
  .px { text-align: right; }
  .px .v { font-size: 1.4rem; font-weight: 700; }
  hr.sep { border: none; border-top: 1px solid var(--grid); margin: 10px 0; }
  .tag { display:inline-block; font-size:0.66rem; border-radius:5px; padding:1px 6px;
         border:1px solid var(--border); background:var(--surface-2); color:var(--text-muted); }
  .note { font-size: 0.72rem; color: var(--text-muted); }
  .scroll-x { overflow-x: auto; }
  /* カードの中の小パネル。複数のレポートで使うので共通側に置く
     (個別ファイルの <head> で定義するとポータルに取り込まれず、そこだけ崩れる) */
  .box { background: var(--surface-2); border-radius: 9px; padding: 11px 12px; margin: 9px 0;
         font-size: 0.76rem; line-height: 1.85; color: var(--text-secondary); }
  .box b { color: var(--text-primary); }
"""

PORTAL_CSS = """
  .topbar { display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
  .brand { font-size:1.15rem; font-weight:700; }
  .btn-back {
    display:none; align-items:center; gap:6px; font-size:0.78rem; font-weight:600;
    background:var(--surface-1); color:var(--text-primary); border:1px solid var(--border);
    border-radius:999px; padding:7px 14px; cursor:pointer; box-shadow:var(--shadow);
    font-family:inherit; transition:transform .12s ease, background .12s ease;
  }
  .btn-back:hover { background:var(--surface-2); }
  .btn-back:active { transform:scale(0.97); }
  body.detail .btn-back { display:inline-flex; }

  .sector-h { font-size:0.72rem; font-weight:700; color:var(--text-muted); letter-spacing:.06em;
              margin:16px 0 8px; padding-bottom:5px; border-bottom:1px solid var(--grid); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(232px,1fr)); gap:10px; }
  .tile {
    display:block; width:100%; text-align:left; cursor:pointer; font-family:inherit;
    background:var(--surface-1); border:1px solid var(--border); border-radius:12px;
    padding:12px 13px; box-shadow:var(--shadow); color:var(--text-primary);
    transition:transform .12s ease, border-color .12s ease, box-shadow .12s ease;
  }
  .tile:hover { transform:translateY(-2px); border-color:var(--pos); }
  .tile:active { transform:translateY(0) scale(0.99); }
  .tile:focus-visible { outline:2px solid var(--pos); outline-offset:2px; }
  .tile-top { display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
  .tile-name { font-size:0.92rem; font-weight:700; }
  .tile-code { font-size:0.66rem; color:var(--text-muted); font-weight:600; }
  .tile-px { font-size:0.98rem; font-weight:700; margin-top:3px; }
  .tile-px small { font-size:0.62rem; color:var(--text-muted); font-weight:500; margin-left:4px; }
  .tile-sum { font-size:0.68rem; color:var(--text-secondary); line-height:1.6; margin-top:6px;
              display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
  .vb { display:inline-block; font-size:0.62rem; font-weight:700; border-radius:5px; padding:1px 6px; border:1px solid; }
  .vb.hi { color:var(--neg); border-color:var(--neg); }
  .vb.lo { color:var(--pos); border-color:var(--pos); }
  .vb.mid { color:var(--text-muted); border-color:var(--baseline); }
  .go { font-size:0.66rem; color:var(--pos); font-weight:700; margin-top:8px; }

  .view { display:none; }
  .view.active { display:block; animation:fade .18s ease; }
  @keyframes fade { from { opacity:0; transform:translateY(4px);} to {opacity:1; transform:none;} }
  @media (prefers-reduced-motion: reduce) { .view.active{animation:none} .tile{transition:none} }
  .theme-btn {
    display:block; width:100%; text-align:left; cursor:pointer; font-family:inherit;
    background:linear-gradient(135deg, var(--surface-1), var(--surface-2));
    border:1px solid var(--pos); border-radius:12px; padding:13px 14px; margin-bottom:14px;
    box-shadow:var(--shadow); color:var(--text-primary);
    transition:transform .12s ease, box-shadow .12s ease;
  }
  .theme-btn:hover { transform:translateY(-2px); }
  .theme-btn:active { transform:translateY(0) scale(0.995); }
  .theme-btn:focus-visible { outline:2px solid var(--pos); outline-offset:2px; }
  .theme-btn .tt { font-size:0.88rem; font-weight:700; }
  .theme-btn .td { font-size:0.7rem; color:var(--text-secondary); line-height:1.6; margin-top:3px; }
  .theme-btn .tg { font-size:0.66rem; color:var(--pos); font-weight:700; margin-top:6px; }
  .theme-lead { font-size:0.66rem; font-weight:700; color:var(--text-muted); letter-spacing:.06em; margin-bottom:7px; }
  .foot { font-size:0.68rem; color:var(--text-muted); margin-top:18px; padding-top:12px; border-top:1px solid var(--grid); }

  .seg { display:inline-flex; background:var(--surface-2); border:1px solid var(--border); border-radius:999px; padding:3px; gap:2px; margin-bottom:4px; }
  .seg button {
    font-family:inherit; font-size:0.74rem; font-weight:600; cursor:pointer;
    background:transparent; color:var(--text-secondary); border:0; border-radius:999px;
    padding:6px 14px; transition:background .12s ease, color .12s ease;
  }
  .seg button.on { background:var(--surface-1); color:var(--text-primary); box-shadow:var(--shadow); }
  .seg button:focus-visible { outline:2px solid var(--pos); outline-offset:2px; }
  .sector-h.val { display:flex; align-items:baseline; gap:8px; font-size:0.82rem; letter-spacing:0; border-bottom-width:2px; }
  .sector-h.val.lo { color:var(--pos); border-bottom-color:var(--pos); }
  .sector-h.val.hi { color:var(--neg); border-bottom-color:var(--neg); }
  .sector-h.val.mid { color:var(--text-secondary); border-bottom-color:var(--baseline); }
  .sector-h.val .cnt { font-size:0.66rem; font-weight:600; color:var(--text-muted); }
  .bdesc { font-size:0.68rem; color:var(--text-muted); margin:-2px 0 9px; }
  .secchip { display:inline-block; font-size:0.62rem; font-weight:600; border-radius:5px; padding:1px 6px;
             border:1px solid var(--border); background:var(--surface-2); color:var(--text-muted); }
  .search { width:100%; padding:9px 12px; border:1px solid var(--baseline); border-radius:10px;
            background:var(--surface-1); color:var(--text-primary); font-size:0.82rem;
            font-family:inherit; margin-bottom:12px; }
  .search:focus-visible { outline:2px solid var(--pos); outline-offset:1px; }
  .empty { font-size:0.76rem; color:var(--text-muted); padding:14px 2px; display:none; }
"""

DIARY_CSS = """
  .tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 12px; }
  .tile-k { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
  .tile-k .label { font-size: 0.7rem; color: var(--text-muted); }
  .tile-k .value { font-size: 1.3rem; font-weight: 700; }
  .tile-k .note { font-size: 0.68rem; color: var(--text-secondary); }
  .kanojo { color: var(--accent-pink); font-weight: 600; }
  .chart-wrap { position: relative; }
  svg { width: 100%; height: auto; display: block; }
  details { margin-top: 4px; }
  details summary { cursor: pointer; font-size: 0.84rem; font-weight: 600; padding: 4px 0; }
  details .body { padding-top: 8px; }
  details ul { margin: 6px 0 0 18px; }
  details li { margin-bottom: 6px; }
  .task { border: 2px solid var(--neg); background: rgba(227,73,72,0.06); }
  .task h2 { color: var(--neg); }
  .ok-row { background: rgba(0,99,0,0.06); }
  .pink-row { background: rgba(232,123,164,0.08); }
  .flag { display:inline-block; font-size:0.66rem; font-weight:700; border-radius:5px;
          padding:1px 6px; border:1px solid; }
  .flag.red { color: var(--neg); border-color: var(--neg); }
  .flag.yellow { color: var(--warn); border-color: var(--warn); }
  .flag.green { color: var(--good-text); border-color: var(--good-text); }
  .private-banner { border: 2px solid var(--accent-pink); border-radius: 12px; padding: 10px 14px;
                    margin-bottom: 14px; font-size: 0.76rem; color: var(--text-secondary); }
  .private-banner b { color: var(--accent-pink); }
"""


def document(title: str, body: str, extra_css: str = "", lang: str = "ja") -> str:
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{BASE_CSS}{extra_css}</style>
</head>
<body class="viz-root">
{body}
</body>
</html>
"""
