## Summary

<!-- What changed and why? -->

## Validation

- [ ] `pytest -q`
- [ ] `ruff check vox_sentry providers tests`
- [ ] JavaScript syntax checks
- [ ] EGO package generated and inspected (when applicable)
- [ ] Performance impact considered (when applicable)

## GNOME lifecycle

- [ ] Resources created in `enable()` are cleaned up in `disable()`.
- [ ] Signals, timers, cancellables and notifications have bounded lifetimes.
