#!/usr/bin/env python3
"""Create a deterministic, fully synthetic actuarial insurance test set.

Uses only the Python standard library. No real policyholder or claim records are
used. The clean input tables and deliberately defective fixtures are written to
separate directories so the defective profile cannot be mistaken for clean data.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import math
import random
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20261120
DEFAULT_POLICY_COUNT = 2000
ACCIDENT_YEARS = tuple(range(2019, 2025))
DATA_CUTOFF = date(2025, 12, 31)
CURRENCY = "EUR"
REGIONS = ("north", "south", "east", "west", "central")
RISK_BANDS = ("1", "2", "3", "4", "5")
RISK_WEIGHTS = (0.12, 0.24, 0.30, 0.22, 0.12)
REGION_WEIGHTS = (0.19, 0.21, 0.18, 0.20, 0.22)
AGE_BANDS = ("under_25", "25_39", "40_59", "60_plus")
AGE_WEIGHTS = (0.12, 0.27, 0.42, 0.19)
VEHICLE_AGE_BANDS = ("0_5", "6_15", "16_plus")
VEHICLE_AGE_WEIGHTS = (0.37, 0.45, 0.18)
DEVELOPMENT_MONTHS = (3, 6, 12, 24, 36, 60, 72)

POLICY_FIELDS = [
    "exposure_id", "policy_id", "policy_year", "inception_date", "expiry_date",
    "exposure_years", "product", "region", "risk_band", "driver_age_band",
    "asset_age_band", "insured_value_eur", "gross_premium_eur", "currency",
    "policy_status",
]
CLAIM_FIELDS = [
    "claim_id", "exposure_id", "policy_id", "policy_year", "product", "region",
    "risk_band", "loss_date", "report_date", "claim_type", "cat_event_id",
    "claim_status_at_cutoff", "currency",
]
DEVELOPMENT_FIELDS = [
    "claim_id", "accident_year", "valuation_date", "development_months",
    "gross_paid_cumulative_eur", "gross_case_reserve_eur", "gross_incurred_eur",
    "ceded_paid_cumulative_eur", "ceded_case_reserve_eur", "ceded_incurred_eur",
    "net_incurred_eur", "currency",
]
TREATY_FIELDS = [
    "treaty_id", "product", "effective_from", "effective_to", "attachment_eur",
    "limit_eur", "participation_pct", "treaty_type",
]
MARKET_FIELDS = [
    "valuation_date", "currency", "maturity_years", "risk_free_rate_pct",
    "credit_spread_bps", "source_label",
]
EVENT_FIELDS = [
    "cat_event_id", "event_date", "hazard_type", "region", "severity_multiplier",
    "event_note",
]
SCENARIO_FIELDS = [
    "scenario_id", "scenario_name", "scenario_type", "claims_inflation_pct",
    "rate_shift_bp", "catastrophe_multiplier", "lapse_increase_pct",
    "horizon_years", "calibration_status", "scenario_note",
]
TRUTH_FIELDS = [
    "claim_id", "gross_ultimate_eur", "ceded_ultimate_eur", "net_ultimate_eur",
]
POLICY_TRUTH_FIELDS = [
    "exposure_id", "expected_frequency_per_year", "generated_claim_count",
    "generated_ultimate_loss_eur", "expected_loss_eur",
]
DEFECT_FIELDS = [
    "fixture_id", "validator_code", "file_name", "row_key", "defect_type",
    "expected_detection",
]

EVENTS = [
    {
        "cat_event_id": "CAT-2020-FLOOD-WEST",
        "event_date": date(2020, 7, 18),
        "hazard_type": "flood",
        "region": "west",
        "severity_multiplier": 3.2,
        "event_note": "Synthetic event; not linked to a real disaster.",
    },
    {
        "cat_event_id": "CAT-2022-STORM-NORTH",
        "event_date": date(2022, 10, 6),
        "hazard_type": "storm",
        "region": "north",
        "severity_multiplier": 2.8,
        "event_note": "Synthetic event; not linked to a real disaster.",
    },
    {
        "cat_event_id": "CAT-2024-HAIL-SOUTH",
        "event_date": date(2024, 6, 22),
        "hazard_type": "hail",
        "region": "south",
        "severity_multiplier": 2.5,
        "event_note": "Synthetic event; not linked to a real disaster.",
    },
]

TREATIES = [
    {
        "treaty_id": "XL-MOTOR-2019-2025", "product": "motor",
        "effective_from": "2019-01-01", "effective_to": "2025-12-31",
        "attachment_eur": 25000, "limit_eur": 175000,
        "participation_pct": 100, "treaty_type": "per_claim_excess_of_loss",
    },
    {
        "treaty_id": "XL-PROPERTY-2019-2025", "product": "property",
        "effective_from": "2019-01-01", "effective_to": "2025-12-31",
        "attachment_eur": 50000, "limit_eur": 300000,
        "participation_pct": 100, "treaty_type": "per_claim_excess_of_loss",
    },
]

SCENARIOS = [
    {
        "scenario_id": "BASE", "scenario_name": "Synthetischer Basisfall",
        "scenario_type": "baseline", "claims_inflation_pct": 0,
        "rate_shift_bp": 0, "catastrophe_multiplier": 1,
        "lapse_increase_pct": 0, "horizon_years": 1,
        "calibration_status": "synthetic_example_only",
        "scenario_note": "Baseline für Pipeline- und Darstellungstests; kein Unternehmensbefund.",
    },
    {
        "scenario_id": "ST-CLAIMS-INFLATION", "scenario_name": "Schadeninflation",
        "scenario_type": "single_factor_stress", "claims_inflation_pct": 10,
        "rate_shift_bp": 0, "catastrophe_multiplier": 1,
        "lapse_increase_pct": 0, "horizon_years": 1,
        "calibration_status": "synthetic_example_only",
        "scenario_note": "Illustrativer Schock; nicht regulatorisch kalibriert.",
    },
    {
        "scenario_id": "ST-RATE-UP", "scenario_name": "Zinsanstieg",
        "scenario_type": "single_factor_stress", "claims_inflation_pct": 0,
        "rate_shift_bp": 200, "catastrophe_multiplier": 1,
        "lapse_increase_pct": 0, "horizon_years": 1,
        "calibration_status": "synthetic_example_only",
        "scenario_note": "Illustrativer Schock; nicht regulatorisch kalibriert.",
    },
    {
        "scenario_id": "ST-CAT", "scenario_name": "Naturgefahren-Kumul",
        "scenario_type": "single_factor_stress", "claims_inflation_pct": 0,
        "rate_shift_bp": 0, "catastrophe_multiplier": 3,
        "lapse_increase_pct": 0, "horizon_years": 1,
        "calibration_status": "synthetic_example_only",
        "scenario_note": "Illustrativer Schock; nicht regulatorisch kalibriert.",
    },
    {
        "scenario_id": "ST-COMBINED", "scenario_name": "Kombinierter Stress",
        "scenario_type": "combined_stress", "claims_inflation_pct": 8,
        "rate_shift_bp": 150, "catastrophe_multiplier": 2,
        "lapse_increase_pct": 20, "horizon_years": 1,
        "calibration_status": "synthetic_example_only",
        "scenario_note": "Illustrative Kombination; Abhängigkeiten sind nicht vorgegeben.",
    },
    {
        "scenario_id": "ST-REVERSE", "scenario_name": "Reverse-Stress-Ausgangspunkt",
        "scenario_type": "reverse_stress_template", "claims_inflation_pct": "",
        "rate_shift_bp": "", "catastrophe_multiplier": "",
        "lapse_increase_pct": "", "horizon_years": 1,
        "calibration_status": "parameterise_for_test",
        "scenario_note": "Schocks anhand einer selbst festgelegten Risikoappetitgrenze bestimmen.",
    },
]


def weighted_choice(rng: random.Random, values: Sequence[str], weights: Sequence[float]) -> str:
    point = rng.random() * sum(weights)
    cumulative = 0.0
    for value, weight in zip(values, weights):
        cumulative += weight
        if point < cumulative:
            return value
    return values[-1]


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    day_of_month = min(day.day, calendar.monthrange(year, month)[1])
    return date(year, month, day_of_month)


def format_money(value: float) -> str:
    return f"{value:.2f}"


def format_rate(value: float, decimals: int = 4) -> str:
    return f"{value:.{decimals}f}"


def stable_lognormal(rng: random.Random, median: float, sigma: float) -> float:
    u1 = max(rng.random(), 1e-12)
    u2 = rng.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return median * math.exp(sigma * z)


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth Poisson sampler; all generated means are small (< 2)."""
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    product = 1.0
    count = 0
    while product > limit:
        count += 1
        product *= max(rng.random(), 1e-15)
    return count - 1


