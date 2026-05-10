# tools/ — Agent Tool Implementations

**Parent:** Root AGENTS.md (tool registration pattern, toolsets, anti-patterns)

## OVERVIEW
78 tool registrations across 31 files, plus 42 utility modules and 4 subdirectory architectures. Auto-discovered via `registry.py` AST scanning.

## REGISTRY API (`registry.py`)

```python
registry.register(
    name=str, toolset=str, schema=dict, handler=Callable,
    check_fn=Callable=None,      # TTL-cached 30s availability check
    requires_env=list=None,      # env vars for availability display
    is_async=bool=False,         # auto-bridged via _run_async
    dynamic_schema_overrides=Callable=None,  # runtime schema mutation
    max_result_size_chars=int=None,
)
```

**Helper functions:** `tool_error(msg)` / `tool_result(data)` — use these instead of raw `json.dumps`
**Discovery:** `discover_builtin_tools()` AST-scans for `registry.register()` calls at module top-level
**Thread safety:** `threading.RLock` on all mutations; `_snapshot_entries()` for stable reader copies

## SUBDIRECTORY ARCHITECTURES (all follow ABC + factory pattern)

| Subdirectory | ABC | Backends | Selection |
|-------------|-----|----------|-----------|
| environments/ | `base.py` BaseEnvironment | local, docker, ssh, singularity, modal, daytona, vercel_sandbox | `TERMINAL_ENV` config |
| browser_providers/ | `base.py` CloudBrowserProvider | browserbase, browser_use, firecrawl | `_PROVIDER_REGISTRY` |
| computer_use/ | `backend.py` ComputerUseBackend | cua_backend (MCP over stdio) | fixed |
| web_providers/ | `base.py` WebSearchProvider + WebExtractProvider | ddgs, brave_free, searxng | `web.search_backend` / `web.extract_backend` config |

## WHERE TO LOOK

| Task | File(s) |
|------|---------|
| Add a new tool | Create `tools/<name>.py` with `registry.register()` → add to `toolsets.py` |
| Add a terminal backend | `environments/<name>.py` → implement BaseEnvironment ABC → wire into `terminal_tool._create_environment()` |
| Add a browser provider | `browser_providers/<name>.py` → implement CloudBrowserProvider ABC → add to `_PROVIDER_REGISTRY` |
| Change approval logic | `approval.py` (dangerous commands, allowlist, smart approval) |
| Tool result persistence | `tool_result_storage.py` (3-layer: per-tool → per-result → per-turn budget) |
| Path security | `path_security.py` (validate_within_dir), `env_passthrough.py` (sandbox env allowlist) |
| Schema cleanup | `schema_sanitizer.py` (strips allOf/anyOf/oneOf/enum/not at top level) |

## CONVENTIONS

- **All handlers MUST return JSON string** — use `tool_error()` / `tool_result()` helpers
- **`check_fn` TTL 30s** — external state probes (Docker, Modal, playwright) cached. Call `invalidate_check_fn_cache()` after config changes
- **Tool shadowing rejected** — built-in tools cannot be shadowed by plugins. Only MCP-to-MCP overwrites allowed
- **`dynamic_schema_overrides`** — zero-arg callable returning schema overrides at `get_definitions()` time
- **MCP tool naming** — `mcp-{server_name}_{original_tool_name}` with toolset `mcp-{server_name}`
- **File state coordination** — `file_state.py` prevents cross-agent write conflicts with per-path locks

## KEY UTILITY MODULES

| Module | Purpose |
|--------|---------|
| approval.py | Dangerous command detection, per-session approval state |
| interrupt.py | Per-thread interrupt signaling (`is_interrupted/set_interrupt/clear_interrupt`) |
| env_passthrough.py | Session-scoped env var allowlist for sandboxes (ContextVar-backed) |
| credential_files.py | File mount registry for remote terminal backends |
| patch_parser.py | V4A patch format (Update/Add/Delete/Move File) |
| fuzzy_match.py | 8-strategy fuzzy text matching for LLM-generated patches |
| tool_output_limits.py | Configurable truncation (max_bytes, max_lines, max_line_length) |
| budget_config.py | Tool result size thresholds |
| osv_check.py | OSV malware check for MCP extension packages |

## GOTCHAS

- **`_last_resolved_tool_names` is process-global in `model_tools.py`** — saved/restored around subagent execution. May be stale during child runs
- **`discover_builtin_tools()` uses AST** — NOT import-based. Files without top-level `registry.register()` calls are skipped
- **Sandbox env var security** — `env_passthrough.py` enforces `_HERMES_PROVIDER_ENV_BLOCKLIST` to prevent credential exfiltration into sandboxes
- **3-layer result persistence** — per-tool cap → per-result `maybe_persist_tool_result` → per-turn `enforce_turn_budget`. Files go to `/tmp/hermes-results/`
