#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "shapely", "ezdxf", "matplotlib", "pillow", "numpy", "trimesh", "scipy", "pypdfium2"]
# ///
"""Regression tests for draftsheet themes and viewer HUD/theming options."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import trimesh

import draft
import draftsheet
import pcbsheet
import viewer
from PIL import Image

ROOT = Path(__file__).resolve().parent


class DraftSheetThemeTests(unittest.TestCase):
    def test_parse_hex_rgb(self):
        self.assertEqual(draftsheet.parse_hex_rgb("#9fdcff"), (159, 220, 255))
        self.assertEqual(draftsheet.parse_hex_rgb("5ac4b8"), (90, 196, 184))
        with self.assertRaises(draft.DraftError):
            draftsheet.parse_hex_rgb("not-a-color")

    def test_light_and_dark_themes_render_distinct_canvas(self):
        d = draft.load(ROOT / "examples/coupon_case.draft.yaml")
        views = [next(iter(d.views.values()))]
        light_img = draftsheet.build_sheet(d, views, theme_name="light")
        dark_img = draftsheet.build_sheet(d, views, theme_name="dark", accent="#9fdcff")
        self.assertEqual(light_img.size, dark_img.size)
        # Sample the top-left interior of the first drawing tile (past header & padding)
        sample_xy = (draftsheet.PAD + 20, 46 + 20)
        self.assertEqual(light_img.getpixel(sample_xy), (255, 255, 255))
        self.assertEqual(dark_img.getpixel(sample_xy), draftsheet.THEMES["dark"]["paper"])


class ViewerOptionsTests(unittest.TestCase):
    def _make_stl(self, td: Path, name: str = "box.stl") -> Path:
        p = td / name
        trimesh.creation.box(extents=[10, 10, 10]).export(p)
        return p

    def test_defaults_and_compact_hud(self):
        with tempfile.TemporaryDirectory() as td:
            stl = self._make_stl(Path(td))
            html, glb_len = viewer.build_html([stl], title="Unit Box")
        self.assertGreater(glb_len, 0)
        self.assertIn('class="hud-bar"', html)
        self.assertIn('id="clipDrawer"', html)
        self.assertIn('id="clipToggle"', html)
        self.assertIn("--bg: #1b1d22;", html)
        self.assertIn("--accent: #7fb4e8;", html)
        self.assertIn(json.dumps({"exploded": False, "rotate": False, "bg": "#1b1d22", "accent": "#7fb4e8"}), html)

    def test_exploded_rotate_theme_and_css_url(self):
        with tempfile.TemporaryDirectory() as td:
            stl = self._make_stl(Path(td))
            html, _ = viewer.build_html(
                [stl], title="Embed", exploded=True, rotate=True,
                bg="#080b10", accent="#9fdcff", css="/demos/loupe-theme.css",
            )
        self.assertIn('<link rel="stylesheet" href="/demos/loupe-theme.css">', html)
        self.assertIn("--bg: #080b10;", html)
        self.assertIn("--accent: #9fdcff;", html)
        self.assertIn(json.dumps({"exploded": True, "rotate": True, "bg": "#080b10", "accent": "#9fdcff"}), html)

    def test_local_css_file_is_inlined(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            stl = self._make_stl(p)
            css = p / "custom.css"
            css.write_text(":root { --accent: #ff00aa; }")
            html, _ = viewer.build_html([stl], css=str(css))
        self.assertIn(":root { --accent: #ff00aa; }", html)
        self.assertNotIn('<link rel="stylesheet"', html)


class PcbSheetThemeTests(unittest.TestCase):
    def test_autocrop_plot_dark_and_light(self):
        dark_bg = pcbsheet._hex_to_rgb(pcbsheet.THEMES["dark"]["plot_bg"])
        im = Image.new("RGB", (400, 300), dark_bg)
        for x in range(150, 250):
            for y in range(100, 200):
                im.putpixel((x, y), (220, 60, 60))
        cropped = pcbsheet.autocrop_plot(im, bg_color=pcbsheet.THEMES["dark"]["plot_bg"], pad=10)
        self.assertEqual(cropped.size, (120, 120))
        self.assertEqual(cropped.getpixel((0, 0)), dark_bg)

    def test_tile_composites_transparent_rgba_onto_dark_canvas(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pcb.png"
            rgba = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            for x in range(40, 60):
                for y in range(40, 60):
                    rgba.putpixel((x, y), (30, 120, 60, 255))
            rgba.save(p)
            tile_img = pcbsheet.tile(p, "3D · top", "raytraced", theme=pcbsheet.THEMES["dark"])
        self.assertEqual(tile_img.getpixel((4, 4)), pcbsheet.THEMES["dark"]["tile_bg"])
        self.assertEqual(tile_img.getpixel((pcbsheet.TILE_W // 2, pcbsheet.TILE_H // 2)), (30, 120, 60))


if __name__ == "__main__":
    unittest.main()
