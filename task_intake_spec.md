# Task Intake Format (v0)

The shared "envelope" for every task Sheila delegates. Sheila is both the
writer and, via `delegation.py`, the one who acts on it immediately —
there is no separate CEO/orchestrator agent reading this table later.
The table still exists as record-keeping/history: a queryable log of
everything Sheila has delegated, and a place for tasks to sit when no
specialist exists yet for their category (e.g. research, before that
agent is built).

## Fields

| Field         | Type      | Notes |
|---------------|-----------|-------|
| `id`          | text (uuid) | generated on insert |
| `created_at`  | timestamp | UTC |
| `source`      | text      | who filed it — `"sheila"` for now, always |
| `raw_input`   | text      | what Samuel actually said, verbatim |
| `category`    | text      | `"finance" \| "travel" \| "research" \| "reminder" \| "unsure"` |
| `title`       | text      | short summary Sheila generates |
| `brief`       | text      | 2-4 sentence handoff — what the eventual owner needs to know |
| `priority`    | text      | `"low" \| "normal" \| "high"` |
| `status`      | text      | `"new" \| "in_progress" \| "done" \| "dropped"` — starts `"new"`; synchronous execution moves through `"in_progress"` to `"done"` or `"dropped"` |
| `owner`       | text      | who *should* handle it — `"richard" \| "juan_whey" \| "dee_gmail" \| "sheila" \| "samuel" \| "unassigned"` |
| `deadline`    | timestamp, nullable | only if Samuel mentioned one |
| `metadata`    | JSON, nullable | free-form — source thread id, links, etc. |

## Why this shape

- Matches the existing Second Brain convention in the repo (structured records
  with category, provenance, timestamps, JSON metadata) — same mental model,
  new table.
- `category` + `owner` are separate on purpose: category is Sheila's best
  guess at classification, owner is who actually ends up handling it — these
  can disagree, and that gap is useful signal later (are things landing where
  you'd expect?).
- `status` lets this table double as a lightweight dashboard of open items
  even before anything downstream reads from it automatically.

## What Sheila does, concretely

1. During a conversation, she decides a message is delegation-worthy (not
   just a reminder she can set herself) — e.g. "check if I should rebalance
   my Roth" vs. "remind me to call Nora."
2. She calls `delegation.handle_message(raw_input)`, which classifies the
   message (`category`, `title`, `brief`, `owner`, `priority`), writes it to
   the tasks table via `create_task(...)`, and — if a specialist exists for
   that `owner` — dispatches to it immediately and gets a result back, all
   in the same call.
3. She composes her own reply to Samuel using the outcome. The table write
   is bookkeeping, not a visible step in the conversation.

## What happens later (not built yet)

- Richard/Juan Whey get real API connections instead of stub responses.
- Sam 2 gets queried for context before a task is delegated, and that
  context gets folded into the `brief` field.
- `sweep_unassigned()` gets run whenever a new specialist (e.g. a
  researcher) comes online, to retroactively process anything that was
  queued with no owner available at the time.
- A simple read-only view of this table becomes the first real "company
  dashboard" — what's been delegated, to whom, and what's still queued.

None of that needs to exist for step 1-3 above to be useful today: even just
having every delegation-worthy ask land in one structured place, instead of
scattered across chat history, is the actual unlock.
