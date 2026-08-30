#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
extension_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/vox-sentry@gnome-vox-sentry"
systemd_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
runtime_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-vox-sentry"
venv_dir="$runtime_dir/venv"

if [ ! -x "$venv_dir/bin/python" ]; then
    mkdir -p "$runtime_dir"
    python3 -m venv --system-site-packages "$venv_dir"
fi

"$venv_dir/bin/python" -m pip install --no-deps "$project_dir"
mkdir -p "$HOME/.local/bin"
ln -sfn "$venv_dir/bin/vox-sentry" "$HOME/.local/bin/vox-sentry"
ln -sfn "$venv_dir/bin/vox-sentryd" "$HOME/.local/bin/vox-sentryd"
mkdir -p "$extension_dir" "$systemd_dir"
if [ -f "$extension_dir/schemas/gschemas.compiled" ]; then
    unlink "$extension_dir/schemas/gschemas.compiled"
fi
if [ -f "$extension_dir/schemas/io.github.gnome_vox_sentry.gschema.xml" ]; then
    unlink "$extension_dir/schemas/io.github.gnome_vox_sentry.gschema.xml"
fi
cp -a "$project_dir/gnome-extension/." "$extension_dir/"
cp "$project_dir/systemd/vox-sentryd.service" "$systemd_dir/"

if command -v glib-compile-schemas >/dev/null 2>&1; then
    glib-compile-schemas "$extension_dir/schemas"
fi

echo "Installed Vox Sentry. Reload the GNOME extension and run:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now vox-sentryd"
echo "Then enable the panel indicator:"
echo "  gnome-extensions enable vox-sentry@gnome-vox-sentry"
echo "On Wayland, log out and back in once before enabling it if GNOME cannot find the extension."
