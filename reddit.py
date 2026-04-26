#!/usr/bin/env python3
import os
import sys
import json
import time
import signal
import logging
import threading
import traceback
from datetime import datetime, timedelta, timezone

import praw
import apprise
from dotenv import load_dotenv
from tenacity import retry, wait_fixed, stop_after_attempt

# --------------------------------------------------
# Environment & configuration
# --------------------------------------------------
load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "prod").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logger.info(f"Environment: {ENVIRONMENT}")
logger.info(f"Log level: {LOG_LEVEL}")

# --------------------------------------------------
# Required environment variables
# --------------------------------------------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

if ENVIRONMENT == "prod":
    APPRISE_URL = os.getenv("APPRISE_URL_PROD")
elif ENVIRONMENT == "stage":
    APPRISE_URL = os.getenv("APPRISE_URL_STAGE")
else:
    logger.critical("Unknown ENVIRONMENT value")
    sys.exit(1)

SUBREDDIT_NAME = os.getenv("SUBREDDIT_NAME", "soccer")

FLAIR_KEYWORDS = [
    k.strip().lower()
    for k in os.getenv("FLAIR_KEYWORD", "media").split(",")
    if k.strip()
]

PROCESSED_POSTS_FILE = os.getenv(
    "PROCESSED_POSTS_FILE", "/app/posts/processed_posts.json"
)

AUTOSAVE_INTERVAL = int(os.getenv("AUTOSAVE_INTERVAL", 60))
STATE_RETENTION_DAYS = int(os.getenv("STATE_RETENTION_DAYS", 30))

os.makedirs(os.path.dirname(PROCESSED_POSTS_FILE), exist_ok=True)

if not all(
    [
        REDDIT_CLIENT_ID,
        REDDIT_CLIENT_SECRET,
        REDDIT_USER_AGENT,
        APPRISE_URL,
    ]
):
    logger.critical("Missing required environment variables")
    sys.exit(1)

# --------------------------------------------------
# Reddit & Apprise initialization
# --------------------------------------------------
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)

subreddit = reddit.subreddit(SUBREDDIT_NAME)

apobj = apprise.Apprise()
apobj.add(APPRISE_URL)

# --------------------------------------------------
# State handling
# --------------------------------------------------
lock = threading.Lock()
processed_posts: dict[str, str] = {}

def load_state() -> dict:
    if not os.path.exists(PROCESSED_POSTS_FILE):
        return {}
    try:
        with open(PROCESSED_POSTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
    return {}

def save_state():
    with lock:
        try:
            with open(PROCESSED_POSTS_FILE, "w", encoding="utf-8") as f:
                json.dump(processed_posts, f)
            logger.debug("State saved")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

def prune_state():
    if STATE_RETENTION_DAYS <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=STATE_RETENTION_DAYS)
    with lock:
        before = len(processed_posts)
        for post_id, ts in list(processed_posts.items()):
            try:
                post_dt = datetime.fromisoformat(ts)

                # If timestamp is naive, assume UTC
                if post_dt.tzinfo is None:
                    post_dt = post_dt.replace(tzinfo=timezone.utc)

                if post_dt < cutoff:
                    processed_posts.pop(post_id, None)
            except Exception:
                processed_posts.pop(post_id, None)
        after = len(processed_posts)
        if before != after:
            logger.info(f"Pruned {before - after} old processed posts")

# --------------------------------------------------
# Autosave thread
# --------------------------------------------------
def autosave_loop():
    while True:
        time.sleep(AUTOSAVE_INTERVAL)
        prune_state()
        save_state()

autosave_thread = threading.Thread(target=autosave_loop, daemon=True)
autosave_thread.start()

# --------------------------------------------------
# Graceful shutdown
# --------------------------------------------------
def shutdown_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down")
    save_state()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# --------------------------------------------------
# Notification
# --------------------------------------------------
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
        body_format=apprise.NotifyFormat.MARKDOWN,
    )

    logger.info(f"Notification sent: {submission.id}")

# --------------------------------------------------
# Helper
# --------------------------------------------------
def flair_matches(submission) -> bool:
    flair = (submission.link_flair_text or "").lower()
    return any(k in flair for k in FLAIR_KEYWORDS)

# --------------------------------------------------
# Main loop (STREAM-BASED)
# --------------------------------------------------
def main():
    global processed_posts

    processed_posts = load_state()
    logger.info(f"Loaded {len(processed_posts)} processed posts")

    try:
        for submission in subreddit.stream.submissions(skip_existing=True):
            try:
                with lock:
                    if submission.id in processed_posts:
                        continue

                if not flair_matches(submission):
                    continue

                send_notification(submission)

                with lock:
                    processed_posts[submission.id] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                logger.error(f"Error processing submission: {e}")
                logger.error(traceback.format_exc())
                time.sleep(2)

    finally:
        logger.info("Exiting main loop")
        save_state()

# --------------------------------------------------
# Entry point
# --------------------------------------------------
if __name__ == "__main__":
    main()
