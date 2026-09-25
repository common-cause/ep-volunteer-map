---
name: training-map-sweep
description: >
  Run the EP volunteer-map training sweep: turn the EP Training Map's public
  payload plus the coalition plan's recruitment links into one front-door item
  per state role in the volunteer-map Sheet, with generated titles and
  descriptions. Writes only the sweep's own rows (source = sweep) through
  scripts/sweep_apply.py. Use for the scheduled 06:00 / 14:00 fire, or when
  asked to refresh or re-run the volunteer-map sweep.
---

# Training-map sweep: EP Volunteer Map

You fill the volunteer-map Sheet with a starting set of **front-door items**,
one per volunteer role a state offers, so a volunteer who clicks a state lands
where that state wants them to start. State staff add and edit their own rows
in the same Sheet. **You never touch theirs.** Read `docs/SPEC.md` "Phase 2"
first; every rule here was settled with Rob there.

```
11:00 / 23:00  ep-training-map   publishes the public training payload   <- INPUT
06:00 / 14:00  YOU               sweep -> Sheet rows (source = sweep)
07:00 / 15:00  Civis             Sheet -> opportunities.json -> Pages    (not yours)
```

The judgment is in steps 3 and 4: which trainings are the **same role**, what
the role is **called**, how it's **described**, and (in a few states) **which
link** is the front door. Everything else is mechanical and enforced by
scripts. When the scripts refuse, the refusal is the answer. Report it, and
never reshape a proposal just to get past a check you think is wrong.

## 1. Preconditions

From the repo root, with the project venv:

```bash
.venv/Scripts/python.exe -m pytest -q        # must be green; if red, stop (failed)
```

## 2. Build the worklist

```bash
.venv/Scripts/python.exe scripts/sweep_worklist.py      # -> tmp/sweep/worklist.json
```

Read the printed summary, then `tmp/sweep/worklist.json`. Per state it gives:
`ptv_state`, `k_link` (the state's own recruitment link, from coalition-plan
column K), `front_door` (already resolved: K, else protectthevote.net for PTV
states), `agent_picks_link`, `has_staff_rows`, and `roles`, the trainings
grouped by their raw role string. It also gives `current_sweep_rows` (what you
wrote last time) and `staff_owned_keys` (keys a human took over).

**Staleness check.** If `_meta.training_payload_generated_at` is over 36 hours
old, the training map has stopped publishing. **Stop:** write no proposal,
close `failed`, and name ep-training-map as the owner. A stale payload drops
roles and would disable good rows.

## 3. Decide the items

**Read the contract's `status.in_flight` first.** Rob uses it for per-cycle
instructions, such as a role to skip while a state unpublishes it. Those notes
override the rules below.

A key in `staff_owned_keys` means a human owns **that role**. Don't recreate
the role under a different slug either.

For each state with trainings:

- **One item per distinct role.** Different raw strings for the same job are
  one role ("2026 Poll Monitor", "Poll Monitoring" and "Poll monitor" are all
  Poll Monitor). Different jobs stay separate ("Roving Poll Monitor",
  "Stationary Poll Monitor", "Count Observer", "Legal Volunteer",
  "Trusted Messenger"). When in doubt, merge: a front door lists what someone
  can sign up to be, not every training variant.
- **PTV states:** the items are the PTV roles. Outside trainings in a PTV state
  (for example AZ's Mobilize events) are **folded in, not listed**. Volunteers
  reach them through PTV (SPEC Q2). A role that exists only outside PTV in a
  PTV state is folded into the closest PTV role, or dropped if nothing fits.
- **Non-PTV states:** one item per distinct outside role.
- **`(no role given)`:** infer the role from the training names if it's clear,
  otherwise use "Election Protection Volunteer".
- **Hub states** (`hub_links` is set: the state's column K link is a
  Linktree, currently FL). The state listed its own roles, so **the hub
  replaces the training data for that state.** Make one item per hub link
  that is a volunteer role someone can sign up for, linking to **that link's
  own URL**. Take the title from the hub entry, cleaned. Put who it's for
  ("for Lawyers", "for Clergy, Organizers, Law Students") in the
  description, not the title. **Skip** hub links that aren't roles, such as a
  messaging doc, a resources page or a hotline banner. A training-map role
  with no matching hub link is not added. Say which hub links you skipped
  and why in `link_choices`.
- **Blank states whose `k_link` is set** (no trainings, but the state
  submitted a recruitment link, for example AL): one `door:XX:volunteer` item
  with the default title and copy, linking to `k_link`. Blank states without a
  K link get **nothing**: the map's built-in default covers them.

**Keys** are `ptv:XX:role-slug`, `ext:XX:role-slug` or `door:XX:volunteer`,
lowercase and hyphenated (`ptv:MI:roving-poll-monitor`). **Reuse the key from
`current_sweep_rows`** when a row already exists for that role. A new key for
the same role disables the old row and creates a twin, and that churn is
visible to states. **Never use a key in `staff_owned_keys`.** A human owns
that role now, so skip it.

## 4. Write the copy and pick links

**Copy stability first.** If a row already exists for the key and its role
hasn't changed, **copy its title and description through unchanged.** Rob
approved the first run's wording, so don't polish it. Rewrite only when the
role itself changed (for example new modalities, or on-demand added or
removed).

For new rows (SPEC Q6):

- **Title:** the plain role name. No year, no internal labels, and no "(1
  site)"-style jargon unless it tells a volunteer what the job is. 60 chars
  max.
