"""
Gets a YouTube refresh token using Google's "Device Authorization" flow -
the same kind of flow TV apps use ("go to a website, enter this code").
No computer needed: this is meant to be run as a one-off GitHub Action from
your phone. You'll get a short code, open a link in your phone's browser,
type the code in, and this script does the rest automatically.

ONE-TIME SETUP IN GOOGLE CLOUD CONSOLE (console.cloud.google.com, via your
phone's browser):
  1. Create a project (or use an existing one).
  2. APIs & Services -> Library -> search "YouTube Data API v3" -> Enable.
  3. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID.
  4. Application type: "TVs and Limited Input devices"  <-- important, NOT
     "Desktop app" - this is the type that supports this exact flow.
  5. Copy the Client ID and Client Secret it gives you.
  6. Add them as GitHub Secrets: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET.

Then trigger the "Get YouTube Token" GitHub Action (workflow_dispatch) that
runs this script. Watch the Action log - it will print a URL and a code.
"""

import os
import time
import requests

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
SCOPE = "https://www.googleapis.com/auth/youtube.upload"

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET as GitHub Secrets first.")


def main():
    # Step 1: request a device code + user code
    res = requests.post("https://oauth2.googleapis.com/device/code", data={
        "client_id": CLIENT_ID,
        "scope": SCOPE,
    })
    res.raise_for_status()
    data = res.json()

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_url = data.get("verification_url") or data.get("verification_uri")
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 1800)

    print("=" * 60)
    print(f"1. On your phone, open:  {verification_url}")
    print(f"2. Enter this code:      {user_code}")
    print(f"3. Log in and approve access.")
    print("=" * 60)
    print(f"Waiting for approval (expires in {expires_in // 60} min)...")

    # Step 2: poll until the user approves (or it expires)
    waited = 0
    while waited < expires_in:
        time.sleep(interval)
        waited += interval

        token_res = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        token_data = token_res.json()

        if "error" in token_data:
            if token_data["error"] == "authorization_pending":
                print("  Still waiting for you to approve in the browser...")
                continue
            elif token_data["error"] == "slow_down":
                interval += 5
                continue
            else:
                raise RuntimeError(f"OAuth error: {token_data}")

        # Success!
        print("\nApproved! Here are your GitHub Secrets:")
        print("=" * 60)
        print(f"YOUTUBE_REFRESH_TOKEN={token_data['refresh_token']}")
        print("=" * 60)
        print("Copy the YOUTUBE_REFRESH_TOKEN value above into your GitHub Secrets.")
        return

    raise TimeoutError("You didn't approve in time - re-run this workflow to try again.")


if __name__ == "__main__":
    main()
