> [!CAUTION]
> All of the code in this repository was created with AI.

# Reddit to Telegram Media Notifier

A **Dockerized Reddit bot** that monitors a subreddit for posts with a specific flair and sends notifications via Apprise. Designed for reliability, persistence, and easy deployment.

---

## Prerequisites

Before you start, make sure you have the following ready:

### 1. Reddit API

1. Create a Reddit account (if you don’t have one).
2. Go to [Reddit Apps](https://www.reddit.com/prefs/apps) and create a **new app**:

   * Name: anything you like (e.g., `Reddit Media Notifier`)
   * Type: **script**
   * Redirect URI: `http://localhost:8080` (can be anything for scripts)
3. Note down the **Client ID** (under the app name) and **Client Secret**.
4. These two values (`REDDIT_CLIENT_ID` & `REDDIT_CLIENT_SECRET`) will go into your `.env` file.

### 2. Telegram Bot

* Create a bot using [BotFather](https://t.me/BotFather).
* Save the **bot token**; you’ll need it for Apprise.

### 3. Telegram Channel

* Create a channel where the bot will send notifications.
* Make sure the bot is an **administrator** of that channel (required to post messages).

### 4. Channel ID

* To get the Telegram channel ID:

  1. Forward any message from the channel to [@jsondumpbot](https://t.me/jsondumpbot).
  2. Look for the `"chat":{"id":-100xxxx}` value.
  3. Use this numeric ID (including the `-100` prefix) in your Apprise URL.

### 5. Apprise URL

* Format for Telegram:

  ```
  tgram://<bot-token>/<channel-id>
  ```
* Example:

  ```
  tgram://123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/-1009876543210
  ```

> \[!IMPORTANT]
> Make sure the bot is **added to the channel and has permission to post messages**, otherwise notifications will fail.

---

Wenn du willst, kann ich direkt die **ganze README mit den Reddit-Prerequisites integriert** fertig zusammenstellen, sodass alles sauber sortiert ist. Willst du, dass ich das mache?


## Quick Start

Deploy the bot quickly:

```bash
# 1. Fork or clone the repository
git clone https://github.com/red-to-tel/red-to-tel.git
cd red-to-tel

# 2. Create .env file (update credentials)
cp .env.example .env
nano .env  # edit with Reddit & Apprise credentials

# 3. Create "posts" folder
mkdir -p posts

# 4. Start the Docker container
docker compose up -d --build

# 5. Check logs (optional)
docker logs -f red-to-tel
```

After editing code or dependencies, rebuild with:

```bash
docker compose up -d --build --force-recreate
```

---

## Features

* Monitors a specified subreddit for posts with a configurable flair keyword (default: `media`).
* Sends notifications through Apprise (Telegram, Discord, email, etc.).
* Tracks processed posts to avoid duplicates.
* JSON-based state persistence for safety and transparency.
* Crash-resilient and reboot-safe using Docker and autosave.
* Configurable intervals and parameters via environment variables.
* Thread-safe autosave and retry logic for notifications.
* Easy deployment and updates with Docker Compose.

---

## How the Python Script Works

1. **Reddit Connection:** Fetches newest posts using [praw](https://praw.readthedocs.io/) and filters by flair keyword.
2. **Notifications:** Sends Markdown-formatted messages to Apprise-supported services, with retry logic.
3. **State Persistence:** Tracks processed posts in `posts/processed_posts.json`. Autosaves at a configurable interval.
4. **Thread-Safe Autosave:** Background thread writes state safely without interrupting main processing.
5. **Error Handling & Retry:** Uses [tenacity](https://tenacity.readthedocs.io/) for robust retry logic on both Reddit API and notifications.
6. **Docker-Friendly:** Fully configurable via `.env`. Auto-restarts using Docker restart policies.

---

## Environment Variables

Create a `.env` file in the project root:

```env
ENVIRONMENT=prod            # prod or stage

# Reddit API Credentials
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent   # Example: script:reddit-notifier:v1.0 (by u/yourusername)

# Apprise Notification URLs
APPRISE_URL_PROD=tgram://bot-id/channel-id
APPRISE_URL_STAGE=tgram://bot-id/channel-id   # Optional staging URL
# Full list of supported services: https://github.com/caronc/apprise#supported-notifications

# Subreddit Configuration
SUBREDDIT_NAME=soccer       # Subreddit to monitor
FLAIR_KEYWORD=media         # Flair text keyword to filter posts

# Persistence
PROCESSED_POSTS_FILE=/app/posts/processed_posts.json

# Timing / Intervals
POLL_INTERVAL=5             # Seconds between Reddit checks (default: 5)
AUTOSAVE_INTERVAL=60        # Seconds between saving state (default: 60)
```

* **`PROCESSED_POSTS_FILE`** → JSON file where the bot stores processed post IDs. Persistent across restarts.
* **`POLL_INTERVAL`** → Controls how often the bot polls Reddit for new posts.
* **`AUTOSAVE_INTERVAL`** → Controls how often the bot writes state to disk.
* **`FLAIR_KEYWORD`** → The flair text to filter posts by (case-insensitive).
* **`REDDIT_USER_AGENT`** → Must be unique and descriptive per Reddit’s API rules.

---

## How Notifications Look in Telegram

Once the bot posts a new media post to your channel, it will appear like this:

```
Club Brugge 4 - [1] Monaco - Ansu Fati  90+2'
https://streamin.one/v/3e772388
[View on Reddit](https://redd.it/1nkgin4)
```


* The **title** appears on the first line.
* The **media URL** is clickable.
* The **View on Reddit** link lets you jump directly to the Reddit post.

> [!NOTE]
> Long titles are displayed fully. No emojis or extra formatting; everything is kept clean and readable.

---

## Persistent State

* Stored in `posts/processed_posts.json`.
* Docker volume ensures persistence across restarts:

```yaml
volumes:
  - ./posts:/app/posts
```

> [!IMPORTANT]
> Make sure the left side of the volume path (`./posts`) points to the `posts/` folder in your cloned repo.

* Autosaves every `AUTOSAVE_INTERVAL` seconds, plus graceful save on shutdown.

---

## Updating Python Packages

The bot’s Python dependencies are pinned in `requirements.txt` to ensure stability and reproducible builds. When you want to update packages:

### 1. Check outdated packages

Enter the running container and list outdated packages:

```bash
docker exec -it red-to-tel bash
pip list --outdated
```

This will show all packages with available updates, including `praw`, `apprise`, and their dependencies.

### 2. Update main packages

* Identify the **main packages** you want to update (e.g., `praw`, `apprise`, `tenacity`).
* Update `requirements.txt` with the new version range, for example:

```text
praw>=7.9.0,<8.0
apprise==1.9.4
tenacity>=9.1.2,<10.0
python-dotenv==1.1.1
# keep other sub-dependencies pinned as before
```
> [!TIP]
> Use `==` for strict pinning, or `>=,<` ranges if you want controlled flexibility.
Only update main packages; sub-dependencies are updated automatically if compatible.

### 3. Rebuild the container

```bash
docker compose up -d --build --force-recreate
```

### 4. Test the bot

* Check logs to ensure it’s working correctly:

```bash
docker logs -f red-to-tel
```

* Verify that notifications are still sent as expected.

> [!WARNING]
> Always test package updates in a **staging or local environment** before deploying to production.

---

## Troubleshooting

* **No notifications:** Verify `.env` credentials and Apprise URL.
* **Processed posts not updating:** Check volume mapping and permissions.
* **Bot hammering Reddit API:** Increase `POLL_INTERVAL` in `.env`.
* **Rate-limited by Reddit:** Increase `POLL_INTERVAL` or reduce the number of posts fetched in `reddit.py`.
* **Container not restarting on reboot:** Ensure `restart: unless-stopped` is set in `docker-compose.yml`.

---

## Contributing

* Fork the repository
* Create a feature branch
* Submit a pull request

---

## License

MIT License. See [LICENSE](LICENSE) for details.
