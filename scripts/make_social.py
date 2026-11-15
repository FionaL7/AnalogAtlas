"""Build the social/link-preview assets in web/public/ from web/public/favicon.svg
and real index data.

    python scripts/make_social.py

Writes:
    web/public/og.png             1200x630 link-preview card (og:image, twitter:image)
    web/public/apple-touch-icon.png   180x180 iOS home-screen icon
    web/public/favicon.ico        16/32/48 fallback for browsers that ignore favicon.svg

The card's numbers come from analogatlas.sites and data/index, so they can't go
stale silently. The two terrain chips are the real de Gerlache Rim 2 <-> Puna de
Atacama pair from the close study.

Needs: data/ (python scripts/data.py pull all), rsvg-convert and ImageMagick
(brew install librsvg imagemagick). Re-run and commit the PNGs when the numbers
or the mark change.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"
INDEX = ROOT / "data" / "index"

# App tokens (web/src/index.css) converted from oklch to sRGB hex.
BASE = "#0b0f18"
PANEL = "#161b24"
EDGE = "#2e333d"
INK = "#ebeef5"
MUTED = "#9ea5b2"
ACCENT = "#95b5d6"
EARTH_BLUE = "#418ad1"
MARS_RUST = "#d97230"

FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"

# The close-study pair shown on the card.
PAIR_ID = "de-gerlache-puna"
MOON_TILE = "moonsp_4_5"  # the de Gerlache Rim 2 tile (slope 4.6 deg, relief 2.8 km)


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(f"{tool} not found. brew install librsvg imagemagick")
    return path


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def counts() -> dict[str, str]:
    """Headline numbers, read from the same sources the pipeline uses."""
    sys.path.insert(0, str(ROOT))
    import pandas as pd

    from analogatlas import sites

    moon = len(sites.MOON_SITES) + len(sites.MOON_BASE_REGIONS)
    mars = len(sites.MARS_SITES)
    earth = len(pd.read_parquet(INDEX / "earth_meta.parquet"))
    return {
        "moon": f"{moon}",
        "mars": f"{mars}",
        "earth": f"{earth:,}",
    }


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(text: str, width: int, lines: int) -> list[str]:
    """Greedy word wrap, padded to exactly `lines` entries."""
    out: list[str] = [""]
    for word in text.split():
        candidate = f"{out[-1]} {word}".strip()
        if len(candidate) <= width or not out[-1]:
            out[-1] = candidate
        else:
            out.append(word)
    return (out + [""] * lines)[:lines]


def card_svg(tmp: Path) -> str:
    pairs = json.loads((INDEX / "close_study.json").read_text())
    pair = next(p for p in pairs if p["id"] == PAIR_ID)
    n = counts()

    # Earth chip: centre crop of the Sentinel-2 picture, so the chip isn't a
    # letterboxed whole scene.
    earth_src = INDEX / "close_study" / pair["picture"]["file"]
    earth_chip = tmp / "earth_chip.jpg"
    subprocess.run(
        [need("magick"), str(earth_src), "-gravity", "center", "-crop", "70%x70%+0+0",
         "+repage", "-resize", "392x392", "-quality", "88", str(earth_chip)],
        check=True,
    )
    moon_chip = ROOT / "data" / "tiles" / "moon_polar" / "img" / f"{MOON_TILE}.png"

    chip = 196
    gap = 36
    left_x, right_x = 700, 700 + chip + gap
    chip_y = 196

    def stat(x: int, value: str, label: str) -> str:
        return (
            f'<text x="{x}" y="462" font-size="34" font-weight="700" fill="{INK}">{value}</text>'
            f'<text x="{x}" y="488" font-size="15" fill="{MUTED}" letter-spacing="0.6">{label}</text>'
        )

    def chip_block(x: int, href: str, body: str, body_colour: str, place: str) -> str:
        return (
            f'<image x="{x}" y="{chip_y}" width="{chip}" height="{chip}" href="{href}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#chip-{x})"/>'
            f'<rect x="{x}.5" y="{chip_y}.5" width="{chip - 1}" height="{chip - 1}" rx="9" '
            f'fill="none" stroke="{EDGE}"/>'
            f'<text x="{x}" y="{chip_y + chip + 26}" font-size="13" font-weight="700" '
            f'fill="{body_colour}" letter-spacing="1.4">{esc(body.upper())}</text>'
            f'<text x="{x}" y="{chip_y + chip + 48}" font-size="15" fill="{MUTED}">{esc(place)}</text>'
        )

    caption = wrap(pair["headline"], 46, 2)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="1200" height="630" viewBox="0 0 1200 630" font-family="{FONT}">
  <defs>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{EARTH_BLUE}"/>
      <stop offset="1" stop-color="{MARS_RUST}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.78" cy="0.3" r="0.6">
      <stop offset="0" stop-color="{PANEL}" stop-opacity="0.9"/>
      <stop offset="1" stop-color="{BASE}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="chip-{left_x}"><rect x="{left_x}" y="{chip_y}" width="{chip}" height="{chip}" rx="9"/></clipPath>
    <clipPath id="chip-{right_x}"><rect x="{right_x}" y="{chip_y}" width="{chip}" height="{chip}" rx="9"/></clipPath>
  </defs>

  <rect width="1200" height="630" fill="{BASE}"/>
  <rect width="1200" height="630" fill="url(#glow)"/>
  <rect width="1200" height="5" fill="url(#bar)"/>

  <!-- brand row -->
  <g transform="translate(72 62) scale(0.72)">
    <path d="M32 4 A28 28 0 0 0 32 60 Z" fill="{EARTH_BLUE}" transform="translate(-2.5 0)"/>
    <path d="M32 4 A28 28 0 0 1 32 60 Z" fill="{MARS_RUST}" transform="translate(2.5 0)"/>
  </g>
  <text x="128" y="96" font-size="30" font-weight="700" fill="{INK}" letter-spacing="-0.3">AnalogAtlas</text>
  <text x="1128" y="96" font-size="15" fill="{MUTED}" text-anchor="end" letter-spacing="0.8">NASA Space Apps 2026 &#183; Team Mars Needs Maps</text>
  <rect x="72" y="126" width="1056" height="1" fill="{EDGE}"/>

  <!-- headline -->
  <text x="72" y="228" font-size="46" font-weight="700" fill="{INK}" letter-spacing="-0.8">Earth analogs for</text>
  <text x="72" y="282" font-size="46" font-weight="700" fill="{INK}" letter-spacing="-0.8">Moon-base and Mars sites</text>

  <text x="72" y="338" font-size="20" fill="{MUTED}">CLIP finds the candidates. Slope, relief, rock cover,</text>
  <text x="72" y="366" font-size="20" fill="{MUTED}">temperature and radar decide whether the analogy holds</text>
  <text x="72" y="394" font-size="20" fill="{MUTED}">&#8212; and where it breaks.</text>

  <!-- numbers -->
  {stat(72, n["moon"], "Moon sites")}
  {stat(222, n["mars"], "Mars sites")}
  {stat(372, n["earth"], "Earth land tiles")}

  <!-- one measured pair -->
  <text x="{left_x}" y="176" font-size="13" fill="{MUTED}" letter-spacing="1.6">ONE MATCH, MEASURED</text>
  {chip_block(left_x, data_uri(moon_chip), "Moon", ACCENT, pair["site"])}
  {chip_block(right_x, data_uri(earth_chip), "Earth", EARTH_BLUE, pair["earth_name"].split(",")[0])}
  <text x="{left_x + chip + gap // 2}" y="{chip_y + chip // 2 + 12}" font-size="34"
        fill="{INK}" text-anchor="middle">&#8776;</text>
  <text x="{left_x}" y="486" font-size="15" fill="{MUTED}" font-style="italic">{esc(caption[0])}</text>
  <text x="{left_x}" y="508" font-size="15" fill="{MUTED}" font-style="italic">{esc(caption[1])}</text>

  <!-- footer -->
  <rect x="72" y="548" width="1056" height="1" fill="{EDGE}"/>
  <text x="72" y="586" font-size="19" font-weight="700" fill="{ACCENT}">analogatlas.earth</text>
  <text x="1128" y="586" font-size="16" fill="{MUTED}" text-anchor="end">LRO &#183; LOLA &#183; Mini-RF &#183; MOLA &#183; THEMIS &#183; Copernicus DEM &#183; Sentinel-2</text>
</svg>
"""


