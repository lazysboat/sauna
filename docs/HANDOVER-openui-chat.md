# Handover — make the booking chatbot's answers nicer with OpenUI

**Goal:** the buyer-agent chat UI at `http://localhost:8000` (the dark terminal) currently
answers in **plain text only** and shows **no images**. We want richer output — sauna
**cards** (image, provider, city, price, capacity, a Book affordance) instead of a
paragraph — using **OpenUI** (Generative UI: <https://www.openui.com>).

This doc is the runbook for a fresh session. Read `docs/ARCHITECTURE.md` for how the whole
project works; read `CLAUDE.md` for the spin-up runbook. Everything below is specific to
this feature.

---

## ✅ Status: implemented on branch `feat/openui-chat`

Built per the **recommended** path below — no new Python deps, backend stays Anthropic-only:

- **Integration shape:** `browser-bundle` (kept the single-HTML chat UI). The pinned CDN
  bundle `@openuidev/browser-bundle@0.1.1` (sets `window.__OpenUI`) + its stylesheet are
  loaded in `app/main.py`'s `PAGE`.
- **Return shape (B, structured):** `answer()` now returns `{answer, ui, queries}` where
  `ui` is an OpenUI Lang program (or `null`).
- **How UI is produced:** a new **`present_ui` tool** in the agent loop — the model authors
  OpenUI Lang (true generative UI). The tool description carries a tailored OpenUI Lang guide
  + a sauna-card few-shot. `imageUrl` was added to the schema description and the prompt tells
  the agent to `SELECT` it.
- **Renderer:** `showAnswer()` mounts the OpenUI `Renderer` (`library: openuiChatLibrary`)
  into the turn when `ui` is present; plain-text prose + the "show work" audit trail are
  preserved. Plain-text-only answers (e.g. revenue) are unchanged.
- **Booking affordance (interactive):** card Book buttons emit `@ToAssistant("Book session
  <id>")`; the renderer's `onAction` feeds that straight back into the chat, closing the loop.

**Verified live end-to-end** (real `ANTHROPIC_API_KEY` + ClickHouse, after `seed`): "show me
smoke saunas for a group of 10+" → live Claude (`claude-opus-4-5`) emitted well-formed OpenUI
Lang with real data → rendered as a Carousel of image cards → clicking a card's **Book** button
fired `onAction` → the agent booked the session and rendered a "✅ Booking Confirmed!" card →
the slot flipped to `booked` in ClickHouse. The OpenUI cards auto-theme dark and sit cleanly in
the terminal. Three fixes came out of that test: `MAX_STEPS` 6→9 (room for the extra `present_ui`
step), the `onAction` message lives under `humanFriendlyMessage` (added to the extractor), and
the seed has no published Tampere smoke sauna so suggestion `[1]` now matches real data.
Streaming was intentionally **not** added (v1 renders the full block on response).

---

## 1. How the chatbot works today (so you don't relearn it)

One JSON endpoint drives everything: `POST /ask`.

- **Agent loop** — `app/agent.py`, `answer(question, ch)` at [agent.py:112](../app/agent.py).
  A Claude tool-use loop, `MAX_STEPS = 6`. Two tools only ([agent.py:60](../app/agent.py)):
  - `run_sql` — read-only ClickHouse query; errors come back as text so the loop self-corrects.
  - `book_session` — flips an open slot to `booked`.
  - Returns a fixed shape: `{"answer": str, "queries": list[str]}`.
  - `answer` is just the concatenated **text blocks** of Claude's final message
    ([agent.py:149](../app/agent.py)).
- **System prompt** — `SYSTEM` at [agent.py:41](../app/agent.py), with the live ClickHouse
  schema appended at runtime (`schema_text(ch)`, [agent.py:117](../app/agent.py)).
- **Chat UI** — a **single hardcoded HTML string** `PAGE` served by `GET /` at
  [main.py:54](../app/main.py). No React, no build step, no bundler.
- **Renderer** — `showAnswer()` in that HTML at [main.py:145](../app/main.py). It does
  `el.textContent = d.answer` (HTML-escaped) then **one** upgrade: `**bold**` → `<strong>`
  ([main.py:148](../app/main.py)). It also renders a collapsible "show work" list from `queries`.
- `/ask` is a **non-streaming** POST that returns the full JSON at once
  ([main.py:43](../app/main.py)).

## 2. Why there are no images today (3 compounding reasons)

1. **Data is there but unused.** `Experience.imageUrl` exists ([models.py:27](../app/models.py))
   and the Next.js directory on :3000 uses it (`frontend/src/lib/store.ts`,
   `frontend/src/components/Directory.tsx`). But the agent's schema description
   ([agent.py:44-50](../app/agent.py)) **omits `imageUrl`**, so Claude never `SELECT`s it.
2. **The prompt asks for prose.** `SYSTEM` says answer in *"a few plain sentences"* — image
   isn't even requested.
3. **The renderer can't show it.** `showAnswer` only un-escapes `**bold**`; a markdown image
   or `<img>` would render as literal text.

All three must change.

---

## 3. The plan with OpenUI

OpenUI is a React generative-UI framework. The model emits **OpenUI Lang** (a compact
streaming UI language); a renderer turns it into live components. Key packages:
`@openuidev/react-lang` (runtime), `@openuidev/react-ui` (prebuilt components),
`@openuidev/lang-core` / `@openuidev/openui-cli` (framework-agnostic **prompt generation**
from a component library), `@openuidev/browser-bundle` (**script-tag/CDN bundle, no build**).

### Core tension to resolve first

Our chat UI is a **no-build single HTML string** ([main.py:54](../app/main.py)) and our
backend is **Python + Anthropic** — but OpenUI is **React + JS**, and its prompt-generation
tooling (`lang-core`/CLI) is **JS/TS**. So decide the integration shape before coding.

### Recommended approach — `browser-bundle`, keep the architecture

Preserve the single-HTML-string UI and the Python loop:

1. **Component library + prompt (one-time, JS side).** Use `@openuidev/openui-cli` /
   `@openuidev/lang-core` to define a small component library (a `SaunaCard` + a list/grid)
   and **generate the OpenUI Lang system-prompt text**. This is a build/dev step, not a
   runtime dependency of the Python app.
2. **Embed that generated prompt into the Python agent.** Append it to `SYSTEM`
   ([agent.py:41](../app/agent.py)) so Claude knows to emit OpenUI Lang describing sauna
   cards. **Also add `imageUrl`** to the schema description ([agent.py:44-50](../app/agent.py))
   and instruct the agent to `SELECT` it and include it in each card.
3. **Render client-side with the browser bundle.** Add the OpenUI `browser-bundle`
   `<script>` + `<link>` to `PAGE` and replace/augment `showAnswer` ([main.py:145](../app/main.py))
   so that when `d.answer` (or a new field) contains OpenUI Lang, it's rendered by the OpenUI
   Renderer instead of being treated as plain text. Keep the plain-text path as a fallback.

**Why this shape:** smallest blast radius — `app/store.py`, `app/models.py`, the REST API,
and the :3000 frontend are all untouched; you only edit `agent.py` (prompt + return) and the
`PAGE` string in `main.py`.

### Alternative — rebuild the chat UI as a React app

Use `@openuidev/react-ui` + `@openuidev/react-lang` for a full prebuilt chat experience.
Cleaner OpenUI integration and streaming, but it means introducing a bundler/React app for
the :8000 surface (today it's literally one HTML string). Heavier; only do this if the
browser-bundle path proves too limiting.

### Return-shape decision (backend)

Two ways for the agent to deliver UI; pick one in `answer()` ([agent.py:147-152](../app/agent.py)):
- **(A) Inline:** keep `{answer, queries}`, but `answer` now contains OpenUI Lang. Minimal
  change; renderer branches on "looks like Lang vs plain text."
- **(B) Structured:** add a field, e.g. `{"answer": str, "ui": <OpenUI Lang>, "queries": [...]}`.
  Cleaner separation (prose summary + UI block); requires the renderer to handle both.
  **Recommended.**

### Streaming

OpenUI is streaming-first, but `/ask` is a single non-streaming POST today
([main.py:43](../app/main.py)) and the agent loop is synchronous. **Do not add streaming in
v1** — render the full OpenUI Lang block on response. Streaming is a separate, later upgrade
(would need SSE/chunked `/ask` and a streaming agent loop).

---

## 4. Concrete change list

| File | Change |
|---|---|
| (JS, dev step) | Define `SaunaCard` + grid component library; generate OpenUI Lang system prompt via `openui-cli`/`lang-core`. |
| `app/agent.py` [:44](../app/agent.py) | Add `imageUrl` to the schema description; instruct agent to `SELECT` it. |
| `app/agent.py` [:41](../app/agent.py) | Append the generated OpenUI Lang prompt to `SYSTEM`; tell the agent to return matched saunas as cards. |
| `app/agent.py` [:147](../app/agent.py) | Decide return shape (A inline / **B structured `ui` field**); populate it. |
| `app/main.py` [:54](../app/main.py) `PAGE` | Add OpenUI `browser-bundle` `<script>`/`<link>` tags. |
| `app/main.py` [:145](../app/main.py) `showAnswer` | Render OpenUI Lang via the Renderer; keep plain-text + "show work" fallback. |

**Untouched:** `app/store.py`, `app/models.py`, `app/crud.py`, `render.yaml`, the whole
`frontend/` directory.

---

## 5. De-risking — do this spike FIRST (≈30 min)

Before committing to the full build, validate the two riskiest assumptions:

1. **Can Claude reliably emit valid OpenUI Lang?** OpenUI is model-agnostic (quickstart is
   OpenAI-keyed) but we use `claude-opus-4-8`. Hand-write the generated system prompt into
   `SYSTEM`, ask one question, and inspect whether the model returns well-formed Lang. If it's
   shaky, the prompt may need OpenUI's CLI-generated instructions verbatim + a few-shot example.
2. **Does the browser-bundle render that Lang in a plain HTML page** (no React app)? Drop the
   bundle into a throwaay HTML file, paste a sample card Lang, confirm it renders.

If both pass, proceed. If (1) fails, consider keeping prose + emitting just a structured
`cards: [{title, city, price, imageUrl}]` JSON list and rendering cards with hand-written
HTML in `showAnswer` (no OpenUI) — much simpler, but doesn't satisfy "use OpenUI."

## 6. Gotchas / risks

- **Stack mismatch is the whole risk.** No-build HTML + Python backend vs React/JS OpenUI.
  The `browser-bundle` is the bridge — confirm it works embedded before going deep.
- **OpenUI quickstart assumes OpenAI** (`OPENAI_API_KEY`). We are **Anthropic**. Use only the
  framework-agnostic pieces (`lang-core`/`browser-bundle`); the LLM call stays in `agent.py`
  ([agent.py:22](../app/agent.py), `_create`). Do **not** add an OpenAI dependency.
- **`imageUrl` must reach the model.** Easy to forget — it's both a schema-description edit
  *and* an instruction to `SELECT` it. Images come from `picsum.photos` (needs internet).
- **Renderer escaping.** Today `showAnswer` deliberately HTML-escapes. When you add OpenUI
  rendering, only the OpenUI path should bypass escaping; keep the plain-text fallback escaped.
- **`make seed` must have run** or there are no saunas to render ([CLAUDE.md] gotcha #3).
- **Adaptive thinking** auto-falls-back already ([agent.py:31](../app/agent.py)) — leave it.
- **Keep `queries` / "show work."** It's a nice audit trail ([main.py:153](../app/main.py));
  don't drop it when reworking the renderer.

## 7. Definition of done

- Ask "find a smoke sauna in Tampere for 10 people" in the :8000 chat → response renders one
  or more **sauna cards with images** (not a paragraph), each showing image, provider, city,
  price, capacity.
- A booking question still works end-to-end (a `-- book_session(...)` entry appears; the slot
  disappears from the :3000 directory after refresh) — i.e. the agent loop and `queries` audit
  trail are intact.
- Plain-text questions (e.g. "how much revenue is booked?") still render correctly via the
  fallback path.
- No OpenAI dependency added; backend still Anthropic-only; `/health` still `{"ok": true}`.

## 8. Open decisions to confirm with the user

1. **Integration shape:** `browser-bundle` (keep single-HTML UI) **[recommended]** vs full
   React rebuild of the :8000 chat.
2. **Return shape:** structured `ui` field **[recommended]** vs inline Lang in `answer`.
3. **Scope of components:** just `SaunaCard` for v1, or also a schedule/availability table and
   a revenue chart later.
4. **Booking affordance in cards:** display-only for v1, or an interactive "Book" button
   (interactive components = more OpenUI wiring; defer to v2 unless asked).

## 9. References

- OpenUI docs: <https://openui.com> · Playground: <https://www.openui.com/playground>
- Packages: `@openuidev/lang-core`, `@openuidev/browser-bundle`, `@openuidev/react-lang`,
  `@openuidev/react-ui`, `@openuidev/openui-cli`
- OpenUI ships a Claude Code skill: `npx skills add thesysdev/openui --skill openui` — install
  it; it covers component-library design, OpenUI Lang syntax, prompt generation, the Renderer,
  and debugging malformed LLM output. **Start there.**
