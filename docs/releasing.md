# Releasing Vox Sentry

Releases are created from an annotated semantic-version tag. The GitHub Actions workflow at
`.github/workflows/release.yml` runs the test suite, Python linting, JavaScript syntax checks,
ShellCheck, GNOME tooling, the GNOME `shexli` static analyzer and the EGO package validator before
publishing the extension bundle. The workflow pins `shexli` to `0.2.1` and `tree-sitter` below
`0.26` because the current analyzer crashes with the newer parser ABI; this keeps the release
pipeline reproducible until `shexli` publishes a compatible fix.

## Release procedure

1. Update `project.version` in `pyproject.toml` and the corresponding entry in `CHANGELOG.md`.
2. Run the local checks and package validation:

   ```bash
   pytest -q
   ruff check vox_sentry providers tests
   ./pack-ego.sh dist
   python -m pip install shexli==0.2.1 'tree-sitter<0.26'
   shexli --format text dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
   ./scripts/validate-ego-package.sh \
     dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
   sha256sum dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
   ```

3. Commit the release changes and create an annotated tag with the exact project version:

   ```bash
   git tag -a v0.1.0 -m "Release Vox Sentry 0.1.0"
   git push origin main --follow-tags
   ```

4. The workflow publishes a GitHub Release containing the reviewable
   `vox-sentry@gnome-vox-sentry.shell-extension.zip` and its SHA-256 checksum. It also stores the
   same files as workflow artifacts.

The workflow never stores GNOME account credentials and does not automate a browser login. This
keeps the EGO account protected and leaves the authenticated upload under the maintainer's control.

## Uploading to extensions.gnome.org

After the GitHub Release is green, download the ZIP from the release and open the upload page:

<https://extensions.gnome.org/accounts/login/?next=/upload/>

Log in, upload the exact `.shell-extension.zip` asset, and select the GNOME Shell version(s) that
were actually tested. Keep the UUID stable and do not upload the source repository, `dist/`, Python
daemon, tests, documentation or installation scripts. The bundle is intentionally limited to the
extension runtime, Preferences client, schema, stylesheet, license and required JavaScript
modules.

Before submitting, verify the checksum shown in the release and retain the EGO review URL in the
release notes or project issue. Address reviewer feedback in a new tag/release rather than
replacing an already published asset.
