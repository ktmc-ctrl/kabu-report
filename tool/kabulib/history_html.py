# -*- coding: utf-8 -*-
"""沿革と資産推移。年表と資産カーブを1枚に並べる私的ページ。

入金・確定損益・口座資産の3本を同じ時間軸に重ねると、
「増えた分のどこまでが入金で、どこからが稼ぎか」が目で分かる。
6〜7月は口座資産のスナップショットが無いので、そこは線を引かず欠測として扱う。
"""
from __future__ import annotations

from datetime import date, datetime

from .store import Store
from .theme import DIARY_CSS, document, private_nav

# 入金履歴(GMOの入出金履歴、処理済のみ。中止3件は除外)
DEPOSITS = [
    ("2026-06-11", 2_000_000), ("2026-06-17", 200_000),
    ("2026-06-19", 1_000_000), ("2026-06-19", 1_000_000),
    ("2026-06-26", 500_000), ("2026-06-29", 300_000),
    ("2026-06-30", 450_000), ("2026-07-06", 300_000),
    ("2026-07-07", 850_000), ("2026-07-07", 1_030_000),
    ("2026-07-14", 510_000), ("2026-09-02", 300_000),
    ("2026-09-04", 7_500_000),
]

# 年表。日付・見出し・本文・種別(good/bad/rule/money)
EVENTS = [
    ("2026-06-11", "money", "運用開始", "初回入金200万円。ここが元本の起点。"),
    ("2026-06-22", "good", "最初の決済", "記録に残る最初のトレード。"),
    ("2026-07-21", "good", "7月の山場", "1日6件の決済。7月は29回決済して+452,650円と、回数で稼いだ月。"),
    ("2026-07-27", "bad", "川崎重工で連敗の始まり",
     "この日4件の決済で−26,925円。川重は7月に計−82,900円と、唯一「繰り返し負けた銘柄」になる。"),
    ("2026-07-30", "rule", "フジクラで4つのルールを使い切った",
     "1銘柄で買う前メモ・ラダー・一過性分解・再エントリーが全部回った初のケース。"),
    ("2026-08-06", "rule", "トレーリングへの方針転換",
     "「上がったら利確」から「⑩のラダーに任せる」へ。この日を境に運用の形が変わる。"),
    ("2026-08-12", "good", "通算100万円を超えた日", "含み+454,000円、確定+577,800円。"),
    ("2026-08-14", "rule", "⑩に第6段・第7段を新設",
     "+40%→4/5、+60%→5/6を追加。3/4で打ち止めだと含み益が伸びるほど帯から外れるため。"
     "同日、約定履歴93件と全件突合して確定損益を+582,550円に確定させた。"),
    ("2026-08-17", "good", "総リスクがプラス転換",
     "全逆指値が同時に発動しても損失が出ない状態に(−29,600 → +4,600)。"),
    ("2026-08-18", "money", "3銘柄を決済(+104,850円)", "SBGを5,843円で売却。長期枠+volatileで買い直す方針に。"),
    ("2026-08-19", "bad", "金利ショックの全面安",
     "日経が一時2,000円超安。三菱重(+108,300)と東レ(+24,600)が⑩で発動。"
     "同日、住友電工と三菱商事を④を押し切って購入——「手順を飛ばした買い」の記録が始まる。"),
    ("2026-08-19", "rule", "値動きで長期仮説を判定しない",
     "商社特集の初版で「インフレ耐性は1日しか持たなかった」と書いた誤りを、"
     "本人の指摘で全面改稿。判定は業績への波及経路で行い、値動きは観察として別置きする。"),
    ("2026-08-20", "bad", "銀行2本が寄りの投げで切られた",
     "三井住友FG(−34,700)・三菱UFJ(−56,100)。直後にV字回復し、往復ビンタの形。"
     "スイング枠のため再エントリーはしない。"),
    ("2026-08-25", "bad", "太陽誘電を1日で往復(−48,100円)",
     "レポートで「今は見ない」と結論した当日に購入し、翌朝手仕舞い。"
     "④サイズ・⑧メモ・⑭判定・⑨逆指値の4つを飛ばしていた。"),
    ("2026-08-31", "bad", "住友電工に1,500株を追加(勝負)",
     "「人生一度きりに勝負したい」。1,800株・約394万円は総資産の23.6%で④超過。"
     "逆指値を2,090→1,950へ切り下げ(⑩違反を--forceで記録)。以後この1本が総リスクの大半を占める。"),
    ("2026-09-01", "rule", "⑨の照合を注文履歴タブに変更",
     "GMOの逆指値が消える事故が5件(三菱重・三井物×2・トヨタ・任天堂)。"
     "逆指値の値段まで見える注文履歴タブでの照合を標準にした。"),
    ("2026-09-04", "money", "750万円を入金", "累計入金1,594万円へ。同日に商社ETF(1629)を151万円分取得。"),
    ("2026-09-07", "good", "任天堂を+154,100円で収穫",
     "4月取得の7,087円から5か月、ラダー3段引き上げの末に8,628円で発動。"
     "ピーク+29.1%の利益の75%を持ち帰った、この作業場の最大の勝ち。"),
    ("2026-09-07", "bad", "大勝ちの直後に判断が加速",
     "任天堂の3分後に信越116万、1時間後に川重74万を⑧なしで購入し、川重は4時間で往復。"
     "動機を本人が「SBGを取り逃した悔しさ」「現金で持っているのが嫌」と自認した。"),
    ("2026-09-08", "rule", "テーマタグの誤りを訂正",
     "きんでん・関電工・クラフティアを「DC・AI」から「建設・設備工事」へ。"
     "建設会社の受注の中心は都市再開発・物流・電力インフラで、DCは一部にすぎない。"
     "訂正の結果「DC・AIが36%で帯の上限」という警告は誤報と判明した。"),
    ("2026-09-08", "money", "円高耐性への組み替え",
     "JAL・JR東海・クラフティア・鹿島を新規取得(合計約389万円)。"
     "保有9銘柄、テーマは建設・商社・空運・鉄道・DCへ分散。"),
]

