#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["build123d>=0.11"]
# ///
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Charles Bine
"""Parametric 5-part desk telemetry instrument — the showcase assembly for loupe.

Demonstrates multi-part enclosure + electronics co-design in one shared mm frame
(origin lower-left at (0, 0), +Y back, +Z up):

  1. pod_chassis.stl   — rounded lower housing, 4 M2.5 standoffs, floor ribs,
                         side louvre vents, rear USB-C recess, stepped mating rim
  2. pod_pcb.stl       — populated PCB with matching M2.5 mounting holes, USB-C
                         receptacle, RF shield can, 2x5 header, encoder & switches
  3. pod_oled.stl      — recessed OLED display module framed behind the top bezel
  4. pod_bezel.stl     — chamfered upper shell with interlocking mating skirt,
                         beveled display window, encoder well, and clamp bosses
  5. pod_knob.stl      — 20-flute rotary encoder knob with pointer notch & D-bore

Also writes `pod_bezel_bug.stl` (a deliberate tall clamp-boss error crashing the
PCB) for the interference-detection shot.

Usage:
  uv run examples/sensor_pod.py
  uv run check.py pod_chassis.stl pod_pcb.stl pod_oled.stl pod_bezel.stl pod_knob.stl \\
      --interference-max 0.05 --min-wall 1.0
  uv run viewer.py pod_chassis.stl pod_pcb.stl pod_oled.stl pod_bezel.stl pod_knob.stl \\
      --group electronics=pod_pcb,pod_oled -o pod.html --title "Desk Sensor Pod"
"""
from __future__ import annotations

import math
from pathlib import Path

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Location,
    Locations,
    Mode,
    Plane,
    Rectangle,
    RectangleRounded,
    SlotCenterToCenter,
    chamfer,
    export_stl,
    extrude,
    fillet,
)

# ------------------------------------------------------------------ dimensions
W, D = 92.0, 56.0
CORNER_R = 7.0
WALL = 2.8
FLOOR = 2.4
Z_SPLIT = 15.0
Z_TOP = 25.0
CLEAR = 0.25                                      # FDM radial slip fit

# Stepped lip-and-groove joint around the split seam
STEP_W = 1.4                                      # outer lip thickness
STEP_H = 2.4                                      # vertical tongue overlap

# PCB + standoff stack
STANDOFF_H = 5.6                                  # top at Z = FLOOR + 5.6 = 8.0
Z_PCB_BOT = FLOOR + STANDOFF_H + 0.05             # 8.05 (tiny numerical clearance)
PCB_T = 1.6
Z_PCB_TOP = Z_PCB_BOT + PCB_T                     # 9.65
PCB_MARGIN = WALL + 1.0                           # 3.8 mm inset per side
STANDOFF_XY = [
    (9.5, 9.5),
    (W - 9.5, 9.5),
    (9.5, D - 9.5),
    (W - 9.5, D - 9.5),
]

# Key functional axes (shared between chassis, PCB, bezel, and knob)
ENC_X, ENC_Y = 71.0, 28.0                         # rotary encoder center
OLED_X, OLED_Y = 33.0, 32.0                       # OLED display window center
OLED_W, OLED_H = 38.0, 22.0
USBC_X = 26.0                                     # rear USB-C port centerline
BTN_XY = [(25.0, 11.0), (41.0, 11.0)]

MIN_XY = (Align.MIN, Align.MIN)
CTR = (Align.CENTER, Align.CENTER, Align.MIN)
CTR2 = (Align.CENTER, Align.CENTER)
MESH_KW = dict(tolerance=0.015, angular_tolerance=0.14)


