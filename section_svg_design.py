"""Deterministic, parameterized section SVG artwork.

All inputs must be validated against SECTION_SVG_FIELDS before calling render_svg.
The same renderer is used for the editor preview and persisted public images.
"""
from __future__ import annotations

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

    # Preserve the original FriPeri shapes as the aesthetic foundation.
    # These are deliberately large, quiet Bézier surfaces rather than
    # repeated sinusoidal bands competing with foreground content.
    if pattern == "ribbons":
        bend = (frequency - 3) * 12
        lift = (amplitude - 45) * 1.4
        ribbons = [
            (f"M870-140h240C{890+bend:.1f} {30+lift:.1f} "
             f"{1180+bend:.1f} {290+lift:.1f} 1550 290v240"
             f"C{1100-bend:.1f} {590-lift:.1f} "
             f"{615-bend:.1f} {175-lift:.1f} 870-140Z", .72),
            (f"M1060-100h220c45 235 140 345 320 470v280"
             f"C{1235-bend:.1f} {465+lift:.1f} "
             f"{1050-bend:.1f} {220+lift:.1f} 1060-100Z", .68),
            (f"M-130 750C{265+bend:.1f} {620-lift:.1f} "
             f"{330+bend:.1f} {410-lift:.1f} 474 230"
             f"C595 80 718 32 910-30h90"
             f"C756 85 646 157 570 342"
             f"C470 590 348 741 130 830h-260Z", .30),
        ]
        # Third and fourth colors are optional translucent accents, not
        # additional fully opaque stripes.
        for j, (d, alpha) in enumerate(ribbons):
            path(d, colors[j % len(colors)], alpha)
        if len(colors) >= 3:
            path("M1110-100h220C1210 160 1350 340 1540 410v200C1300 500 1100 240 1110-100Z",
                 colors[2], .16)
        if len(colors) >= 4:
            path("M-100 755C220 650 370 370 520 180C410 405 280 690 40 820h-140Z",
                 colors[3], .13)
    elif pattern == "waves":
        bend = (frequency - 3) * 15
        lift = (amplitude - 45) * 1.5
        path((f"M0 500c{275+bend:.1f} {-140-lift:.1f} "
              f"{330+bend:.1f} {145+lift:.1f} 645 66 "
              f"c{303-bend:.1f} {-76-lift:.1f} "
              f"{420-bend:.1f} {-239-lift:.1f} 795-81v275H0Z"),
             colors[0], .60)
        path((f"M0 670c{341+bend:.1f} {79-lift:.1f} "
              f"{476+bend:.1f} {-126-lift:.1f} 757-96 "
              f"c{247-bend:.1f} {26+lift:.1f} "
              f"{415-bend:.1f} {135+lift:.1f} 683 18v168H0Z"),
             colors[1], .68)
        if len(colors) >= 3:
            path("M0 710C300 635 570 735 850 625S1210 655 1440 600v160H0Z",
                 colors[2], .17)
        if len(colors) >= 4:
            path("M0 744C380 690 650 740 990 702S1260 736 1440 690v70H0Z",
                 colors[3], .14)
    elif pattern in ("grid", "mesh"):
        step = max(24, round(640 / density))
        lines = []
        for x in range(step, 1441, step):
            lines.append(f"M{x} 0V760")
        for y in range(step - 20, 761, step):
            lines.append(f"M0 {y}H1440")
        path(" ".join(lines), colors[0], .28 if pattern == "grid" else .20, False)
        if pattern == "mesh":
            # Curved, light meshes should not obscure titles and body text.
            count = max(2, density // 2)
            for j in range(count):
                y = 180 + j * (420 / count)
                path(wave(y, j * .32, amplitude * .8),
                     colors[(j + 1) % len(colors)], .22, False)
        else:
            path("M1440 0v540L820 0Z", colors[1], .16)
            if len(colors) >= 3:
                path("M1440 0v230L1160 0Z", colors[2], .10)
            if len(colors) >= 4:
                path("M0 760v-190L210 760Z", colors[3], .08)
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