KIND_COLOR = {"good": "var(--pos)", "bad": "var(--neg)",
              "rule": "var(--accent-pink)", "money": "var(--baseline)"}
KIND_LABEL = {"good": "成果", "bad": "痛み", "rule": "仕組み", "money": "資金"}

CSS = """
  .hist .tl { position:relative; margin:6px 0 0 0; padding-left:28px; }
  .hist .tl::before { content:""; position:absolute; left:9px; top:4px; bottom:4px;
                      width:2px; background:var(--border); }
  .hist .ev { position:relative; margin-bottom:16px; }
  .hist .ev::before { content:""; position:absolute; left:-24px; top:5px; width:11px; height:11px;
                      border-radius:50%; border:2px solid var(--surface-0); }
  .hist .ev.good::before { background:var(--pos); }
  .hist .ev.bad::before  { background:var(--neg); }
  .hist .ev.rule::before { background:var(--accent-pink); }
  .hist .ev.money::before{ background:var(--baseline); }
  .hist .ev .when { font-size:0.68rem; color:var(--text-muted); font-weight:700;
                    letter-spacing:0.02em; }
  .hist .ev .what { font-size:0.88rem; font-weight:700; margin:1px 0 3px; }
  .hist .ev .why  { font-size:0.76rem; color:var(--text-secondary); line-height:1.65; }
  .hist .kind { display:inline-block; font-size:0.62rem; font-weight:700; border-radius:5px;
                padding:0 6px; border:1px solid; margin-left:6px; vertical-align:1px; }
  .hist .mon { font-size:0.7rem; color:var(--text-muted); margin:14px 0 8px;
               border-top:1px dashed var(--border); padding-top:10px; font-weight:700; }
  .hist .mon:first-child { border-top:0; padding-top:0; margin-top:0; }
"""


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def _series(store: Store) -> list[dict]:
    """入金・確定損益・口座資産を同じ日付軸に並べる。"""
    dep, run = {}, 0
    for d, a in sorted(DEPOSITS):
        run += a
        dep[d] = run

    real, run = {}, 0.0
    for t in sorted(store.trades, key=lambda x: x["date"]):
        if t.get("pl") is not None:
            run += t["pl"]
        real[t["date"]] = run

    eq = {s["date"]: s["equity"] for s in store.data["account"]["snapshots"]
          if s.get("equity")}
    today = date.today().isoformat()
    eq[today] = store.equity()

    days = sorted(set(list(dep) + list(real) + list(eq)))
    out, cd, cr = [], 0, 0.0
    for d in days:
        cd = dep.get(d, cd)
        cr = real.get(d, cr)
        out.append({"d": d, "dep": cd, "real": cr, "eq": eq.get(d)})
    return out


