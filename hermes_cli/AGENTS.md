# hermes_cli/ — CLI Subcommands & Infrastructure

**Parent:** Root AGENTS.md (CLI architecture, slash commands, config system, skin engine)

## OVERVIEW
74 files, ~83k LOC. CLI subcommands, setup wizard, config management, auth, model resolution, profiles, dashboard, gateway CLI, and all `hermes <subcommand>` handlers.

## KEY SUBSYSTEMS

### Core Entry & Parsing
- `main.py` (~12k LOC) — argparse tree, `_apply_profile_override()`, `_require_tty()` guard
- `_parser.py` — top-level parser, `_inherited_flag()` for relaunch-aware flags
- `relaunch.py` — self-re-exec preserving `--tui`, `--dev`, `--profile`, `--model` across process replacement

### Command Registry
- `commands.py` (~1.3k LOC) — `COMMAND_REGISTRY`, `CommandDef`, `resolve_command()`, platform menu generators

### Configuration
- `config.py` (~5.1k LOC) — `DEFAULT_CONFIG`, `OPTIONAL_ENV_VARS`, `_config_version`, thread-safe caching (`_CONFIG_LOCK`), managed mode (`is_managed()`)
- `env_loader.py` — `.env` loading with credential sanitization

### Auth System (5-file chain)
- `auth.py` (~5.4k LOC) — monolith: OAuth flows, `auth.json` persistence, cross-process file locking
- `auth_commands.py` — `hermes auth add/list/remove/test`
- `copilot_auth.py`, `dingtalk_auth.py`, `vercel_auth.py` — provider-specific flows

### Model Resolution (6-file chain)
- `providers.py` — provider identity (single source of truth)
- `model_normalize.py` — per-provider name formatting
- `model_catalog.py` — remote catalog fetcher + disk cache
- `models.py` (~3.6k LOC) — canonical model catalogs
- `model_switch.py` (~1.8k LOC) — switch pipeline for CLI and gateway `/model`
- `runtime_provider.py` — runtime provider resolution

### Windows Compatibility (3 dedicated modules)
- `_subprocess_compat.py` — all `if win32` branching centralized here
- `stdio.py` — UTF-8 console configuration
- `gateway_windows.py` — service management via Scheduled Tasks

## WHERE TO LOOK

| Task | File(s) |
|------|---------|
| Add `hermes <subcommand>` | Add argparse in `main.py` → create handler module → dispatch in `main.py` |
| Add a slash command | `commands.py` CommandDef → `cli.py` process_command handler → `gateway/run.py` if gateway-available |
| Change config defaults | `config.py` DEFAULT_CONFIG (bump `_config_version` ONLY if migration needed) |
| Add new .env variable | `config.py` OPTIONAL_ENV_VARS with metadata dict |
| Change model resolution | `model_switch.py` (switching) or `runtime_provider.py` (resolution) |
| Change auth flow | `auth.py` (core) + provider-specific file if new OAuth provider |
| Profile operations | `profiles.py` — create/delete/use/list/export/import |
| Dashboard API | `web_server.py` FastAPI endpoints |
| Setup wizard | `setup.py` — modular section-based wizard |

## CONVENTIONS

- **`cli_output.py` shared helpers**: Use `print_info/success/warning/error/header()` — do NOT duplicate print helpers in new modules
- **`_require_tty(command_name)`**: Must guard any subcommand using curses or `input()`. Prevents 100% CPU on piped stdin
- **`_inherited_flag()` over `add_argument()`**: New persistent flags MUST use `_inherited_flag()` so they survive relaunch
- **`flush_stdin()` after curses**: Must call after `curses.wrapper()` returns, before any `input()`/`getpass()`, to prevent buffered escape corruption
- **Managed mode**: Check `is_managed()` before writing config/env — emit `managed_error()` instead
- **Config thread safety**: `_CONFIG_LOCK` (RLock) on all read/write. `_LOAD_CONFIG_CACHE` uses `(mtime_ns, size)` invalidation. Atomic writes preserve stat-based invalidation
- **No inline platform checks**: Use `_subprocess_compat.py` helpers instead of `if sys.platform == "win32"`

## GOTCHAS

- **`main.py` is ~12k LOC** — the entire argparse tree and subcommand dispatch lives here
- **`auth.py` is ~5.4k LOC** — monolith handling all auth flows. Changes here affect CLI, gateway, and cron
- **Colons in model names**: Reserved for OpenRouter variants. Provider:model syntax uses `/` separator internally
- **Oneshot mode (`-z`)**: `oneshot.py` bypasses `cli.py` entirely. No banner, spinner, session. Sets `HERMES_YOLO_MODE=1`
- **`kanban_db.py` is ~4.6k LOC** — SQLite-backed, multi-board, multi-profile. Effectively its own subsystem
- **`gateway.py` is ~5.4k LOC** — handles systemd/launchd service management + process lifecycle
