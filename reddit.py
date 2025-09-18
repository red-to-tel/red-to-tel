#!/usr/bin/env python3
import praw
import time
import apprise
import os
import json
import logging
import traceback
import sys
import signal
import threading
from tenacity import retry, wait_fixed, stop_after_attempt
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Environment
environment = os.getenv("ENVIRONMENT", "prod")
logger.info(f"Environment: {environment}")

# Reddit credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Apprise URL
if environment == "prod":
    APPRISE_URL = os.getenv("APPRISE_URL_PROD")
elif environment == "stage":
    APPRISE_URL = os.getenv("APPRISE_URL_STAGE")
else:
    logger.critical("Unknown environment specified")
    raise ValueError("Unknown environment specified")

# Subreddit to monitor
SUBREDDIT_NAME = os.getenv("SUBREDDIT_NAME", "soccer")

# Processed posts file
PROCESSED_POSTS_FILE = os.getenv(
    "PROCESSED_POSTS_FILE", "/app/posts/processed_posts.json"
)
os.makedirs(os.path.dirname(PROCESSED_POSTS_FILE), exist_ok=True)

# Configurable intervals
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 5))  # check every 5 seconds
AUTOSAVE_INTERVAL = int(os.getenv("AUTOSAVE_INTERVAL", 60))  # seconds
FLAIR_KEYWORD = os.getenv("FLAIR_KEYWORD", "media").lower()

# -----------------------------
# Validate required env vars
# -----------------------------
if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, APPRISE_URL]):
    logger.critical("Missing required environment variables. Exiting.")
    sys.exit(1)

# -----------------------------
# Initialize Reddit and Apprise
# -----------------------------
reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                     client_secret=REDDIT_CLIENT_SECRET,
                     user_agent=REDDIT_USER_AGENT)

apobj = apprise.Apprise()
apobj.add(APPRISE_URL)

subreddit = reddit.subreddit(SUBREDDIT_NAME)

MIN_DELAY = 2  # Delay for errors

# -----------------------------
# Load / Save processed posts
# -----------------------------
def load_processed_posts():
    if os.path.exists(PROCESSED_POSTS_FILE):
        try:
            with open(PROCESSED_POSTS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load processed posts: {e}")
    return set()

def save_processed_posts(processed_posts):
    try:
        with open(PROCESSED_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_posts), f)
        logger.debug("Processed posts saved.")
    except Exception as e:
        logger.error(f"Failed to save processed posts: {e}")

# -----------------------------
# Fetch new posts
# -----------------------------
@retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
def fetch_new_posts(processed_posts):
    try:
        new_posts = [
            s for s in subreddit.new(limit=20)
            if s.id not in processed_posts
            and FLAIR_KEYWORD in (s.link_flair_text or "").lower()
        ]
        if new_posts:
            logger.info(f"Found {len(new_posts)} new post(s).")
        return new_posts
    except Exception as e:
        logger.error(f"Error fetching new posts: {e}")
        raise

# -----------------------------
# Send notification (clean spacing for Telegram)
# -----------------------------
@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def send_notification(submission):
    body = (
        f"{submission.title}\n"
        f"{submission.url}\n"
        f"[View on Reddit]({submission.shortlink})"
    )

    apobj.notify(
        body=body,
        notify_type=apprise.NotifyType.INFO,
        body_format=apprise.NotifyFormat.MARKDOWN
    )
    logger.info(f"Notification sent for: {submission.title}")

# -----------------------------
# Globals and autosave
# -----------------------------
processed_posts = None
lock = threading.Lock()

def autosave_loop():
    global processed_posts
    while True:
        if processed_posts is not None:
            with lock:
                save_processed_posts(processed_posts)
        time.sleep(AUTOSAVE_INTERVAL)

autosave_thread = threading.Thread(target=autosave_loop, daemon=True)
autosave_thread.start()

# -----------------------------
# Graceful shutdown
# -----------------------------
def handle_shutdown(signum, frame):
    logger.info(f"Received shutdown signal ({signum}). Saving state and exiting...")
    global processed_posts
    if processed_posts is not None:
        with lock:
            save_processed_posts(processed_posts)
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# -----------------------------
# Main loop
# -----------------------------
def main():
    global processed_posts
    processed_posts = load_processed_posts()

    try:
        while True:
            logger.debug("Polling subreddit for new posts...")
            try:
                media_posts = fetch_new_posts(processed_posts)
                for submission in reversed(media_posts):
                    send_notification(submission)
                    with lock:
                        processed_posts.add(submission.id)
                    time.sleep(1)

            except Exception as e:
                logger.error(f"An error occurred while fetching/sending: {e}")
                logger.error(traceback.format_exc())
                time.sleep(MIN_DELAY)

            time.sleep(POLL_INTERVAL)

    finally:
        logger.info("Exiting main loop — saving processed posts.")
        if processed_posts is not None:
            with lock:
                save_processed_posts(processed_posts)

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    main()
