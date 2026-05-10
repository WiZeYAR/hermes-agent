# agent/ — Internal Agent Architecture

**Parent:** Root AGENTS.md (project overview, dependency chain, anti-patterns)

## OVERVIEW
Agent internals: provider adapters, memory/context/image-gen ABCs, transport layer, credential management, prompt assembly. NOT the agent loop itself (that's `run_agent.py`).

## FOUR ABSTRACT BASE CLASSES

| ABC | File | Extended By | Key Methods |
|-----|------|-------------|-------------|
| MemoryProvider | `memory_provider.py` | plugins/memory/* | initialize, prefetch, sync_turn, get_tool_schemas, handle_tool_call, on_session_switch |
| ContextEngine | `context_engine.py` | plugins/context_engine/* | update_from_response, should_compress, compress, on_session_start |
| ImageGenProvider | `image_gen_provider.py` | plugins/image_gen/* | generate, is_available, list_models |
| ProviderTransport | `transports/base.py` | transports/*.py | convert_messages, convert_tools, build_kwargs, normalize_response |

## TRANSPORT vs ADAPTER

**Transports** (`agent/transports/`) own the normalized data path — convert in/out to `NormalizedResponse`.
**Adapters** (`agent/*_adapter.py`) own SDK client construction and low-level format conversion.
A new provider typically needs changes in BOTH layers.

Transport registry: `transports/__init__.py` auto-discovers on first `get_transport()`.
Built-in transports: `chat_completions` (default), `anthropic_messages`, `codex_responses`, `bedrock`.

## KEY FILES

| File | LOC | Role |
|------|-----|------|
| auxiliary_client.py | ~4200 | Central provider resolver, failover, credential rotation, `call_llm()` for all side-LLM tasks |
| prompt_builder.py | ~1448 | System prompt assembly, skills manifest, context files |
| context_compressor.py | ~1556 | LLM-based summarization (extends ContextEngine) |
| credential_pool.py | ~1603 | Multi-credential failover pool |
| error_classifier.py | ~1058 | FailoverReason enum (17 categories), `classify_api_error()` |
| curator.py | ~1750 | Background skill review loop |
| display.py | ~1008 | KawaiiSpinner, skin integration |

## WHERE TO LOOK

| Task | File(s) |
|------|---------|
| Add a new transport | `transports/<name>.py` → implement ABC → `register_transport()` at module bottom |
| Add a new provider adapter | `agent/<name>_adapter.py` → wire into `auxiliary_client.py` |
| Add a new memory provider | `agent/memory_provider.py` ABC → `plugins/memory/<name>/` |
| Change error classification | `error_classifier.py` FailoverReason enum |
| Modify system prompt | `prompt_builder.py` |
| Context compression | `context_compressor.py` + `context_references.py` |

## CONVENTIONS

- **Lazy imports everywhere**: Most modules use local imports to prevent circular deps given the dense web
- **`get_hermes_home()` for all paths**: 17/52 files import it from `hermes_constants`. Never `Path.home() / ".hermes"`
- **Register-at-import-time**: Transports, credential sources, providers self-register when imported
- **`logger = logging.getLogger(__name__)`**: Universal pattern (33/52 files)
- **Fail-open error handling in MemoryManager**: Every provider call try/except'd. One failure never blocks others

## GOTCHAS

- **auxiliary_client.py is ~4200 LOC** — handles ALL provider resolution, failover, side-LLM calls. Changes here ripple everywhere
- **NormalizedResponse backward compat**: `ToolCall.function` returns `self`, `ToolCall.type` returns `"function"` — shim for 45+ call sites in run_agent.py
- **StreamingContextScrubber** (memory_manager.py): Stateful state machine that scrubs `<memory-context>` from streaming deltas
- **StreamingThinkScrubber** (think_scrubber.py): Same pattern for `<think xmlns>` XML blocks
- **SubdirectoryHintTracker**: Discovers AGENTS.md/CLAUDE.md in tool-navigated subdirectories, appends to tool results (not system prompt)
- **Provider-specific schema sanitizers**: `gemini_schema.py`, `moonshot_schema.py` strip unsupported JSON Schema features
- **Credential removal registry** (credential_sources.py): Each auth source registers a RemovalStep for clean revocation
