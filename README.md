# Reddit to Telegram Media Notifier

> [!CAUTION]
> All of the code in this repository was created with AI.

A **Dockerized Reddit bot** that monitors a subreddit for posts with a specific flair and sends notifications via **Apprise** (Telegram, Discord, email, etc.).

Designed for:

* low Reddit API usage
* crash-safe persistence
* clean Docker deployment
* zero duplicate notifications

---

## What This Bot Does

* Listens to a subreddit **in real time** using Reddit’s streaming API
* Filters posts by **flair keyword(s)** (case-insensitive)
* Sends clean, Markdown-formatted notifications
* Tracks processed posts to avoid duplicates
* Persists state safely across restarts
* Prunes old state automatically to avoid infinite growth

---

## Prerequisites

### 1. Reddit API

1. Create a Reddit account (if you don’t have one).
2. Go to **Reddit → Preferences → Apps**
   [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
3. Create a **new app**:

   * **Name:** anything (e.g. `Reddit Media Notifier`)
   * **Type:** `script`
   * **Redirect URI:** `http://localhost:8080` (value doesn’t matter)
4. Save:

   * **Client ID**
   * **Client Secret**

---

### 2. Telegram Bot

1. Open Telegram and start **@BotFather**
2. Create a new bot
3. Save the **bot token**

---

### 3. Telegram Channel

1. Create a Telegram channel
2. Add your bot as **administrator**
3. The bot must have permission to post messages

---

### 4. Get the Channel ID

1. Forward any message from your channel to **@jsondumpbot**
2. Look for:

```
"chat": { "id": -100xxxxxxxxxx }
```

3. Copy the full numeric ID (including `-100`)

---

### 5. Apprise URL (Telegram)

Format:

```
tgram://<bot-token>/<channel-id>
```

Example:

```
tgram://123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/-1009876543210
```

> [!IMPORTANT]
> The bot **must** be an admin in the channel, or notifications will fail.

---

## Quick Start (Docker)

```bash
# Clone the repository
git clone https://github.com/red-to-tel/red-to-tel.git
cd red-to-tel

# Create environment file
cp .env.example .env
nano .env

# Create persistent state folder
mkdir -p posts

# Build & start container
docker compose up -d --build

# View logs
docker logs -f red-to-tel
```

Rebuild after code or dependency changes:

```bash
docker compose up -d --build --force-recreate
```

---

## Features

* Real-time Reddit monitoring (no aggressive polling)
* Configurable flair keyword filtering
* Multi-keyword flair support
* Markdown notifications via Apprise
* Duplicate-safe processing
* JSON-based persistent state
* Automatic state pruning
* Graceful shutdown handling
* Docker-friendly & restart-safe

---

## How the Bot Works (Technical Overview)

1. **Reddit Stream**

   * Uses `subreddit.stream.submissions(skip_existing=True)`
   * Reacts instantly to new posts
   * Minimal Reddit API usage

2. **Filtering**

   * Post flair text is matched against one or more keywords
   * Case-insensitive substring matching

3. **Notifications**

   * Sent via Apprise with Markdown formatting
   * Retry logic for transient failures

4. **Persistence**

   * Processed post IDs stored in JSON
   * Each entry includes a timestamp
   * Autosaved on interval and shutdown

5. **State Pruning**

   * Old entries automatically removed after N days
   * Prevents infinite file growth

---

## Environment Variables

Create a `.env` file in the project root.

```env
ENVIRONMENT=prod              # prod or stage
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR

# Reddit API
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=script:reddit-notifier:v1.0 (by u/yourusername)

# Apprise
APPRISE_URL_PROD=tgram://bot-token/channel-id
APPRISE_URL_STAGE=tgram://bot-token/channel-id

# Subreddit
SUBREDDIT_NAME=soccer

# Flair filtering
FLAIR_KEYWORD="Match Clips"            # comma-separated allowed (e.g. media,goal,highlight)

# Persistence
PROCESSED_POSTS_FILE=/app/posts/processed_posts.json
STATE_RETENTION_DAYS=30        # days to keep processed posts (0 = keep forever)

# Autosave
AUTOSAVE_INTERVAL=60           # seconds
```

### Notes

* `FLAIR_KEYWORD` supports **multiple values**, comma-separated
* `STATE_RETENTION_DAYS` prevents unbounded JSON growth
* `LOG_LEVEL=DEBUG` is useful for troubleshooting

---

## Telegram Message Format

Example notification:

```
Club Brugge 4 - [1] Monaco - Ansu Fati 90+2'
https://streamin.one/v/3e772388
[View on Reddit](https://redd.it/1nkgin4)
```

* Line 1: Reddit post title
* Line 2: Media URL
* Line 3: Direct Reddit link

No emojis. No clutter. Clean and readable.

---

## Persistent State & Docker Volumes

State is stored in:

```
posts/processed_posts.json
```

Recommended Docker volume:

```yaml
volumes:
  - ./posts:/app/posts
```

This ensures:

* no duplicate notifications after restart
* safe recovery after crashes or reboots

---

## Updating Python Packages

Dependencies are pinned in `requirements.txt`.

### Check outdated packages

```bash
docker exec -it red-to-tel bash
pip list --outdated
```

### Update main dependencies only

```text
praw>=7.9.0,<8.0
apprise==1.9.4
tenacity>=9.1.2,<10.0
python-dotenv==1.1.1
```

Rebuild after updates:

```bash
docker compose up -d --build --force-recreate
```

> [!WARNING]
> Always test updates in staging before deploying to production.

---

## Troubleshooting

**No notifications**

* Verify Apprise URL
* Check bot permissions in Telegram channel

**Bot not sending after restart**

* Check volume mapping
* Verify write permissions for `posts/`

**Rate limits**

* This bot uses Reddit streaming; rate limits are rare
* If hit, restart container after cooldown

**Debugging**

* Set `LOG_LEVEL=DEBUG`
* Watch logs with `docker logs -f red-to-tel`

---

## Contributing

* Fork the repository
* Create a feature branch
* Open a pull request

---

## License

MIT License — see `LICENSE` for details.
