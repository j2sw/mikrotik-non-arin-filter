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

Upload non-arin.rsc to your router:

/import file-name=non-arin.rsc

## Example Firewall Rule

/ip firewall filter
add chain=input in-interface-list=WAN \
    src-address-list=non-arin \
    action=drop \
    comment="Drop non-ARIN sources"
