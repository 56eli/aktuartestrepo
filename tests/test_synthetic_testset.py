from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_testset import generate
from validate_dataset import validate  # noqa: E402

DATASET = ROOT / "data" / "synthetic" / "aktuariat-risikobewertung-v1"


class SyntheticTestsetTests(unittest.TestCase):
    def test_clean_profile_passes_core_contract(self) -> None:
        issues, _ = validate(DATASET / "clean")
        self.assertEqual([], issues)

    def test_defect_profile_has_exact_expected_error_classes(self) -> None:
        directory = DATASET / "defect_fixtures"
        issues, _ = validate(directory)
        with (directory / "defect_catalog.csv").open("r", newline="", encoding="utf-8") as handle:
            expected = {row["validator_code"] for row in csv.DictReader(handle)}
        found = {item["code"] for item in issues}
        self.assertEqual(expected, found)

    def test_partner_layout_accepts_external_manifest_and_optional_development(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            normalized = workspace / "normalized"
            metadata = workspace / "metadata"
            normalized.mkdir()
            metadata.mkdir()
            manifest_tables = []
            for filename in ("policy_exposure.csv", "claim_header.csv"):
                source = DATASET / "clean" / filename
                target = normalized / filename
                shutil.copy2(source, target)
                with target.open(encoding="utf-8") as handle:
                    row_count = sum(1 for _ in handle) - 1
                manifest_tables.append({
                    "file": filename,
                    "row_count": row_count,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                })
            manifest_tables.append({
                "file": "claim_development.csv",
                "optional": True,
                "row_count": None,
                "sha256": "",
            })
            (metadata / "manifest.json").write_text(json.dumps({
                "reporting_currency": "EUR",
                "tables": manifest_tables,
            }), encoding="utf-8")
            issues, _ = validate(normalized)
        self.assertEqual([], issues)

    def test_generator_preflight_does_not_touch_existing_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            shutil.copytree(DATASET / "clean", target / "clean")
            (target / "reference").mkdir()
            (target / "reference/foreign.txt").write_text("keep")
            with self.assertRaises(ValueError):
                generate(target, 50, 11)
            self.assertEqual((DATASET / "clean/manifest.json").read_bytes(),
                             (target / "clean/manifest.json").read_bytes())
            self.assertEqual("keep", (target / "reference/foreign.txt").read_text())

    def test_generator_rolls_back_failed_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name in ("clean", "reference", "defect_fixtures"):
                shutil.copytree(DATASET / name, target / name)
            snapshot = lambda: {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            before = snapshot()
            original_rename = Path.rename

            def fail_reference(source, destination):
                if destination == target / "reference" and source.parent.name.startswith(".testset-"):
                    raise OSError("simulated publish failure")
                return original_rename(source, destination)

            with patch.object(Path, "rename", fail_reference), self.assertRaisesRegex(OSError, "simulated"):
                generate(target, 50, 11)
            self.assertEqual(before, snapshot())

    def test_manifest_rejects_invalid_or_incomplete_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "clean"
            shutil.copytree(DATASET / "clean", target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["row_counts_and_sha256"].pop()
            for value, code in [({}, "MANIFEST-002"), ([], "MANIFEST-002"), (manifest, "DQ-009")]:
                with self.subTest(value=value):
                    manifest_path.write_text(json.dumps(value))
                    self.assertIn(code, {item["code"] for item in validate(target)[0]})

    def test_correctly_manifested_invalid_valuation_and_net_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "clean"
            shutil.copytree(DATASET / "clean", target)
            csv_path = target / "claim_development.csv"
            lines = csv_path.read_text().splitlines()
            row = lines[1].split(",")
            row[2], row[10] = "2030-01-01", "9999999"
            lines[1] = ",".join(row)
            csv_path.write_text("\n".join(lines) + "\n")
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            for entry in manifest["row_counts_and_sha256"]:
                if entry["path"] == csv_path.name:
                    entry["sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual({"DQ-017", "DQ-018"}, {item["code"] for item in validate(target)[0]})

    def test_ground_truth_is_separate_from_model_inputs(self) -> None:
        clean_files = {path.name for path in (DATASET / "clean").glob("*.csv")}
        self.assertNotIn("claim_ultimate_truth.csv", clean_files)
        self.assertNotIn("policy_year_truth.csv", clean_files)
        self.assertTrue((DATASET / "reference" / "claim_ultimate_truth.csv").is_file())
        self.assertTrue((DATASET / "reference" / "policy_year_truth.csv").is_file())


if __name__ == "__main__":
    unittest.main()
