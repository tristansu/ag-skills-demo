#!/usr/bin/env python3
"""
Get Hourly Temperature Data from Open-Meteo API.

This script retrieves hourly temperature data for a given lat/lon coordinate
from the Open-Meteo Historical Forecast API. It automatically falls back to
NASA POWER daily data for dates before 2022-01-01.

Usage (command line):
    python scripts/get_hourly_temperature.py LAT LON START_DATE END_DATE [-o OUTPUT.CSV]

    Arguments:
        LAT        - Latitude (e.g., 38.6022)
        LON        - Longitude (e.g., -120.6619399)
        START_DATE - Start date (YYYY-MM-DD, e.g., 2024-01-01)
        END_DATE   - End date (YYYY-MM-DD, e.g., 2024-12-31)
        -o         - Optional: save to CSV file

    Example:
        python scripts/get_hourly_temperature.py 38.6022 -120.6619399 2024-04-01 2024-11-15 -o somerset_2024.csv

Usage (as module):
    from scripts.get_hourly_temperature import get_hourly_temperature
    df = get_hourly_temperature(lat, lon, start_date, end_date, output_csv=None)

API Documentation:
    Open-Meteo: https://open-meteo.com/en/docs/historical-forecast-api
    NASA POWER: https://power.larc.nasa.gov/docs/

Output CSV columns:
    datetime, temperature_c, lat, lon, source
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

# Configuration
OPEN_METEO_BASE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Default parameters - T2M is mean temperature
DEFAULT_PARAMS_OPEN_METEO = "temperature_2m"
DEFAULT_PARAMS_NASA_POWER = "T2M"


def install_deps():
    """Install required packages if missing."""
    packages = ["pandas", "requests", "tqdm"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + packages, check=True)


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object."""
    if isinstance(date_str, datetime):
        return date_str
    return datetime.strptime(date_str, "%Y-%m-%d")


def make_request_with_retry(url: str, params: dict, max_attempts: int = 10, timeout: int = 60) -> requests.Response:
    """
    Make HTTP GET request with exponential backoff retry.

    Args:
        url: API endpoint URL
        params: Query parameters
        max_attempts: Maximum retry attempts (default 10)
        timeout: Request timeout in seconds (default 60)

    Returns:
        Response object

    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_attempts - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    raise requests.exceptions.RequestException("Max retries exceeded")


def get_week_chunks(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Split date range into weekly (start, end) tuples."""
    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)
    
    chunks = []
    current = start_dt
    while current <= end_dt:
        chunk_end = min(current + timedelta(days=6), end_dt)
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + timedelta(days=1)
    
    days_diff = (end_dt - start_dt).days + 1
    print(f"  Date range: {start_date} to {end_date} ({days_diff} days)")
    print(f"  Splitting into {len(chunks)} weekly chunk(s) for API requests...")
    
    return chunks


def get_open_meteo_hourly(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str
) -> pd.DataFrame | None:
    """
    Fetch hourly temperature from Open-Meteo Historical Forecast API.
    Automatically splits date range into weekly chunks to avoid timeouts.
    Failed chunks are retried with 3-day sub-chunks.

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        DataFrame with hourly temperature data, or None on failure
    """
    chunks = get_week_chunks(start_date, end_date)
    
    all_records = []
    chunk_num = 0
    failed_chunks = []
    
    print(f"\n  Fetching from Open-Meteo:")
    for chunk_start, chunk_end in tqdm(chunks, desc="    Weekly chunks", unit="chunk", leave=True):
        chunk_num += 1
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": chunk_start,
            "end_date": chunk_end,
            "hourly": DEFAULT_PARAMS_OPEN_METEO,
            "timezone": "auto",
            "format": "json"
        }

        try:
            response = make_request_with_retry(OPEN_METEO_BASE_URL, params)
            response.raise_for_status()
            data = response.json()

            hourly_data = data.get("hourly", {})
            times = hourly_data.get("time", [])
            temps = hourly_data.get("temperature_2m", [])

            if times:
                for i, t in enumerate(times):
                    temp = temps[i] if i < len(temps) else None
                    all_records.append({
                        "datetime": t,
                        "temperature_c": temp,
                    })
            else:
                failed_chunks.append((chunk_start, chunk_end))

        except requests.exceptions.RequestException as e:
            print(f"    Chunk {chunk_start} to {chunk_end} failed: {e}")
            failed_chunks.append((chunk_start, chunk_end))
        
        time.sleep(3.0)  # rate limiting between chunks

    # Retry failed chunks with 3-day sub-chunks
    if failed_chunks:
        print(f"\n  Retrying {len(failed_chunks)} failed chunk(s) with 3-day sub-chunks...")
        sub_chunk_size = 3
        
        for chunk_start, chunk_end in tqdm(failed_chunks, desc="    Retrying failed", unit="chunk", leave=True):
            sub_start = parse_date(chunk_start)
            sub_end = parse_date(chunk_end)
            current = sub_start
            
            while current <= sub_end:
                sub_end_date = min(current + timedelta(days=sub_chunk_size - 1), sub_end)
                sub_start_str = current.strftime("%Y-%m-%d")
                sub_end_str = sub_end_date.strftime("%Y-%m-%d")
                
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": sub_start_str,
                    "end_date": sub_end_str,
                    "hourly": DEFAULT_PARAMS_OPEN_METEO,
                    "timezone": "auto",
                    "format": "json"
                }
                
                print(f"    Retry: {sub_start_str} to {sub_end_str}...", end=" ")
                
                try:
                    response = make_request_with_retry(OPEN_METEO_BASE_URL, params)
                    response.raise_for_status()
                    data = response.json()
                    
                    hourly_data = data.get("hourly", {})
                    times = hourly_data.get("time", [])
                    temps = hourly_data.get("temperature_2m", [])
                    
                    if times:
                        for i, t in enumerate(times):
                            temp = temps[i] if i < len(temps) else None
                            all_records.append({
                                "datetime": t,
                                "temperature_c": temp,
                            })
                        print(f"OK ({len(times)} records)")
                    else:
                        print("No data")
                        
                except requests.exceptions.RequestException as e:
                    print(f"Failed: {e}")
                
                current = sub_end_date + timedelta(days=1)
                time.sleep(3.0)

    if not all_records:
        print("  No data retrieved from Open-Meteo")
        return None

    df = pd.DataFrame(all_records)
    print(f"  Retrieved {len(df)} hourly records from Open-Meteo")
    return df


