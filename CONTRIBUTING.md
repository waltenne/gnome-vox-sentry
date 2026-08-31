# Contributing

Vox Sentry has two runtime boundaries: the Python daemon performs provider discovery and the GNOME
Shell extension presents normalized state. Keep provider I/O and process inspection out of the
Shell process.

Before opening a pull request, run:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]' ruff
pytest -q
ruff check vox_sentry providers tests
for file in gnome-extension/*.js; do node --check "$file"; done
./pack-ego.sh dist
```

For release candidates, use Python 3.12 and run `shexli` plus
`scripts/validate-ego-package.sh` as documented in [docs/releasing.md](docs/releasing.md).

Changes affecting provider detection, D-Bus behavior, lifecycle cleanup, notifications or package
contents should include tests and an update to the relevant documentation. Do not add a provider
polling loop, subprocess storm or Shell-side filesystem scan without measuring and documenting its
need.
