#!/usr/bin/env python3
"""
LinkedIn Tech News Bot
- Fetches top story from RSS feeds
- Scrapes real OG image from article
- Generates 2-para post via Claude API
- Posts to LinkedIn with image
- Tracks posted URLs to avoid duplicates
"""

import os, json, sys, time, logging, hashlib, mimetypes
from pathlib import Path
from datetime import datetime
import requests
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

CLIENT_ID     = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
TOKENS_FILE   = Path(".tokens.json")
POSTED_FILE   = Path(".posted_urls.json")
LOGS_DIR      = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

RSS_FEEDS = [
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
    "https://feeds.wired.com/wired/index",
    "https://www.technologyreview.com/feed/",
]

# Topics to prioritise (case-insensitive match in title/summary)
PREFERRED_TOPICS = [
    "AI", "artificial intelligence", "machine learning", "open source",
    "robotics", "quantum", "chip", "semiconductor", "breakthrough",
    "research", "launch", "release", "model", "LLM", "hardware",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / f"{datetime.now():%Y-%m-%d}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Token management ──────────────────────────────────────────────────────────

def load_tokens() -> dict:
    if not TOKENS_FILE.exists():
        log.error("No .tokens.json found. Run `python auth.py` first.")
        sys.exit(1)
    return json.loads(TOKENS_FILE.read_text())


def refresh_access_token(tokens: dict) -> dict:
    """LinkedIn tokens last ~60 days; refresh_token lasts ~1 year."""
    if "refresh_token" not in tokens:
        log.warning("No refresh_token available. Re-run auth.py when token expires.")
        return tokens

    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.ok:
        new_tokens = {**tokens, **resp.json()}
        TOKENS_FILE.write_text(json.dumps(new_tokens, indent=2))
        log.info("Access token refreshed successfully.")
        return new_tokens
    else:
        log.warning(f"Token refresh failed: {resp.text}")
        return tokens

# ── Duplicate tracking ────────────────────────────────────────────────────────

def load_posted() -> set:
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text()))
    return set()


def mark_posted(url: str):
    posted = load_posted()
    posted.add(url)
    # Keep last 200 only
    trimmed = list(posted)[-200:]
    POSTED_FILE.write_text(json.dumps(trimmed, indent=2))

# ── RSS fetching ──────────────────────────────────────────────────────────────

def score_entry(entry) -> int:
    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    return sum(1 for topic in PREFERRED_TOPICS if topic.lower() in text)


def fetch_best_article(posted_urls: set) -> dict:
    candidates = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                url = entry.get("link", "")
                if not url or url in posted_urls:
                    continue
                candidates.append({
                    "url":     url,
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "source":  feed.feed.get("title", feed_url),
                    "score":   score_entry(entry),
                })
        except Exception as e:
            log.warning(f"Failed to parse feed {feed_url}: {e}")

    if not candidates:
        log.error("No new candidates found across all feeds.")
        return None

    # Sort by relevance score, then take top
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]
    log.info(f"Selected article: [{best['score']}pts] {best['title'][:80]}")
    return best

# ── OG image scraper ──────────────────────────────────────────────────────────

def scrape_og_image(url: str) -> bytes:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LinkedInBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        img_url = None
        # Try og:image first, then twitter:image
        for attr in [("property", "og:image"), ("name", "twitter:image")]:
            tag = soup.find("meta", {attr[0]: attr[1]})
            if tag and tag.get("content"):
                img_url = tag["content"]
                break

        if not img_url:
            log.warning("No OG image found for article.")
            return None

        img_r = requests.get(img_url, headers=headers, timeout=10)
        if img_r.ok and img_r.headers.get("content-type", "").startswith("image/"):
            log.info(f"Got OG image: {img_url[:80]} ({len(img_r.content)//1024}KB)")
            return img_r.content, img_r.headers.get("content-type", "image/jpeg")
        return None

    except Exception as e:
        log.warning(f"OG image scrape failed: {e}")
        return None

# ── Gemini post generator ─────────────────────────────────────────────────────