def build_chassis() -> object:
    """Lower housing: rounded shell, stepped rim, 4 standoffs, ribs, louvres, USB-C."""
    with BuildPart() as p:
        # Outer body with bottom chamfer
        with BuildSketch():
            RectangleRounded(W, D, CORNER_R, align=MIN_XY)
        extrude(amount=Z_SPLIT)
        chamfer(p.edges().filter_by(lambda e: abs(e.center().Z) < 0.01), length=1.2)

        # Hollow main cavity above floor
        with BuildSketch(Plane.XY.offset(FLOOR)):
            with Locations((WALL, WALL)):
                RectangleRounded(W - 2 * WALL, D - 2 * WALL, CORNER_R - WALL, align=MIN_XY)
        extrude(amount=Z_SPLIT - FLOOR, mode=Mode.SUBTRACT)

        # Stepped inner ledge around top rim so the bezel skirt nests cleanly inside
        ledge_in = STEP_W
        with BuildSketch(Plane.XY.offset(Z_SPLIT - STEP_H)):
            with Locations((ledge_in, ledge_in)):
                RectangleRounded(
                    W - 2 * ledge_in,
                    D - 2 * ledge_in,
                    CORNER_R - ledge_in,
                    align=MIN_XY,
                )
        extrude(amount=STEP_H, mode=Mode.SUBTRACT)

        # 4 internal M2.5 mounting standoffs with coaxial pilot bores
        for sx, sy in STANDOFF_XY:
            with Locations(Location((sx, sy, FLOOR))):
                Cylinder(3.6, STANDOFF_H, align=CTR)
                Cylinder(1.2, STANDOFF_H, align=CTR, mode=Mode.SUBTRACT)

        # 3 longitudinal floor stiffening ribs between the standoffs
        for ry in (18.0, 28.0, 38.0):
            with Locations(Location((W / 2, ry, FLOOR))):
                Box(W - 24.0, 1.8, 3.0, align=CTR)

        # Side ventilation louvres (5 vertical stadium slots on left & right walls)
        for x_side in (0.0, W):
            with BuildSketch(Plane.YZ.offset(x_side)):
                for i in range(5):
                    ly = 16.0 + i * 6.0
                    with Locations((ly, 8.2)):
                        SlotCenterToCenter(5.2, 2.0, rotation=90)
            extrude(amount=WALL + 1.0, both=True, mode=Mode.SUBTRACT)

        # Rear USB-C port pass-through + shallow outer connector recess
        with BuildSketch(Plane.XZ.offset(D)):
            with Locations((USBC_X, Z_PCB_TOP + 1.65)):
                SlotCenterToCenter(6.4, 3.6)
        extrude(amount=WALL + 2.0, both=True, mode=Mode.SUBTRACT)

        with BuildSketch(Plane.XZ.offset(D)):
            with Locations((USBC_X, Z_PCB_TOP + 1.65)):
                SlotCenterToCenter(9.0, 5.6)
        extrude(amount=1.0, both=True, mode=Mode.SUBTRACT)

    return p.part


def build_pcb() -> object:
    """Populated electronics PCB sitting cleanly on the 4 chassis standoffs."""
    pw, pd = W - 2 * PCB_MARGIN, D - 2 * PCB_MARGIN
    with BuildPart() as p:
        # FR4 substrate
        with BuildSketch(Plane.XY.offset(Z_PCB_BOT)):
            with Locations((PCB_MARGIN, PCB_MARGIN)):
                RectangleRounded(pw, pd, CORNER_R - PCB_MARGIN, align=MIN_XY)
        extrude(amount=PCB_T)

        # 4 concentric M2.5 mounting holes
        for sx, sy in STANDOFF_XY:
            with Locations(Location((sx, sy, Z_PCB_BOT))):
                Cylinder(1.35, PCB_T + 0.2, align=CTR, mode=Mode.SUBTRACT)

        # Rear USB-C receptacle (aligned dead-center with rear chassis cutout)
        with Locations(Location((USBC_X, D - WALL - 4.0, Z_PCB_TOP))):
            Box(8.8, 7.6, 3.1, align=CTR)

        # ESP32-style metal RF shield can
        with Locations(Location((33.0, 32.0, Z_PCB_TOP))):
            Box(18.0, 15.0, 3.2, align=CTR)

        # Supporting power/sensor ICs
        with Locations(Location((52.0, 14.0, Z_PCB_TOP))):
            Box(7.0, 7.0, 1.8, align=CTR)
        with Locations(Location((16.0, 18.0, Z_PCB_TOP))):
            Box(6.0, 4.5, 2.0, align=CTR)

        # 2x5 shrouded debug header along upper edge
        with Locations(Location((50.0, 46.0, Z_PCB_TOP))):
            Box(15.0, 6.0, 5.2, align=CTR)

        # Rotary encoder body + threaded bushing + D-shaft
        with Locations(Location((ENC_X, ENC_Y, Z_PCB_TOP))):
            Box(12.2, 12.2, 6.2, align=CTR)
        with Locations(Location((ENC_X, ENC_Y, Z_PCB_TOP + 6.2))):
            Cylinder(3.4, 5.8, align=CTR)
        # Shaft rises up into the fluted knob bore (D-flat cut on +X side)
        with Locations(Location((ENC_X, ENC_Y, Z_PCB_TOP + 12.0))):
            Cylinder(2.9, 9.2, align=CTR)
        with Locations(Location((ENC_X + 2.9, ENC_Y, Z_PCB_TOP + 14.0))):
            Box(1.8, 6.4, 7.4, align=CTR, mode=Mode.SUBTRACT)

        # Two tactile switch bodies + actuators
        for bx, by in BTN_XY:
            with Locations(Location((bx, by, Z_PCB_TOP))):
                Box(6.0, 6.0, 3.8, align=CTR)
            with Locations(Location((bx, by, Z_PCB_TOP + 3.8))):
                Cylinder(1.7, 11.4, align=CTR)

    return p.part


