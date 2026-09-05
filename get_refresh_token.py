#!/usr/bin/env python3
"""One-time helper: get the Strava refresh token this project needs.

Prereqs: Python 3 and `pip install requests`. Have your Strava API app's
Client ID and Client Secret ready (https://www.strava.com/settings/api).
"""

from urllib.parse import parse_qs, urlparse

import requests

client_id = input("Client ID: ").strip()
client_secret = input("Client Secret: ").strip()

authorize_url = (
    "https://www.strava.com/oauth/authorize"
    f"?client_id={client_id}"
    "&redirect_uri=http://localhost"
    "&response_type=code"
    "&approval_prompt=force"
    "&scope=read,activity:read_all"
)

print("\n1. Open this URL in your browser:\n")
print(f"   {authorize_url}\n")
print("2. Log in to Strava if asked, leave both permission boxes checked, and click Authorize.")
print("3. Your browser will land on a localhost address that fails to load. That is expected.")
print("4. Copy the ENTIRE URL from the address bar and paste it below.\n")

redirected = input("Paste the redirected URL here: ").strip()
params = parse_qs(urlparse(redirected).query)
if "error" in params:
    raise SystemExit(f"Strava returned an error: {params['error'][0]}. Run the script again.")
if "code" not in params:
    raise SystemExit("No 'code' parameter found in that URL. Copy the full address-bar URL and try again.")
code = params["code"][0]

resp = requests.post(
    "https://www.strava.com/oauth/token",
    data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    },
    timeout=30,
)
if resp.status_code != 200:
    raise SystemExit(f"Token exchange failed ({resp.status_code}): {resp.text}")
tokens = resp.json()

print("\nSuccess. Add these three repository secrets (Settings -> Secrets and variables -> Actions):\n")
print(f"  STRAVA_CLIENT_ID      = {client_id}")
print(f"  STRAVA_CLIENT_SECRET  = {client_secret}")
print(f"  STRAVA_REFRESH_TOKEN  = {tokens['refresh_token']}")
print(f"\n(granted scope: {tokens.get('scope', 'unknown')})")