def generate_post(article: dict) -> str:
    prompt = f"""You are writing a LinkedIn post for a tech professional audience.

Article title: {article['title']}
Article summary: {article['summary'][:800]}
Source: {article['source']}
URL: {article['url']}

Write a LinkedIn post with EXACTLY this format:
- Paragraph 1 (3-4 sentences): What happened and why it matters technically. Be specific, not generic.
- One blank line
- Paragraph 2 (2-3 sentences): Broader implications for developers/the industry. End with a question to spark engagement.
- One blank line
- A line with 4-5 relevant hashtags (e.g. #AI #OpenSource #TechNews)
- One blank line
- "Source: {article['url']}"

Rules:
- No emojis
- No "I", no first-person
- No "Excited to share" or any hype opener
- Start directly with the news
- Max 280 words total
"""

    resp = requests.post(
        "http://localhost:11434/api/generate",
        headers={"Content-Type": "application/json"},
        json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["response"].strip()
    log.info(f"Generated post ({len(text.split())} words)")
    return text

# ── LinkedIn API ──────────────────────────────────────────────────────────────

def upload_image(access_token: str, author_urn: str, img_bytes: bytes, content_type: str) -> str:
    """Upload image to LinkedIn and return asset URN."""
    # Step 1: Register upload
    reg = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers={
            "Authorization":  f"Bearer {access_token}",
            "Content-Type":   "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json={
            "registerUploadRequest": {
                "recipes":           ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner":             author_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier":       "urn:li:userGeneratedContent",
                }],
            }
        },
        timeout=15,
    )
    if not reg.ok:
        log.warning(f"Image register failed: {reg.text}")
        return None

    reg_data   = reg.json()
    upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn  = reg_data["value"]["asset"]

    # Step 2: PUT the image bytes
    put = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": content_type},
        data=img_bytes,
        timeout=30,
    )
    if put.ok or put.status_code == 201:
        log.info(f"Image uploaded: {asset_urn}")
        return asset_urn
    else:
        log.warning(f"Image upload PUT failed: {put.status_code} {put.text[:200]}")
        return None


def post_to_linkedin(access_token: str, author_urn: str, text: str, asset_urn = None) -> bool:
    author = f"urn:li:person:{author_urn}"

    body = {
        "author":         author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary":  {"text": text},
                "shareMediaCategory": "IMAGE" if asset_urn else "NONE",
                **({"media": [{
                    "status":      "READY",
                    "description": {"text": ""},
                    "media":       asset_urn,
                    "title":       {"text": ""},
                }]} if asset_urn else {}),
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization":  f"Bearer {access_token}",
            "Content-Type":   "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json=body,
        timeout=15,
    )

    if resp.ok or resp.status_code == 201:
        post_id = resp.headers.get("x-restli-id", "unknown")
        log.info(f"✓ Posted successfully. Post ID: {post_id}")
        return True
    else:
        log.error(f"Post failed: {resp.status_code} {resp.text}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info(f"LinkedIn News Bot — {datetime.now():%Y-%m-%d %H:%M:%S IST}")

    tokens      = load_tokens()
    tokens      = refresh_access_token(tokens)
    access_token = tokens["access_token"]
    author_sub   = tokens["sub"]  # OpenID sub = LinkedIn member ID

    posted_urls = load_posted()
    article     = fetch_best_article(posted_urls)
    if not article:
        sys.exit(1)

    post_text = generate_post(article)
    print("\n── Generated Post Preview ──────────────────────────────")
    print(post_text)
    print("────────────────────────────────────────────────────────\n")

    # Try to get OG image
    asset_urn = None
    og_result = scrape_og_image(article["url"])
    if og_result:
        img_bytes, content_type = og_result
        asset_urn = upload_image(access_token, f"urn:li:person:{author_sub}", img_bytes, content_type)

    if not asset_urn:
        log.warning("No image — posting as text-only.")

    success = post_to_linkedin(access_token, author_sub, post_text, asset_urn)

    if success:
        mark_posted(article["url"])
        log.info("Done.")
    else:
        log.error("Post failed — URL not marked as posted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
