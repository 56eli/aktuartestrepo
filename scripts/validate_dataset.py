#!/usr/bin/env python3
"""Validate the canonical synthetic actuarial CSV data contract.

The validator has no third-party dependencies. Run it on the clean dataset to
require zero errors, or on defect_fixtures with --expect-defects to confirm that
the intentionally seeded data-quality failures are detected.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "policy_exposure.csv": {
        "exposure_id", "policy_id", "policy_year", "inception_date", "expiry_date",
        "exposure_years", "product", "region", "risk_band", "insured_value_eur",
        "gross_premium_eur", "currency",
    },
    "claim_header.csv": {
        "claim_id", "exposure_id", "policy_id", "policy_year", "product", "region",
        "loss_date", "report_date", "claim_type", "cat_event_id", "currency",
    },
}
OPTIONAL_COLUMNS = {
    "claim_development.csv": {
        "claim_id", "accident_year", "valuation_date", "development_months",
        "gross_paid_cumulative_eur", "gross_case_reserve_eur", "gross_incurred_eur",
        "ceded_paid_cumulative_eur", "ceded_case_reserve_eur", "ceded_incurred_eur",
        "net_incurred_eur", "currency",
    },
    "catastrophe_events.csv": {"cat_event_id", "event_date", "hazard_type", "region"},
    "reinsurance_treaties.csv": {"treaty_id", "product", "attachment_eur", "limit_eur", "participation_pct"},
    "market_curve.csv": {"valuation_date", "currency", "maturity_years", "risk_free_rate_pct", "credit_spread_bps"},
    "scenario_catalog.csv": {"scenario_id", "scenario_type", "horizon_years", "calibration_status"},
}


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite value")
    return number


def validate(directory: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, str]]]]:
    issues: list[dict[str, Any]] = []
    tables: dict[str, list[dict[str, str]]] = {}
    reporting_currency = "EUR"

    def issue(code: str, file_name: str, row_key: str, message: str) -> None:
        issues.append({"code": code, "file": file_name, "row_key": row_key, "message": message})

    all_schemas = {**REQUIRED_COLUMNS, **OPTIONAL_COLUMNS}
    for filename, required in all_schemas.items():
        path = directory / filename
        if not path.is_file():
            if filename in REQUIRED_COLUMNS:
                issue("SCHEMA-001", filename, "", "Required table is missing.")
            continue
        try:
            headers, rows = read_rows(path)
        except (OSError, csv.Error, UnicodeError) as exc:
            issue("SCHEMA-002", filename, "", f"Could not read CSV: {exc}")
            continue
        missing = sorted(required - set(headers))
        if missing:
            issue("SCHEMA-003", filename, "", f"Missing required columns: {', '.join(missing)}")
        tables[filename] = rows

    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        metadata_manifest = directory.parent / "metadata" / "manifest.json"
        if metadata_manifest.is_file():
            manifest_path = metadata_manifest
    if not manifest_path.is_file():
        issue("MANIFEST-001", "manifest.json", "", "Dataset manifest is missing.")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            reporting_currency = str(manifest.get("reporting_currency", manifest.get("currency", "EUR")))
            entries = manifest.get("row_counts_and_sha256")
            if entries is None:
                entries = manifest.get("tables", [])
            for entry in entries:
                filename = str(entry.get("path", entry.get("file", "")))
                path = directory / filename
                if not path.is_file():
                    if entry.get("optional", False):
                        continue
                    issue("DQ-009", filename, "", "Manifested file is missing.")
                    continue
                _, rows = read_rows(path)
                expected_rows = entry.get("rows", entry.get("row_count"))
                if expected_rows is not None and len(rows) != int(expected_rows):
                    issue("DQ-009", filename, "", "Manifest row count does not match the file.")
                expected_hash = entry.get("sha256")
                if expected_hash and sha256_file(path) != expected_hash:
                    issue("DQ-009", filename, "", "Manifest checksum does not match the file.")
        except (OSError, ValueError, TypeError, csv.Error) as exc:
            issue("MANIFEST-002", "manifest.json", "", f"Manifest is invalid: {exc}")

    if "policy_exposure.csv" in tables:
        seen_exposures: set[str] = set()
        exposure_by_id: dict[str, dict[str, str]] = {}
        for index, row in enumerate(tables["policy_exposure.csv"], start=2):
            key = row.get("exposure_id", "")
            if not key:
                issue("DQ-013", "policy_exposure.csv", f"line:{index}", "Exposure key is empty.")
            if key in seen_exposures:
                issue("DQ-001", "policy_exposure.csv", key, "Duplicate exposure_id.")
            seen_exposures.add(key)
            exposure_by_id.setdefault(key, row)
            try:
                exposure_years = parse_number(row.get("exposure_years", ""))
                if exposure_years <= 0:
                    issue("DQ-002", "policy_exposure.csv", key, "Exposure must be greater than zero.")
            except (ValueError, TypeError):
                issue("DQ-002", "policy_exposure.csv", key, "Exposure is not a finite number greater than zero.")
            if row.get("currency") != reporting_currency:
                issue("DQ-003", "policy_exposure.csv", key, f"Currency does not match reporting_currency {reporting_currency!r}: {row.get('currency', '')!r}.")
            try:
                start = parse_date(row.get("inception_date", ""))
                end = parse_date(row.get("expiry_date", ""))
                int(row.get("policy_year", ""))
                if start > end:
                    issue("DQ-012", "policy_exposure.csv", key, "Policy inception_date is after expiry_date.")
            except (ValueError, TypeError):
                issue("DQ-012", "policy_exposure.csv", key, "Invalid inception_date, expiry_date, or policy_year.")

    exposure_by_id = {}
    if "policy_exposure.csv" in tables:
        for row in tables["policy_exposure.csv"]:
            exposure_by_id.setdefault(row.get("exposure_id", ""), row)

    claim_ids: set[str] = set()
    claim_by_id: dict[str, dict[str, str]] = {}
    if "claim_header.csv" in tables:
        for index, row in enumerate(tables["claim_header.csv"], start=2):
            claim_id = row.get("claim_id", "")
            exposure_id = row.get("exposure_id", "")
            if not claim_id:
                issue("DQ-013", "claim_header.csv", f"line:{index}", "Claim key is empty.")
            if claim_id in claim_ids:
                issue("DQ-011", "claim_header.csv", claim_id, "Duplicate claim_id.")
            claim_ids.add(claim_id)
            claim_by_id.setdefault(claim_id, row)
            matched_exposure = exposure_by_id.get(exposure_id)
            if matched_exposure is None:
                issue("DQ-004", "claim_header.csv", claim_id, f"No matching exposure for {exposure_id!r}.")
            elif (row.get("policy_id") != matched_exposure.get("policy_id")
                  or row.get("product") != matched_exposure.get("product")
                  or row.get("policy_year") != matched_exposure.get("policy_year")):
                issue("DQ-015", "claim_header.csv", claim_id, "Claim policy/product/year does not match its exposure record.")
            if row.get("currency") != reporting_currency:
                issue("DQ-003", "claim_header.csv", claim_id, f"Currency does not match reporting_currency {reporting_currency!r}: {row.get('currency', '')!r}.")
            try:
                loss_date = parse_date(row.get("loss_date", ""))
                report_date = parse_date(row.get("report_date", ""))
                if report_date < loss_date:
                    issue("DQ-012", "claim_header.csv", claim_id, "report_date is before loss_date.")
                if matched_exposure is not None:
                    term_start = parse_date(matched_exposure.get("inception_date", ""))
                    term_end = parse_date(matched_exposure.get("expiry_date", ""))
                    if loss_date < term_start or loss_date > term_end:
                        issue("DQ-016", "claim_header.csv", claim_id, "loss_date lies outside the linked exposure period.")
            except (ValueError, TypeError):
                issue("DQ-012", "claim_header.csv", claim_id, "Invalid loss_date or report_date.")

    if "catastrophe_events.csv" in tables and "claim_header.csv" in tables:
        known_events = {row.get("cat_event_id", "") for row in tables["catastrophe_events.csv"]}
        for row in tables["claim_header.csv"]:
            event_id = row.get("cat_event_id", "")
            if event_id and event_id not in known_events:
                issue("DQ-010", "claim_header.csv", row.get("claim_id", ""), f"Unknown cat_event_id {event_id!r}.")

    if "claim_development.csv" in tables:
        seen_development: set[tuple[str, str]] = set()
        paid_by_claim: dict[str, list[tuple[int, float, str]]] = defaultdict(list)
        for index, row in enumerate(tables["claim_development.csv"], start=2):
            claim_id = row.get("claim_id", "")
            dev_month = row.get("development_months", "")
            key = (claim_id, dev_month)
            if key in seen_development:
                issue("DQ-006", "claim_development.csv", f"{claim_id}:{dev_month}", "Duplicate claim_id + development_months key.")
            seen_development.add(key)
            if claim_id not in claim_ids:
                issue("DQ-014", "claim_development.csv", claim_id, "Development record has no claim header.")
            try:
                month_int = int(dev_month)
                valuation_date = parse_date(row.get("valuation_date", ""))
                claim = claim_by_id.get(claim_id)
                if claim and valuation_date < parse_date(claim.get("loss_date", "")):
                    issue("DQ-012", "claim_development.csv", f"{claim_id}:{dev_month}", "valuation_date is before loss_date.")
                paid = parse_number(row.get("gross_paid_cumulative_eur", ""))
                case_reserve = parse_number(row.get("gross_case_reserve_eur", ""))
                incurred = parse_number(row.get("gross_incurred_eur", ""))
                if paid < 0:
                    issue("DQ-005", "claim_development.csv", f"{claim_id}:{dev_month}", "Cumulative paid amount is negative.")
                if case_reserve < 0:
                    issue("DQ-005", "claim_development.csv", f"{claim_id}:{dev_month}", "Case reserve is negative.")
                if abs((paid + case_reserve) - incurred) > 0.02:
                    issue("DQ-007", "claim_development.csv", f"{claim_id}:{dev_month}", "gross_incurred is not equal to paid + case reserve within rounding tolerance.")
                paid_by_claim[claim_id].append((month_int, paid, f"{claim_id}:{dev_month}"))
            except (ValueError, TypeError):
                issue("DQ-012", "claim_development.csv", f"{claim_id}:{dev_month}", "Invalid development month, date, or amount.")
            if row.get("currency") != reporting_currency:
                issue("DQ-003", "claim_development.csv", f"{claim_id}:{dev_month}", f"Currency does not match reporting_currency {reporting_currency!r}: {row.get('currency', '')!r}.")

        for claim_id, points in paid_by_claim.items():
            points.sort(key=lambda item: item[0])
            previous: float | None = None
            for _, paid, key in points:
                if previous is not None and paid + 0.005 < previous:
                    issue("DQ-008", "claim_development.csv", key, "Cumulative paid amount decreases with development age.")
                previous = paid

    return issues, tables


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir", type=Path, help="Ordner mit normalisierten CSV-Tabellen und manifest.json")
    parser.add_argument("--expect-defects", action="store_true", help="Erfolg, wenn genau die im defect_catalog.csv erwarteten Validator-Codes erkannt werden")
    args = parser.parse_args()
    directory = args.dataset_dir.resolve()
    issues, _ = validate(directory)

    if args.expect_defects:
        catalog_path = directory / "defect_catalog.csv"
        if not catalog_path.is_file():
            print("FEHLER: --expect-defects benötigt defect_catalog.csv", file=sys.stderr)
            return 2
        _, defects = read_rows(catalog_path)
        expected = {row.get("validator_code", "") for row in defects if row.get("validator_code")}
        found = {item["code"] for item in issues}
        if expected != found:
            print(f"Erwartete Fehlercodes: {', '.join(sorted(expected)) or '(keine)'}")
            print(f"Erkannte Fehlercodes:  {', '.join(sorted(found)) or '(keine)'}")
            for item in issues:
                print(f"{item['code']} {item['file']} {item['row_key']}: {item['message']}")
            return 1
        print(f"PASS: Alle absichtlich eingebauten Fehler erkannt ({len(expected)} Fehlerklassen).")
        for item in issues:
            print(f"  {item['code']} {item['file']} {item['row_key']}: {item['message']}")
        return 0

    if issues:
        print(f"FAIL: {len(issues)} Datenqualitäts-/Schemafehler in {directory}")
        for item in issues[:100]:
            print(f"  {item['code']} {item['file']} {item['row_key']}: {item['message']}")
        if len(issues) > 100:
            print(f"  … {len(issues) - 100} weitere Fehler nicht angezeigt")
        return 1

    print(f"PASS: Keine Fehler in den geprüften Kernregeln ({directory}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
