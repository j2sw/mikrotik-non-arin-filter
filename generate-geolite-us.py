#!/usr/bin/env python3
import csv
import glob
import os
import sys
from pathlib import Path

US_ISO = "US"

def find_one(pattern: str) -> Path:
    matches = glob.glob(pattern)
    if len(matches) == 0:
        raise FileNotFoundError(f"No matches for: {pattern}")
    if len(matches) > 1:
        # pick newest by mtime
        matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return Path(matches[0])

def load_geoname_to_iso(locations_csv: Path) -> dict[str, str]:
    geoname_to_iso: dict[str, str] = {}
    with locations_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"geoname_id", "country_iso_code"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError(f"{locations_csv} missing columns: {required}")
        for row in reader:
            gid = (row.get("geoname_id") or "").strip()
            iso = (row.get("country_iso_code") or "").strip()
            if gid and iso:
                geoname_to_iso[gid] = iso
    return geoname_to_iso

def pick_country_geoname_id(row: dict) -> str:
    # MaxMind blocks file can have multiple ids; prefer registered_country_geoname_id if present.
    for key in ("registered_country_geoname_id", "country_geoname_id", "represented_country_geoname_id"):
        v = (row.get(key) or "").strip()
        if v:
            return v
    return ""

def main() -> int:
    base = Path(os.environ.get("GEOLITE_DIR", "geolite2"))
    if not base.exists():
        print(f"ERROR: GEOLITE_DIR '{base}' not found. Unzip GeoLite2-Country-CSV.zip into ./geolite2/", file=sys.stderr)
        return 2

    blocks = find_one(str(base / "**" / "GeoLite2-Country-Blocks-IPv4.csv"))
    locs = find_one(str(base / "**" / "GeoLite2-Country-Locations-en.csv"))

    geoname_to_iso = load_geoname_to_iso(locs)

    out_path = Path(os.environ.get("OUT_US_RSC", "geo-allow-us.rsc"))
    list_name = os.environ.get("US_LIST_NAME", "geo-allow-us")
    comment = os.environ.get("US_COMMENT", "GeoLite2 US")

    count = 0
    with blocks.open(newline="", encoding="utf-8") as f, out_path.open("w", encoding="utf-8") as out:
        reader = csv.DictReader(f)
        if "network" not in (reader.fieldnames or []):
            print(f"ERROR: {blocks} missing column 'network'", file=sys.stderr)
            return 2

        out.write("/ip firewall address-list\n")
        for row in reader:
            gid = pick_country_geoname_id(row)
            if not gid:
                continue
            iso = geoname_to_iso.get(gid)
            if iso != US_ISO:
                continue

            net = (row.get("network") or "").strip()
            if not net:
                continue

            out.write(f'add list={list_name} address={net} comment="{comment}"\n')
            count += 1

    print(f"Generated {count} US prefixes -> {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
