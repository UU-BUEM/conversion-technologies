# `.claude/` index

Ported from `UU-BUEM/occupancy`'s `.claude/` convention (itself ported from
`weather`). Purpose: keep durable engineering context out of the
always-loaded root `CLAUDE.md`, split by domain so an agent only loads what's
relevant to the task at hand.

- Root `open.md` / `resolved.md` — cross-cutting items (packaging, exporters,
  registry, CLI). Check `resolved.md` before proposing a change; it lists
  decisions already made, "do not re-raise."
- `boiler/`, `heat_pump/`, `combined_heat_and_power/` — one `open.md`/`resolved.md`
  pair per `src/conversion_technologies/new/` category. Load only the
  category folder relevant to the current task.

Format: one-liners, newest at top, markdownlint-clean.
