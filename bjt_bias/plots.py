"""Server-rendered SVG charts for the Lab 04 amplifier workbench.

No JavaScript and no plotting library: the simulator writes plain SVG that
the browser can render at any width.  Every point comes from parsed ngspice
data passed in by the caller.
"""

from __future__ import annotations

import html
import math
from typing import Iterable, Sequence

WIDTH = 760
HEIGHT = 300
MARGIN_LEFT = 64
MARGIN_RIGHT = 18
MARGIN_TOP = 38
MARGIN_BOTTOM = 48

TEXT = "#33261d"
MUTED = "#7b6758"
GRID = "#efdccb"
AXIS = "#c9b09a"
ORANGE = "#e65100"
GREEN = "#1c7a3c"
NAVY = "#9a3d00"


def _fmt(value: float) -> str:
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1e5 or magnitude < 1e-3:
        return f"{value:.2e}"
    return f"{value:.4g}"


def _fmt_frequency(value: float) -> str:
    if value >= 1e9:
        return f"{value / 1e9:g}G"
    if value >= 1e6:
        return f"{value / 1e6:g}M"
    if value >= 1e3:
        return f"{value / 1e3:g}k"
    return f"{value:g}"


def _linear_ticks(low: float, high: float, count: int = 5) -> list[float]:
    if high <= low:
        return [low]
    return [low + (high - low) * index / (count - 1) for index in range(count)]


