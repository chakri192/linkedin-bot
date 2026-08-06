<div align="center">

<img src="docs/dawn.svg" width="840" alt="" />

# linkedin-bot

**Posts one tech story to LinkedIn each morning, at a minute it picks itself.**

Local LLM for the copy, the real article image, and no two posts at the same time on consecutive days.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3-1c1c1e?style=flat-square&logo=python&logoColor=3776AB" />
  <img alt="LLM" src="https://img.shields.io/badge/Ollama-llama3.1%3A8b-1c1c1e?style=flat-square&logo=ollama&logoColor=white" />
  <img alt="Scheduler" src="https://img.shields.io/badge/scheduler-launchd-1c1c1e?style=flat-square&logo=apple&logoColor=white" />
  <img alt="Hosted LLM" src="https://img.shields.io/badge/hosted%20LLM-not%20used-1c1c1e?style=flat-square" />
</p>

</div>

---

Five tech RSS feeds go in. One LinkedIn post comes out, once a day, somewhere between 08:00 and 08:55 — a different minute each morning, so it doesn't read as a cron job.

The copy is written by `llama3.1:8b` running locally through Ollama. The image is the article's own `og:image`. Nothing about the article, the draft, or your credentials is sent to a hosted model.

## Setup

Needs [Ollama](https://ollama.com) running with `llama3.1:8b` pulled, and a LinkedIn Developer app with both **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.

```zsh
pip3 install -r requirements.txt
cp .env.template .env      # add your client ID and secret
python3 auth.py            # browser flow, writes .tokens.json
python3 post.py            # test it end to end
./setup_launchd.sh         # scheduler + daily token check
```

> `cron_setup.sh` is the older approach — fixed 08:00 and 13:00 via `crontab`. `setup_launchd.sh` supersedes it and removes what it replaces. Use launchd; cron doesn't survive sleep, which on a laptop means missed mornings.

## How the timing works

`launchd` can't schedule "sometime random in a window", so the randomness lives one level up.

The scheduler runs every five minutes and does nothing until the clock passes a target minute. That target is drawn once per day, at random, within 08:00–08:55, and stored in `.schedule.json` alongside the date. When the date stops matching, a fresh time is drawn.

Once a slot fires successfully it's marked `posted`, so the rest of the day's runs are no-ops. If `post.py` exits non-zero the slot stays unposted — but deliberately isn't retried, because the failure modes here (expired token, Ollama down) repeat, and a retry loop would just multiply the noise.

## How a post gets made

**Fetch and rank** — Ars Technica, The Verge, TechCrunch, Wired, MIT Technology Review. Each entry scores on how many of fifteen preferred topics it matches. Anything already in `.posted_urls.json` is skipped.

**Write** — the prompt asks for a fixed shape: what happened and why it matters technically, then the broader implication ending in a question, then hashtags and the source. It forbids emoji, first person, and "Excited to share" openers. Three attempts, 90-second timeout.

**Image** — `og:image`, `twitter:image`, `og:image:secure_url`, in that order. If nothing usable comes back, a text card is generated with Pillow and the post still goes out.

**Upload and post** — LinkedIn wants the asset registered first, then the bytes `PUT` to the URL it returns, then a UGC post referencing it.

### The part that needed a guard

The `og:image` URL comes out of arbitrary third-party HTML — a crafted page could point the bot at `http://localhost:11434` or an address on your LAN, and it would dutifully fetch it. Every candidate is resolved to an IP first and rejected if private, loopback, link-local, reserved, multicast, or unspecified. Content types are limited to JPEG, PNG, and GIF.

Small function. It's the difference between a scraper and an open proxy into your own network.

## Keeping it running

LinkedIn access tokens last about 60 days and there's no way around re-authorising. `check_token.py` runs daily at 08:05 and posts a macOS notification at seven days, one day, and expired.

```zsh
launchctl list | grep linkedinbot     # both agents loaded?
python3 scheduler.py                  # what time is it firing today?
tail -f logs/$(date +%F).log          # today's run
```

| Symptom | Cause |
|---|---|
| `Ollama is not running` | `ollama serve`, and check the model is pulled |
| Stopped, no visible errors | Token expired — `python3 check_token.py` |
| Scheduler runs, nothing fires | Today's slot is already `posted` |
| `401` from LinkedIn | Token expired, or the app is missing *Share on LinkedIn* |
| Same article twice | `.posted_urls.json` was deleted — it's the only dedup record |

## Layout

```
linkedin-bot/
├── post.py             fetch · rank · write · image · upload · post
├── scheduler.py        picks a random daily minute, fires post.py once
├── auth.py             one-time OAuth flow → .tokens.json
├── check_token.py      daily expiry warning
├── setup_launchd.sh    installs both agents  ← use this
└── cron_setup.sh       superseded
```

Untracked by design: `.env`, `.tokens.json`, `.posted_urls.json`, `.schedule.json`, `logs/`.

## Tuning

| What | Where |
|---|---|
| Which feeds | `RSS_FEEDS` in `post.py` |
| What counts as interesting | `PREFERRED_TOPICS` |
| Tone, length, structure | the prompt in `generate_post()` |
| Posting window, or adding more | `WINDOWS` in `scheduler.py` — a second tuple gives you a second post |