def random_day(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=int(rng.random() * (span + 1)))


def claim_type_for(rng: random.Random, product: str, hazard: str | None = None) -> str:
    if hazard:
        return hazard
    if product == "motor":
        return weighted_choice(rng, ("collision", "liability", "glass"), (0.45, 0.40, 0.15))
    return weighted_choice(rng, ("water", "storm", "fire", "other"), (0.34, 0.32, 0.10, 0.24))


def risk_factors(product: str, risk_band: str, region: str, age_band: str, asset_age_band: str) -> tuple[float, float]:
    risk_frequency = {"1": 0.70, "2": 0.85, "3": 1.00, "4": 1.25, "5": 1.60}[risk_band]
    region_frequency = {"north": 1.05, "south": 1.08, "east": 0.92, "west": 1.02, "central": 0.96}[region]
    age_frequency = {"under_25": 1.35, "25_39": 1.00, "40_59": 0.90, "60_plus": 1.08, "not_applicable": 1.0}[age_band]
    asset_frequency = {"0_5": 0.95, "6_15": 1.00, "16_plus": 1.18, "not_applicable": 1.0}[asset_age_band]
    if product == "motor":
        return risk_frequency * region_frequency * age_frequency, risk_frequency ** 0.25
    return risk_frequency * region_frequency * asset_frequency, (risk_frequency * asset_frequency) ** 0.25


