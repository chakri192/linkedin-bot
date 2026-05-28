#!/usr/bin/env python3
"""
LinkedIn Tech News Bot
- Fetches top story from RSS feeds
- Scrapes real OG image from article
- Generates 2-para post via local LLM (Ollama)
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

def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: Missing required env var: {key}. Check your .env file.")
        sys.exit(1)
    return val

CLIENT_ID     = _require_env("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = _require_env("LINKEDIN_CLIENT_SECRET")
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
        log.error("No .tokens.json found. Run python3 auth.py first.")
        sys.exit(1)
    try:
        return json.loads(TOKENS_FILE.read_text())
    except (json.JSONDecodeError, ValueError):
        log.error(".tokens.json is corrupted. Run python3 auth.py to re-authenticate.")
        sys.exit(1)


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
        try:
            return set(json.loads(POSTED_FILE.read_text()))
        except (json.JSONDecodeError, ValueError):
            log.warning(".posted_urls.json is corrupted — resetting.")
            POSTED_FILE.write_text("[]")
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
            if feed.bozo and not feed.entries:
                log.warning(f"Feed malformed or unreachable: {feed_url}")
                continue
            for entry in feed.entries[:10]:
                url = entry.get("link", "").strip()
                title = entry.get("title", "").strip()
                if not url or not title or url in posted_urls:
                    continue
                candidates.append({
                    "url":     url,
                    "title":   title,
                    "summary": BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:800],
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

# ── Image fallback generator ─────────────────────────────────────────────────

def make_fallback_image(title: str) -> tuple:
    """Generate a clean text-card PNG when OG image scraping fails."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        W, H = 1200, 630
        img = Image.new("RGB", (W, H), color=(15, 20, 40))
        draw = ImageDraw.Draw(img)

        # Border
        draw.rectangle([0, 0, W-1, H-1], outline=(60, 120, 200), width=4)

        # Source label
        draw.rectangle([40, 40, 300, 80], fill=(60, 120, 200))
        try:
            font_label = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        except Exception:
            font_label = ImageFont.load_default()
            font_title = font_label

        draw.text((50, 48), "TECH NEWS", fill=(255, 255, 255), font=font_label)

        # Title wrapping
        wrapped = textwrap.wrap(title, width=32)[:4]
        y = 160
        for line in wrapped:
            draw.text((60, y), line, fill=(240, 240, 240), font=font_title)
            y += 70

        # Bottom bar
        draw.rectangle([0, H-60, W, H], fill=(60, 120, 200))
        draw.text((50, H-45), "linkedin-bot · automated tech news", fill=(255,255,255), font=font_label)

        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        log.info("Generated fallback image card.")
        return buf.read(), "image/jpeg"
    except ImportError:
        log.warning("Pillow not installed — skipping fallback image. Run: pip3 install Pillow --break-system-packages")
        return None
    except Exception as e:
        log.warning(f"Fallback image generation failed: {e}")
        return None


