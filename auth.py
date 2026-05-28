#!/usr/bin/env python3
"""
One-time OAuth flow to get LinkedIn access + refresh tokens.
Run this ONCE: python auth.py
Saves tokens to .tokens.json — never commit this file.
"""

import os, json, secrets, urllib.parse, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REDIRECT_URI  = "http://localhost:8080/callback"
SCOPES        = "openid profile email w_member_social"
TOKENS_FILE   = Path(".tokens.json")

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # silence access logs

    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Auth successful. You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Error: no code returned.</h2>")


def get_tokens(code: str) -> dict:
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()


def get_profile(access_token: str) -> dict:
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()


def main():
    state = secrets.token_urlsafe(16)
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT_URI,
            "scope":         SCOPES,
            "state":         state,
        })
    )

    print(f"\nOpening browser for LinkedIn auth...\n{auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8080), CallbackHandler)
    print("Waiting for callback on http://localhost:8080/callback ...")
    server.handle_request()

    if not auth_code:
        print("ERROR: Did not receive auth code.")
        return

    print("Got auth code. Exchanging for tokens...")
    tokens = get_tokens(auth_code)

    profile = get_profile(tokens["access_token"])
    tokens["sub"] = profile["sub"]  # LinkedIn member URN ID
    tokens["name"] = profile.get("name", "")

    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"\n✓ Tokens saved to {TOKENS_FILE}")
    print(f"  Authenticated as: {tokens['name']} (sub: {tokens['sub']})")
    print(f"  Access token expires in: {tokens.get('expires_in', '?')} seconds (~60 days)")
    print("\nNext: run `python post.py` to test a post, or set up cron with `cron_setup.sh`")


if __name__ == "__main__":
    main()

