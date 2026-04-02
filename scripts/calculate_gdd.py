#!/usr/bin/env python3
"""
Calculate Growing Degree Days (GDD) from hourly temperature data.

This script processes hourly temperature CSV files (e.g., from get_hourly_temperature.py)
and calculates daily GDD using base and saturation temperature thresholds.

Usage (command line):
    python scripts/calculate_gdd.py INPUT.CSV [-o OUTPUT.CSV] [--base BASE] [--saturation SAT]

    Arguments:
        INPUT.CSV       - Path to hourly temperature CSV (required)
        -o, --output    - Optional: save to CSV file
        --base          - Base temperature in °C (default: 10)
        --saturation    - Saturation temperature in °C (default: 30)

    Example:
        python scripts/calculate_gdd.py somerset_2024.csv -o somerset_gdd.csv

Usage (as module):
    from scripts.calculate_gdd import calculate_gdd
    df = calculate_gdd("somerset_2024.csv", base=10, saturation=30, output_csv=None)

GDD Calculation:
    For each hour:
        contribution = max(0, min(hourly_temp, saturation) - base)

    For each day:
        daily_gdd = sum(hourly_contributions) / number_of_hours_with_data

    Method 2 (old/simple):
        For each day:
            daily_gdd_old = max(0, 0.5 * (max_temp + min_temp) - base)

    Cumulative GDD is the running total from the first day.

Output CSV columns:
    date, gdd, cumulative_gdd, gdd_old, cumulative_gdd_old
"""

import sys
from pathlib import Path

import pandas as pd


def calculate_gdd(
    input_csv: str,
    base: float = 10.0,
    saturation: float = 30.0,
    output_csv: str | None = None
) -> pd.DataFrame:
    """
    Calculate Growing Degree Days from hourly temperature data.

    Args:
        input_csv: Path to hourly temperature CSV with 'datetime' and 'temperature_c' columns
        base: Base temperature in °C (default: 10)
        saturation: Saturation temperature in °C (default: 30)
        output_csv: Optional path to save CSV file

    Returns:
        DataFrame with columns: date, gdd, cumulative_gdd, gdd_old, cumulative_gdd_old

    Example:
        >>> df = calculate_gdd("somerset_2024.csv", base=10, saturation=30)
        >>> print(df.head())
              date       gdd  cumulative_gdd    gdd_old  cumulative_gdd_old
        0 2024-04-01  7.500000            7.50   7.500000             7.50
        1 2024-04-02  8.125000           15.62   8.125000            15.62
        2 2024-04-03  9.375000           25.00   9.375000            25.00
    """
    df = pd.read_csv(input_csv)

    if "datetime" not in df.columns or "temperature_c" not in df.columns:
        raise ValueError("CSV must contain 'datetime' and 'temperature_c' columns")

    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date

    df = df.dropna(subset=["temperature_c"])

    df["capped_temp"] = df["temperature_c"].clip(upper=saturation)
    df["contribution"] = (df["capped_temp"] - base).clip(lower=0)

    daily = df.groupby("date").agg(
        gdd_sum=("contribution", "sum"),
        hour_count=("contribution", "count"),
        t_min=("temperature_c", "min"),
        t_max=("temperature_c", "max")
    ).reset_index()

    daily["gdd"] = daily["gdd_sum"] / daily["hour_count"]
    daily["cumulative_gdd"] = daily["gdd"].cumsum()

    daily["gdd_old"] = (0.5 * (daily["t_max"] + daily["t_min"]) - base).clip(lower=0)
    daily["cumulative_gdd_old"] = daily["gdd_old"].cumsum()

    result = daily[["date", "gdd", "cumulative_gdd", "gdd_old", "cumulative_gdd_old"]].copy()
    result["date"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m-%d")

    if output_csv:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_csv, index=False)
        print(f"Saved {len(result)} days to {output_csv}")

    return result


def main():
    """Command-line interface for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Calculate Growing Degree Days from hourly temperature data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/calculate_gdd.py somerset_2024.csv -o somerset_gdd.csv
    python scripts/calculate_gdd.py somerset_2024.csv --base 8 --saturation 25
    python scripts/calculate_gdd.py somerset_2024.csv | head -20

GDD Calculation Methods (base=10, saturation=30):
    Method 1 (hourly):
        Hour 01: 20°C -> min(20,30) - 10 = 10
        Hour 12: 35°C -> min(35,30) - 10 = 20 (capped)
        Hour 18:  5°C -> max(0, 5 - 10)  = 0 (below base)

        If 24 hours with sum = 180:
            daily_gdd = 180 / 24 = 7.5

    Method 2 (old/simple):
        daily_gdd_old = max(0, 0.5 * (T_max + T_min) - base)
        """
    )
    parser.add_argument("input_csv", help="Path to hourly temperature CSV")
    parser.add_argument(
        "-o", "--output",
        help="Output CSV file path (default: stdout)"
    )
    parser.add_argument(
        "--base",
        type=float,
        default=10.0,
        help="Base temperature in °C (default: 10)"
    )
    parser.add_argument(
        "--saturation",
        type=float,
        default=30.0,
        help="Saturation temperature in °C (default: 30)"
    )

    args = parser.parse_args()

    if not Path(args.input_csv).exists():
        print(f"Error: Input file not found: {args.input_csv}", file=sys.stderr)
        sys.exit(1)

    print(f"Calculating GDD (base={args.base}°C, saturation={args.saturation}°C)...")

    result = calculate_gdd(
        args.input_csv,
        base=args.base,
        saturation=args.saturation,
        output_csv=args.output
    )

    print(f"\nProcessed {len(result)} days")
    print("\nFirst 10 days:")
    print(result.head(10).to_string(index=False))

    if not args.output:
        print("\n(Use -o to save to file)")


if __name__ == "__main__":
    main()