def get_nasa_power_daily(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str
) -> pd.DataFrame | None:
    """
    Fetch daily temperature from NASA POWER API (fallback for pre-2022 data).

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        DataFrame with daily temperature data, or None on failure
    """
    params = {
        "parameters": DEFAULT_PARAMS_NASA_POWER,
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
        "format": "JSON"
    }

    print(f"\n  Fetching from NASA POWER:")
    for _ in tqdm(range(1), desc="    NASA POWER request", unit="request", leave=True):
        try:
            response = make_request_with_retry(NASA_POWER_BASE_URL, params)
            response.raise_for_status()
            data = response.json()

            param_data = data["properties"]["parameter"]
            first_param = list(param_data.keys())[0]
            dates = list(param_data[first_param].keys())

            if not dates:
                print("  No data returned from NASA POWER")
                return None

            records = []
            for d in dates:
                t2m = param_data["T2M"].get(d, -999.0)

                records.append({
                    "datetime": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                    "temperature_c": None if t2m == -999.0 else t2m,
                })

            df = pd.DataFrame(records)
            print(f"    Retrieved {len(df)} daily records (fallback)")
            return df

        except requests.exceptions.RequestException as e:
            print(f"    NASA POWER request failed: {e}")
            return None


def get_hourly_temperature(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    output_csv: str | None = None
) -> pd.DataFrame:
    """
    Retrieve hourly temperature data for a given coordinate.

    Automatically uses Open-Meteo for dates >= 2022-01-01, and falls back
    to NASA POWER daily data for older dates.

    Args:
        lat: Latitude of the location
        lon: Longitude of the location
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_csv: Optional path to save CSV file

    Returns:
        DataFrame with columns:
            - datetime: Timestamp
            - temperature_c: Temperature (°C)
            - lat: Input latitude
            - lon: Input longitude
            - source: "open-meteo" or "nasa-power"
    """
    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)

    cutoff_date = datetime(2022, 1, 1)

    print("\n" + "=" * 60)
    print("Step 1 of 3: Preparing request...")
    print(f"  Location: ({lat}, {lon})")
    print(f"  Date range: {start_date} to {end_date}")
    print("=" * 60)

    dataframes = []

    print("\n" + "=" * 60)
    print("Step 2 of 3: Fetching temperature data...")
    print("=" * 60)

    if start_dt < cutoff_date:
        pre_2022_end = min(end_dt, datetime(2021, 12, 31))
        if start_dt <= pre_2022_end:
            pre_start = start_dt.strftime("%Y-%m-%d")
            pre_end = pre_2022_end.strftime("%Y-%m-%d")
            df_pre = get_nasa_power_daily(lat, lon, pre_start, pre_end)
            if df_pre is not None:
                df_pre["source"] = "nasa-power"
                dataframes.append(df_pre)

        if end_dt >= cutoff_date:
            df_post = get_open_meteo_hourly(lat, lon, "2022-01-01", end_date)
            if df_post is not None:
                df_post["source"] = "open-meteo"
                dataframes.append(df_post)
    else:
        df = get_open_meteo_hourly(lat, lon, start_date, end_date)
        if df is not None:
            df["source"] = "open-meteo"
            dataframes.append(df)

    if not dataframes:
        raise ValueError("No temperature data retrieved for the given date range")

    print("\n" + "=" * 60)
    print("Step 3 of 3: Processing and combining results...")
    print("=" * 60)

    result = pd.concat(dataframes, ignore_index=True)

    result["lat"] = lat
    result["lon"] = lon

    result = result[[
        "datetime",
        "temperature_c",
        "lat",
        "lon",
        "source"
    ]]

    if output_csv:
        Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_csv, index=False)
        print(f"  Saved {len(result)} records to {output_csv}")

    return result


def main():
    """Command-line interface for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Get hourly temperature data for a lat/lon coordinate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/get_hourly_temperature.py 45.5152 -122.6784 2024-06-01 2024-06-03
    python scripts/get_hourly_temperature.py 45.5152 -122.6784 2024-01-01 2024-12-31 -o temps.csv
        """
    )
    parser.add_argument("lat", type=float, help="Latitude (e.g., 45.5152)")
    parser.add_argument("lon", type=float, help="Longitude (e.g., -122.6784)")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "-o", "--output",
        help="Output CSV file path (optional)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Hourly Temperature Data Retrieval")
    print("=" * 60)
    print(f"Location: ({args.lat}, {args.lon})")
    print(f"Date range: {args.start_date} to {args.end_date}")
    print("=" * 60)

    try:
        df = get_hourly_temperature(
            args.lat,
            args.lon,
            args.start_date,
            args.end_date,
            args.output
        )

        print("\n" + "=" * 60)
        print(f"Retrieved {len(df)} records")
        print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Source: {df['source'].unique()}")
        print("=" * 60)
        print("\nSample data:")
        print(df.head(10).to_string(index=False))

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()