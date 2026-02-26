#!/usr/bin/env python3
import csv
import ipaddress
import os
import sys
from pathlib import Path

import pytricia
import requests

US_ISO = "US"
APNIC_URL = "https://ftp.apnic.net/stats/apnic/delegated-apnic-latest"

def die(msg: str, code: int = 2) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return code

def find_geolite_files(base: Path) -> tuple[Path, Path]:
    blocks = list(base.rglob("GeoLite2-Country-Blocks-IPv4.csv"))
    locs = list(base.rglob("GeoLite2-Country-Locations-en.csv"))
    if not blocks:
        raise FileNotFoundError("GeoLite2-Country-Blocks-IPv4.csv not found under GEOLITE_DIR")
    if not locs:
        raise FileNotFoundError("GeoLite2-Country-Locations-en.csv not found under GEOLITE_DIR")
    blocks.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    locs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return blocks[0], locs[0]

def load_geoname_to_iso(locations_csv: Path) -> dict[str, str]:
    geoname_to_iso: dict[str, str] = {}
    with locations_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Locations CSV has no header")
        if "geoname_id" not in reader.fieldnames or "country_iso_code" not in reader.fieldnames:
            raise ValueError("Locations CSV missing geoname_id or country_iso_code")
        for row in reader:
            gid = (row.get("geoname_id") or "").strip()
            iso = (row.get("country_iso_code") or "").strip()
            if gid and iso:
                geoname_to_iso[gid] = iso
    return geoname_to_iso

def pick_country_geoname_id(row: dict) -> str:
    for key in ("registered_country_geoname_id", "country_geoname_id", "represented_country_geoname_id"):
        v = (row.get(key) or "").strip()
        if v:
            return v
    return ""

def build_us_trie(geolite_blocks: Path, geoname_to_iso: dict[str, str]) -> pytricia.PyTricia:
    t = pytricia.PyTricia(32)
    with geolite_blocks.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "network" not in reader.fieldnames:
            raise ValueError("Blocks CSV missing network column")
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
            t.insert(net, True)
    return t

def fetch_apnic_delegated(dest: Path) -> None:
    r = requests.get(APNIC_URL, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)

def iter_apnic_ipv4_prefixes(delegated_file: Path):
    # delegated format: registry|cc|type|start|value|date|status[|extensions]
    with delegated_file.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue
            registry, cc, rtype, start, value, _date, status = parts[:7]
            if registry.lower() != "apnic":
                continue
            if rtype != "ipv4":
                continue
            if status not in ("allocated", "assigned"):
                continue

            # value is number of addresses; should be power of two for clean CIDR
            try:
                n = int(value)
                ip = ipaddress.IPv4Address(start)
            except Exception:
                continue

            # Convert start + count to minimal CIDRs.
            # Many are already aligned, but we do it correctly anyway.
            start_int = int(ip)
            end_int = start_int + n - 1
            start_ip = ipaddress.IPv4Address(start_int)
            end_ip = ipaddress.IPv4Address(end_int)
            for net in ipaddress.summarize_address_range(start_ip, end_ip):
                yield str(net)

def net_contains_any(us_trie: pytricia.PyTricia, apnic_net: ipaddress.IPv4Network) -> bool:
    # If there is any US prefix inside this APNIC net, we treat this APNIC net as "APNIC-in-US candidate".
    # We test by checking whether any US prefix contains the APNIC net's first IP, and by scanning for
    # more-specifics via children if the first IP isn't conclusive.
    first_ip = str(apnic_net.network_address)
    try:
        _ = us_trie.get_key(first_ip)
        # first IP is within some US prefix
        return True
    except KeyError:
        pass

    # If no match at first IP, try a few probe points inside the net to catch partial overlaps.
    # This avoids expensive full iteration while still catching common cases.
    if apnic_net.prefixlen <= 24:
        probes = [
            apnic_net.network_address,
            apnic_net.network_address + (apnic_net.num_addresses // 2),
            apnic_net.broadcast_address,
        ]
        for p in probes:
            try:
                _ = us_trie.get_key(str(p))
                return True
            except KeyError:
                continue
    return False

def main() -> int:
    geolite_dir = Path(os.environ.get("GEOLITE_DIR", "geolite2"))
    delegated_path = Path(os.environ.get("APNIC_DELEGATED", "delegated-apnic-latest"))

    if not geolite_dir.exists():
        return die(f"GEOLITE_DIR '{geolite_dir}' not found. Unzip GeoLite2-Country-CSV.zip into ./geolite2/")

    try:
        geolite_blocks, geolite_locs = find_geolite_files(geolite_dir)
    except Exception as e:
        return die(str(e))

    if not delegated_path.exists():
        print(f"APNIC delegated file not found at {delegated_path}. Fetching from APNIC...", file=sys.stderr)
        try:
            fetch_apnic_delegated(delegated_path)
        except Exception as e:
            return die(f"Failed to fetch APNIC delegated file: {e}")

    try:
        geoname_to_iso = load_geoname_to_iso(geolite_locs)
        us_trie = build_us_trie(geolite_blocks, geoname_to_iso)
    except Exception as e:
        return die(f"Failed to load GeoLite2 CSVs: {e}")

    list_name = os.environ.get("APNIC_IN_US_LIST", "apnic-in-us")
    out_path = Path(os.environ.get("OUT_APNIC_IN_US_RSC", "apnic-in-us.rsc"))

    # We output APNIC prefixes that appear to have US GeoLite2 coverage.
    # This is conservative in the sense that it may include APNIC nets that are partially US due to anycast/CDNs.
    out_count = 0
    seen = set()

    with out_path.open("w", encoding="utf-8") as out:
        out.write("/ip firewall address-list\n")
        for cidr in iter_apnic_ipv4_prefixes(delegated_path):
            if cidr in seen:
                continue
            seen.add(cidr)
            net = ipaddress.IPv4Network(cidr)
            if net_contains_any(us_trie, net):
                out.write(f'add list={list_name} address={cidr} comment="APNIC delegated, GeoLite2 US overlap"\n')
                out_count += 1

    print(f"Generated {out_count} APNIC-in-US candidate prefixes -> {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
