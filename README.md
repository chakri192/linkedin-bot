# LinkedIn Tech News Bot

Automatically posts tech news to LinkedIn twice daily (8:00 AM + 1:00 PM IST) with real article images scraped from the source.

## Stack
- **News**: RSS feeds — Ars Technica, The Verge, TechCrunch, Wired, MIT Tech Review
- **Post copy**: Local LLM via Ollama (`llama3.1:8b`) — 2-paragraph format, no emojis
- **Images**: OG images scraped directly from article URLs with fallback text card generation
- **Scheduler**: macOS cron

## Prerequisites
- [Ollama](https://ollama.com) installed and running
- `llama3.1:8b` pulled: `ollama pull llama3.1:8b`
- LinkedIn Developer App with `Share on LinkedIn` + `Sign In with LinkedIn using OpenID Connect` products added

---

## Setup

### 1. Install dependencies
```zsh
pip3 install -r requirements.txt --break-system-packages
```

### 2. Create .env
```zsh
cp .env.template .env
open -e .env   # add your LinkedIn Client ID and Secret
```

### 3. One-time LinkedIn auth (browser flow)
```zsh
python3 auth.py
# Browser opens → log in → approve → tokens saved to .tokens.json
# If browser doesn't redirect, copy the URL and open in Safari
```

### 4. Test a post manually
```zsh
python3 post.py
```

### 5. Set up cron (twice daily automation)
```zsh
chmod +x cron_setup.sh && ./cron_setup.sh
crontab -l  # verify
```

---

## File structure
```
linkedin-bot/
├── auth.py              # One-time OAuth flow
├── post.py              # Main bot
├── check_token.py       # Token expiry checker — runs daily via cron
├── requirements.txt
├── cron_setup.sh        # Installs cron jobs (8 AM + 1 PM IST + daily token check)
├── .env.template        # Copy to .env and fill in credentials
├── .env                 # Your secrets — never commit
├── .tokens.json         # LinkedIn tokens — never commit (auto-created)
├── .posted_urls.json    # Dedup tracker — never commit (auto-created)
├── .gitignore
└── logs/                # Daily log files + cron.log
```

---

## Error handling

### Image scraping
| Failure | Handling |
|---|---|
| Site returns 403 | Retries with 3 different User-Agents |
| Relative image URL | Fixed automatically |
| SVG or WebP format | Rejected — generates fallback card |
| Image over 4MB | Rejected — generates fallback card |
| Image too small (placeholder) | Rejected via dimension check |
| All scrape attempts fail | Generates local text card via Pillow |

### LLM (Ollama)
| Failure | Handling |
|---|---|
| Ollama not running | Exits with clear message: run `ollama serve` |
| Timeout | Retries 3x with backoff |
| Empty response | Retries 3x |

### LinkedIn API
| Failure | Handling |
|---|---|
| 401 Unauthorized | Exits with message to re-run `python3 auth.py` |
| 422 Asset not ready | Waits 5s and retries up to 3x |
| 429 Rate limited | Waits `retry-after` header duration |
| 5xx Server error | Retries 3x with backoff |

### Data integrity
| Failure | Handling |
|---|---|
| `.tokens.json` corrupted | Exits with message to re-run `python3 auth.py` |
| `.posted_urls.json` corrupted | Resets file automatically and continues |
| RSS feed malformed or down | Skips feed, continues with others |
| Article missing title or URL | Skipped silently |
| Missing `.env` variable | Exits with clear message naming the missing key |

---

## Token expiry
LinkedIn access tokens last ~60 days. `check_token.py` runs daily at 8 AM and sends a macOS notification:

| Days remaining | Severity | Action |
|---|---|---|
| 7 days | [WARNING] | Run `python3 auth.py` soon |
| 1 day | [CRITICAL] | Run `python3 auth.py` today |
| 0 days | [EXPIRED] | Posts are failing — run immediately |

Check manually at any time:
```zsh
python3 check_token.py
```

---

## Monitoring
```zsh
tail -f logs/cron.log          # live cron output
cat logs/$(date +%Y-%m-%d).log # today's log
```

## Remove cron jobs
```zsh
crontab -l | grep -v "linkedin-bot" | crontab -
```
