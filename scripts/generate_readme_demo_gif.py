#!/usr/bin/env python3
"""Generate the Cortex README demo GIF — memory fabric flow animation."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "cortex-memory-fabric.gif"

W, H = 960, 420
FRAMES = 48
BG = (8, 12, 18)
ACCENT = (56, 214, 192)
ACCENT2 = (255, 140, 66)
MUTED = (120, 132, 150)
GRID = (22, 30, 42)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in (
        "/System/Library/Fonts/Supplemental/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        path = Path(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _draw_grid(draw: ImageDraw.ImageDraw) -> None:
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=GRID, width=1)


def _node(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    label: str,
    *,
    active: bool = False,
    font: ImageFont.ImageFont,
) -> None:
    x, y = xy
    r = 34
    fill = (18, 28, 38) if not active else (20, 48, 52)
    outline = ACCENT if active else (48, 62, 78)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=3)
    draw.text((x - 28, y - 8), label, fill="white" if active else MUTED, font=font)


def _pulse(t: float) -> float:
    return 0.5 + 0.5 * math.sin(t * math.pi * 2)


def render_frame(i: int) -> Image.Image:
    t = i / FRAMES
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw)

    title_font = _font(28)
    label_font = _font(14)
    small_font = _font(12)

    draw.text((32, 24), "CORTEX", fill=ACCENT, font=title_font)
    draw.text((32, 58), "Organizational memory fabric — decisions, not documents", fill=MUTED, font=small_font)

    nodes = [
        (120, 220, "Slack"),
        (120, 300, "GitHub"),
        (280, 260, "Kafka"),
        (440, 260, "Extract"),
        (600, 220, "Neo4j"),
        (600, 300, "Redis"),
        (800, 260, "Agent"),
    ]

    # Traveling packet along the pipeline
    path_x = [120, 280, 440, 600, 800]
    seg = (t * (len(path_x) - 1)) % (len(path_x) - 1)
    seg_i = int(seg)
    seg_t = seg - seg_i
    px = int(_lerp(path_x[seg_i], path_x[seg_i + 1], seg_t))
    py = 260 + int(8 * math.sin(t * math.pi * 4))

    active_idx = min(seg_i + 1, len(nodes) - 1)

    for idx, (x, y, label) in enumerate(nodes):
        _node(draw, (x, y), label, active=idx == active_idx, font=label_font)

    # Connectors
    pairs = [(0, 2), (1, 2), (2, 3), (3, 4), (3, 5), (4, 6), (5, 6)]
    for a, b in pairs:
        x1, y1, _ = nodes[a]
        x2, y2, _ = nodes[b]
        draw.line([(x1 + 34, y1), (x2 - 34, y2)], fill=(40, 56, 72), width=2)

    # Injection beam to agent on last third of loop
    if t > 0.55:
        alpha = _pulse(t * 3)
        beam_w = int(3 + 4 * alpha)
        draw.line([(640, 260), (766, 260)], fill=ACCENT2, width=beam_w)
        draw.text(
            (650, 180),
            '"Why CockroachDB for payments?"',
            fill=ACCENT2,
            font=small_font,
        )
        draw.text((650, 198), "→ incident, owners, tradeoffs, PR", fill=MUTED, font=small_font)

    # Packet
    draw.ellipse((px - 10, py - 10, px + 10, py + 10), fill=ACCENT, outline="white", width=2)

    # Decision card flash near Neo4j
    if 0.35 < (t % 1.0) < 0.55:
        card_x, card_y = 520, 120
        draw.rounded_rectangle(
            (card_x, card_y, card_x + 220, card_y + 72),
            radius=10,
            fill=(16, 24, 32),
            outline=ACCENT,
            width=2,
        )
        draw.text((card_x + 12, card_y + 10), "DecisionEvent", fill=ACCENT, font=small_font)
        draw.text(
            (card_x + 12, card_y + 30),
            "Migrate payments → CockroachDB",
            fill="white",
            font=small_font,
        )
        draw.text((card_x + 12, card_y + 48), "importance 0.91 · trust 0.84", fill=MUTED, font=small_font)

    draw.text(
        (32, H - 36),
        "capture → score → graph → inject",
        fill=(80, 96, 112),
        font=small_font,
    )
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [render_frame(i) for i in range(FRAMES)]
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