def build_oled() -> object:
    """OLED glass display module mounted above the RF shield can behind the bezel."""
    z_bot = Z_PCB_TOP + 8.0                           # 17.65 mm, clears shield can cleanly
    with BuildPart() as p:
        # Display PCB carrier + rounded glass face clearing the beveled bezel window
        with Locations(Location((OLED_X, OLED_Y, z_bot))):
            Box(OLED_W + 2.0, OLED_H + 2.0, 1.4, align=CTR)
        with BuildSketch(Plane.XY.offset(z_bot + 1.4)):
            with Locations((OLED_X, OLED_Y)):
                RectangleRounded(OLED_W - 2.8, OLED_H - 2.8, 1.8, align=CTR2)
        extrude(amount=3.8)
        # Dual riser posts down toward the PCB (stop 0.1 mm above PCB to stay non-overlapping)
        for rx in (OLED_X - 17.0, OLED_X + 17.0):
            with Locations(Location((rx, OLED_Y, Z_PCB_TOP + 0.1))):
                Box(2.4, 15.0, z_bot - (Z_PCB_TOP + 0.1), align=CTR)
    return p.part


def build_bezel(buggy_boss: bool = False) -> object:
    """Chamfered upper shell with interlocking skirt, OLED bevel, encoder well & clamp bosses."""
    roof = 3.0
    skirt_in = STEP_W + CLEAR                         # 1.65 mm from outer wall
    skirt_t = 1.5                                     # clean solid tongue thickness
    skirt_z0 = Z_SPLIT - STEP_H + 0.35                # 12.95 mm (0.35 mm bottom gap)

    with BuildPart() as p:
        # Upper outer body with crisp top perimeter chamfer
        with BuildSketch(Plane.XY.offset(Z_SPLIT)):
            RectangleRounded(W, D, CORNER_R, align=MIN_XY)
        extrude(amount=Z_TOP - Z_SPLIT)
        chamfer(p.edges().filter_by(lambda e: abs(e.center().Z - Z_TOP) < 0.01), length=1.6)

        # Downward mating skirt nesting inside chassis lip
        with BuildSketch(Plane.XY.offset(skirt_z0)):
            with Locations((skirt_in, skirt_in)):
                RectangleRounded(
                    W - 2 * skirt_in,
                    D - 2 * skirt_in,
                    CORNER_R - skirt_in,
                    align=MIN_XY,
                )
        extrude(amount=Z_SPLIT - skirt_z0)

        # Hollow interior cavity under roof
        cav_in = skirt_in + skirt_t
        with BuildSketch(Plane.XY.offset(skirt_z0)):
            with Locations((cav_in, cav_in)):
                RectangleRounded(
                    W - 2 * cav_in,
                    D - 2 * cav_in,
                    CORNER_R - cav_in,
                    align=MIN_XY,
                )
        extrude(amount=(Z_TOP - roof) - skirt_z0, mode=Mode.SUBTRACT)

        # 4 internal hold-down bosses clamping down toward the PCB corners
        boss_bottom = (Z_PCB_BOT - 2.0) if buggy_boss else (Z_PCB_TOP + 0.35)
        for idx, (sx, sy) in enumerate(STANDOFF_XY):
            # In the buggy variant, extrude two clamp bosses straight through the PCB
            z_b = boss_bottom if (buggy_boss and idx in (0, 2)) else (Z_PCB_TOP + 0.35)
            with Locations(Location((sx, sy, z_b))):
                Cylinder(3.0, (Z_TOP - roof) - z_b, align=CTR)
                Cylinder(1.2, (Z_TOP - roof) - z_b, align=CTR, mode=Mode.SUBTRACT)

        # If buggy, also drop an extra misplaced rib straight into the RF shield can!
        if buggy_boss:
            with Locations(Location((33.0, 32.0, Z_PCB_TOP + 0.2))):
                Box(14.0, 4.0, (Z_TOP - roof) - (Z_PCB_TOP + 0.2), align=CTR)

        # Stepped / beveled OLED display window
        with BuildSketch(Plane.XY.offset(Z_TOP - roof - 0.5)):
            with Locations((OLED_X, OLED_Y)):
                RectangleRounded(OLED_W - 2.0, OLED_H - 2.0, 2.0, align=CTR2)
        extrude(amount=roof + 1.0, mode=Mode.SUBTRACT)

        with BuildSketch(Plane.XY.offset(Z_TOP - 1.2)):
            with Locations((OLED_X, OLED_Y)):
                RectangleRounded(OLED_W + 2.4, OLED_H + 2.4, 3.0, align=CTR2)
        extrude(amount=1.6, mode=Mode.SUBTRACT)

        # Recessed circular well for the rotary encoder knob + center bushing bore
        with Locations(Location((ENC_X, ENC_Y, Z_TOP - 1.6))):
            Cylinder(12.2, 2.0, align=CTR, mode=Mode.SUBTRACT)
        with Locations(Location((ENC_X, ENC_Y, Z_TOP - roof - 0.5))):
            Cylinder(4.3, roof + 1.0, align=CTR, mode=Mode.SUBTRACT)

        # Two tactile button cutouts
        for bx, by in BTN_XY:
            with Locations(Location((bx, by, Z_TOP - roof - 0.5))):
                Cylinder(2.5, roof + 1.0, align=CTR, mode=Mode.SUBTRACT)

    return p.part


