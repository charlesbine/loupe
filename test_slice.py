#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Slice audit regressions. Synthetic profiles; no Bambu Studio needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import slice as slicer

START = "G28\nM970 Q1\nG29\n; purge line"
FILAMENT = {
    "name": "PLA Test @P1S",
    "textured_plate_temp_initial_layer": ["55"],
    "cool_plate_temp_initial_layer": ["35"],
    "nozzle_temperature_initial_layer": ["220"],
}


def good(bed_type="Textured PEI Plate", bed=55):
    config = {
        "curr_bed_type": bed_type,
        "nozzle_temperature_initial_layer": ["220"],
        "machine_start_gcode": START,
        "filament_settings_id": ["PLA Test @P1S"],
    }
    return f"M190 S{bed} ; wait for bed\n", config


class AuditTests(unittest.TestCase):
    machine = {"machine_start_gcode": START}

    def audit(self, gcode, config, bed_type="Textured PEI Plate"):
        return slicer.audit(gcode, config, self.machine, FILAMENT, bed_type)

    def test_standard_slice_passes(self):
        self.assertEqual(self.audit(*good()), [])

    def test_cool_plate_default_is_rejected(self):
        # The failure this guards: the CLI's Cool Plate default, 35 C on textured PEI.
        problems = self.audit(*good("Cool Plate", 35))
        self.assertTrue(any("plate is 'Cool Plate'" in p for p in problems))
        self.assertTrue(any("bed temp 35 C, profile says 55 C" in p for p in problems))

    def test_generic_start_gcode_is_rejected(self):
        gcode, config = good()
        config["machine_start_gcode"] = "G28 ; home all axes\nG1 Z5 F5000"
        self.assertIn("machine start G-code differs from the printer profile",
                      self.audit(gcode, config))

    def test_wrong_nozzle_and_filament_are_rejected(self):
        gcode, config = good()
        config["nozzle_temperature_initial_layer"] = ["190"]
        config["filament_settings_id"] = ["Generic PLA"]
        problems = self.audit(gcode, config)
        self.assertEqual(len(problems), 2, problems)

    def test_missing_bed_command_is_rejected(self):
        _, config = good()
        self.assertTrue(self.audit("G28\n", config))

    def test_other_plate_uses_its_own_temperature(self):
        self.assertEqual(self.audit(*good("Cool Plate", 35), bed_type="Cool Plate"), [])


class FlattenTests(unittest.TestCase):
    def test_merges_the_whole_inherits_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "filament").mkdir()
            for name, data in {
                "common": {"textured_plate_temp_initial_layer": ["45"], "density": 1},
                "pla": {"inherits": "common", "textured_plate_temp_initial_layer": ["55"]},
                "pla p1s": {"inherits": "pla", "name": "pla p1s"},
            }.items():
                (root / "filament" / f"{name}.json").write_text(json.dumps(data))
            with mock.patch.object(slicer, "PROFILES", root):
                merged = slicer.flattened("filament", "pla p1s")
        self.assertEqual(merged["textured_plate_temp_initial_layer"], ["55"])
        self.assertEqual(merged["density"], 1)
        self.assertNotIn("inherits", merged)


if __name__ == "__main__":
    unittest.main()
