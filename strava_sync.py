#!/usr/bin/env python3
"""Sync activities from the Strava API into data/activities.json and data/activities.csv.

Reads credentials from environment variables:
  STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN

Strava rotates the refresh token on every token refresh and invalidates the old
one immediately, so when GH_TOKEN and GITHUB_REPOSITORY are also set (as in the
included GitHub Actions workflow), a rotated refresh token is written back to the
repository's STRAVA_REFRESH_TOKEN Actions secret automatically.
"""

import base64
import csv
import json
import os
import sys
from pathlib import Path

import requests

TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
PER_PAGE = 200  # Strava API max

DATA_DIR = Path(__file__).resolve().parent / "data"
JSON_PATH = DATA_DIR / "activities.json"
CSV_PATH = DATA_DIR / "activities.csv"

CSV_FIELDS = [
    "id", "name", "sport_type", "type", "start_date", "start_date_local",
    "distance", "moving_time", "elapsed_time", "total_elevation_gain",
    "average_speed", "max_speed", "average_heartrate", "max_heartrate",
    "average_cadence", "average_watts", "kilojoules", "suffer_score",
    "kudos_count", "comment_count", "visibility", "commute", "trainer",
]


def env(name, required=True):
    value = os.environ.get(name, "").strip()
    if required and not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


def refresh_access_token(client_id, client_secret, refresh_token):
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        sys.exit(
            f"Token refresh failed ({resp.status_code}): {resp.text}\n"
            "If this says the refresh token is invalid, re-run get_refresh_token.py "
            "and update the STRAVA_REFRESH_TOKEN secret."
        )
    return resp.json()


def update_github_secret(secret_name, secret_value):
    """Write a rotated refresh token back to the repo's Actions secrets."""
    gh_token = env("GH_TOKEN", required=False)
    repo = env("GITHUB_REPOSITORY", required=False)
    if not gh_token or not repo:
        print("NOTE: Strava rotated the refresh token but GH_TOKEN/GITHUB_REPOSITORY "
              "are not set; cannot persist it. Update the secret manually.")
        return
    from nacl import encoding, public

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
        timeout=30,
    )
    key_resp.raise_for_status()
    key_data = key_resp.json()
    sealed = public.SealedBox(public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder))
    encrypted = base64.b64encode(sealed.encrypt(secret_value.encode())).decode()
    put_resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
        timeout=30,
    )
    put_resp.raise_for_status()
    print("Rotated refresh token written back to the STRAVA_REFRESH_TOKEN secret.")


def fetch_all_activities(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    activities = []
    page = 1
    while True:
        resp = requests.get(
            ACTIVITIES_URL,
            headers=headers,
            params={"page": page, "per_page": PER_PAGE},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        activities.extend(batch)
        print(f"Fetched page {page}: {len(batch)} activities")
        if len(batch) < PER_PAGE:
            break
        page += 1
    return activities


def load_existing():
    if JSON_PATH.exists():
        with open(JSON_PATH) as f:
            return {a["id"]: a for a in json.load(f)}
    return {}


def save(by_id):
    DATA_DIR.mkdir(exist_ok=True)
    activities = sorted(
        by_id.values(), key=lambda a: a.get("start_date", ""), reverse=True
    )
    with open(JSON_PATH, "w") as f:
        json.dump(activities, f, indent=2)
        f.write("\n")
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(activities)


def main():
    client_id = env("STRAVA_CLIENT_ID")
    client_secret = env("STRAVA_CLIENT_SECRET")
    refresh_token = env("STRAVA_REFRESH_TOKEN")

    tokens = refresh_access_token(client_id, client_secret, refresh_token)
    if tokens.get("refresh_token") and tokens["refresh_token"] != refresh_token:
        update_github_secret("STRAVA_REFRESH_TOKEN", tokens["refresh_token"])

    fetched = fetch_all_activities(tokens["access_token"])
    by_id = load_existing()
    before = len(by_id)
    for activity in fetched:
        by_id[activity["id"]] = activity  # upsert by activity id
    save(by_id)
    print(f"Done. Store holds {len(by_id)} activities "
          f"({len(by_id) - before} new on this run).")


if __name__ == "__main__":
    main()
