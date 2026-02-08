#!/usr/bin/env python3
"""Generate synthetic IoT telemetry seed data with reproducible random seed."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Set random seed for reproducibility
random.seed(43)

SEEDS_DIR = Path(__file__).parent / "seeds"
SEEDS_DIR.mkdir(exist_ok=True)

# Constants
LOADED_AT = "2026-01-15T00:00:00Z"
SENSOR_TYPES = ["temperature", "pressure", "vibration", "humidity", "flow_rate"]
LOCATIONS = ["line_a", "line_b", "line_c", "warehouse_1", "warehouse_2"]
MAINTENANCE_TYPES = ["preventive", "corrective", "predictive", "emergency"]
TECHNICIANS = [f"Tech_{chr(65 + i)}" for i in range(10)]  # Tech_A through Tech_J

# Sensor type to unit mapping
UNITS = {
    "temperature": "celsius",
    "pressure": "bar",
    "vibration": "mm_s",
    "humidity": "percent",
    "flow_rate": "l_min",
}

# Value ranges by sensor type
VALUE_RANGES = {
    "temperature": (15.0, 95.0),
    "pressure": (0.5, 15.0),
    "vibration": (0.0, 100.0),
    "humidity": (20.0, 99.0),
    "flow_rate": (1.0, 500.0),
}


def generate_sensors() -> None:
    """Generate raw_sensors.csv - 200 rows."""
    output_path = SEEDS_DIR / "raw_sensors.csv"

    with output_path.open("w", newline="") as csvfile:
        fieldnames = [
            "sensor_id",
            "equipment_id",
            "sensor_type",
            "location",
            "installed_at",
            "_loaded_at",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # 50 equipment units, each with 4 sensors (200 total)
        for sensor_num in range(1, 201):
            equipment_num = ((sensor_num - 1) // 4) + 1
            installed_date = datetime(2022, 1, 1) + timedelta(
                days=random.randint(0, 1095)  # 3 years
            )

            writer.writerow(
                {
                    "sensor_id": f"S{sensor_num:03d}",
                    "equipment_id": f"EQ{equipment_num:03d}",
                    "sensor_type": random.choice(SENSOR_TYPES),
                    "location": random.choice(LOCATIONS),
                    "installed_at": installed_date.strftime("%Y-%m-%d"),
                    "_loaded_at": LOADED_AT,
                }
            )

    print(f"Generated {output_path} (200 rows)")


def generate_readings() -> None:
    """Generate raw_readings.csv - 1000 rows."""
    output_path = SEEDS_DIR / "raw_readings.csv"

    # Pre-generate sensor types for each sensor_id
    sensor_types = {}
    for sensor_num in range(1, 201):
        sensor_types[f"S{sensor_num:03d}"] = random.choice(SENSOR_TYPES)

    with output_path.open("w", newline="") as csvfile:
        fieldnames = [
            "reading_id",
            "sensor_id",
            "timestamp",
            "value",
            "unit",
            "_loaded_at",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Generate 1000 readings across November-December 2025
        start_date = datetime(2025, 11, 1)
        end_date = datetime(2025, 12, 31, 23, 59, 59)
        total_seconds = int((end_date - start_date).total_seconds())

        for reading_num in range(1, 1001):
            sensor_id = f"S{random.randint(1, 200):03d}"
            sensor_type = sensor_types[sensor_id]
            min_val, max_val = VALUE_RANGES[sensor_type]

            timestamp = start_date + timedelta(seconds=random.randint(0, total_seconds))
            value = round(random.uniform(min_val, max_val), 2)

            writer.writerow(
                {
                    "reading_id": f"R{reading_num:04d}",
                    "sensor_id": sensor_id,
                    "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
                    "value": value,
                    "unit": UNITS[sensor_type],
                    "_loaded_at": LOADED_AT,
                }
            )

    print(f"Generated {output_path} (1000 rows)")


def generate_maintenance_log() -> None:
    """Generate raw_maintenance_log.csv - 100 rows."""
    output_path = SEEDS_DIR / "raw_maintenance_log.csv"

    with output_path.open("w", newline="") as csvfile:
        fieldnames = [
            "log_id",
            "equipment_id",
            "maintenance_type",
            "performed_at",
            "technician",
            "_loaded_at",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Generate 100 maintenance records throughout 2025
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 12, 31, 23, 59, 59)
        total_seconds = int((end_date - start_date).total_seconds())

        for log_num in range(1, 101):
            equipment_id = f"EQ{random.randint(1, 50):03d}"
            performed_at = start_date + timedelta(
                seconds=random.randint(0, total_seconds)
            )

            writer.writerow(
                {
                    "log_id": f"ML{log_num:03d}",
                    "equipment_id": equipment_id,
                    "maintenance_type": random.choice(MAINTENANCE_TYPES),
                    "performed_at": performed_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    "technician": random.choice(TECHNICIANS),
                    "_loaded_at": LOADED_AT,
                }
            )

    print(f"Generated {output_path} (100 rows)")


if __name__ == "__main__":
    generate_sensors()
    generate_readings()
    generate_maintenance_log()
    print("\n✓ All seed files generated successfully")