def _chart(rows: list[dict]) -> str:
    """入金・口座資産・確定損益の3本。横軸は日付を等間隔でなく実日数で取る。"""
    W, H = 760, 300
    L, R, T, B = 62, 14, 14, 30
    x0 = datetime.fromisoformat(rows[0]["d"]).date()
    x1 = datetime.fromisoformat(rows[-1]["d"]).date()
    span = max((x1 - x0).days, 1)
    ymax = max(max(r["dep"] for r in rows),
               max((r["eq"] or 0) for r in rows)) * 1.06

    def px(d: str) -> float:
        n = (datetime.fromisoformat(d).date() - x0).days
        return L + (W - L - R) * n / span

    def py(v: float) -> float:
        return T + (H - T - B) * (1 - v / ymax)

    def path(key: str) -> str:
        pts, started = [], False
        for r in rows:
            v = r.get(key)
            if v is None:
                started = False
                continue
            pts.append(("M" if not started else "L") + f"{px(r['d']):.1f},{py(v):.1f}")
            started = True
        return " ".join(pts)

    grid, labels = [], []
    for i in range(5):
        v = ymax * i / 4
        y = py(v)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" '
                    f'stroke="var(--border)" stroke-width="1"/>')
        labels.append(f'<text x="{L-8}" y="{y+3:.1f}" text-anchor="end" font-size="9" '
                      f'fill="var(--text-muted)">{v/10000:,.0f}万</text>')

    ticks = []
    seen = set()
    for r in rows:
        m = r["d"][:7]
        if m in seen:
            continue
        seen.add(m)
        x = px(r["d"])
        ticks.append(f'<text x="{x:.1f}" y="{H-10}" text-anchor="middle" font-size="9" '
                     f'fill="var(--text-muted)">{int(m[5:7])}月</text>')

    # 入金は面で塗る(元本のかさ)。その上に口座資産の線を重ねる
    area = path("dep")
    if area:
        area_fill = (f'<path d="{area} L{px(rows[-1]["d"]):.1f},{py(0):.1f} '
                     f'L{px(rows[0]["d"]):.1f},{py(0):.1f} Z" '
                     f'fill="var(--baseline)" opacity="0.10"/>')
    else:
        area_fill = ""

    return f"""<div class="chart-wrap"><svg viewBox="0 0 {W} {H}" role="img"
  aria-label="入金・口座資産・確定損益の推移">
  {''.join(grid)}
  {area_fill}
  <path d="{path('dep')}" fill="none" stroke="var(--baseline)" stroke-width="1.6"
        stroke-dasharray="4 3"/>
  <path d="{path('eq')}" fill="none" stroke="var(--pos)" stroke-width="2.4"/>
  <path d="{path('real')}" fill="none" stroke="var(--accent-pink)" stroke-width="1.8"/>
  {''.join(labels)}{''.join(ticks)}
</svg></div>
<div class="legend">
  <span><i style="background:var(--pos)"></i>口座資産</span>
  <span><i style="background:var(--baseline)"></i>累計入金(元本)</span>
  <span><i style="background:var(--accent-pink)"></i>累計確定損益</span>
</div>
<div class="note-s" style="font-size:0.68rem;color:var(--text-muted)">
  ※口座資産は8/12以降のスナップショットのみ。6〜7月は記録がないため線を引いていない。
</div>"""


def _gain_chart(rows: list[dict]) -> str:
    """稼ぎだけを自分のスケールで見る。資産のグラフでは潰れて読めないため。"""
    W, H = 760, 190
    L, R, T, B = 62, 14, 14, 26
    x0 = datetime.fromisoformat(rows[0]["d"]).date()
    x1 = datetime.fromisoformat(rows[-1]["d"]).date()
    span = max((x1 - x0).days, 1)

    vals = [r["real"] for r in rows] + [
        (r["eq"] - r["dep"]) for r in rows if r["eq"] is not None]
    lo, hi = min(vals + [0]), max(vals + [0])
    pad = max((hi - lo) * 0.12, 20_000)
    lo, hi = lo - pad, hi + pad

    def px(d: str) -> float:
        return L + (W - L - R) * (datetime.fromisoformat(d).date() - x0).days / span

    def py(v: float) -> float:
        return T + (H - T - B) * (1 - (v - lo) / (hi - lo))

    def path(fn) -> str:
        pts, started = [], False
        for r in rows:
            v = fn(r)
            if v is None:
                started = False
                continue
            pts.append(("M" if not started else "L") + f"{px(r['d']):.1f},{py(v):.1f}")
            started = True
        return " ".join(pts)

    grid, labels = [], []
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        y = py(v)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" '
                    f'stroke="var(--border)" stroke-width="1"/>')
        labels.append(f'<text x="{L-8}" y="{y+3:.1f}" text-anchor="end" font-size="9" '
                      f'fill="var(--text-muted)">{v/10000:+,.0f}万</text>')
    zero = (f'<line x1="{L}" y1="{py(0):.1f}" x2="{W-R}" y2="{py(0):.1f}" '
            f'stroke="var(--text-muted)" stroke-width="1.2" stroke-dasharray="2 2"/>')

    ticks, seen = [], set()
    for r in rows:
        m = r["d"][:7]
        if m in seen:
            continue
        seen.add(m)
        ticks.append(f'<text x="{px(r["d"]):.1f}" y="{H-8}" text-anchor="middle" '
                     f'font-size="9" fill="var(--text-muted)">{int(m[5:7])}月</text>')

    return f"""<div class="chart-wrap"><svg viewBox="0 0 {W} {H}" role="img"
  aria-label="稼ぎの推移">
  {''.join(grid)}{zero}
  <path d="{path(lambda r: r['real'])}" fill="none" stroke="var(--accent-pink)"
        stroke-width="2.2"/>
  <path d="{path(lambda r: (r['eq'] - r['dep']) if r['eq'] is not None else None)}"
        fill="none" stroke="var(--pos)" stroke-width="2.2" stroke-dasharray="5 3"/>
  {''.join(labels)}{''.join(ticks)}
</svg></div>
<div class="legend">
  <span><i style="background:var(--accent-pink)"></i>累計確定損益(税引前)</span>
  <span><i style="background:var(--pos)"></i>口座資産 − 入金(実際の手残り)</span>
</div>
<div class="note-s" style="font-size:0.68rem;color:var(--text-muted)">
  ※2本の差は、源泉徴収税・含み損益・株式以外(CFD −10万/FX −7万)の合計。
</div>"""


