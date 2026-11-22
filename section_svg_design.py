"""Deterministic, parameterized section SVG artwork.

All inputs must be validated against SECTION_SVG_FIELDS before calling render_svg.
The same renderer is used for the editor preview and persisted public images.
"""
from __future__ import annotations

import html
import math


def render_svg(o: dict) -> str:
    pattern = o["svg_pattern"]
    colors = [o["svg_primary"], o["svg_secondary"], o.get("svg_tertiary", "#e6b768"),
              o.get("svg_quaternary", "#9a88da")][:o.get("svg_colors", 2)]
    opacity = o.get("svg_opacity", 100) / 100
    frequency = o.get("svg_frequency", 3)
    amplitude = o.get("svg_amplitude", 45)
    density = o.get("svg_density", 8)
    scale = o.get("svg_scale", 100) / 100
    rotate = o.get("svg_rotation", 0)
    stroke = o.get("svg_stroke", 3)
    location = o.get("svg_placement", "full")
    positions = {"full": (720, 380), "left": (180, 380), "right": (1260, 380),
                 "top": (720, 130), "bottom": (720, 640),
                 "top_left": (230, 140), "top_right": (1210, 140),
                 "bottom_left": (230, 620), "bottom_right": (1210, 620),
                 "center": (720, 380)}
    cx, cy = positions[location]
    if location not in ("full", "center"):
        scale *= 0.78
    pieces = []

    def path(d, color, opacity_=1, fill=True, extra=""):
        attrs = (f'fill="{color}" stroke="none"' if fill
                 else f'fill="none" stroke="{color}" stroke-width="{stroke}"')
        pieces.append(f'<path d="{d}" {attrs} opacity="{opacity_:.3f}" {extra}/>')

    def wave(y, phase=0, height=None):
        h = amplitude * 3 if height is None else height
        return " ".join((("M" if i == 0 else "L") +
                         f"{i * 12:.1f},{y + math.sin(i / 120 * math.pi * 2 * frequency + phase) * h:.1f}")
                        for i in range(121))

    if pattern == "waves":
        for j, color in enumerate(colors):
            y = 380 + (j - (len(colors) - 1) / 2) * (amplitude * 2 + 42)
            d = wave(y, j * 1.15) + " L1440,760 L0,760 Z"
            path(d, color, 0.36 + 0.11 * (j % 3))
    elif pattern == "ribbons":
        for j, color in enumerate(colors):
            y = 180 + j * 95
            high = wave(y, j * 0.75, amplitude * 2.3)
            low = " ".join(f"L{i*12:.1f},{y+72+math.sin(i/120*math.pi*2*frequency+j*.75)*amplitude*2.3:.1f}"
                           for i in range(120, -1, -1))
            path(high + " " + low + " Z", color, .42 + .11 * (j % 3))
    elif pattern in ("grid", "mesh"):
        step = max(15, round(1440 / (density * 4)))
        lines = []
        for x in range(0, 1441, step):
            lines.append(f"M{x} 0V760")
        for y in range(0, 761, step):
            lines.append(f"M0 {y}H1440")
        path(" ".join(lines), colors[0], .54 if pattern == "grid" else .28, False)
        if pattern == "mesh":
            for j in range(1, density * 2):
                points = []
                for i in range(0, 1441, 24):
                    yy = 180 + j * (400 / (density * 2)) + math.sin(i / 1440 * math.pi * 2 * frequency + j * .5) * amplitude
                    points.append(("M" if i == 0 else "L") + f"{i},{yy:.1f}")
                path(" ".join(points), colors[(j % len(colors))], .35, False)
        else:
            path("M900 0H1440V540Z", colors[-1], .14)
    elif pattern == "dots":
        for row in range(density * 3):
            for col in range(density * 5):
                x = 45 + col * (1350 / max(1, density * 5 - 1))
                y = 40 + row * (680 / max(1, density * 3 - 1))
                radius = max(1.8, stroke * 1.1 + math.sin((row + col) * .5) * 1.5)
                color = colors[(row + col) % len(colors)]
                pieces.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity=".72"/>')
    elif pattern == "orbits":
        for j in range(max(3, density)):
            rx = 160 + j * (460 / max(3, density))
            ry = 75 + j * (240 / max(3, density))
            pieces.append(f'<ellipse cx="720" cy="380" rx="{rx:.1f}" ry="{ry:.1f}" '
                          f'fill="none" stroke="{colors[j % len(colors)]}" stroke-width="{stroke}" opacity=".55" '
                          f'transform="rotate({(j * 21) % 180} 720 380)"/>')
    elif pattern == "topography":
        for j in range(density * 4):
            y = 65 + j * (650 / max(1, density * 4 - 1))
            path(wave(y, j * .18, amplitude * (0.6 + j / (density * 10))), colors[j % len(colors)], .36, False)
    elif pattern == "diagonals":
        for j in range(density + 3):
            offset = (j - 3) * (1440 / max(4, density))
            path(f"M{offset:.1f} -100 L{offset+170:.1f} -100 L{offset+780:.1f} 860 L{offset+610:.1f} 860 Z",
                 colors[j % len(colors)], .37)

    transform = f'translate({cx} {cy}) rotate({rotate}) scale({scale:.4f}) translate(-720 -380)'
    body = "".join(pieces)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="section-art" viewBox="0 0 1440 760" '
            f'width="1440" height="760" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<g opacity="{opacity:.3f}" transform="{transform}">{body}</g></svg>')
