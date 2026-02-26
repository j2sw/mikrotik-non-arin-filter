#!/usr/bin/env python3
"""
generate-geolite-us.py

Reads MaxMind GeoLite2 Country CSV files and generates a MikroTik RouterOS
address-list import file containing US-geolocated IPv4 prefixes.

Features:
- Finds GeoLite2 CSVs anywhere under GEOLITE_DIR (default: ./geolite2)
- Joins Blocks IPv4 -> Locations by geoname_id
- Keeps only US (country_iso_code == "US")
- Filters out anything more specific than /24 (keeps prefixlen <= 24)
- Collapses adjacent networks to reduce list size
- Outputs RouterOS .rsc with /ip firewall address-list lines

Usage:
  python3 generate-geolite-us.py

Environment overrides:
  GEOLITE_DIR     Path to unzipped GeoLite2-Country-CSV_* directory (default: geolite2)
  OUT_US_RSC      Output filename (default: geo-allow-us.rsc)
  US_LIST_NAME    RouterOS list name (default: geo-allow-us)
  US_COMMENT      Comment text (default: GeoLite2 US)
  MAX_PREFIXLEN   Keep only prefixes with prefixlen <= this value (default: 24)
"""

import csv
import glob
import os
import sys
import ipaddress
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


US_ISO = "US"


def find_newest(pattern: str) -> Path:
    matches = glob.glob(pattern, recursive=True)
    if not matches:
        raise FileNotFoundError(f"No matches for: {pattern}")
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return Path(matches[0])


def find_geolite_files(base_dir: Path) -> Tuple[Path, Path]:
    blocks = find_newest(str(base_dir / "**" / "GeoLite2-Country-Blocks-IPv4.csv"))
    locs = find_newest(str(base_dir / "**" / "GeoLite2-Country-Locations-en.csv"))
    return blocks, locs


def load_geoname_to_iso(locations_csv: Path) -> Dict[str, str]:
    geoname_to_iso: Dict[str, str] = {}
    with locations_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        required = {"geoname_id", "country_iso_code"}
        if not required.issubset(fields):
            raise ValueError(
                f"{locations_csv} missing required columns {required}. Found: {fields}"
            )
        for row in reader:
            gid = (row.get("geoname_id") or "").strip()
            iso = (row.get("country_iso_code") or "").strip()
            if gid and iso:
                geoname_to_iso[gid] = iso
    return geoname_to_iso


def pick_country_geoname_id(row: Dict[str, str]) -> str:
    # Prefer registered_country_geoname_id where available.
    for key in (
        "registered_country_geoname_id",
        "country_geoname_id",
        "represented_country_geoname_id",
    ):
        v = (row.get(key) or "").strip()
        if v:
            return v
    return ""


def iter_us_networks(
    blocks_csv: Path, geoname_to_iso: Dict[str, str], max_prefixlen: int
) -> Iterable[ipaddress.IPv4Network]:
    with blocks_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        if "network" not in fields:
            raise ValueError(f"{blocks_csv} missing 'network' column. Found: {fields}")

        for row in reader:
            gid = pick_country_geoname_id(row)
            if not gid:
                continue
            iso = geoname_to_iso.get(gid)
            if iso != US_ISO:
                continue

            net_str = (row.get("network") or "").strip()
            if not net_str:
                continue

            try:
                net = ipaddress.IPv4Network(net_str, strict=False)
            except Exception:
                continue

            # Filter out anything more specific than /24 (e.g. /25-/32)
            if net.prefixlen <= max_prefixlen:
                yield net


def main() -> int:
    geolite_dir = Path(os.environ.get("GEOLITE_DIR", "geolite2"))
    out_path = Path(os.environ.get("OUT_US_RSC", "geo-allow-us.rsc"))
    list_name = os.environ.get("US_LIST_NAME", "geo-allow-us")
    comment = os.environ.get("US_COMMENT", "GeoLite2 US")
    try:
        max_prefixlen = int(os.environ.get("MAX_PREFIXLEN", "24"))
    except ValueError:
        print("ERROR: MAX_PREFIXLEN must be an integer", file=sys.stderr)
        return 2

    if not geolite_dir.exists():
        print(
            f"ERROR: GEOLITE_DIR '{geolite_dir}' not found. "
            f"Unzip GeoLite2-Country-CSV.zip into ./{geolite_dir}/",
            file=sys.stderr,
        )
        return 2

    try:
        blocks_csv, locations_csv = find_geolite_files(geolite_dir)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        geoname_to_iso = load_geoname_to_iso(locations_csv)
    except Exception as e:
        print(f"ERROR: Failed to load locations CSV: {e}", file=sys.stderr)
        return 2

    # Collect and collapse to reduce entries
    nets: List[ipaddress.IPv4Network] = list(
        iter_us_networks(blocks_csv, geoname_to_iso, max_prefixlen)
    )
    if not nets:
        print("ERROR: No US networks found. Check GeoLite2 files and paths.", file=sys.stderr)
        return 2

    collapsed = list(ipaddress.collapse_addresses(nets))

    with out_path.open("w", encoding="utf-8") as out:
        out.write("/ip firewall address-list\n")
        for net in collapsed:
            out.write(f'add list={list_name} address={net} comment="{comment}"\n')

    print(f"GeoLite2 blocks file: {blocks_csv}")
    print(f"GeoLite2 locations file: {locations_csv}")
    print(f"Kept prefixes with prefixlen <= /{max_prefixlen}")
    print(f"US prefixes before collapse: {len(nets)}")
    print(f"US prefixes after  collapse: {len(collapsed)}")
    print(f"Generated -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())