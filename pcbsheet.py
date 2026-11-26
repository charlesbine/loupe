#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "pypdfium2"]
# ///
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Charles Bine
"""Contact sheet for PCB review — raytraced 3D views + true layer plots.

Renders a .kicad_pcb into one labeled PNG: 3D top/bottom/iso (kicad-cli's
raytracer, real soldermask + silkscreen + component models) and 2D layer
plots (copper front/back, silk+mask) rasterized from KiCad's own PDF plotter,
so what you see is what the fab gets. Every tile is captioned. Read the PNG.

Usage:
  uv run pcbsheet.py out/blinky.kicad_pcb -o out/blinky_sheet.png
  uv run pcbsheet.py out/blinky.kicad_pcb --dark -o out/blinky_sheet.png
  uv run pcbsheet.py out/blinky.kicad_pcb --no-3d          # layer plots only (faster)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from pcb import kicad_cli  # noqa: E402  (zero-dep sibling)

# ---- style, matched to sheet.py / draftsheet.py
THEMES = {
    "light": {
        "bg": (24, 26, 31),
        "tile_bg": (30, 33, 39),
        "caption_bg": (42, 46, 54),
        "text": (214, 218, 224),
        "dim_text": (150, 156, 166),
        "plot_bg": None,
        "render_bg": "opaque",
    },
    "dark": {
        "bg": (16, 19, 24),
        "tile_bg": (18, 22, 30),
        "caption_bg": (26, 33, 48),
        "text": (224, 232, 242),
        "dim_text": (142, 156, 174),
        "plot_bg": "#12161e",
        "render_bg": "transparent",
    },
}
BG = THEMES["light"]["bg"]
TILE_BG = THEMES["light"]["tile_bg"]
CAPTION_BG = THEMES["light"]["caption_bg"]
TEXT = THEMES["light"]["text"]
DIM_TEXT = THEMES["light"]["dim_text"]
TILE_W, TILE_H = 560, 460
CAPTION_H = 26
HEADER_H = 34


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.strip().lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True)


def render3d(board: Path, out: Path, side: str, rotate: str | None,
             zoom: float, background: str = "opaque") -> bool:
    base = [kicad_cli(), "pcb", "render", board, "-o", out,
            "--width", "1120", "--height", "880", "--quality", "high",
            "--background", background, "--side", side, "--zoom", str(zoom)]
    for cmd in ([base + ["--rotate", rotate]] if rotate else []) + [base]:
        r = run(cmd)
        if r.returncode == 0 and out.exists():
            return True
    sys.stderr.write(f"3D render failed ({side}): {r.stdout}{r.stderr}\n")
    return False


def autocrop_plot(img: Image.Image, bg_color: str | None = None, pad: int = 40) -> Image.Image:
    """Crop a rasterized layer plot to its drawn content against light or dark paper."""
    if bg_color:
        bg_rgb = _hex_to_rgb(bg_color)
        diff = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, bg_rgb))
        mask = diff.convert("L").point(lambda v: 255 if v > 4 else 0)
        bbox = mask.getbbox()
    else:
        bbox = ImageOps.invert(img.convert("L")).getbbox()
    if not bbox:
        return img
    bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
            min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad))
    return img.crop(bbox)


def plot2d(board: Path, layers: str, out_png: Path, mirror: bool = False,
           bg_color: str | None = None) -> bool:
    """kicad-cli PDF plot of `layers` -> autocropped PNG (fab ground truth)."""
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "plot.pdf"
        cmd = [kicad_cli(), "pcb", "export", "pdf", board, "-o", pdf,
               "--layers", layers]
        if bg_color:
            cmd += ["--bg-color", bg_color]
        if mirror:
            cmd.append("--mirror")
        r = run(cmd)
        if r.returncode != 0 or not pdf.exists():
            sys.stderr.write(f"pdf plot failed ({layers}): {r.stdout}{r.stderr}\n")
            return False
        page = pdfium.PdfDocument(str(pdf))[0]
        img = page.render(scale=8.0).to_pil().convert("RGB")
        img = autocrop_plot(img, bg_color=bg_color)
        img.save(out_png)
        return True


def tile(img_path: Path | None, caption: str, hint: str,
         theme: dict | None = None) -> Image.Image:
    th = theme or THEMES["light"]
    t = Image.new("RGB", (TILE_W, TILE_H + CAPTION_H), th["tile_bg"])
    d = ImageDraw.Draw(t)
    if img_path and img_path.exists():
        raw = Image.open(img_path)
        if raw.mode in ("RGBA", "LA") or "transparency" in raw.info:
            rgba = raw.convert("RGBA")
            rgba.thumbnail((TILE_W - 8, TILE_H - 8), Image.LANCZOS)
            bg_patch = Image.new("RGBA", rgba.size, (*th["tile_bg"], 255))
            img = Image.alpha_composite(bg_patch, rgba).convert("RGB")
        else:
            img = raw.convert("RGB")
            img.thumbnail((TILE_W - 8, TILE_H - 8), Image.LANCZOS)
        t.paste(img, ((TILE_W - img.width) // 2, (TILE_H - img.height) // 2))
    else:
        d.text((TILE_W // 2, TILE_H // 2), "render failed", fill=th["dim_text"],
               font=font(16), anchor="mm")
    d.rectangle([0, TILE_H, TILE_W, TILE_H + CAPTION_H], fill=th["caption_bg"])
    d.text((8, TILE_H + CAPTION_H // 2), caption, fill=th["text"], font=font(13), anchor="lm")
    d.text((TILE_W - 8, TILE_H + CAPTION_H // 2), hint, fill=th["dim_text"],
           font=font(12), anchor="rm")
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("board", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument("--no-3d", action="store_true", help="skip raytraced views")
    ap.add_argument("--zoom", type=float, default=1.0, help="3D zoom factor")
    ap.add_argument("--theme", choices=("light", "dark"), default="light",
                    help="sheet palette: light (default, white layer plots) or dark (#12161e canvas)")
    ap.add_argument("--dark", action="store_true", help="shorthand for --theme dark")
    args = ap.parse_args()
    theme_name = "dark" if args.dark else args.theme
    th = THEMES[theme_name]
    out_png = args.output or args.board.with_name(args.board.stem + "_sheet.png")

    # board stats from the pcb.py spec, if it lives next door
    stats = ""
    specp = args.board.with_name(args.board.stem + ".pcbspec.json")
    if specp.exists():
        s = json.loads(specp.read_text())
        stats = (f"{s['w']}×{s['h']}mm · {s['layers']}L · "
                 f"{len(s['parts'])} parts · {len(s['nets'])} nets")

    tiles: list[Image.Image] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        if not args.no_3d:
            jobs3d = [("top", None, "3D · top", "raytraced"),
                      ("bottom", None, "3D · bottom", "raytraced"),
                      ("top", "-35,0,25", "3D · iso", "raytraced")]
            for i, (side, rot, cap, hint) in enumerate(jobs3d):
                p = tmp / f"r{i}.png"
                render3d(args.board, p, side, rot, args.zoom, background=th["render_bg"])
                tiles.append(tile(p if p.exists() else None, cap, hint, theme=th))
        jobs2d = [("F.Cu,Edge.Cuts", False, "F.Cu + edge", "plot · from front"),
                  ("B.Cu,Edge.Cuts", False, "B.Cu + edge", "plot · from front"),
                  ("F.SilkS,F.Mask,Edge.Cuts", False, "F.Silk + F.Mask", "plot · from front")]
        for i, (layers, mirror, cap, hint) in enumerate(jobs2d):
            p = tmp / f"p{i}.png"
            plot2d(args.board, layers, p, mirror, bg_color=th["plot_bg"])
            tiles.append(tile(p if p.exists() else None, cap, hint, theme=th))

        cols = 3
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * TILE_W + (cols + 1) * 8,
                                  HEADER_H + rows * (TILE_H + CAPTION_H + 8) + 8), th["bg"])
        d = ImageDraw.Draw(sheet)
        d.text((10, HEADER_H // 2), args.board.stem, fill=th["text"], font=font(18), anchor="lm")
        if stats:
            d.text((sheet.width - 10, HEADER_H // 2), stats, fill=th["dim_text"],
                   font=font(14), anchor="rm")
        for i, t in enumerate(tiles):
            x = 8 + (i % cols) * (TILE_W + 8)
            y = HEADER_H + (i // cols) * (TILE_H + CAPTION_H + 8)
            sheet.paste(t, (x, y))
        sheet.save(out_png)
    print(f"{out_png}  ({sheet.width}×{sheet.height}, {len(tiles)} tiles)")


if __name__ == "__main__":
    main()
