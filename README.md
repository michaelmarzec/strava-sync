# strava-sync

Personal Strava activity sync. It pulls your activities from the Strava API and stores them in this repo as JSON and CSV, refreshed daily by a GitHub Action. No server, no database.

## How it works

- `strava_sync.py` refreshes your Strava access token, downloads all of your activities, and upserts them (by activity ID) into `data/activities.json` and `data/activities.csv`.
- `.github/workflows/sync.yml` runs the script daily and commits any changes back to this repo. You can also run it manually from the Actions tab.
- Strava invalidates your old refresh token every time a new access token is issued, so on each run the script writes the rotated refresh token back to the `STRAVA_REFRESH_TOKEN` repo secret. That is what the `GH_TOKEN` secret in step 4 is for.

## Setup (one time, about 15 minutes)

You need: this repo, a free Strava API application, and about 15 minutes.

### 1. Create a Strava API application

1. Go to <https://www.strava.com/settings/api> while logged in to Strava.
2. Fill in the form. Only one field actually matters for this project:
   - **Application Name**: anything, e.g. `strava-sync`
   - **Category**: anything, e.g. `Data Importer`
   - **Club**: leave blank
   - **Website**: anything, e.g. `http://localhost`
   - **Application Description**: optional, leave blank
   - **Authorization Callback Domain**: `localhost` (this is the one that matters)
3. Agree to the terms and click **Create**.
4. On the next page, note your **Client ID** and **Client Secret**.

### 2. Get your refresh token

Run the included helper script on any machine with Python 3:

```bash
pip install requests
python get_refresh_token.py
```

The script asks for your Client ID and Client Secret, then prints a Strava authorization URL. Open it, leave both permission boxes checked (`View data about your activities` includes private ones via the `read,activity:read_all` scope), and click **Authorize**.

Your browser then lands on a `http://localhost/...` URL that fails to load. That is expected. Copy the **entire URL from the address bar** and paste it into the script. It exchanges the one-time code and prints your three secret values.

Prefer curl? The manual version:

```bash
# 1. Open in a browser (replace YOUR_CLIENT_ID):
# https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&approval_prompt=force&scope=read,activity:read_all
# 2. Authorize, then copy the `code` value from the localhost URL you land on.
# 3. Exchange it:
curl -X POST https://www.strava.com/oauth/token \
  -d client_id=YOUR_CLIENT_ID \
  -d client_secret=YOUR_CLIENT_SECRET \
  -d code=THE_CODE_FROM_THE_URL \
  -d grant_type=authorization_code
# The response JSON contains your refresh_token.
```

### 3. Create a token for refresh-token rotation

Every sync run gets a new refresh token from Strava, and the old one stops working immediately. To keep the Action running unattended, the workflow writes the new token back to the repo secret using a fine-grained personal access token scoped to this repo only:

1. Go to <https://github.com/settings/personal-access-tokens/new>.
2. Fill in:
   - **Token name**: e.g. `strava-sync-secret-rotation`
   - **Expiration**: your choice (note it - you will need to regenerate and update the `GH_TOKEN` secret when it expires)
   - **Repository access**: **Only select repositories**, and select this repo (`strava-sync`)
   - **Permissions** -> **Repository permissions** -> **Secrets**: set to **Read and write**
3. Click **Generate token** and copy it.

### 4. Add the four repository secrets

In this repo: **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**, and add:

| Secret | Value |
| --- | --- |
| `STRAVA_CLIENT_ID` | Client ID from step 1 |
| `STRAVA_CLIENT_SECRET` | Client Secret from step 1 |
| `STRAVA_REFRESH_TOKEN` | Refresh token printed in step 2 |
| `GH_TOKEN` | Fine-grained PAT from step 3 |

### 5. Run it

1. Go to the **Actions** tab. If GitHub asks, enable workflows for this repo.
2. Select the **Sync Strava activities** workflow, click **Run workflow** to do the first full sync immediately (this backfills every activity).
3. After that it runs daily on its own (the cron schedule in `.github/workflows/sync.yml` is in UTC; edit it to taste).

If a run fails with a refresh-token error, re-run `get_refresh_token.py` and update the `STRAVA_REFRESH_TOKEN` secret.

## The data

- `data/activities.json` - the full activity objects the API returns, newest first. This is the source of truth; re-runs upsert by activity ID, so renames and edits on Strava are picked up.
- `data/activities.csv` - a flat summary (name, sport, date, distance, time, elevation, heart rate, etc.) for quick spreadsheet use.

Both are regenerated in full on every run, so only the diff gets committed.

## Notes

- Only your own activities are synced, and only you can see them - this repo is private.
- Strava API rate limits (100 requests / 15 min, 1000 / day at the time of writing) are far above what this uses: one token refresh plus a handful of paginated activity-list requests per day.
- The refresh token, client secret, and PAT are never written into the repo - they live only in GitHub Actions secrets.