def build_knob() -> object:
    """Machined 20-flute rotary encoder knob with top index groove & D-shaft socket."""
    z0 = Z_TOP - 1.0                                  # hovers 0.6 mm above recessed well floor
    kh = 10.2
    kr = 10.6
    with BuildPart() as p:
        with Locations(Location((ENC_X, ENC_Y, z0))):
            Cylinder(kr, kh, align=CTR)
        chamfer(p.edges().filter_by(lambda e: abs(e.center().Z - (z0 + kh)) < 0.01), length=1.1)

        # 20 radial grip flutes around the barrel
        n_flutes = 20
        for i in range(n_flutes):
            ang = 2 * math.pi * i / n_flutes
            fx = ENC_X + (kr + 0.35) * math.cos(ang)
            fy = ENC_Y + (kr + 0.35) * math.sin(ang)
            with Locations(Location((fx, fy, z0 + 1.4))):
                Cylinder(0.85, kh - 2.8, align=CTR, mode=Mode.SUBTRACT)

        # Milled top pointer indicator notch
        with Locations(Location((ENC_X + 4.8, ENC_Y, z0 + kh - 0.9))):
            Box(5.6, 1.4, 1.2, align=CTR, mode=Mode.SUBTRACT)

        # Underside bore clearing the encoder bushing & mating with the D-shaft
        with Locations(Location((ENC_X, ENC_Y, z0 - 0.1))):
            Cylinder(3.25, 7.6, align=CTR, mode=Mode.SUBTRACT)

    return p.part


def main() -> None:
    out_dir = Path(".")
    parts = [
        ("pod_chassis.stl", build_chassis()),
        ("pod_pcb.stl", build_pcb()),
        ("pod_oled.stl", build_oled()),
        ("pod_bezel.stl", build_bezel(buggy_boss=False)),
        ("pod_knob.stl", build_knob()),
        ("pod_bezel_bug.stl", build_bezel(buggy_boss=True)),
    ]
    for name, solid in parts:
        export_stl(solid, str(out_dir / name), **MESH_KW)
        bb = solid.bounding_box()
        print(f"wrote {name:18s}  {bb.size.X:5.1f} × {bb.size.Y:5.1f} × {bb.size.Z:5.1f} mm")


if __name__ == "__main__":
    main()
