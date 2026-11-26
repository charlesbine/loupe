---
name: loupe
description: Use when designing, reviewing, or verifying parametric 3D-printable CAD models (build123d, CadQuery, STL assemblies) or KiCad 10 PCBs. Runs deterministic geometry/fit checks, renders labeled contact sheets and cross-section slices inline, checks YAML dimension drafts, and runs content-bound loupe.json electronics workflows.
---

# Loupe CAD & PCB Review Loop

Use Loupe's MCP tools whenever you create or modify parametric CAD models (STL assemblies), YAML dimension drafts, or `loupe.json` electronics projects. Never guess geometry from code alone, and never trust a pretty render without deterministic checks.

## Available MCP Tools

1. **`draft_check(spec, stl=None)`** — Planning-stage gate before writing CAD. Verifies dimension expressions, containment, min walls, fit classes, and (when `stl` is passed) asserts the exported mesh has not drifted from the drafted dimensions or hole positions.
2. **`draft_sheet(spec, views=None, theme="light", accent=None)`** — Renders a true-scale 1:1 dimensioned blueprint and provenance table inline as a PNG (`theme="dark"` for white-on-charcoal blueprints).
3. **`check(files, interference_max=0.05, min_wall=1.2, overhang=None, clearance=None)`** — Deterministic 3D geometry verifier. Checks watertightness, exact manifold boolean overlap volume between every pair of parts (`mm³`), sustained thin walls, region-scoped clearances (`"partA:partB:0.2@z=2:18"`), and overhangs.
4. **`sheet(files, views=None, slices=None, cutaways=None, view=None, roi=None)`** — Renders labeled orthographic/isometric views, 3D cutaways (`["y<50%"]`), and 2D cross-section slices (`["y=28", "z=11"]`) inline as a PNG. Part-vs-part interference is painted bright red with measured `mm²` in the caption.
5. **`slice(files, process=None, filament=None, bed_type=None)`** — Headless Bambu Studio print estimate (time, filament grams, spool cost, slicer warnings, plate and bed temperature; requires local Bambu Studio). The slice is audited against the standard profiles and fails with no `.gcode.3mf` on any mismatch. Pass the installed plate as `bed_type` (default `Textured PEI Plate`) and a `filament` matching the loaded spool.
6. **`project_status(project)`** — Reports fresh/stale content-bound evidence for a local `loupe.json` electronics project.
7. **`project_run(project, action)`** — Runs `build`, `check`, `review`, or local `release` on a `loupe.json` project. Preserves reviewed native PCBs and schematics; blocks release if any evidence is stale.

## Standard CAD Review Loop

1. **Draft first** when designing from scratch or mating with real parts: write a `.draft.yaml` dimension record, run `draft_check`, and inspect `draft_sheet`.
2. **Export assembled STLs** in shared world-millimeter coordinates (every part at its seated position).
3. **Gate with `check`** (`interference_max=0.05`, `min_wall=1.2`) — fix any non-watertight mesh, thin wall, or boolean collision before proceeding.
4. **Inspect with `sheet`** — always include at least one cross-section slice through mating seams, shafts, standoffs, or threads so you verify clearances visually.
5. **Confirm as-built dimensions** with `draft_check(spec, stl=[...])` whenever a draft exists.
6. **For `loupe.json` electronics projects:** check `project_status`, run `build` → `check` → `review`, and never overwrite manually routed native boards as a side effect of checking.
