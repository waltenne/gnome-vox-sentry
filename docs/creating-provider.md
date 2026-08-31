# Creating a provider

1. Create `providers/new-agent/provider.py` and subclass `AgentProvider`.
2. Implement `id`, `name`, `detect`, `get_capabilities`, `get_status` and `get_sessions`.
3. Return `AgentSession` objects using normalized `AgentStatus` values.
4. Set unsupported capability flags to `false`; never create placeholder usage values.
5. Register it in `vox_sentry/builtins.py` and add isolated tests.

Provider code owns all parsing of vendor-specific processes, files, APIs or IPC. Core must never
import vendor-specific fields.