def scrape_og_image(url: str, title: str = "") -> tuple:
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif"}
    MAX_SIZE_BYTES = 4 * 1024 * 1024  # 4MB — safe under LinkedIn's 5MB limit
    MIN_DIMENSION  = 400              # reject tiny placeholder images

    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Mozilla/5.0 (compatible; LinkedInBot/1.0; +http://www.linkedin.com/)",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
    ]

    for ua in USER_AGENTS:
        try:
            headers = {"User-Agent": ua}
            r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            if not r.ok:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            img_url = None

            for attr in [("property", "og:image"), ("name", "twitter:image"), ("property", "og:image:secure_url")]:
                tag = soup.find("meta", {attr[0]: attr[1]})
                if tag and tag.get("content"):
                    img_url = tag["content"].strip()
                    break

            if not img_url:
                log.warning(f"No OG image tag found with UA: {ua[:40]}")
                continue

            # Fix relative URLs
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                from urllib.parse import urlparse
                base = urlparse(url)
                img_url = f"{base.scheme}://{base.netloc}{img_url}"

            # Download image with redirect following
            img_r = requests.get(img_url, headers=headers, timeout=15, allow_redirects=True)
            if not img_r.ok:
                log.warning(f"Image download failed: {img_r.status_code} {img_url[:60]}")
                continue

            content_type = img_r.headers.get("content-type", "").split(";")[0].strip().lower()

            # Reject unsupported formats (svg, webp, etc)
            if content_type not in ALLOWED_TYPES:
                log.warning(f"Unsupported image format: {content_type} — skipping")
                continue

            # Reject oversized images
            if len(img_r.content) > MAX_SIZE_BYTES:
                log.warning(f"Image too large: {len(img_r.content)//1024}KB — skipping")
                continue

            # Reject tiny placeholder images using PIL if available
            try:
                from PIL import Image
                import io
                im = Image.open(io.BytesIO(img_r.content))
                w, h = im.size
                if w < MIN_DIMENSION or h < MIN_DIMENSION:
                    log.warning(f"Image too small ({w}x{h}) — likely a placeholder, skipping")
                    continue
                log.info(f"Image validated: {w}x{h} {content_type} {len(img_r.content)//1024}KB")
            except ImportError:
                pass  # Pillow not installed — skip dimension check
            except Exception as e:
                log.warning(f"Image validation error: {e}")
                continue

            log.info(f"Got OG image: {img_url[:80]}")
            return img_r.content, content_type

        except requests.exceptions.Timeout:
            log.warning(f"Timeout scraping image with UA: {ua[:40]}")
        except Exception as e:
            log.warning(f"OG image scrape error: {e}")

    # All user agents failed — generate fallback
    log.warning("All scrape attempts failed — generating fallback image card.")
    return make_fallback_image(title) or None

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

    for attempt in range(1, 4):
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                headers={"Content-Type": "application/json"},
                json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
                timeout=90,
            )
            resp.raise_for_status()
            text = resp.json()["response"].strip()
            if not text:
                raise ValueError("Ollama returned empty response")
            log.info(f"Generated post ({len(text.split())} words)")
            return text
        except requests.exceptions.ConnectionError:
            log.error("Ollama is not running. Start it with: ollama serve")
            sys.exit(1)
        except requests.exceptions.Timeout:
            log.warning(f"Ollama timeout on attempt {attempt}/3 — retrying...")
            time.sleep(5 * attempt)
        except Exception as e:
            log.warning(f"Ollama attempt {attempt}/3 failed: {e}")
            time.sleep(5 * attempt)
    log.error("Ollama failed after 3 attempts.")
    sys.exit(1)

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

    # Step 2: PUT the image bytes — retry up to 3 times
    for attempt in range(1, 4):
        try:
            put = requests.put(
                upload_url,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": content_type},
                data=img_bytes,
                timeout=30,
            )
            if put.ok or put.status_code == 201:
                # Wait briefly for LinkedIn to process the asset
                time.sleep(2)
                log.info(f"Image uploaded: {asset_urn}")
                return asset_urn
            elif put.status_code >= 500:
                log.warning(f"Upload attempt {attempt}/3 failed with {put.status_code} — retrying...")
                time.sleep(3 * attempt)
            else:
                log.warning(f"Image upload PUT failed: {put.status_code} {put.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            log.warning(f"Upload attempt {attempt}/3 timed out — retrying...")
            time.sleep(3 * attempt)
        except Exception as e:
            log.warning(f"Upload attempt {attempt}/3 error: {e}")
            return None
    log.warning("All upload attempts failed.")
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

    for attempt in range(1, 4):
        try:
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
                log.info(f"Posted successfully. Post ID: {post_id}")
                return True
            elif resp.status_code == 422 and asset_urn:
                # Asset not ready yet — wait and retry
                log.warning(f"Asset not ready (422) — waiting 5s before retry {attempt}/3...")
                time.sleep(5)
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("retry-after", 60))
                log.warning(f"Rate limited (429) — waiting {retry_after}s...")
                time.sleep(retry_after)
            elif resp.status_code == 401:
                log.error("LinkedIn token expired or invalid. Run python3 auth.py.")
                return False
            elif resp.status_code >= 500:
                log.warning(f"LinkedIn 5xx on attempt {attempt}/3 — retrying...")
                time.sleep(5 * attempt)
            else:
                log.error(f"Post failed: {resp.status_code} {resp.text}")
                return False
        except requests.exceptions.Timeout:
            log.warning(f"Post request timed out on attempt {attempt}/3 — retrying...")
            time.sleep(5 * attempt)
        except Exception as e:
            log.error(f"Post request error: {e}")
            return False
    log.error("All post attempts failed.")
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
    og_result = scrape_og_image(article["url"], article["title"])
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
