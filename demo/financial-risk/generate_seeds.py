#!/usr/bin/env python3
"""Generate seed data for financial-risk demo with random seed 44."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_positions(output_path: Path, num_rows: int = 500) -> None:
    """Generate raw_positions.csv with 500 rows."""
    random.seed(44)

    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "position_id",
                "portfolio_id",
                "instrument_id",
                "quantity",
                "entry_price",
                "entry_date",
                "_loaded_at",
            ]
        )

        for i in range(1, num_rows + 1):
            position_id = f"POS{i:04d}"
            portfolio_id = f"PORT{random.randint(1, 20):03d}"
            instrument_id = f"INST{random.randint(1, 100):03d}"
            quantity = random.randint(1, 10000)
            entry_price = round(random.uniform(1.0, 5000.0), 2)

            # Random date in 2024-2025
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2025, 12, 31)
            days_between = (end_date - start_date).days
            entry_date = start_date + timedelta(days=random.randint(0, days_between))

            loaded_at = "2026-01-15T00:00:00Z"

            writer.writerow(
                [
                    position_id,
                    portfolio_id,
                    instrument_id,
                    quantity,
                    f"{entry_price:.2f}",
                    entry_date.strftime("%Y-%m-%d"),
                    loaded_at,
                ]
            )


def generate_market_data(output_path: Path, num_rows: int = 1000) -> None:
    """Generate raw_market_data.csv with 1000 rows."""
    random.seed(44)

    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "instrument_id",
                "date",
                "close_price",
                "volume",
                "volatility",
                "_loaded_at",
            ]
        )

        # Generate daily data for instruments across Oct-Dec 2025
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 12, 31)
        num_days = (end_date - start_date).days + 1

        instruments = [f"INST{i:03d}" for i in range(1, 101)]
        dates = [start_date + timedelta(days=i) for i in range(num_days)]

        # Generate rows by cycling through instruments and dates
        rows_generated = 0
        while rows_generated < num_rows:
            for instrument_id in instruments:
                if rows_generated >= num_rows:
                    break

                date = dates[rows_generated % len(dates)]
                close_price = round(random.uniform(1.0, 5000.0), 2)
                volume = random.randint(1000, 10000000)
                volatility = round(random.uniform(0.01, 0.80), 4)
                loaded_at = "2026-01-15T00:00:00Z"

                writer.writerow(
                    [
                        instrument_id,
                        date.strftime("%Y-%m-%d"),
                        f"{close_price:.2f}",
                        volume,
                        f"{volatility:.4f}",
                        loaded_at,
                    ]
                )

                rows_generated += 1


def generate_counterparties(output_path: Path, num_rows: int = 100) -> None:
    """Generate raw_counterparties.csv with 100 rows."""
    random.seed(44)

    bank_prefixes = [
        "Bank of",
        "Capital",
        "Financial",
        "Trust",
        "Securities",
        "Holdings",
    ]
    bank_suffixes = [
        "Alpha",
        "Beta",
        "Gamma",
        "Delta",
        "Omega",
        "Prime",
        "Global",
        "International",
    ]
    ratings = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]
    countries = ["US", "UK", "DE", "JP", "CH", "SG", "HK", "AU", "CA", "FR"]

    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "counterparty_id",
                "name",
                "rating",
                "country",
                "exposure_limit",
                "_loaded_at",
            ]
        )

        for i in range(1, num_rows + 1):
            counterparty_id = f"CP{i:03d}"
            name = f"{random.choice(bank_prefixes)} {random.choice(bank_suffixes)}"
            rating = random.choice(ratings)
            country = random.choice(countries)
            exposure_limit = random.randint(1000000, 500000000)
            loaded_at = "2026-01-15T00:00:00Z"

            writer.writerow(
                [counterparty_id, name, rating, country, exposure_limit, loaded_at]
            )


if __name__ == "__main__":
    seeds_dir = Path(__file__).parent / "seeds"
    seeds_dir.mkdir(exist_ok=True)

    print("Generating raw_positions.csv...")
    generate_positions(seeds_dir / "raw_positions.csv")

    print("Generating raw_market_data.csv...")
    generate_market_data(seeds_dir / "raw_market_data.csv")

    print("Generating raw_counterparties.csv...")
    generate_counterparties(seeds_dir / "raw_counterparties.csv")

    print("Seed generation complete!")
