# LinkedIn Tech News Bot

Automatically posts tech news to LinkedIn twice daily (8:00 AM + 1:00 PM IST) with real article images scraped from the source.

## Stack
- **News**: RSS feeds — Ars Technica, The Verge, TechCrunch, Wired, MIT Tech Review
- **Post copy**: Local LLM via Ollama (`llama3.1:8b`) — 2-paragraph format, no emojis
- **Images**: OG images scraped directly from article URLs (no AI generation)
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
├── requirements.txt
├── cron_setup.sh        # Installs cron jobs (8 AM + 1 PM IST)
├── .env.template        # Copy to .env and fill in credentials
├── .env                 # Your secrets — never commit
├── .tokens.json         # LinkedIn tokens — never commit (auto-created)
├── .posted_urls.json    # Dedup tracker — never commit (auto-created)
├── .gitignore
└── logs/                # Daily log files + cron.log
```

---

## Monitoring
```zsh
tail -f logs/cron.log          # live cron output
cat logs/$(date +%Y-%m-%d).log # today's log
```

## Token expiry
LinkedIn access tokens last ~60 days. Re-run when posts start failing:
```zsh
python3 auth.py
```

## Remove cron jobs
```zsh
crontab -l | grep -v "linkedin-bot" | crontab -
```

