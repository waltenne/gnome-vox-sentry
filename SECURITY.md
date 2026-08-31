# Security policy

Vox Sentry is local-first. The daemon reads local process and provider session metadata and exposes
it only through the user session D-Bus bus. It must not log prompts, responses, source files,
credentials or access tokens.

Please do not publish sensitive information in a public issue. Report a suspected vulnerability
privately to the repository maintainer through the contact method listed on the GitHub repository.
Include affected version, reproduction steps and the smallest useful diagnostic output.

The GNOME Shell package intentionally excludes the Python daemon, provider executables, tests and
development scripts. Custom audio paths are treated as untrusted input and are validated before
playback.
