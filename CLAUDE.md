# ep-volunteer-map

A sheet-backed US map of Election Protection volunteer opportunities, to be
embedded on protectthevote.net. Organizers list opportunities (state, title,
description, get-involved link) in a Google Sheet. A twice-daily Civis job
publishes them to GitHub Pages, and each state opens a list of its
opportunities. Requested by Amy (a state ED); owned and signed off by Rob (campaigns).

## Status: LIVE (not yet embedded)

**Read `docs/SPEC.md` first**; it records every decision. The repo is
**public** (org is on GitHub free, so no Pages from private repos), so keep
the Sheet id and anything row-like out of it.

- `scripts/sync_opportunities.py`: Sheet → `data/opportunities.json` (tests in `tests/`)
- `civis/`: job body + `SCHEDULED_SCRIPTS.md` (the live job's config and its setup quirks)
- `site/`: the front end; `scripts/build_site.sh` is the publish allowlist,
  used by `.github/workflows/deploy.yml` and for local preview
  (`bash scripts/build_site.sh && python -m http.server -d _site`)
- `docs/wordpress_embed.md`: the snippet + runbook for the protectthevote.net admin

Live: Civis job 370504796 runs 07:00 + 15:00 ET. The Sheet was seeded
2026-09-25 by a Rob-reviewed first sweep (33 rows). The scheduled sweep
(06:00 / 14:00) is **granted tier 2** (2026-09-25), with its Task Scheduler
vehicle enabled. First fire: 2026-09-26 06:00. Remaining: send the embed
runbook to the protectthevote.net admin; rotate the PAT before 2026-12-24.

## Shape (from the spec)

- **Two jobs, two mechanisms.** The *publish* (Sheet → JSON → Pages) is
  deterministic and runs on Civis (`civis/SCHEDULED_SCRIPTS.md`). The
  *training-map sweep* (SPEC "Phase 2") fills the Sheet ahead of each publish,
  and it is a judgment pass: role grouping, public copy, link choice. So it's
  a dispatch `loop` (`.claude/dispatch.yaml`, runbook
  `.claude/skills/training-map-sweep/`), and it writes only `source = sweep`
  rows, through `scripts/sweep_apply.py`. State staff edit their own rows in
  the same Sheet.
- **Lift, don't rewrite:** the pipeline comes from `dynamic-action-map`
  (sync, Civis body, allowlist Pages deploy). The per-state list map and iframe
  height reporting come from `ep-training-map`'s public build. The brand comes
  from `ep-tools-home/docs/ep-coalition-style-guide.md`.
- **Public by construction:** everything in the Sheet ends up on a public page
  that will spread. Validate link schemes (http/https only) in both the sync
  and the front end.
- **Pushing workflow files needs the `workflow` token scope,** which isn't
  present today. See SPEC.md "Known snag".

## Local Python

Python is needed for the sync. The cc-embed scaffold creates no venv, so create
it with the fleet pattern (`C:/venvs/ep-volunteer-map` plus a `.venv` junction;
see the meta-project CLAUDE.md), then install `ccef-connections[sheets]`
editable from its local clone.

## PII / Data Handling

Row-level PII (names, emails, phones, street addresses, gift amounts) **never gets
committed to git** — repos here are org-visible via shared corpora and export pipelines.
Any directory that will receive raw dumps or query results gets gitignored BEFORE the
first file lands (allowlist known-clean file types; never enumerate known-bad files).
Committed derivatives must be masked or aggregated; fabricate example rows in docs.
Row-level people-data lives in access-controlled systems (BigQuery, ROI, Action Network,
shared Sheets) — point at it, don't copy it. Full policy: knowledge library entry
`pii-handling-policy` (`kl_get`).

## Agent Automation & Dispatch

Two different mechanisms. Picking the wrong one wastes the build:

- **Deterministic pipeline → Civis.** Plain Python/dbt ETL, no judgment; tracked in
  this project's `civis/SCHEDULED_SCRIPTS.md`.
- **Judgment pass → local scheduled agent, via a dispatch contract.** Anything whose
  correctness depends on a rubric, world knowledge, or a call a human would otherwise
  make. Subscription Claude Code **cannot be invoked from Civis at all** — no API-key
  path there uses the subscription — so "a Civis job that exercises judgment" is
  unbuildable, not merely discouraged. Don't start building one.

Agent-dispatchable work is governed by the **Dispatch Treaty** (ratified 2026-08-20,
in force since 2026-08-25; law: meta-project `docs/dispatch_treaty.md`). The
rob-assistant "tower" spawns headless agents at named task types that a project
declares in a committed contract. Live fleet status — who has declared what, and what
is actually granted — is the meta-project's generated `dispatch/roster.yaml`; don't
trust a count written in prose anywhere, including here.

**To make a task type in this project dispatchable:**

1. Write `.claude/dispatch.yaml` from the meta-project's `templates/dispatch.yaml`
   (one file, all of this project's task types). **Absence of that file means
   hands-off** — eligibility is declared, never inferred, and no stub is wanted for
   an interactive-only project.
2. Package the procedure itself as the runbook the contract points at — a skill at
   `.claude/skills/<name>/SKILL.md`, or a doc under `docs/`.
3. Confirm **git can see the contract.** A blanket `.claude/*` gitignore swallows it
   silently; add `!.claude/dispatch.yaml`. A contract git can't see does not exist.
4. Validate from the meta-project: `python sync_projects.py --check`, then
   `--dispatch-roster`.
5. **Stop there.** Tiers are dated grants that live only in the meta catalog
   (`projects_index.yaml`), and **only Rob grants one** — an agent proposes, never
   self-authorizes. An ungranted contract is the correct resting state: the roster
   computes `dispatchable: false` and nothing fires.

Do not register a Windows Task Scheduler job for an agent pass either — scheduled
fires go through the tower, or they earn no track record. Background and the
scheduler mechanics: knowledge library entries `dispatch-treaty-and-the-tower` and
`local-scheduled-claude-agents-task-scheduler-the-pattern-for-recurring-agentic-p`
(`kl_get`).
