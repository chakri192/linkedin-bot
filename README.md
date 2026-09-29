# linkedin-bot

Posts one tech news article to LinkedIn every morning. It picks a story from tech news feeds, writes the post with a local AI model (Ollama), adds the article's image, and publishes at a random time between 8:00 and 8:55.

## Requirements

- macOS with Python 3
- [Ollama](https://ollama.com) with `ollama pull llama3.1:8b`
- A LinkedIn developer app with **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect** enabled, and `http://localhost:8080/callback` added as a redirect URL

## Setup

```sh
git clone https://github.com/chakri192/linkedin-bot.git
cd linkedin-bot
pip3 install -r requirements.txt
cp .env.template .env        # add your LinkedIn client ID and secret
```

Log in to LinkedIn once:

```sh
python3 auth.py
```

Check what it would post, without publishing anything:

```sh
python3 post.py --dry-run
```

Post once by hand to check the LinkedIn side works. **This publishes a real post:**

```sh
python3 post.py
```

Then schedule it:

```sh
./setup_launchd.sh
```

## How posts are made

1. It reads the latest articles from Ars Technica, The Verge, TechCrunch, Wired, and MIT Technology Review.
2. It picks the article that mentions the most topics you care about (AI, open source, chips, and so on) and hasn't been posted before.
3. It writes a short post: what happened, why it matters, a question, hashtags, and the source link.
4. It uses the article's preview image, or makes a simple title card if there isn't one.
5. It publishes to your profile.

## Settings

| What | Where |
|---|---|
| News feeds | `RSS_FEEDS` in `post.py` |
| Preferred topics | `PREFERRED_TOPICS` in `post.py` |
| Post style and length | The prompt in `generate_post()` in `post.py` |
| AI model | `"model"` in `generate_post()` |
| Posting time | `WINDOWS` in `scheduler.py` |

To post twice a day, add a second time window:

```python
WINDOWS = [
    ("morning",   8,  0,  8, 55),
    ("evening",  18,  0, 18, 55),
]
```

## Things to know

- **LinkedIn logins expire after about 60 days.** You'll get a Mac notification 7 days before, and again on the last day. Run `python3 auth.py` to log in again.
- If your Mac is asleep at the chosen time, it posts when the Mac wakes up, as long as that's before 11:55. Later than that, the day is skipped.
- If a post fails, it isn't retried until the next day. Check the log.
- Don't use `cron_setup.sh`; it's the old setup, replaced by `setup_launchd.sh`.

## Checking on it

```sh
launchctl list | grep linkedinbot    # is it scheduled?
python3 scheduler.py                 # today's post time
python3 check_token.py               # days until you need to log in again
tail -f logs/$(date +%F).log         # today's log
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Ollama is not running` | Start Ollama and check `ollama list` shows `llama3.1:8b` |
| `401` error | Your login expired. Run `python3 auth.py` |
| Error about `redirect_uri` during login | Add `http://localhost:8080/callback` to your LinkedIn app's redirect URLs |
| Nothing posted today | Check the log; the Mac may have been asleep all morning |
| Posts have no image | The log says why the image was skipped |

## Contributors

| | |
|---|---|
| [chakri192](https://github.com/chakri192) | Author |
| [aider](https://github.com/Aider-AI/aider) | AI pair programmer |
