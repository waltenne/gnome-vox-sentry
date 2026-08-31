#!/usr/bin/env bash
set -euo pipefail

package=${1:?usage: $0 PATH_TO_SHELL_EXTENSION_ZIP}
expected_uuid='vox-sentry@gnome-vox-sentry'
expected_name="${expected_uuid}.shell-extension.zip"

if [[ ! -f "$package" ]]; then
    printf 'Package not found: %s\n' "$package" >&2
    exit 1
fi

if [[ $(basename "$package") != "$expected_name" ]]; then
    printf 'Unexpected package name: %s (expected %s)\n' "$(basename "$package")" "$expected_name" >&2
    exit 1
fi

unzip -tq "$package" >/dev/null
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
unzip -q "$package" -d "$work_dir"

required_files=(
    LICENSE
    metadata.json
    extension.js
    prefs.js
    notificationManager.js
    soundManager.js
    stylesheet.css
    schemas/org.gnome.shell.extensions.vox-sentry.gschema.xml
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$work_dir/$file" ]]; then
        printf 'Required file is missing: %s\n' "$file" >&2
        exit 1
    fi
done

while IFS= read -r file; do
    if [[ "$file" == /* || "$file" == *'../'* || "$file" == '..' || "$file" == ../* ]]; then
        printf 'Unsafe path in package: %s\n' "$file" >&2
        exit 1
    fi
    case "$file" in
        *.py|*.pyc|*.map|schemas/gschemas.compiled|install.sh|pack-ego.sh|systemd/*|tests/*|docs/*)
            printf 'Development/runtime file must not be in EGO package: %s\n' "$file" >&2
            exit 1
            ;;
    esac
done < <(unzip -Z1 "$package")

python3 - "$work_dir/metadata.json" "$expected_uuid" <<'PY'
import json
import sys

metadata_path, expected_uuid = sys.argv[1:]
with open(metadata_path, encoding="utf-8") as stream:
    metadata = json.load(stream)

required = {"uuid", "name", "description", "shell-version", "url", "settings-schema"}
missing = required - metadata.keys()
if missing:
    raise SystemExit(f"metadata.json is missing: {', '.join(sorted(missing))}")
if metadata["uuid"] != expected_uuid:
    raise SystemExit(f"metadata UUID is {metadata['uuid']!r}, expected {expected_uuid!r}")
if not metadata["shell-version"] or any(not isinstance(version, str) for version in metadata["shell-version"]):
    raise SystemExit("metadata shell-version must be a non-empty list of strings")
if "version" in metadata:
    raise SystemExit("metadata.json must not contain the deprecated version key")
if metadata["settings-schema"] != "org.gnome.shell.extensions.vox-sentry":
    raise SystemExit("metadata settings-schema does not match the extension schema")
PY

schema="$work_dir/schemas/org.gnome.shell.extensions.vox-sentry.gschema.xml"
grep -Fq '<schema id="org.gnome.shell.extensions.vox-sentry"' "$schema"
grep -Fq 'path="/org/gnome/shell/extensions/vox-sentry/"' "$schema"
grep -Fq 'GNU GENERAL PUBLIC LICENSE' "$work_dir/LICENSE"

printf 'EGO package is valid: %s\n' "$package"
