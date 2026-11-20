from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

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

    def test_ground_truth_is_separate_from_model_inputs(self) -> None:
        clean_files = {path.name for path in (DATASET / "clean").glob("*.csv")}
        self.assertNotIn("claim_ultimate_truth.csv", clean_files)
        self.assertNotIn("policy_year_truth.csv", clean_files)
        self.assertTrue((DATASET / "reference" / "claim_ultimate_truth.csv").is_file())
        self.assertTrue((DATASET / "reference" / "policy_year_truth.csv").is_file())


if __name__ == "__main__":
    unittest.main()