def main() -> None:
    rsvg, magick = need("rsvg-convert"), need("magick")
    favicon = PUBLIC / "favicon.svg"

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        svg = tmp / "og.svg"
        svg.write_text(card_svg(tmp))
        subprocess.run(
            [rsvg, "-w", "1200", "-h", "630", str(svg), "-o", str(PUBLIC / "og.png")],
            check=True,
        )

        # iOS has no transparency and no rounding of its own here: paint the mark
        # on the app background with a little padding.
        mark = tmp / "mark180.png"
        subprocess.run([rsvg, "-w", "148", "-h", "148", str(favicon), "-o", str(mark)], check=True)
        subprocess.run(
            [magick, str(mark), "-background", BASE, "-gravity", "center", "-extent", "180x180",
             str(PUBLIC / "apple-touch-icon.png")],
            check=True,
        )

        sizes = []
        for px in (16, 32, 48):
            out = tmp / f"fav{px}.png"
            subprocess.run([rsvg, "-w", str(px), "-h", str(px), str(favicon), "-o", str(out)], check=True)
            sizes.append(str(out))
        subprocess.run([magick, *sizes, str(PUBLIC / "favicon.ico")], check=True)

    for name in ("og.png", "apple-touch-icon.png", "favicon.ico"):
        path = PUBLIC / name
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
