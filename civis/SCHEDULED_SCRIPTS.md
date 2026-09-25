# Scheduled Scripts — EP Volunteer Map

*Last verified: 2026-09-25 (end-to-end run: Sheet → Civis → commit → Pages → live JSON)*

## Workflows

### Twice-daily Sheet → opportunities.json sync
- **Civis name:** EP Volunteer Map Sync (job `370504796`), standalone container job (no workflow)
- **Schedule:** Daily at 07:00 and 15:00 ET (America/New_York)
- **Steps:** sync_opportunities.sh

## Scripts

### sync_opportunities.sh
- **Type:** Scheduled (via Twice-daily Sheet → opportunities.json sync, step 1)
- **Civis job name:** EP Volunteer Map Sync (`370504796`)
- **Source script:** `civis/sync_opportunities.sh` (version-controlled job body)
- **APIs:** Google Sheets API (60 reads/min/user; 2 reads per run), GitHub API (5000 requests/hr/authenticated PAT)
- **Description:** Runs `python app/scripts/sync_opportunities.py --push`. Reads the `Opportunities` tab of the source Google Sheet (by name; the first tab is `Read me`), validates rows, drops rows whose `ends` date has passed (Eastern), and writes `data/opportunities.json`. Publishes to `main` via the GitHub contents API (`ccef_connections.GitHubConnector`, deploy PAT; no local git push) only when the content hash differs from the file in the fresh clone. GitHub Actions deploys the JSON to Pages on push. Exits 3 without publishing if a required column header is missing, so a renamed header can't blank the map.

#### Civis configuration

| Field | Value |
|---|---|
| Source repo | `common-cause/ep-volunteer-map` |
| Branch | `main` |
| Docker image | `civisanalytics/datascience-python:8.5.0` |
| Command | `bash app/civis/sync_opportunities.sh` |
| Resources | cpu 512m, memory 1024 MB, disk 1 GB |
| Failure email | rkerth@commoncause.org |

The job is **GitHub-backed**: Civis clones the repo into `app/` and runs the
stub command above. Setup/run steps live in the version-controlled
`civis/sync_opportunities.sh`; edit and push to change them, never edit the
body in the Civis UI. Credentials/env the job must provide (see the
`sync_opportunities.py` docstring):

| Param | Bound to |
|---|---|
| `GOOGLE_SHEETS_CREDENTIALS` | credential 39363 (fleet Sheets service account, shared with Dynamic Action Map) |
| `EP_VOLUNTEER_MAP_GITHUB_PAT` | credential 39693 "EP Volunteer Map Github PAT" |
| `GOOGLE_SHEET_ID` | string param (value lives in Civis and the local `.env`, not here) |

`GITHUB_REPO` and `GOOGLE_SHEET_TAB` default correctly and need not be set.

- **PAT:** fine-grained, resource owner common-cause, this repo only,
  **Contents: Read and write** (read-only fails the push with a 403,
  "Resource not accessible by personal access token"). **Expires
  2026-12-24**: rotate it before then if the map is still live
  (`civis_rotate_credential` on 39693, plus the meta `.env`).
- **Setup gaps in the civis MCP (2026-09-25):** `civis_create_job` binds only
  credential ids and `civis_set_schedule` takes one hour, so `GOOGLE_SHEET_ID`
  and the two-hour schedule were set with the civis Python client
  (`scripts.patch_containers`, then read back). Re-creating the job would need
  the same.

## On-Demand Scripts

None. Preview locally with `python scripts/sync_opportunities.py --dry-run`.
