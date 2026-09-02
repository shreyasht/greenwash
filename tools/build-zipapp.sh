#!/bin/sh
# Build a self-contained astroturf.pyz — the NFR-3 offline install path.
#
# No pip, no PyPI, no dependency access required to *run* it:
#     curl -O https://github.com/shreyasht/astroturf/releases/latest/download/astroturf.pyz
#     python3 astroturf.pyz --help
#
# Python stdlib only, so the single archive is the whole tool.
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
out="${1:-$root/dist/astroturf.pyz}"

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

cp -r "$root/astroturf" "$stage/astroturf"
find "$stage" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$(dirname "$out")"
python3 -m zipapp "$stage" \
    --main "astroturf.cli:_console" \
    --python "/usr/bin/env python3" \
    --compress \
    --output "$out"

echo "built $out"