- **Description:** one or two sentences, about 30 to 50 words (60 to 400
  characters), addressed to the reader. Say what the volunteer does and how
  training works (live online, in person, or on demand), taken from the
  trainings' `modality` and `on_demand`.
- **Never** include session dates, names, emails, phone numbers, the
  866-OUR-VOTE hotline or any hotline, or anything partisan. The hotline is a
  separate Lawyers' Committee effort with a geography we don't control.
- **Default door item:** title "Election Protection Volunteer", description
  "Help make sure every eligible voter in {State} can cast their ballot. Sign
  up to volunteer with Election Protection and we'll connect you with
  training and opportunities near you."

**Links:** where `front_door` is set, every item in that state uses it
exactly. The apply script enforces this. Where `agent_picks_link` is true:

1. A page that centralizes the role's timeslots, if one exists: a single
   event whose `n_sessions` covers the role's dates, or a state signup or form
   page that several trainings share (the same URL appearing across trainings
   is the tell).
2. Otherwise the soonest upcoming event (`next_date`), or the on-demand one.

Links must be one of that state's own training URLs, or share their host.
**Don't browse the web** to find a better page. The worklist is your only
source, and a link you found elsewhere can't be verified by the next run.

## 5. Write the proposal

`tmp/sweep/proposal.json`, the COMPLETE desired set of sweep rows (anything
you leave out gets disabled):

```json
{"rows": [
  {"key": "ptv:AZ:poll-monitor", "state": "AZ", "title": "Poll Monitor",
   "description": "...", "link": "https://protectthevote.net/"}
],
 "link_choices": {"TX:poll-monitor": "soonest upcoming event; 5 separate Mobilize events, no shared page"}}
```

`link_choices` records the reason for every link where `agent_picks_link` was
true. It goes in your report.

## 6. Apply

```bash
.venv/Scripts/python.exe scripts/sweep_apply.py --dry-run
.venv/Scripts/python.exe scripts/sweep_apply.py
```

Read the dry run's diff first. **Expect a small diff on a normal run**, most
often zero. A large diff when trainings barely changed means you re-keyed or
re-worded rows. Fix the proposal, not the checks.

| Exit | Meaning | What you do |
|---|---|---|
| 0 | Applied, or no change | Report and close |
| 3 | Validation refused the proposal | Fix a genuine mistake in YOUR proposal and retry once. If the refusal looks wrong, stop and report it. Never retry more than once |
| 4 | Shrink guard: would disable more than half the enabled sweep rows | **Stop.** Diagnose (is the training payload partial? did roles really end?) and report. Never pass `--allow-shrink`; that flag is Rob's |
| 5 | Sheet shape wrong (a column is missing) | Stop and report. Never add or rename columns |

The Civis sync at 07:00 / 15:00 publishes what you wrote. You don't run it.

## 7. Report (evidence of done)

- The training payload's `generated_at` and age.
- Counts: states with trainings, PTV states, K links, sweep items proposed.
- The apply diff: created, updated and disabled counts plus their keys (keys
  and state codes are safe; they carry no people-data).
- `link_choices` for every agent-picked link.
- Every `staff_owned_keys` entry you skipped.
- Anything odd: a role you couldn't classify, a K link that looks wrong (for
  example pointing at a different state), a state whose trainings all vanished.

## Never

- Touch a row whose `source` isn't `sweep`, or edit the Sheet by any route
  other than `sweep_apply.py`.
- Pass `--allow-shrink`.
- Read coalition-plan columns other than A and K, or copy anything from it
  beyond the K link. The tab holds state leads and partners.
- Mention the hotline, name a person, or include contact details in copy.
- Run the Civis job, edit `data/opportunities.json`, or push to the repo. The
  Civis sync owns publishing.
