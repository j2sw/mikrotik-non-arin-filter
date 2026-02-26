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

On RouterOS v7, the actual commands usually look like this, run from terminal after the files exist on the router:

/import file-name=geo-allow-us.rsc

/import file-name=apnic-in-us.rsc

/import file-name=non-arin.rsc

## Raw Firewall Rules
/ip firewall raw
add chain=prerouting in-interface-list=WAN dst-address-type=local src-address-list=apnic-in-us action=accept comment="RAW: allow APNIC-in-US to router"

add chain=prerouting in-interface-list=WAN dst-address-type=local src-address-list=geo-allow-us action=accept comment="RAW: allow US Geo to router"

add chain=prerouting in-interface-list=WAN dst-address-type=local src-address-list=non-arin action=drop comment="RAW: drop non-ARIN to router"

This geofences only traffic destined to the router.

Transit is untouched.

If you host services for customers, scope geo only to those public IPs.

First create the list:
/ip firewall address-list

add list=ISP-HOSTED-SERVICES address=X.X.X.X comment="VoIP/SBC"

add list=ISP-HOSTED-SERVICES address=Y.Y.Y.Y comment="Other hosted service"

/ip firewall raw
add chain=prerouting in-interface-list=WAN dst-address-list=ISP-HOSTED-SERVICES src-address-list=apnic-in-us action=accept comment="RAW: allow APNIC-in-US to hosted"

add chain=prerouting in-interface-list=WAN dst-address-list=ISP-HOSTED-SERVICES src-address-list=geo-allow-us action=accept comment="RAW: allow US Geo to hosted"

add chain=prerouting in-interface-list=WAN dst-address-list=ISP-HOSTED-SERVICES src-address-list=non-arin action=drop comment="RAW: drop non-ARIN to hosted"

These do not apply to transit
