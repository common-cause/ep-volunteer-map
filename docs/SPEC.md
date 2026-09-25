# ep-volunteer-map — project spec

**Status:** spec only, nothing built yet. · **Written:** 2026-09-25, in the
meta-project, from Rob's brief. · **Requested by:** Amy. **Owner:** Rob
(campaigns).

## One line

A US map of Election Protection **volunteer opportunities**, fed by a Google
Sheet and embedded on protectthevote.net. It's **dynamic-action-map with many
items per state**: each state opens a list of opportunities rather than one
action.

## What it shows

Organizers keep a Google Sheet. Each row is one opportunity:

| column | required | notes |
|---|---|---|
| `state` | yes | full name or USPS code; see "National rows" below |
| `title` | yes | short, shown as the list-item heading |
| `description` | yes | a paragraph; blank-line runs collapse (same rule as dynamic-action-map) |
| `link` | yes | the "get involved" URL. **http(s) only**, validated at both ends |
| `enabled` | no | blank or TRUE = shown; FALSE hides the row without deleting it |

Reserve `last updated` and `updated by` columns for editors, and have the sync
ignore them, as dynamic-action-map does. Headers match case-insensitively.

The map colours each state that has at least one opportunity. Clicking a state
(or choosing it from a dropdown, for accessibility) opens its list. A state with
nothing shows a fallback that points to protectthevote.net's main signup.

## Architecture (a deterministic pipeline, so it runs on Civis, not the tower)

```
Google Sheet (organizers edit)
  -> Civis job, TWICE DAILY (times TBD)      scripts/sync_opportunities.py
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
| `dynamic-action-map/scripts/sync_actions.py` | Sheet read, header normalisation, URL scheme check, atomic write, content-hash gate, `--push` | one row → **list** per state; no DEFAULT-row logic; add `enabled` and national rows |
| `dynamic-action-map/civis/sync_actions.sh` + `SCHEDULED_SCRIPTS.md` | the GitHub-backed job body; the pinned `ccef-connections[sheets] @ git+…@<tag>` install; `.gitattributes` `*.sh eol=lf` | names; schedule ×2 |
| `dynamic-action-map/.github/workflows/deploy.yml` | the **allowlist** Pages deploy (publishes named files, not the checkout) | file list |
| `ep-training-map/src/ep_training_map/public.py` | the state-list-map front end (per-state lists, postMessage height reporting for the iframe) and EP coalition styling | render opportunities instead of trainings; header copy |
| `ep-training-map-public/docs/wordpress_embed.md` | the iframe + height-listener snippet and admin runbook | id, message type, URL |
| `ep-tools-home/docs/ep-coalition-style-guide.md` | the brand, as source of record | — |

## Decided (Rob, 2026-09-25)

- **Host:** protectthevote.net, as an iframe in a Custom HTML block (same admin
  and same pattern as the public training map). **Brand:** EP coalition.
- **Department:** campaigns.
- **Refresh:** twice daily.

## Open (settle these with Rob or Amy before building; one at a time)

1. **Who owns the Sheet, and where does it live?** It should be in a Shared
   Drive, shared (Viewer) with the service account behind
   `GOOGLE_SHEETS_CREDENTIALS_PASSWORD`. Who, besides Amy, can edit?
2. **National/remote opportunities.** Proposal: `state` = `ALL` (or
   `National`) shows the row in every state's list, marked "Nationwide", so no
   one copies a row 50 times. Confirm the keyword.
3. **Do opportunities expire?** An optional `ends` date that auto-hides past
   rows would stop the map going stale, the main way a sheet-backed map rots.
4. **Contact details in descriptions.** The map is public and will spread. Should
   the sync **refuse** rows whose description contains an email address or phone
   number (and warn), with contact going through the link only? Recommended: yes.
5. **Public repo or private?** The repo was created private (the fleet
   default). Pages from a private org repo depends on the org's plan. The
   published site is public either way, so the real question is only whether
   the source is visible. Check `gh api orgs/common-cause --jq .plan` before
   choosing.
6. **Run times** for the two Civis runs. Check `schedules/cloud_schedule.md`
   for Sheets-API neighbours at those hours.
7. **Header copy and empty-state copy.** Suggestion: "Volunteer with Election
   Protection. Find opportunities in your state." Amy's call.
8. **Ordering within a state:** Sheet order (editor-controlled), or
   alphabetical/by date?

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

- `gh auth refresh -s workflow` (above).
- Mint the PAT once the repo is ready to receive pushes, and put it in the
  meta `.env` and in Civis.
- Enable Pages (source: GitHub Actions) after the first deploy.
- Send the protectthevote.net admin the embed runbook.
