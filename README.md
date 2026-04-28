# Reddit to Telegram Media Notifier (Self-Healing Edition)

> [!CAUTION]
> All of the code in this repository was created with AI.

A **resilient, Dockerized Reddit bot** that monitors a subreddit for posts with a specific flair and sends notifications via **Apprise** (Telegram, Discord, email, etc.).

Designed for:
* **High reliability:** Automatically recovers from Reddit API stalls/errors.
* **Initial Catch-up:** On first run, it automatically sends the last 5 recent posts.
* **Low Reddit API usage:** Uses streaming instead of aggressive polling.
* **Crash-safe persistence:** JSON-based state management.
* **Docker-native:** Includes built-in healthchecks to prevent "zombie" containers.

---

## What This Bot Does

* Listens to a subreddit **in real time** using Reddit’s streaming API.
* **Initial Catch-up:** If the bot is starting for the first time (no history), it scans the last 5 posts and notifies you.
* Filters posts by **flair keyword(s)** (case-insensitive).
* Sends clean, Markdown-formatted notifications.
* Tracks processed posts to avoid duplicate notifications.
* **Self-Heals:** If the connection to Reddit hangs or returns errors, the bot automatically restarts the stream without needing manual intervention.

---

## Prerequisites

### 1. Reddit API
1. Create a Reddit account.
2. Go to [Reddit → Preferences → Apps](https://www.reddit.com/prefs/apps).
3. Create a **new app**:
   * **Type:** `script`
   * **Name:** `Reddit Notifier`
   * **Redirect URI:** `http://localhost:8080`
4. Save the **Client ID** and **Client Secret**.

### 2. Telegram Bot
1. Open Telegram and start **@BotFather**.
2. Create a new bot and save the **bot token**.
3. Create a Telegram channel and add your bot as an **administrator**.
4. Get the **Channel ID** using **@jsondumpbot** (ensure it includes the `-100` prefix).

### 3. Apprise URL (Telegram)
Format: `tgram://<bot-token>/<channel-id>`

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/red-to-tel/red-to-tel.git
cd red-to-tel

# 2. Setup Environment
cp .env.example .env
nano .env

# 3. Create persistent directory
mkdir -p posts

# 4. Build and Start
docker compose up -d --build
```

**To view logs:**
```bash
docker logs -f red-to-tel
```

---

## Technical Architecture (How it stays alive)

To prevent the bot from appearing "Running" while actually being "Stalled," this version implements two layers of protection:

### 1. The Python Supervisor (Watchdog)
The `reddit.py` script does not just run a single loop. It runs a **Supervisor Loop**. If the Reddit stream encounters a `500 Error` or a network timeout, the internal loop crashes, the Supervisor catches the error, waits 10 seconds, and instantly re-establishes a fresh connection.

### 2. Docker Healthchecks (Heartbeat)
The bot maintains a "Heartbeat" file (`/tmp/heartbeat`). Every time a post is processed or the stream is checked, the file is updated.
* Docker monitors this file.
* If the file is not updated for more than 30 minutes, Docker marks the container as **`unhealthy`**.
* Because `restart: unless-stopped` is enabled, Docker will automatically kill the zombie container and start a fresh one.

---

## Environment Variables

Create a `.env` file in the project root.

```env
ENVIRONMENT=prod              # prod or stage
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR

# Reddit API
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=script:reddit-notifier:v1.0 (by u/yourusername)

# Apprise
APPRISE_URL_PROD=tgram://bot-token/channel-id
APPRISE_URL_STAGE=tgram://bot-token/channel-id

# Subreddit
SUBREDDIT_NAME=soccer

# Flair filtering (comma-separated)
FLAIR_KEYWORD="Match Clips,Goal"

# Persistence
PROCESSED_POSTS_FILE=/app/posts/processed_posts.json
STATE_RETENTION_DAYS=30

# Autosave
AUTOSAVE_INTERVAL=60
```

---

## Troubleshooting

### Container Status
Run `docker ps` to check the status:
* **`Up (healthy)`**: Everything is working perfectly.
* **`Up (health: starting)`**: The bot is booting up. Wait 30-60 seconds.
* **`Up (unhealthy)`**: The bot has stalled. Docker is currently attempting to restart it. Check `docker logs red-to-tel` to see why.

### No Notifications
1. **Check Logs:** `docker logs -f red-to-tel`. Look for `Error processing submission`.
2. **Check Apprise URL:** Ensure the Telegram bot is an **Admin** in the channel.
3. **Check Flair:** Ensure the `FLAIR_KEYWORD` matches the exact text (or substring) of the Reddit flair.

### Rate Limits
If you see `429 Too Many Requests`, the bot will automatically wait and retry using the `tenacity` library. Do not manually restart the container immediately; let the retry logic work first.

