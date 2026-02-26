# MikroTik Non-ARIN IPv4 Filter

This project generates a MikroTik firewall address list containing
all IPv4 /8 blocks not administered by ARIN.

Data source:
IANA IPv4 Address Space Registry
https://www.iana.org/assignments/ipv4-address-space/

## Purpose

Drop inbound traffic to routers from non-ARIN IPv4 space.

## Generate List

./generate-non-arin.sh

## Import Into MikroTik

Upload to your mikrotik
/import file-name=non-arin.rsc
/import file-name=geo-allow-us.rsc
/import file-name=apnic-in-us.rsc

The verify counts
/ip firewall address-list print count-only where list="non-arin"
/ip firewall address-list print count-only where list="geo-allow-us"
/ip firewall address-list print count-only where list="apnic-in-us"

4) Don’t lock yourself out
Before you add the drop rule, do these two things:
Confirm you have an out-of-band path (console, VPN from a known IP, or local LAN access).
Add and test mgmt-allow and make sure it matches your real source IP.

## Example Firewall Rule

/ip firewall filter
add chain=input in-interface-list=WAN \
    src-address-list=non-arin \
    action=drop \
    comment="Drop non-ARIN sources"
