# ep-volunteer-map — project spec

**Status:** spec settled (all open questions answered 2026-09-25); sync and
front end built 2026-09-25, not yet deployed. · **Written:** 2026-09-25, in the
meta-project, from Rob's brief. · **Requested by:** Amy (a state ED, not
national program staff). **Owner and sign-off:** Rob (campaigns). Amy's input
is welcome, but she doesn't have final approval over copy or behaviour.

## One line

A US map of Election Protection **volunteer opportunities**, fed by a Google
Sheet and embedded on protectthevote.net. It's **dynamic-action-map with many
items per state**: each state opens a list of opportunities rather than one
action.

## What it shows

Organizers keep a Google Sheet. Each row is one opportunity:

| column | required | notes |
|---|---|---|
| `state` | yes | full name or USPS code; one state per row (no national rows) |
| `title` | yes | short, shown as the list-item heading |
| `description` | yes | a paragraph; blank-line runs collapse (same rule as dynamic-action-map) |
| `link` | yes | the "get involved" URL. **http(s) only**, validated at both ends |
| `enabled` | no | blank or TRUE = shown; FALSE hides the row without deleting it |
| `ends` | no | a date; the row shows through 23:59 America/New_York that day, then the sync drops it. Blank = no expiry. An unparseable date rejects the row with a warning (fail visible, not open) |

Reserve `last updated` and `updated by` columns for editors, and have the sync
ignore them, as dynamic-action-map does. Headers match case-insensitively.

The map colours each state that has at least one opportunity. Clicking a state
(or choosing it from a dropdown, for accessibility) opens its list. A state with
nothing shows a fallback that points to protectthevote.net's main signup.

## Architecture (a deterministic pipeline, so it runs on Civis, not the tower)

```
Google Sheet (organizers edit)
  -> Civis job, daily 07:00 + 15:00 ET       scripts/sync_opportunities.py
       read via ccef_connections SheetsConnector
       validate rows -> data/opportunities.json
       skip if content unchanged (hash of payload, NOT a timestamp)
       push via ccef_connections GitHubConnector (contents API; no checkout on Civis)
  -> GitHub Actions -> GitHub Pages
  -> <iframe> in a WordPress Custom HTML block on protectthevote.net
```

No judgment is involved, so it's plain ETL on Civis, with no dispatch contract
and no grant (treaty §2.8). The job needs a `civis/SCHEDULED_SCRIPTS.md` entry
the moment it exists.

### Lift, don't rewrite

| from | take | change |
|---|---|---|
| `dynamic-action-map/scripts/sync_actions.py` | Sheet read, header normalisation, URL scheme check, atomic write, content-hash gate, `--push` | one row → **list** per state; no DEFAULT-row logic; add `enabled` |
| `dynamic-action-map/civis/sync_actions.sh` + `SCHEDULED_SCRIPTS.md` | the GitHub-backed job body; the pinned `ccef-connections[sheets] @ git+…@<tag>` install; `.gitattributes` `*.sh eol=lf` | names; schedule ×2 |
| `dynamic-action-map/.github/workflows/deploy.yml` | the **allowlist** Pages deploy (publishes named files, not the checkout) | file list |
| `ep-training-map/src/ep_training_map/public.py` | the state-list-map front end (per-state lists, postMessage height reporting for the iframe) and EP coalition styling | render opportunities instead of trainings; header copy |
| `ep-training-map-public/docs/wordpress_embed.md` | the iframe + height-listener snippet and admin runbook | id, message type, URL |
| `ep-tools-home/docs/ep-coalition-style-guide.md` | the brand, as source of record | — |

## Decided (Rob, 2026-09-25)

- **Host:** protectthevote.net, as an iframe in a Custom HTML block (same admin
  and same pattern as the public training map). **Brand:** EP coalition.
- **Department:** campaigns.
- **Refresh:** twice daily, 07:00 and 15:00 ET (Q6).
- **The Sheet** (Q1): "EP Volunteer Opportunities Map", tab `Opportunities`.
  Its id is `GOOGLE_SHEET_ID` in the local `.env` (the repo is public; keep
  the id out of it). It lives in the C&O external Shared Drive folder, the
  Sheets MCP's default. Access is inherited from that folder: campaigns-g and
  named staff are organizers, allstaff-g can read, and the fleet Sheets
  service account is fileOrganizer, so the sync can read it. Header row written (the columns
  above, plus the two editor columns). Organizers outside campaigns-g need
  editor access granted on the file itself.

