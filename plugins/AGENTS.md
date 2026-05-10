# plugins/ — Plugin System

**Parent:** Root AGENTS.md (plugin surfaces, memory/model-provider plugins, rules)
**Authoring guides:** `website/docs/developer-guide/model-provider-plugin.md`, `memory-provider-plugin.md`, `context-engine-plugin.md`, `image-gen-provider-plugin.md`

## OVERVIEW
Multi-surface plugin system with 5 kinds, 4 independent discovery systems, and 37 plugin manifests across 15 top-level directories.

## FIVE PLUGIN KINDS

| Kind | Auto-Load? | Selection | Examples |
|------|-----------|-----------|----------|
| standalone | No (`plugins.enabled`) | Opt-in | disk-cleanup, langfuse, google_meet |
| backend | Yes (if bundled) | Category config | spotify, image_gen providers |
| exclusive | No (single-select) | `<category>.provider` config | memory providers, context engines |
| platform | Yes (if bundled) | Gateway adapter | irc, google_chat, teams |
| model-provider | No (lazy) | First `get_provider_profile()` call | 28 provider plugins |

## FOUR DISCOVERY SYSTEMS (Independent)

1. **General PluginManager** (`hermes_cli/plugins.py`): Scans bundled/user/project/pip for `plugin.yaml` + `__init__.py` with `register(ctx)`. Handles standalone/backend/platform.
2. **Memory Provider** (`plugins/memory/__init__.py`): Scans `plugins/memory/<name>/` + `$HERMES_HOME/plugins/`. Loads ONE active provider via `memory.provider`.
3. **Model Provider** (`providers/__init__.py`): Lazy scan of `plugins/model-providers/<name>/`. Each calls `register_provider(ProviderProfile(...))`.
4. **Context Engine** (`plugins/context_engine/__init__.py`): Scans `plugins/context_engine/<name>/`. Loads ONE active engine via `context.engine`.

## plugin.yaml SCHEMA

```yaml
name: string                    # Required
kind: standalone|backend|exclusive|platform|model-provider
version: string
description: string
author: string
platforms: [linux, macos]       # OS gate
provides_tools: [tool_name]
provides_hooks: [post_tool_call]
requires_env:                   # String or rich-dict form
  - API_KEY_VAR                 # Simple
  - name: IRC_SERVER            # Rich (for setup wizard)
    description: "IRC server"
    prompt: "Server"
    password: false
optional_env: [...]             # Non-blocking env vars
pip_dependencies: [...]         # Python packages
```

## PLUGIN CONTEXT REGISTRATION METHODS

| Method | Purpose |
|--------|---------|
| `register_tool()` | Add tool to global registry |
| `register_hook()` | Lifecycle callback (pre/post tool, session start/end, etc.) |
| `register_command()` | Slash command in sessions |
| `register_cli_command()` | `hermes <subcommand>` in argparse |
| `register_platform()` | Gateway messaging adapter |
| `register_image_gen_provider()` | Image generation backend |
| `register_context_engine()` | Context compression engine |
| `register_skill()` | Plugin-bundled skill |
| `dispatch_tool()` | Call a tool from plugin code |
| `inject_message()` | Push message into active conversation |

## VALID LIFECYCLE HOOKS

`pre_tool_call`, `post_tool_call`, `transform_terminal_output`, `transform_tool_result`, `transform_llm_output`, `pre_llm_call`, `post_llm_call`, `pre_api_request`, `post_api_request`, `on_session_start`, `on_session_end`, `on_session_finalize`, `on_session_reset`, `subagent_stop`, `pre_gateway_dispatch`, `pre_approval_request`, `post_approval_response`

## WHERE TO LOOK

| Task | File(s) |
|------|---------|
| Add a standalone plugin | Create `plugins/<name>/plugin.yaml` + `__init__.py` with `register(ctx)` |
| Add a memory provider | See `website/docs/developer-guide/memory-provider-plugin.md` |
| Add a model provider | See `website/docs/developer-guide/model-provider-plugin.md` + `plugins/model-providers/README.md` |
| Add a gateway platform | See `gateway/platforms/ADDING_A_PLATFORM.md` + register via `ctx.register_platform()` |
| Change plugin discovery | `hermes_cli/plugins.py` (general) or category `__init__.py` (specific) |
| Debug plugin loading | `HERMES_PLUGINS_DEBUG=1` — verbose discovery logging |

## GOTCHAS

- **Plugins MUST NOT modify core files** — expand the plugin surface instead
- **Asset-only directories** exist (hermes-achievements, kanban/dashboard, example-dashboard) — NO `__init__.py`, loaded by web server not plugin system
- **Auto-coercion**: Without explicit `kind:`, PluginManager detects memory/model-provider from `__init__.py` source text
- **`HERMES_BUNDLED_PLUGINS`** override for Nix/packaged installs
- **`HERMES_ENABLE_PROJECT_PLUGINS=1`** opt-in for `./.hermes/plugins/` scanning
- **Memory provider CLI auto-wiring**: `discover_plugin_cli_commands()` loads `cli.py` from ONLY the active provider
- **Model-provider scan is lazy**: Triggered on first `get_provider_profile()` or `list_providers()`, NOT at import time
- **`pip_dependencies`** in plugin.yaml used by setup wizard, not consumed by plugin loader itself
