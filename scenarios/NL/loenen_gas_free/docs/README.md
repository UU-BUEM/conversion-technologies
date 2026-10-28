# Scenario docs: Loenen gas-free

Working log for this scenario — what's been checked, what each phase
actually found, and what's still open. Mirrors the parent repo's
`docs/` convention (reference material, not a `.claude/` internal note),
but scoped to this scenario since it spans multiple repos (`buem`,
`occupancy`, `weather`, `conversion-technologies`, `MEME`) that this
package alone doesn't own.

- `phase0_scaffold.md` — scenario folder layout, constraints, decisions made before any data was touched.
- `phase1_demand.md` — buem batch run against Loenen: environment checks, data checks, run log, output validation.
- `phase2_technologies.md` — non-gas technology export from this repo: which ids, what scale, validation.
- `phase3_nodes.md` — per-building node assembly (not started).
- `phase4_solve.md` — MEME/Calliope submission (not started).

Each phase file states, up front: what was checked, what passed, what
didn't, and what's blocking the next phase — not a narrative of how we
got there.