## Questions (all eight settled with Rob, 2026-09-25)

1. ~~Who owns the Sheet, and where does it live?~~ Settled; see Decided.
2. ~~National/remote opportunities.~~ Settled (Rob, 2026-09-25): **none.**
   Every row belongs to one state. No national keyword; a `state` value that
   isn't a state name or USPS code is rejected with a warning, like any other
   bad row.
3. ~~Do opportunities expire?~~ Settled (Rob, 2026-09-25): **yes**, optional
   `ends` column, visible through end of day Eastern (see the column table).
   With the 07:00 run, an expired row lingers up to ~7h past midnight;
   accepted. Note: the content-hash gate means an expiry changes the payload,
   so the run that drops it pushes, as it should.
4. ~~Contact details in descriptions.~~ Settled (Rob, 2026-09-25): **no
   filter.** States publish what they choose. The Sheet itself states plainly
   that everything entered is published on a public national map; that notice
   is the control. It lives in a first-position `Read me` tab, so the sync
   must open the `Opportunities` tab **by name**, never "first tab". If the
   column set changes, update `Read me` too. Safety (not content policy) still
   applies: the sync stores plain text and enforces http(s)-only links, and
   the front end renders all Sheet text as text (`textContent`), never as HTML,
   and re-checks link schemes.
5. ~~Public repo or private?~~ Settled (Rob, 2026-09-25): **public**. The org
   is on GitHub's free plan, which has no Pages for private repos; siblings
   dynamic-action-map and ep-training-map-public are public for the same
   reason. Consequence: nothing sensitive in the repo, ever, including the
   Sheet id (local `.env` only) and anything that looks like row data.
6. ~~Run times.~~ Settled (Rob, 2026-09-25): **daily 07:00 and 15:00
   America/New_York.** Clear of the other Sheets-API jobs (DAM 06:00, EP
   Syncs 08:15, EP Dashboards 10:30/22:30 per `cloud_schedule.md` that day).
   07:00 publishes overnight edits and drops rows whose `ends` day has passed;
   15:00 publishes the morning's edits the same day.
7. ~~Header copy and empty-state copy.~~ Settled (Rob, 2026-09-25):
   - Header: **"Volunteer with Election Protection"**, subhead **"Find
     opportunities in your state."**
   - Empty state: **"There are no listed opportunities in {State} right now.
     You can still sign up to volunteer with Election Protection."** plus a
     button to the main signup, `https://protectthevote.net` (the signup is
     front and center on its home page).
8. ~~Ordering within a state.~~ Settled (Rob, 2026-09-25): **Sheet order.**
   The sync preserves row order per state; the front end must not re-sort.

## Credentials (declare blank, then reseed from meta, scoped with `--keys`)

- `GOOGLE_SHEETS_CREDENTIALS_PASSWORD`: already fleet-held.
- `EP_VOLUNTEER_MAP_GITHUB_PAT_PASSWORD`: **new.** A fine-grained PAT,
  common-cause owner, this repo only, Contents read and write. Catalog it
  `scope: project`, `projects: [ep-volunteer-map]`, following the
  DYNAMIC_ACTION_MAP model. It's also a Civis credential for the job.
- `GOOGLE_SHEET_ID`: config, project-local.

## Known snag

**Pushing `.github/workflows/*` needs the `workflow` scope on the gh/git
token.** It isn't present today, and that's why the scaffold's first push was
rejected (the template workflow was stripped to land the scaffold). Before
adding `deploy.yml`, Rob runs `gh auth refresh -h github.com -s workflow`.

## Rob's steps

- ~~`gh auth refresh -s workflow`~~ Done 2026-09-25 (via a fresh
  `gh auth login`; refresh failed because gh had the account under its old
  name, `common-cause`, since renamed `rkerth-cc`).
- ~~Enable Pages~~ Done 2026-09-25 (`build_type=workflow`); live at
  https://common-cause.github.io/ep-volunteer-map/.
- Mint the PAT and put it in the meta `.env` and in Civis.
- Send the protectthevote.net admin `docs/wordpress_embed.md`.