def _nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Return human-friendly round ticks inside the requested range."""
    if high <= low:
        return [low]
    span = high - low
    raw_step = span / max(count - 1, 1)
    exponent = math.floor(math.log10(raw_step))
    base = 10.0 ** exponent
    step = base
    for multiplier in (1.0, 2.0, 2.5, 5.0, 10.0):
        step = multiplier * base
        if span / step <= count + 1:
            break
    start = math.ceil(low / step) * step
    ticks: list[float] = []
    value = start
    while value <= high + step * 1e-9:
        if value >= low - step * 1e-9:
            ticks.append(round(value, 10))
        value += step
    return ticks or [low, high]


def _log_ticks(low: float, high: float) -> list[float]:
    low = max(low, 1e-12)
    start = math.floor(math.log10(low))
    stop = math.ceil(math.log10(high))
    span = stop - start
    step = 1 if span <= 9 else math.ceil(span / 9)
    ticks = [10.0 ** exponent for exponent in range(start, stop + 1, step)]
    return [tick for tick in ticks if low * 0.999 <= tick <= high * 1.001]


def _project(value: float, low: float, high: float,
             out_low: float, out_high: float) -> float:
    if high == low:
        return (out_low + out_high) / 2.0
    fraction = (value - low) / (high - low)
    return out_low + fraction * (out_high - out_low)


def _path(xs: Sequence[float], ys: Sequence[float], x_log: bool,
          x_low: float, x_high: float, y_low: float, y_high: float) -> str:
    left, right = MARGIN_LEFT, WIDTH - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, HEIGHT - MARGIN_BOTTOM
    parts: list[str] = []
    for x, y in zip(xs, ys):
        if not (math.isfinite(x) and math.isfinite(y)):
            continue
        if x_log:
            if x <= 0:
                continue
            x = math.log10(x)
        if x < x_low or x > x_high or y < y_low or y > y_high:
            continue
        px = _project(x, x_low, x_high, left, right)
        py = _project(y, y_low, y_high, bottom, top)
        parts.append(f"{'M' if not parts else 'L'}{px:.2f},{py:.2f}")
    return " ".join(parts)


def line_chart(*, title: str, x_label: str, y_label: str,
               series: Sequence[dict], x_log: bool = False,
               y_min: float | None = None, y_max: float | None = None,
               y_ticks: Sequence[float] | None = None,
               hlines: Sequence[tuple[float, str, str]] = (),
               vlines: Sequence[tuple[float, str, str]] = (),
               width: int = WIDTH, height: int = HEIGHT) -> str:
    """Return one accessible SVG line chart.

    Each series is ``{"label", "x", "y", "color", "width", "dash"}``.
    ``hlines`` and ``vlines`` are ``(value, label, colour)`` annotations.
    """
    all_x = [value for item in series for value in item["x"]
             if math.isfinite(value) and (not x_log or value > 0)]
    all_y = [value for item in series for value in item["y"]
             if math.isfinite(value)]
    if not all_x or not all_y:
        return ('<svg class="plot-svg" viewBox="0 0 760 120" role="img" '
                'aria-label="No plot data"><text x="20" y="60" '
                f'fill="{MUTED}">No plot data.</text></svg>')

    x_values = [math.log10(value) for value in all_x] if x_log else all_x
    x_low, x_high = min(x_values), max(x_values)
    if x_high == x_low:
        x_high = x_low + 1.0
    y_low = y_min if y_min is not None else min(all_y)
    y_high = y_max if y_max is not None else max(all_y)
    if y_high == y_low:
        y_high = y_low + 1.0
    if y_min is None or y_max is None:
        padding = (y_high - y_low) * 0.08
        y_low = y_low - padding if y_min is None else y_low
        y_high = y_high + padding if y_max is None else y_high

    left, right = MARGIN_LEFT, width - MARGIN_RIGHT
    top, bottom = MARGIN_TOP, height - MARGIN_BOTTOM

    def px(value: float) -> float:
        projected = math.log10(value) if x_log else value
        return _project(projected, x_low, x_high, left, right)

    def py(value: float) -> float:
        return _project(value, y_low, y_high, bottom, top)

    parts = [
        f'<svg class="plot-svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{html.escape(title)}">',
        f'<title>{html.escape(title)}</title>',
        f'<rect x="{left}" y="{top}" width="{right - left}" '
        f'height="{bottom - top}" fill="#ffffff" stroke="{GRID}"/>',
    ]

    if x_log:
        x_ticks = _log_ticks(10 ** x_low, 10 ** x_high)
    else:
        x_ticks = _nice_ticks(x_low, x_high, 6)
    for tick in x_ticks:
        position = _project(math.log10(tick) if x_log else tick,
                            x_low, x_high, left, right)
        parts.append(f'<line x1="{position:.2f}" y1="{top}" x2="{position:.2f}" '
                     f'y2="{bottom}" stroke="{GRID}"/>')
        label = _fmt_frequency(tick) if x_log else _fmt(tick)
        parts.append(f'<text x="{position:.2f}" y="{bottom + 18}" '
                     f'text-anchor="middle" fill="{MUTED}" font-size="11">'
                     f'{html.escape(label)}</text>')

    ticks_y = list(y_ticks) if y_ticks is not None else _nice_ticks(
        y_low, y_high, 5)
    for tick in ticks_y:
        position = py(tick)
        parts.append(f'<line x1="{left}" y1="{position:.2f}" x2="{right}" '
                     f'y2="{position:.2f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{left - 8}" y="{position + 4:.2f}" '
                     f'text-anchor="end" fill="{MUTED}" font-size="11">'
                     f'{html.escape(_fmt(tick))}</text>')

    for value, label, colour in hlines:
        if not y_low <= value <= y_high:
            continue
        position = py(value)
        parts.append(f'<line x1="{left}" y1="{position:.2f}" x2="{right}" '
                     f'y2="{position:.2f}" stroke="{colour}" stroke-width="1.2" '
                     f'stroke-dasharray="5 4"/>')
        parts.append(f'<text x="{right - 4}" y="{position - 5:.2f}" '
                     f'text-anchor="end" fill="{colour}" font-size="10">'
                     f'{html.escape(label)}</text>')

    for value, label, colour in vlines:
        if value is None or not math.isfinite(value):
            continue
        if x_log and value <= 0:
            continue
        projected = math.log10(value) if x_log else value
        if not x_low <= projected <= x_high:
            continue
        position = _project(projected, x_low, x_high, left, right)
        parts.append(f'<line x1="{position:.2f}" y1="{top}" x2="{position:.2f}" '
                     f'y2="{bottom}" stroke="{colour}" stroke-width="1.2" '
                     f'stroke-dasharray="5 4"/>')
        parts.append(f'<text x="{position + 3:.2f}" y="{top + 12}" '
                     f'fill="{colour}" font-size="10">'
                     f'{html.escape(label)}</text>')

    parts.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" '
                 f'stroke="{AXIS}"/>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" '
                 f'stroke="{AXIS}"/>')
    parts.append(f'<text x="{(left + right) / 2:.1f}" y="{height - 8}" '
                 f'text-anchor="middle" fill="{TEXT}" font-size="12">'
                 f'{html.escape(x_label)}</text>')
    parts.append(f'<text x="14" y="{(top + bottom) / 2:.1f}" fill="{TEXT}" '
                 f'font-size="12" text-anchor="middle" '
                 f'transform="rotate(-90 14 {(top + bottom) / 2:.1f})">'
                 f'{html.escape(y_label)}</text>')
    parts.append(f'<text x="{left}" y="20" fill="{TEXT}" font-size="13" '
                 f'font-weight="600">{html.escape(title)}</text>')

    legend_right = right - 6
    for index, item in enumerate(series):
        colour = item.get("color", ORANGE)
        dash = item.get("dash")
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        label = item.get("label", "")
        text_width = min(max(len(label) * 6.2, 28.0), 150.0)
        text_x = legend_right - text_width
        line_x2 = text_x - 6
        line_x1 = max(line_x2 - 24, left + 4)
        y = top + 16 + index * 16
        parts.append(f'<line x1="{line_x1}" y1="{y}" x2="{line_x2}" '
                     f'y2="{y}" stroke="{colour}" stroke-width="2.4"{dash_attr}/>')
        parts.append(f'<text x="{text_x:.2f}" y="{y + 4}" fill="{TEXT}" '
                     f'font-size="11">{html.escape(label)}</text>')

    for item in series:
        colour = item.get("color", ORANGE)
        dash_attr = f' stroke-dasharray="{item["dash"]}"' if item.get("dash") else ""
        path = _path(item["x"], item["y"], x_log, x_low, x_high, y_low, y_high)
        if path:
            parts.append(f'<path d="{path}" fill="none" stroke="{colour}" '
                         f'stroke-width="{item.get("width", 2.0)}" '
                         f'stroke-linejoin="round"{dash_attr}/>')

    parts.append("</svg>")
    return "".join(parts)


def bode_magnitude_svg(ac) -> str:
    """Magnitude plot with the measured -3 dB reference line and cutoffs."""
    annotations = []
    if ac.f_low_3db_hz is not None:
        annotations.append((ac.f_low_3db_hz, "fL", GREEN))
    if ac.f_high_3db_hz is not None:
        annotations.append((ac.f_high_3db_hz, "fH", GREEN))
    return line_chart(
        title="AC magnitude - real ngspice .ac sweep",
        x_label="Frequency (Hz, log scale)",
        y_label="Gain (dB)",
        x_log=True,
        series=[{"label": "|Vout / Vin|", "x": ac.frequencies_hz,
                 "y": ac.gain_db, "color": ORANGE, "width": 2.2}],
        hlines=[(ac.max_gain_db - 3.0, "-3 dB", GREEN)],
        vlines=annotations,
    )


def bode_phase_svg(ac) -> str:
    """Phase plot with an unwrapped phase axis so no false wrap line appears."""
    return line_chart(
        title="AC phase - real ngspice .ac sweep",
        x_label="Frequency (Hz, log scale)",
        y_label="Phase (degrees)",
        x_log=True,
        series=[{"label": "Phase Vout − Vin", "x": ac.frequencies_hz,
                 "y": ac.phase_deg, "color": NAVY, "width": 2.2}],
        hlines=[(-180.0, "-180° (inversion)", MUTED)],
    )


def transient_svg(tran) -> str:
    """Input and output waveforms from the real .tran run."""
    return line_chart(
        title=(f"Transient - {tran.measured_frequency_hz:g} Hz, "
               f"Vin {tran.vin_amplitude_mv:.3g} mV peak"),
        x_label="Time (ms)",
        y_label="Voltage (mV)",
        series=[
            {"label": "Vin", "x": tran.time_ms, "y": tran.vin_mv,
             "color": MUTED, "width": 1.8, "dash": "5 4"},
            {"label": "Vout", "x": tran.time_ms, "y": tran.vout_mv,
             "color": ORANGE, "width": 2.2},
        ],
        hlines=[(0.0, "0 V", AXIS)],
    )
