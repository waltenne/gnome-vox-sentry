#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
output_dir=${1:-"$project_dir/dist"}

mkdir -p "$output_dir"
gnome-extensions pack \
    --force \
    --out-dir "$output_dir" \
    --extra-source=notificationManager.js \
    --extra-source=soundManager.js \
    --extra-source=statusPresentation.js \
    --extra-source="$project_dir/LICENSE" \
    "$project_dir/gnome-extension"
