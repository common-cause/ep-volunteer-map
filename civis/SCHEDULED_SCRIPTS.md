# Scheduled Scripts — EP Volunteer Map

*Last verified: 2026-09-25 (not yet created in Civis)*

## Workflows

### Twice-daily Sheet → opportunities.json sync
- **Civis name:** not yet created — record it here when it is
- **Schedule:** Daily at 07:00 and 15:00 ET (America/New_York)
- **Steps:** sync_opportunities.sh

## Scripts

### sync_opportunities.sh
- **Type:** Scheduled (via Twice-daily Sheet → opportunities.json sync, step 1)
- **Civis job name:** ep-volunteer-map sync_opportunities
- **Source script:** `civis/sync_opportunities.sh` (version-controlled job body)
- **APIs:** Google Sheets API (60 reads/min/user; 2 reads per run), GitHub API (5000 requests/hr/authenticated PAT)
- **Description:** Runs `python app/scripts/sync_opportunities.py --push`. Reads the `Opportunities` tab of the source Google Sheet (by name; the first tab is `Read me`), validates rows, drops rows whose `ends` date has passed (Eastern), and writes `data/opportunities.json`. Publishes to `main` via the GitHub contents API (`ccef_connections.GitHubConnector`, deploy PAT; no local git push) only when the content hash differs from the file in the fresh clone. GitHub Actions deploys the JSON to Pages on push. Exits 3 without publishing if a required column header is missing, so a renamed header can't blank the map.

#### Civis configuration

| Field | Value |
|---|---|
| Source repo | `common-cause/ep-volunteer-map` |
| Branch | `main` |
| Docker image | `civisanalytics/datascience-python:latest` |
| Command | `bash app/civis/sync_opportunities.sh` |

The job is **GitHub-backed**: Civis clones the repo into `app/` and runs the
stub command above. Setup/run steps live in the version-controlled
`civis/sync_opportunities.sh`; edit and push to change them, never edit the
body in the Civis UI. Credentials/env the job must provide (see the
`sync_opportunities.py` docstring): `GOOGLE_SHEETS_CREDENTIALS` (service-account
JSON in the password field), `EP_VOLUNTEER_MAP_GITHUB_PAT` (fine-grained deploy
PAT in the password field), plus `GOOGLE_SHEET_ID` as a job parameter.
`GITHUB_REPO` and `GOOGLE_SHEET_TAB` default correctly and need not be set.

## On-Demand Scripts

None. Preview locally with `python scripts/sync_opportunities.py --dry-run`.
