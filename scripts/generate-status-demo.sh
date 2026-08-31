#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir="$project_dir/docs/assets"
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT

command -v convert >/dev/null 2>&1 || {
    printf '%s\n' 'ImageMagick (convert) is required to generate the documentation GIF.' >&2
    exit 1
}

declare -a statuses=(
    'OFFLINE|Offline|#7a7a7a'
    'IDLE|Idle|#2fb344'
    'THINKING|Thinking|#a855f7'
    'WORKING|Working|#3b82f6'
    'WAITING|Waiting|#facc15'
    'COMPLETED|Completed|#22c55e'
    'ERROR|Error|#ef4444'
    'RATE_LIMITED|Rate limited|#f97316'
    'UNKNOWN|Unknown|#94a3b8'
)

frame=0
for entry in "${statuses[@]}"; do
    IFS='|' read -r code label color <<< "$entry"
    frame_path="$temp_dir/frame-${frame}.png"
    convert -size 900x300 xc:'#101214' \
        -fill '#f4f4f4' -font DejaVu-Sans-Bold -pointsize 30 -gravity North \
        -annotate +0+28 'Vox Sentry · Status Indicator' \
        -fill "$color" -draw 'circle 450,145 450,121' \
        -fill '#f4f4f4' -font DejaVu-Sans-Bold -pointsize 24 -gravity Center \
        -annotate +0+52 "$label" \
        -fill '#a6aab1' -font DejaVu-Sans -pointsize 16 -gravity South \
        -annotate +0+24 "$code · one semantic color" \
        "$frame_path"
    frame=$((frame + 1))
done

mkdir -p "$output_dir"
convert -delay 75 -dispose Background -loop 0 "$temp_dir"/frame-*.png "$output_dir/status-demo.gif"
printf 'Generated %s\n' "$output_dir/status-demo.gif"
