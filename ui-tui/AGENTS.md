# ui-tui/ — Terminal UI (Ink + React)

**Parent:** Root AGENTS.md (TUI architecture, process model, dev commands, dashboard embedding)

## OVERVIEW
Full terminal UI replacement for classic CLI. Ink (React) for rendering, Python backend for sessions/tools/model calls. Two-process: Node renders, Python thinks.

## STRUCTURE
```
ui-tui/
├── src/
│   ├── entry.tsx          # TTY gate → GatewayClient → Ink render
│   ├── app.tsx            # Root <App> (25 LOC, delegates to useMainApp)
│   ├── gatewayClient.ts   # JSON-RPC transport (stdio + WebSocket, 700 LOC)
│   ├── gatewayTypes.ts    # Wire protocol types (40+ response types)
│   ├── theme.ts           # Light/dark + skin merge + ANSI normalization
│   ├── types.ts           # Core domain types (Msg, SessionInfo, Usage)
│   ├── app/               # Core logic (21 files): hooks, stores, slash commands
│   ├── components/        # 22 Ink components (memo-wrapped)
│   ├── hooks/             # 5 reusable React hooks
│   ├── domain/            # 8 pure logic files (no React/Ink deps)
│   ├── content/           # 7 static data files (faces, verbs, fortunes)
│   ├── protocol/          # Shell interpolation, paste handling
│   ├── lib/               # 36 low-level utilities
│   ├── config/            # Feature flags, limits, timing constants
│   └── __tests__/         # 30+ vitest test files
└── packages/hermes-ink/   # Forked Ink renderer (esbuild bundle, ~60 files)
    └── src/ink/           # Custom: AlternateScreen, ScrollBox, mouse selection, etc.
```

## WHERE TO LOOK

| Task | File(s) |
|------|---------|
| Add a new component | `components/<name>.tsx` — use `memo(function Name(...){})` pattern |
| Add a new hook | `hooks/use<Name>.ts` or `app/use<Name>.ts` if stateful |
| Add a slash command | `app/slash/commands/<category>.ts` — export SlashCommand[], add to registry.ts |
| Add a new RPC type | `gatewayTypes.ts` — add response interface + GatewayEvent union member |
| Modify theme | `theme.ts` — fromSkin(), detectLightMode(), normalizeThemeForAnsiLightTerminal() |
| Modify Ink renderer | `packages/hermes-ink/src/ink/` — rebuild with `npm run build` in hermes-ink |
| Change streaming display | `components/streamingMarkdown.tsx` + `components/streamingAssistant.tsx` |
| Change input handling | `components/textInput.tsx` (custom line editor, mouse, paste, word nav) |

## CONVENTIONS

- **Nanostores for all state** — `$uiState`, `$turnState`, `$overlayState` etc. Mutation via `patch*()` functions. No Redux/Context (except `gatewayContext.tsx` for RPC)
- **No default exports** (ESLint-enforced). All named exports
- **ESM-only** — `"type": "module"`, `nodenext` resolution, `.js` extensions in imports
- **Perfectionist ESLint** — sorted imports, exports, JSX props, named imports (alphabetical)
- **React Compiler** in production builds (Babel plugin) + lint rule
- **memo() on all components** — `memo(function Name(...){})` pattern throughout
- **Domain/content/lib split**: domain/ = pure logic (no React), content/ = display data, lib/ = low-level utils
- **Custom Markdown renderer** (837 LOC in markdown.tsx) — handles diff coloring, math Unicode, syntax highlighting
- **Custom Ink fork** (@hermes/ink) — adds ScrollBox, AlternateScreen, NoSelect, RawAnsi, mouse selection, terminal focus

## BUILD PIPELINE

```
hermes-ink (esbuild) → tsc → babel (React Compiler) → chmod +x
```

**Dev:** `npm run dev` (watch mode: rebuilds hermes-ink + tsx --watch)
**Test:** `npm test` (vitest)
**Lint:** `npm run lint` + `npm run fmt` (prettier: singleQuote, no-semi, 120 width)

## THEMING

Detection order: `HERMES_TUI_LIGHT` > `HERMES_TUI_THEME` > `HERMES_TUI_BACKGROUND` hex > `COLORFGBG` > `TERM_PROGRAM` allowlist
Access via `<Fg c="primary">` (from `themed.tsx`) or `$uiState` nanostore
ANSI normalization for terminals without truecolor support

## GOTCHAS

- **`useMainApp.ts` is 846 LOC** — central orchestrator composing 10+ sub-hooks. Most app logic flows through here
- **`gatewayClient.ts` has two modes**: spawned (default, stdio) and attached (WebSocket via `HERMES_TUI_GATEWAY_URL`)
- **Memory/OOM**: Heap dump, OOM monitoring, 8GB heap default. `memoryMonitor.ts` auto-dumps on pressure
- **Feature flags**: `config/env.ts` reads `HERMES_TUI_*` env vars (INLINE, FPS, DISABLE_MOUSE, etc.)
- **Virtual scrolling**: `virtualHeights.ts` + `viewportStore.ts` for large transcript performance
- **Terminal modes cleanup**: `terminalModes.ts` resets mouse/focus/paste on exit — must be called in cleanup
- **@hermes/ink is NOT standard Ink** — adds BIDI, tab stops, cache eviction, search highlighting, external process suspension
