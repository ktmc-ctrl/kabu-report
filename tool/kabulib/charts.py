# -*- coding: utf-8 -*-
"""依存なしの SVG チャート。ライト/ダークの両方で読めるよう色は CSS 変数で持つ。

軸は 0 を必ず含める(損益なので 0 の位置が意味を持つ)。
系列は 1 本だけ——比較が要るときは並べるのではなく別のカードに分ける。
"""
from __future__ import annotations

import html

W, H = 700, 240
PAD_L, PAD_R, PAD_T, PAD_B = 56, 12, 14, 28


def _nice_bounds(values: list, zero_based: bool = True) -> tuple:
    """キリのいい上下限とステップ。

    zero_based=True は 0 を必ず含める(損益グラフ用。0 からの距離が意味を持つ)。
    False はデータの範囲に合わせる——口座資産のように「水準」ではなく「変化」を
    見たい系列で、0 起点にすると線が真横に潰れて何も読めなくなるため。
    """
    vals = list(values)
    lo = min(vals + [0]) if zero_based else min(vals)
    hi = max(vals + [0]) if zero_based else max(vals)
    if lo == hi:
        return (lo - 1, hi + 1, 1) if not zero_based else (-1, 1, 1)
    if not zero_based:                    # 上下に1割の余白を取って線を潰さない
        pad = (hi - lo) * 0.1
        lo, hi = lo - pad, hi + pad
    span = hi - lo
    raw = span / 4
    mag = 10 ** (len(str(int(abs(raw)))) - 1) if abs(raw) >= 1 else 1
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), 10 * mag)
    return (int(lo // step) * step, (int(hi // step) + 1) * step, step)


def _fmt(v: float) -> str:
    if abs(v) >= 10_000:
        return f"{v/10_000:,.0f}万"
    return f"{v:,.0f}"


def _frame(lo: float, hi: float, step: float) -> tuple:
    """目盛り線・軸ラベル・y 座標を返す。"""
    def y(v: float) -> float:
        return PAD_T + (hi - v) / (hi - lo) * (H - PAD_T - PAD_B)

    grid = []
    t = lo
    while t <= hi + step / 2:
        yy = y(t)
        cls = "baseline" if abs(t) < 1e-9 else "grid"
        grid.append(f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W-PAD_R}" y2="{yy:.1f}" '
                    f'stroke="var(--{cls})" stroke-width="1"/>')
        grid.append(f'<text x="{PAD_L-8}" y="{yy+3.5:.1f}" text-anchor="end" '
                    f'font-size="10" fill="var(--text-muted)">{_fmt(t)}</text>')
        t += step
    return y, "".join(grid)


def line_chart(points: list, label: str = "累計", zero_based: bool = True) -> str:
    """[(ラベル, 値), ...] の折れ線。値は累計を想定。

    zero_based=False にすると、0 ではなくデータの範囲に軸を合わせる。
    """
    if len(points) < 2:
        return '<div class="note-s">データが2点未満。まだ描けない。</div>'
    values = [v for _, v in points]
    lo, hi, step = _nice_bounds(values, zero_based)
    y, grid = _frame(lo, hi, step)
    n = len(points)
    base = y(0) if zero_based else y(lo)   # 面の下辺

    def x(i: int) -> float:
        return PAD_L + i / (n - 1) * (W - PAD_L - PAD_R)

    path = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}"
                    for i, (_, v) in enumerate(points))
    area = (f"M{x(0):.1f},{base:.1f} "
            + " ".join(f"L{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(points))
            + f" L{x(n-1):.1f},{base:.1f} Z")
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.5" fill="var(--pos)">'
        f'<title>{html.escape(str(d))} ・ {v:+,.0f}円</title></circle>'
        for i, (d, v) in enumerate(points))
    ticks = "".join(
        f'<text x="{x(i):.1f}" y="{H-8}" text-anchor="middle" font-size="10" '
        f'fill="var(--text-muted)">{html.escape(str(points[i][0])[5:])}</text>'
        for i in _tick_indices(n))
    return (f'<div class="chart-wrap"><svg viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{html.escape(label)}の推移">{grid}'
            f'<path d="{area}" fill="var(--pos)" opacity="0.10"/>'
            f'<path d="{path}" fill="none" stroke="var(--pos)" stroke-width="2" '
            f'stroke-linejoin="round"/>{dots}{ticks}</svg></div>')


def bar_chart(points: list, label: str = "日別") -> str:
    """[(ラベル, 値), ...] の棒グラフ。プラスとマイナスで色を変える。"""
    if not points:
        return '<div class="note-s">データなし。</div>'
    values = [v for _, v in points]
    lo, hi, step = _nice_bounds(values)
    y, grid = _frame(lo, hi, step)
    n = len(points)
    slot = (W - PAD_L - PAD_R) / n
    bw = min(28, slot * 0.62)

    bars = []
    for i, (d, v) in enumerate(points):
        cx = PAD_L + slot * (i + 0.5)
        y0, y1 = y(0), y(v)
        top, height = min(y0, y1), max(1.0, abs(y1 - y0))
        color = "var(--pos)" if v >= 0 else "var(--neg)"
        bars.append(f'<rect x="{cx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                    f'height="{height:.1f}" rx="2" fill="{color}">'
                    f'<title>{html.escape(str(d))} ・ {v:+,.0f}円</title></rect>')
    ticks = "".join(
        f'<text x="{PAD_L + slot*(i+0.5):.1f}" y="{H-8}" text-anchor="middle" '
        f'font-size="10" fill="var(--text-muted)">{html.escape(str(points[i][0])[5:])}</text>'
        for i in _tick_indices(n))
    return (f'<div class="chart-wrap"><svg viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{html.escape(label)}の確定損益">{grid}{"".join(bars)}{ticks}</svg></div>')


def _tick_indices(n: int, target: int = 8) -> list:
    if n <= target:
        return list(range(n))
    stride = max(1, round(n / target))
    idx = list(range(0, n, stride))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return idx