def render(store: Store) -> str:
    rows = _series(store)
    dep = rows[-1]["dep"]
    eq = store.equity()
    gain = eq - dep
    real = rows[-1]["real"]
    unreal = store.unrealized_total()

    tiles = f"""<div class="tiles">
  <div class="tile-k"><div class="label">口座資産</div>
    <div class="value">{_fmt(eq)}円</div>
    <div class="note">保有 {_fmt(store.market_value())} + 現金 {_fmt(store.cash)}</div></div>
  <div class="tile-k"><div class="label">累計入金(元本)</div>
    <div class="value">{_fmt(dep)}円</div>
    <div class="note">{len(DEPOSITS)}回・{rows[0]['d'][5:].replace('-', '/')}から</div></div>
  <div class="tile-k"><div class="label">生涯の稼ぎ</div>
    <div class="value" style="color:{'var(--pos)' if gain >= 0 else 'var(--neg)'}">
      {gain:+,.0f}円</div>
    <div class="note">元本比 {gain/dep*100:+.2f}%</div></div>
  <div class="tile-k"><div class="label">内訳</div>
    <div class="value" style="font-size:1.0rem">確定 {real:+,.0f}</div>
    <div class="note">含み {unreal:+,.0f} / 差額は源泉税と他口座の損失</div></div>
</div>"""

    body = [f'<h1>🗓 沿革と資産推移</h1>', tiles,
            '<div class="card"><h2>資産の推移</h2>', _chart(rows), '</div>',
            '<div class="card"><h2>稼ぎだけを見る</h2>', _gain_chart(rows), '</div>',
            '<div class="card hist"><h2>年表</h2><div class="tl">']

    month = None
    for d, kind, what, why in EVENTS:
        m = d[:7]
        if m != month:
            month = m
            body.append(f'<div class="mon">{int(m[5:7])}月</div>')
        c = KIND_COLOR[kind]
        body.append(
            f'<div class="ev {kind}">'
            f'<div class="when">{d[5:].replace("-", "/")}'
            f'<span class="kind" style="color:{c};border-color:{c}">{KIND_LABEL[kind]}</span></div>'
            f'<div class="what">{what}</div><div class="why">{why}</div></div>')

    body.append('</div></div>')
    body.append(
        '<div class="card"><h2>読み方</h2><div class="body" style="font-size:0.78rem;'
        'line-height:1.75">'
        '灰色の破線と面が<b>入金(元本)</b>、緑が<b>口座資産</b>。'
        'この2本の差が「稼いだ額」で、緑が灰色より上にある限りプラス。'
        'ピンクは<b>累計確定損益</b>で、決済のたびに階段状に上がる。<br><br>'
        '9/4に元本が844万→1,594万へ跳ねているのは750万の入金によるもので、'
        '実力ではない。<b>入金の直後は「稼ぎ」の率が薄まって見える</b>ため、'
        '率だけを見て焦らないこと。<br><br>'
        '年表の色は、<span style="color:var(--pos);font-weight:700">成果</span>・'
        '<span style="color:var(--neg);font-weight:700">痛み</span>・'
        '<span style="color:var(--accent-pink);font-weight:700">仕組み</span>・'
        '<span style="font-weight:700">資金</span>の4種類。'
        '<b>痛みの直後に仕組みが増えている</b>のがこの3か月の形で、'
        'ルールは失敗から1つずつ生まれている。'
        '</div></div>')

    return document("沿革と資産推移", private_nav("history.html") + "\n".join(body),
                    extra_css=DIARY_CSS + CSS)
