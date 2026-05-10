# gateway/ — Messaging Gateway

**Parent:** Root AGENTS.md (project overview, config loaders, anti-patterns)
**Adding platforms:** See `platforms/ADDING_A_PLATFORM.md` for the 16-step checklist.

## OVERVIEW
Unified messaging gateway supporting 22+ platforms from a single process. Async event loop with adapter multiplexing, agent caching, streaming, and cron delivery.

## STRUCTURE
```
gateway/
├── run.py              # GatewayRunner (~16k LOC) — main controller
├── session.py          # SessionStore, SessionContext, session key building
├── config.py           # Platform enum, GatewayConfig, PlatformConfig
├── stream_consumer.py  # Sync-to-async streaming bridge
├── hooks.py            # HookRegistry (gateway:startup, session:*, agent:*, command:*)
├── status.py           # PID detection, runtime state, scoped token locks
├── platform_registry.py # Plugin adapter self-registration
├── delivery.py         # DeliveryRouter for cron/send_message routing
├── platforms/          # 22 built-in adapters + base.py + helpers.py
└── builtin_hooks/      # Extension point (none shipped)
```

## MESSAGE FLOW (Two-Guard Architecture)

1. **Guard 1** (base adapter `handle_message()`): Session ACTIVE → queue in `_pending_messages`, signal interrupt. Session IDLE → spawn `_process_message_background()`
2. **Guard 2** (GatewayRunner `_handle_message()`): Intercepts `/stop`, `/new`, `/queue`, `/status`, `/approve`, `/deny` BEFORE reaching agent. New control commands MUST bypass BOTH guards.

## BASE ADAPTER INTERFACE (`platforms/base.py`)

**Required:** `connect()`, `disconnect()`, `send(chat_id, content, reply_to, metadata)`
**Optional:** `edit_message`, `delete_message`, `send_typing`, `send_image`, `send_voice`, `send_document`, `send_slash_confirm`
**Key data:** `MessageEvent` (inbound), `SendResult` (outbound), `EphemeralReply` (auto-delete with TTL)
**State:** `_active_sessions`, `_pending_messages`, `_session_tasks`, `_background_tasks`

## WHERE TO LOOK

| Task | File(s) |
|------|---------|
| Add a new platform | `platforms/ADDING_A_PLATFORM.md` + `platform_registry.py` |
| Change message routing | `run.py` `_handle_message()` |
| Modify session persistence | `session.py` SessionStore |
| Change streaming behavior | `stream_consumer.py` GatewayStreamConsumer |
| Add gateway hooks | `hooks.py` HookRegistry |
| Cross-platform delivery | `delivery.py` DeliveryRouter + `mirror.py` |

## CONVENTIONS

- **contextvars over os.environ**: `session_context.py` uses ContextVar for HERMES_SESSION_* — prevents concurrent task crosstalk. Use `get_session_env()` not `os.getenv()`
- **Agent cache**: LRU (128 max) + idle TTL (1hr) + config_signature matching. Preserves prefix-cache-friendly AIAgent instances
- **EphemeralReply**: Return from slash handlers for auto-deletion. Base adapter schedules `delete_message()` after TTL
- **REQUIRES_EDIT_FINALIZE**: Class attr on adapters with distinct streaming UI (DingTalk AI Cards)
- **Scoped token locks**: `acquire_scoped_lock(scope, identity)` prevents two profiles from using same bot token
- **Per-platform display tiers**: high (Telegram/Discord), medium (Slack/Matrix), low (WhatsApp/Signal), minimal (Email/SMS)
- **Proxy chain**: Platform env > HTTPS_PROXY > macOS scutil > NO_PROXY exclusion

## GOTCHAS

- **`run.py` is ~16k LOC** — the single largest file in the repo. Most gateway logic lives here
- **Auto-continue freshness window**: After restart, interrupted turns only resume if last timestamp < 1hr
- **Platform enum `_missing_()`**: Accepts dynamic members for plugin-registered platforms
- **Streaming flood-strike**: 3 consecutive edit failures disables progressive editing for that session
- **`_http_client_limits.py`**: Shared tight keepalive limits — prevents fd exhaustion from long-lived adapter HTTP clients
- **WhatsApp identity canonicalization** (`whatsapp_identity.py`): LID vs phone JID resolved through bridge mapping files
