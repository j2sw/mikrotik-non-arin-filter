#!/usr/bin/env bash

set -e

URL="https://www.iana.org/assignments/ipv4-address-space/ipv4-address-space.csv"

echo "/ip firewall address-list" > non-arin.rsc

curl -fsSL "$URL" | awk -F, '
NR==1 {next}
{
  prefix=$1
  designation=$2

  if (prefix !~ /^[0-9][0-9][0-9]\/8$/) next

  if (designation ~ /^ARIN$/) next
  if (designation ~ /Administered by ARIN/) next

  oct=prefix
  sub(/\/8/,"",oct)
  oct+=0

  printf "add list=non-arin address=%d.0.0.0/8 comment=\"IANA: %s\"\n", oct, designation
}' >> non-arin.rsc

echo "Generated non-arin.rsc"