def treaty_for(product: str) -> dict[str, object]:
    return next(item for item in TREATIES if item["product"] == product)


def ceded_amount(gross_amount: float, product: str) -> float:
    treaty = treaty_for(product)
    attachment = float(treaty["attachment_eur"])
    limit = float(treaty["limit_eur"])
    participation = float(treaty["participation_pct"]) / 100.0
    return min(max(gross_amount - attachment, 0.0), limit) * participation


def claim_age_months(loss_date: date, cutoff: date) -> float:
    return max(0.0, (cutoff - loss_date).days / 30.4375)


def build_dataset(policy_count: int, seed: int) -> dict[str, list[dict[str, object]]]:
    rng = random.Random(seed)
    exposures: list[dict[str, object]] = []
    claims: list[dict[str, object]] = []
    development: list[dict[str, object]] = []
    claim_truth: list[dict[str, object]] = []
    policy_truth: list[dict[str, object]] = []
    events_by_year_region = {(e["event_date"].year, e["region"]): e for e in EVENTS}
    claim_number = 0

    # Stable policy characteristics across annual terms create repeat observations.
    policy_profiles: list[dict[str, str]] = []
    for i in range(1, policy_count + 1):
        product = weighted_choice(rng, ("motor", "property"), (0.70, 0.30))
        region = weighted_choice(rng, REGIONS, REGION_WEIGHTS)
        risk_band = weighted_choice(rng, RISK_BANDS, RISK_WEIGHTS)
        age_band = weighted_choice(rng, AGE_BANDS, AGE_WEIGHTS) if product == "motor" else "not_applicable"
        asset_age = weighted_choice(rng, VEHICLE_AGE_BANDS, VEHICLE_AGE_WEIGHTS) if product == "motor" else weighted_choice(rng, VEHICLE_AGE_BANDS, VEHICLE_AGE_WEIGHTS)
        policy_profiles.append({
            "policy_id": f"POL-{i:06d}", "product": product, "region": region,
            "risk_band": risk_band, "driver_age_band": age_band,
            "asset_age_band": asset_age,
        })

    for year in ACCIDENT_YEARS:
        days_in_year = (date(year + 1, 1, 1) - date(year, 1, 1)).days
        for profile in policy_profiles:
            policy_id = profile["policy_id"]
            product = profile["product"]
            region = profile["region"]
            risk_band = profile["risk_band"]
            age_band = profile["driver_age_band"]
            asset_age = profile["asset_age_band"]

            start_offset = int(rng.random() * 46)
            term_days = int(days_in_year * (0.70 + 0.30 * rng.random()))
            end_offset = min(days_in_year - 1, start_offset + term_days - 1)
            term_start = date(year, 1, 1) + timedelta(days=start_offset)
            term_end = date(year, 1, 1) + timedelta(days=end_offset)
            exposure_years = (end_offset - start_offset + 1) / days_in_year
            exposure_id = f"EXP-{policy_id}-{year}"

            frequency_factor, severity_factor = risk_factors(product, risk_band, region, age_band, asset_age)
            base_frequency = 0.075 if product == "motor" else 0.050
            trend_frequency = 1.0 + 0.008 * (year - ACCIDENT_YEARS[0])
            expected_frequency = base_frequency * frequency_factor * trend_frequency
            median_severity = 1350.0 if product == "motor" else 3200.0
            insured_value = (18000 + 60000 * rng.random()) if product == "motor" else (80000 + 520000 * rng.random())
            value_factor = (insured_value / (35000 if product == "motor" else 260000)) ** (0.10 if product == "motor" else 0.18)
            severity_inflation = 1.035 ** (year - ACCIDENT_YEARS[0])
            mean_severity = median_severity * math.exp(0.68 ** 2 / 2.0) * severity_factor * value_factor * severity_inflation
            expected_loss = expected_frequency * mean_severity * exposure_years
            gross_premium = max(45.0, (expected_loss * 1.42 + (65.0 if product == "motor" else 110.0) * exposure_years))

            exposures.append({
                "exposure_id": exposure_id,
                "policy_id": policy_id,
                "policy_year": year,
                "inception_date": term_start.isoformat(),
                "expiry_date": term_end.isoformat(),
                "exposure_years": format_rate(exposure_years, 6),
                "product": product,
                "region": region,
                "risk_band": risk_band,
                "driver_age_band": age_band,
                "asset_age_band": asset_age,
                "insured_value_eur": format_money(insured_value),
                "gross_premium_eur": format_money(gross_premium),
                "currency": CURRENCY,
                "policy_status": "active_at_year_end" if term_end.year == year and term_end.month == 12 and term_end.day == 31 else "ended_during_year",
            })

            # A bounded latent multiplier creates overdispersion without third-party libraries.
            latent_risk = 0.65 + 0.70 * rng.random()
            expected_count = expected_frequency * exposure_years
            count = poisson(rng, expected_count * latent_risk)
            generated_loss_total = 0.0

            def add_claim(loss_date: date, event: dict[str, object] | None = None) -> None:
                nonlocal claim_number, generated_loss_total
                claim_number += 1
                claim_id = f"CLM-{claim_number:07d}"
                hazard = str(event["hazard_type"]) if event else None
                claim_type = claim_type_for(rng, product, hazard)
                year_inflation = 1.035 ** (year - ACCIDENT_YEARS[0])
                cat_multiplier = float(event["severity_multiplier"]) if event else 1.0
                rare_tail_multiplier = 4.0 if rng.random() < 0.012 else 1.0
                median = median_severity * severity_factor * value_factor * year_inflation * cat_multiplier * rare_tail_multiplier
                ultimate = max(50.0, stable_lognormal(rng, median, 0.68))
                delay_days = min(300, 1 + int(-55.0 * math.log(max(1e-12, 1.0 - rng.random()))))
                report_date = loss_date + timedelta(days=delay_days)
                age_months = claim_age_months(loss_date, DATA_CUTOFF)
                closure_probability = 0.18 + 0.012 * min(age_months, 60.0)
                closed = rng.random() < min(0.88, closure_probability)
                treaty = treaty_for(product)
                claim_event_id = str(event["cat_event_id"]) if event else ""

                claims.append({
                    "claim_id": claim_id,
                    "exposure_id": exposure_id,
                    "policy_id": policy_id,
                    "policy_year": year,
                    "product": product,
                    "region": region,
                    "risk_band": risk_band,
                    "loss_date": loss_date.isoformat(),
                    "report_date": report_date.isoformat(),
                    "claim_type": claim_type,
                    "cat_event_id": claim_event_id,
                    "claim_status_at_cutoff": "closed" if closed else "open",
                    "currency": CURRENCY,
                })

                ceded_ultimate = ceded_amount(ultimate, product)
                claim_truth.append({
                    "claim_id": claim_id,
                    "gross_ultimate_eur": format_money(ultimate),
                    "ceded_ultimate_eur": format_money(ceded_ultimate),
                    "net_ultimate_eur": format_money(ultimate - ceded_ultimate),
                })
                generated_loss_total += ultimate

                last_paid = 0.0
                last_fraction = 0.0
                dev_curve = ((3, 0.18), (6, 0.34), (12, 0.55), (24, 0.74), (36, 0.85), (60, 0.94), (72, 0.97))
                product_speed = 1.08 if product == "motor" else 0.92
                for dev_month, base_fraction in dev_curve:
                    valuation_date = add_months(loss_date, dev_month)
                    if valuation_date > DATA_CUTOFF or valuation_date < report_date:
                        continue
                    noisy_fraction = base_fraction * product_speed * (0.94 + 0.12 * rng.random())
                    fraction = min(0.985, max(last_fraction, noisy_fraction))
                    paid = max(last_paid, min(ultimate, ultimate * fraction))
                    final_observed_point = valuation_date == max(
                        (add_months(loss_date, m) for m, _ in dev_curve if add_months(loss_date, m) <= DATA_CUTOFF and add_months(loss_date, m) >= report_date),
                        default=valuation_date,
                    )
                    if closed and final_observed_point:
                        paid = ultimate
                        case_reserve = 0.0
                    else:
                        reserve_noise = 0.78 + 0.42 * rng.random()
                        case_reserve = max(0.0, ultimate - paid) * reserve_noise
                    incurred = paid + case_reserve
                    ceded_paid = ceded_amount(paid, product)
                    ceded_incurred = ceded_amount(incurred, product)
                    ceded_case = max(0.0, ceded_incurred - ceded_paid)
                    development.append({
                        "claim_id": claim_id,
                        "accident_year": year,
                        "valuation_date": valuation_date.isoformat(),
                        "development_months": dev_month,
                        "gross_paid_cumulative_eur": format_money(paid),
                        "gross_case_reserve_eur": format_money(case_reserve),
                        "gross_incurred_eur": format_money(incurred),
                        "ceded_paid_cumulative_eur": format_money(ceded_paid),
                        "ceded_case_reserve_eur": format_money(ceded_case),
                        "ceded_incurred_eur": format_money(ceded_incurred),
                        "net_incurred_eur": format_money(incurred - ceded_incurred),
                        "currency": CURRENCY,
                    })
                    last_paid = paid
                    last_fraction = fraction

            for _ in range(count):
                loss_date = random_day(rng, term_start, term_end)
                add_claim(loss_date)
            generated_count = count

            # Inject a controlled event cluster into eligible property exposure rows.
            event = events_by_year_region.get((year, region))
            if product == "property" and event and term_start <= event["event_date"] <= term_end and rng.random() < 0.12:
                jitter = int(rng.random() * 15) - 7
                event_loss_date = event["event_date"] + timedelta(days=jitter)
                if term_start <= event_loss_date <= term_end:
                    add_claim(event_loss_date, event)
                    generated_count += 1

            policy_truth.append({
                "exposure_id": exposure_id,
                "expected_frequency_per_year": format_rate(expected_frequency, 6),
                "generated_claim_count": generated_count,
                "generated_ultimate_loss_eur": format_money(generated_loss_total),
                "expected_loss_eur": format_money(expected_loss),
            })

    claims.sort(key=lambda row: str(row["claim_id"]))
    development.sort(key=lambda row: (str(row["claim_id"]), int(row["development_months"])))
    claim_truth.sort(key=lambda row: str(row["claim_id"]))
    policy_truth.sort(key=lambda row: str(row["exposure_id"]))

    market_rows: list[dict[str, object]] = []
    month_index = 0
    for year in range(2019, 2026):
        for month in range(1, 13):
            if year == 2025 and month > 12:
                break
            observation_date = date(year, month, 1)
            for tenor in (1, 5, 10, 20):
                base_rate = -0.35 + 0.034 * month_index + 0.13 * math.sin(month_index / 6.0) + 0.018 * tenor
                spread = 95.0 + 5.0 * tenor + 17.0 * math.sin(month_index / 8.0) + (rng.random() - 0.5) * 8.0
                market_rows.append({
                    "valuation_date": observation_date.isoformat(),
                    "currency": CURRENCY,
                    "maturity_years": tenor,
                    "risk_free_rate_pct": format_rate(base_rate, 4),
                    "credit_spread_bps": format_rate(max(20.0, spread), 2),
                    "source_label": "synthetic_not_EIOPA_or_market_data",
                })
            month_index += 1

    event_rows = [
        {
            **event,
            "event_date": event["event_date"].isoformat(),
            "severity_multiplier": format_rate(float(event["severity_multiplier"]), 2),
        }
        for event in EVENTS
    ]
    treaty_rows = [
        {**treaty, "attachment_eur": format_money(float(treaty["attachment_eur"])),
         "limit_eur": format_money(float(treaty["limit_eur"])),
         "participation_pct": format_rate(float(treaty["participation_pct"]), 2)}
        for treaty in TREATIES
    ]
    scenario_rows = [
        {key: (format_rate(value, 2) if isinstance(value, float) else value) for key, value in scenario.items()}
        for scenario in SCENARIOS
    ]

    return {
        "policy_exposure.csv": exposures,
        "claim_header.csv": claims,
        "claim_development.csv": development,
        "reinsurance_treaties.csv": treaty_rows,
        "market_curve.csv": market_rows,
        "catastrophe_events.csv": event_rows,
        "scenario_catalog.csv": scenario_rows,
        "claim_ultimate_truth.csv": claim_truth,
        "policy_year_truth.csv": policy_truth,
    }


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(directory: Path, profile: str, seed: int, policy_count: int) -> dict[str, object]:
    files = []
    for path in sorted(directory.glob("*.csv")):
        _, rows = read_csv(path)
        files.append({"path": path.name, "rows": len(rows), "sha256": sha256_file(path)})
    manifest: dict[str, object] = {
        "dataset_id": "synthetic-actuarial-risk-assessment",
        "dataset_version": "1.0.0",
        "profile": profile,
        "synthetic": True,
        "generator": "scripts/generate_testset.py",
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "policy_count_per_accident_year": policy_count,
        "accident_years": list(ACCIDENT_YEARS),
        "evaluation_cutoff": DATA_CUTOFF.isoformat(),
        "currency": CURRENCY,
        "reporting_currency": CURRENCY,
        "row_counts_and_sha256": files,
        "notes": [
            "Fully synthetic; no real insurer, contract, person, or claim records.",
            "Market curves and catastrophe events are synthetic and are not official data.",
            "Scenario shocks are illustrative test parameters, not regulatory calibration.",
            "Reference truth files are evaluation-only and must not be used as model inputs.",
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def make_defect_fixture(clean_dir: Path, defect_dir: Path, seed: int) -> None:
    if defect_dir.exists():
        shutil.rmtree(defect_dir)
    defect_dir.mkdir(parents=True, exist_ok=True)
    for clean_file in clean_dir.glob("*.csv"):
        shutil.copy2(clean_file, defect_dir / clean_file.name)

    policy_path = defect_dir / "policy_exposure.csv"
    policy_fields, policy_rows = read_csv(policy_path)
    policy_rows.append(dict(policy_rows[0]))  # Exact duplicate exposure key.
    policy_rows[1]["exposure_years"] = "0.000000"
    policy_rows[2]["currency"] = "USD"  # Amounts deliberately remain euro amounts.
    write_csv(policy_path, policy_fields, policy_rows)

    claim_path = defect_dir / "claim_header.csv"
    claim_fields, claim_rows = read_csv(claim_path)
    orphan_claim_id = "CLM-ORPHAN-0001"
    if claim_rows:
        orphan = dict(claim_rows[0])
        orphan.update({
            "claim_id": orphan_claim_id,
            "exposure_id": "EXP-MISSING-999999-2024",
            "policy_id": "POL-MISSING-999999",
            "policy_year": "2024",
            "loss_date": "2024-05-01",
            "report_date": "2024-06-01",
            "cat_event_id": "",
        })
        claim_rows.append(orphan)
    write_csv(claim_path, claim_fields, claim_rows)

    dev_path = defect_dir / "claim_development.csv"
    dev_fields, dev_rows = read_csv(dev_path)
    if dev_rows:
        dev_rows[0]["gross_paid_cumulative_eur"] = "-10.00"
        reserve = float(dev_rows[0]["gross_case_reserve_eur"])
        dev_rows[0]["gross_incurred_eur"] = format_money(reserve - 10.0)
        incurred = float(dev_rows[0]["gross_incurred_eur"])
        ceded = float(dev_rows[0]["ceded_incurred_eur"])
        dev_rows[0]["net_incurred_eur"] = format_money(incurred - ceded)
        duplicate = dict(dev_rows[-1])
        dev_rows.append(duplicate)
    write_csv(dev_path, dev_fields, dev_rows)

    defects = [
        {
            "fixture_id": "DF-001", "validator_code": "DQ-001",
            "file_name": "policy_exposure.csv", "row_key": str(policy_rows[-1]["exposure_id"]),
            "defect_type": "duplicate_exposure_id",
            "expected_detection": "Reject or quarantine duplicate exposure key.",
        },
        {
            "fixture_id": "DF-002", "validator_code": "DQ-002",
            "file_name": "policy_exposure.csv", "row_key": str(policy_rows[1]["exposure_id"]),
            "defect_type": "zero_exposure",
            "expected_detection": "Flag non-positive exposure; do not divide or silently impute.",
        },
        {
            "fixture_id": "DF-003", "validator_code": "DQ-003",
            "file_name": "policy_exposure.csv", "row_key": str(policy_rows[2]["exposure_id"]),
            "defect_type": "currency_mismatch",
            "expected_detection": "Flag unsupported currency/unit or require an explicit conversion.",
        },
        {
            "fixture_id": "DF-004", "validator_code": "DQ-004",
            "file_name": "claim_header.csv", "row_key": orphan_claim_id,
            "defect_type": "orphan_claim_reference",
            "expected_detection": "Flag claim with no matching exposure/policy record.",
        },
        {
            "fixture_id": "DF-005", "validator_code": "DQ-005",
            "file_name": "claim_development.csv", "row_key": f"{dev_rows[0]['claim_id']}:{dev_rows[0]['development_months']}",
            "defect_type": "negative_cumulative_paid",
            "expected_detection": "Flag negative cumulative paid amount.",
        },
        {
            "fixture_id": "DF-006", "validator_code": "DQ-006",
            "file_name": "claim_development.csv", "row_key": f"{dev_rows[-1]['claim_id']}:{dev_rows[-1]['development_months']}",
            "defect_type": "duplicate_claim_development_key",
            "expected_detection": "Flag duplicate claim_id + development_months key.",
        },
    ]
    write_csv(defect_dir / "defect_catalog.csv", DEFECT_FIELDS, defects)
    write_manifest(defect_dir, "defect_fixture", seed, len({row["policy_id"] for row in policy_rows if row.get("policy_id")}))


def generate(output_dir: Path, policy_count: int, seed: int) -> None:
    if policy_count < 50:
        raise ValueError("--policies muss mindestens 50 sein, damit die Segmente sinnvoll getestet werden können.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.glob(".testset-*")):
        raise ValueError(f"Sicherheitsabbruch: offene Generierung/Sicherung in {output_dir}")
    profiles = {
        "clean": {"manifest.json", "policy_exposure.csv", "claim_header.csv",
                  "claim_development.csv", "reinsurance_treaties.csv", "market_curve.csv",
                  "catastrophe_events.csv", "scenario_catalog.csv"},
        "reference": {"manifest.json", "claim_ultimate_truth.csv", "policy_year_truth.csv",
                      "expected_control_totals.json"},
    }
    profiles["defect_fixtures"] = profiles["clean"] | {"defect_catalog.csv"}
    for name, allowed in profiles.items():
        target = output_dir / name
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValueError(f"Sicherheitsabbruch: ungültiger Profilpfad {target}")
        if target.exists() and any(target.iterdir()):
            for entry in target.iterdir():
                if entry.name not in allowed or entry.is_symlink() or not entry.is_file():
                    raise ValueError(f"Sicherheitsabbruch: unerwarteter Eintrag {entry}")
            try:
                manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = None
            if not isinstance(manifest, dict) or manifest.get("dataset_id") != "synthetic-actuarial-risk-assessment":
                raise ValueError(f"Sicherheitsabbruch: kein passendes Manifest in {target}")

    # Same filesystem for directory renames. Keep backups if rollback itself fails.
    staging = Path(tempfile.mkdtemp(prefix=".testset-", dir=output_dir))
    backups = staging / "backups"
    backed_up = []
    installed = []
    try:
        backups.mkdir()
        row_counts = write_profiles(staging, policy_count, seed)
        for name in profiles:
            target = output_dir / name
            if target.exists():
                target.rename(backups / name)
                backed_up.append(name)
            (staging / name).rename(target)
            installed.append(name)
    except BaseException:
        try:
            for name in reversed(installed):
                (output_dir / name).rename(staging / name)
            for name in reversed(backed_up):
                (backups / name).rename(output_dir / name)
        except OSError as exc:
            raise OSError(f"Wiederherstellung fehlgeschlagen; Sicherungen in {backups}") from exc
        shutil.rmtree(staging)
        raise
    shutil.rmtree(staging)
    print(f"Testset erstellt: {output_dir}")
    print(f"  Policen-/Jahresbeobachtungen: {row_counts['policy_exposure.csv']:,}")
    print(f"  Schadenfälle:                {row_counts['claim_header.csv']:,}")
    print(f"  Schadenentwicklungszeilen:   {row_counts['claim_development.csv']:,}")
    print(f"  Zufalls-Seed:                {seed}")
    print("Profile: clean (Eingabe), reference (Ground Truth; getrennt halten), defect_fixtures (absichtlich fehlerhaft).")



def write_profiles(output_dir: Path, policy_count: int, seed: int) -> dict[str, int]:
    tables = build_dataset(policy_count, seed)
    clean_dir = output_dir / "clean"
    reference_dir = output_dir / "reference"
    file_fields = {
        "policy_exposure.csv": POLICY_FIELDS,
        "claim_header.csv": CLAIM_FIELDS,
        "claim_development.csv": DEVELOPMENT_FIELDS,
        "reinsurance_treaties.csv": TREATY_FIELDS,
        "market_curve.csv": MARKET_FIELDS,
        "catastrophe_events.csv": EVENT_FIELDS,
        "scenario_catalog.csv": SCENARIO_FIELDS,
        "claim_ultimate_truth.csv": TRUTH_FIELDS,
        "policy_year_truth.csv": POLICY_TRUTH_FIELDS,
    }

    row_counts: dict[str, int] = {}
    for filename, rows in tables.items():
        if filename.endswith("_truth.csv"):
            row_counts[filename] = write_csv(reference_dir / filename, file_fields[filename], rows)
        else:
            row_counts[filename] = write_csv(clean_dir / filename, file_fields[filename], rows)

    write_manifest(clean_dir, "clean", seed, policy_count)
    reference_totals = {
        "dataset_id": "synthetic-actuarial-risk-assessment",
        "dataset_version": "1.0.0",
        "seed": seed,
        "evaluation_cutoff": DATA_CUTOFF.isoformat(),
        "row_counts": row_counts,
        "total_exposure_years": round(sum(float(row["exposure_years"]) for row in tables["policy_exposure.csv"]), 6),
        "total_gross_premium_eur": round(sum(float(row["gross_premium_eur"]) for row in tables["policy_exposure.csv"]), 2),
        "reported_claim_count": len(tables["claim_header.csv"]),
        "gross_ultimate_loss_eur": round(sum(float(row["gross_ultimate_eur"]) for row in tables["claim_ultimate_truth.csv"]), 2),
        "ceded_ultimate_loss_eur": round(sum(float(row["ceded_ultimate_eur"]) for row in tables["claim_ultimate_truth.csv"]), 2),
        "net_ultimate_loss_eur": round(sum(float(row["net_ultimate_eur"]) for row in tables["claim_ultimate_truth.csv"]), 2),
        "important": "Truth values are evaluation-only; never join them into model features.",
    }
    (reference_dir / "expected_control_totals.json").write_text(
        json.dumps(reference_totals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    reference_file_manifest = []
    for path in sorted(reference_dir.glob("*")):
        if path.is_file():
            reference_file_manifest.append({"path": path.name, "sha256": sha256_file(path)})
    (reference_dir / "manifest.json").write_text(json.dumps({
        "dataset_id": "synthetic-actuarial-risk-assessment",
        "dataset_version": "1.0.0",
        "profile": "evaluation_only_reference",
        "synthetic": True,
        "seed": seed,
        "files": reference_file_manifest,
        "warning": "Do not use truth files as model input or include them in features.",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    make_defect_fixture(clean_dir, output_dir / "defect_fixtures", seed)
    return row_counts


def main() -> int:
    default_output = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "aktuariat-risikobewertung-v1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=default_output, help="Zielordner; Standard: data/synthetic/aktuariat-risikobewertung-v1")
    parser.add_argument("--policies", type=int, default=DEFAULT_POLICY_COUNT, help="Anzahl stabiler Policenprofile pro Unfalljahr (Standard: 2000)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"Deterministischer Seed (Standard: {DEFAULT_SEED})")
    args = parser.parse_args()
    try:
        generate(args.output_dir.resolve(), args.policies, args.seed)
    except (OSError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
