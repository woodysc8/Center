# Center

The delegation logic for Sheila, Samuel's personal AI orchestrator. Not a
separate agent — a library Sheila's own message-handling code calls
directly. This exists so classification, routing, and specialist handoffs
have one clean, testable, swappable implementation, instead of being
scattered inline through Sheila's conversational code.

## Architecture (current)

```
Samuel
  |
  v
Sheila  <-- receives every message, IS the orchestrator
  |
  |-- handles small stuff herself (reminders, calendar) -- no delegation needed
  |
  |-- calls delegation.handle_message(raw_input) for anything else
  |         |
  |         v
  |      classifier.py  -> category, title, brief, owner, priority
  |         |
  |         v
  |      intake.py      -> writes a row to the tasks table (record-keeping)
  |         |
  |         v
  |      specialists/    -> richard.py / juan_whey.py (stubs for now)
  |         |
  v         v
Sheila composes her own reply using the outcome, responds to Samuel
```

There is deliberately **no separate CEO/master-delegator agent.** An
earlier version of this project had one; that turned out to be a
misunderstanding of the intended design — Sheila herself is the
orchestrator. `ceo.py` was renamed to `delegation.py` and reworked from "a
standalone script that polls a queue on its own schedule" into "a function
Sheila calls synchronously, in the same turn she's replying to Samuel."

Sam 2 (the second-brain/memory service, built separately — see
`C:\Users\Sam\Desktop\second-brain`, a FastAPI backend) is not wired into
this repo yet. Per the shared architecture doc, Sam 2 should be reachable
by Sheila through a clean interface (`memory.search(...)`,
`memory.get_context(...)`, etc.) — see "Next real step" below.

## Files

| File | What it does | State |
|---|---|---|
| `config.py` | Shared settings (DB path, API key) | Done, minimal |
| `intake.py` | Task schema + `create_task`/`list_tasks`/`update_status`/`update_owner` | Working — still used for record-keeping even though nothing separate polls it anymore |
| `classifier.py` | Turns raw text into task fields | Rule-based (keyword matching) works now; LLM path stubbed, not implemented |
| `delegation.py` | `handle_message(raw_input) -> dict` — the function Sheila calls per delegation-worthy message | Working v0 |
| `specialists/richard.py` | Interface stub for the finance agent | Stub only — logs, returns canned response |
| `specialists/juan_whey.py` | Interface stub for the travel agent | Stub only — logs, returns canned response |
| `view_tasks.py` | CLI to inspect the task history/queue | Working |
| `task_intake_spec.md` | Task schema reference | Needs a light edit — still accurate on fields, outdated on "the CEO polls this table" language |

Run `python delegation.py` for a quick smoke test of the whole pipeline on
some example inputs. Run `python view_tasks.py` to see what's been
delegated so far. No dependencies beyond the standard library currently.

## Specialist Contract

The synchronous execution path is intentionally small and explicit:

```
Sheila
   |
   v
Center
   |
   v
specialist.handle_task(task)
   |
   v
result
```

Center validates the structured task, selects a specialist from the explicit
`SPECIALISTS` registry, records the task status, and returns the specialist's
result. Specialists implement `handle_task(task: dict) -> dict`. Center is an
execution/delegation layer; it is not memory and does not make LLM calls.

## Sheila → Center Integration

Sheila retrieves relevant Sam 2 context before it decides to delegate a
message. It passes that context into Center via the `context` argument on
`handle_message(...)`, along with any request-scoped integration metadata in
`metadata`.

Center does not own Sam 2 memory and does not retrieve it itself. It treats
`context` as opaque data and persists it in the task's existing
`metadata` JSON field, then passes the same data through to the specialist
when it invokes `handle_task(task)`.

The important separation is:

- Sheila: keeps Sam 2 retrieval and orchestration logic
- Center: routes, persists, and delegates the task
- Specialist: receives the task payload, including context, without needing
  to know where the context came from

## What's real vs. simulated right now

**Real:** the schema, rule-based classification, `handle_message`'s control
flow, the task history you can inspect.

**Simulated:** what happens when a task reaches Richard or Juan Whey — the
stubs just log and return a canned string. No live connection to either
agent yet, and no connection to Sam 2 for context yet either.

## Next real step

Per the shared architecture doc, before delegating to a specialist Sheila
(via `delegation.py`) should first pull relevant context from Sam 2 — e.g.
"what does Samuel need to know before this gets handled" — and pass that
along in the brief, rather than delegating on the raw message alone. That
requires Sam 2's `/api/query` endpoint to be reachable from wherever this
runs. Once it is, the natural addition is a `get_context(query)` call at
the top of `handle_message`, whose result gets folded into the `brief`
field before it's handed to a specialist.

## Known open decisions (for Copilot or future-Samuel)

1. **How does Sheila actually reach Richard/Juan Whey?** Both currently
   live on other platforms (Claude project, ChatGPT). Direct API calls,
   webhooks, or something else (e.g. browser automation for the
   ChatGPT-based Juan Whey, since most travel APIs turned out to be
   dev-only) — not decided.
2. **Sam 2 integration.** Not wired in yet. Needs the scaffolding/interface
   layer described in the architecture doc (agents call `memory.search()`
   etc., never touch Sam 2's database directly) — and per that doc, this
   interface should be usable by Sheila for any agent's context needs, not
   Sheila-exclusive, since delegation briefs to specialists may also need
   Sam 2 context.
3. **LLM classification.** The rule-based classifier is deliberately crude
   — good enough to prove the pipeline. `classifier.py` has a stubbed
   `_llm_classify` with a draft system prompt, ready to wire to an LLM
   (OpenAI, per Sam 2's stated primary-provider strategy, or Gemini to
   match whatever Sheila herself runs on) once it's worth the added
   cost/latency.
4. **The researcher agent** doesn't exist yet. Its owner slot
   (`"unassigned"` for category `"research"`) is reserved — adding it later
   is just: build `specialists/researcher.py`, add it to `delegation.py`'s
   `SPECIALISTS` dict, done.
5. **`sweep_unassigned()`** in `delegation.py` is an optional manual utility
   for re-processing tasks that got queued before a specialist existed for
   them (e.g. research tasks, before a researcher is built). Not scheduled
   — run manually whenever a new specialist comes online.
6. **Where does this live relative to Sheila's actual repo?** Currently a
   standalone folder. Whether `delegation.py` etc. get copied into the
   Sheila repo directly, or imported as a separate local package, hasn't
   been decided.

## Non-goals for v0

- No live API calls to any specialist yet
- No Sam 2 integration yet
- No autonomous scheduling — everything runs synchronously when Sheila
  calls it, or manually via the CLI/`sweep_unassigned()`
- No UI beyond the CLI viewer
- No attempt to make the classifier smart — rule-based is fine until the
  pipeline itself is proven out
