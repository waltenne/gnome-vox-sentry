# Gemini and Antigravity providers

Vox Sentry observes Google coding agents locally and keeps the provider boundary intentionally
small.

## Gemini

The Gemini provider looks for the `gemini` executable and live Gemini processes. It classifies a
process as `cli` unless its environment/command identifies VS Code, A2A or ACP; those sessions are
reported as `vscode`. It reads only the first metadata header of the newest file under
`~/.gemini/tmp/**/chats/*.jsonl`. A session file modified in the last few seconds is evidence of a
working turn; an open process without a recent update is idle.

This intentionally does not parse the `messages` records. Gemini usage and quota data are not
reported yet.

## Antigravity

The Antigravity provider recognizes the Linux `agy` backend and the `antigravity` launcher. A live
hub is exposed as one session, with `desktop` or `vscode` as its source. The provider combines the
local conversation database, process log and descendant agent workers: message streaming marks the
session working, a completed step marks it idle, and the process tree is the fallback. It reports
the process working directory as the workspace and does not read trajectory contents.

Antigravity usage is read from the authenticated Cloud Code quota service used by `agy`. The
provider first requests the shared five-hour and weekly quota summary and falls back to the
project-scoped model quota response when the summary is unavailable. Fractions are converted to
used percentages and reset timestamps are preserved. If the account is not authenticated or the
service denies quota access (for example, a plan or regional entitlement), the UI intentionally
shows `Consumption: Unavailable` rather than guessing. Values are cached for 60 seconds so the
daemon does not contact the service on every status refresh.
