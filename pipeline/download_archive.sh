#!/bin/sh
# Download the FIRMS yearly world archives (public, no login) into data/global/zips/, three at a time; resumable.
# Run: sh pipeline/download_archive.sh
dir="$(dirname "$0")/../data/global/zips"
mkdir -p "$dir" && cd "$dir" || exit 1
B=https://firms.modaps.eosdis.nasa.gov/data/country/zips

get() {
  for i in $(seq 12); do
    # a stalled transfer (under 2 kB/s for 45 s) is dropped and resumed
    curl -sS -L --speed-limit 2000 --speed-time 45 --connect-timeout 30 -C - -o "$1" "$B/$1"
    case $? in
      0 | 22 | 33) return 0 ;; # 22, 33: the file is already complete (range not satisfiable)
    esac
    sleep 5
  done
  echo "FAILED $1"
}

files() {
  for y in $(seq 2012 2025); do echo "viirs-snpp_${y}_all_countries.zip"; done
  for y in $(seq 2000 2025); do echo "modis_${y}_all_countries.zip"; done
  for y in $(seq 2018 2025); do echo "viirs-jpss1_${y}_all_countries.zip"; done
}

n=0
for f in $(files); do
  get "$f" &
  n=$((n + 1))
  [ $((n % 3)) -eq 0 ] && wait
done
wait
echo done
