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

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
SUBREDDIT_NAME = os.getenv("SUBREDDIT_NAME", "soccer")
PROCESSED_POSTS_FILE = os.getenv("PROCESSED_POSTS_FILE", "/app/posts/processed_posts.json")
AUTOSAVE_INTERVAL = int(os.getenv("AUTOSAVE_INTERVAL", 60))
STATE_RETENTION_DAYS = int(os.getenv("STATE_RETENTION_DAYS", 30))
HEARTBEAT_FILE = "/tmp/heartbeat"

if ENVIRONMENT == "prod":
    APPRISE_URL = os.getenv("APPRISE_URL_PROD")
elif ENVIRONMENT == "stage":
    APPRISE_URL = os.getenv("APPRISE_URL_STAGE")
else:
    logger.critical("Unknown ENVIRONMENT value")
    sys.exit(1)

FLAIR_KEYWORDS = [
    k.strip().lower()
    for k in os.getenv("FLAIR_KEYWORD", "media").split(",")
    if k.strip()
]

if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, APPRISE_URL]):
    logger.critical("Missing required environment variables")
    sys.exit(1)

# --------------------------------------------------
# Bot Class
# --------------------------------------------------
class RedditBot:
    def __init__(self):
        self.processed_posts = self.load_state()
        self.lock = threading.Lock()
        self.apobj = apprise.Apprise()
        self.apobj.add(APPRISE_URL)
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        self.subreddit = self.reddit.subreddit(SUBREDDIT_NAME)
        self.running = True
        
        # The "Watchdog" mechanism
        self.last_stream_activity = time.time()

    def load_state(self) -> dict:
        """Loads processed posts from JSON. Handles empty or corrupt files gracefully."""
        if not os.path.exists(PROCESSED_POSTS_FILE):
            return {}
        
        if os.path.getsize(PROCESSED_POSTS_FILE) == 0:
            logger.info("State file is empty. Initializing new state.")
            return {}

        try:
            with open(PROCESSED_POSTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            logger.warning("State file corrupted or invalid JSON. Starting with fresh state.")
            return {}
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return {}

    def save_state(self):
        with self.lock:
            try:
                with open(PROCESSED_POSTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.processed_posts, f)
                logger.debug("State saved")
            except Exception as e:
                logger.error(f"Failed to save state: {e}")

    def prune_state(self):
        if STATE_RETENTION_DAYS <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=STATE_RETENTION_DAYS)
        with self.lock:
            before = len(self.processed_posts)
            for post_id, ts in list(self.processed_posts.items()):
                try:
                    post_dt = datetime.fromisoformat(ts)
                    if post_dt.tzinfo is None:
                        post_dt = post_dt.replace(tzinfo=timezone.utc)
                    if post_dt < cutoff:
                        self.processed_posts.pop(post_id, None)
                except Exception:
                    self.processed_posts.pop(post_id, None)
            after = len(self.processed_posts)
            if before != after:
                logger.info(f"Pruned {before - after} old processed posts")

    def heartbeat_loop(self):
        while self.running:
            now = time.time()
            if now - self.last_stream_activity < 300:
                try:
                    with open(HEARTBEAT_FILE, "w") as f:
                        f.write(str(now))
                except Exception as e:
                    logger.error(f"Heartbeat write error: {e}")
            else:
                logger.warning("Heartbeat: Stream appears to be stalled (no activity for 5m)")
            time.sleep(30)

    def flair_matches(self, submission) -> bool:
        flair = (submission.link_flair_text or "").lower()
        return any(k in flair for k in FLAIR_KEYWORDS)

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def send_notification(self, submission):
        body = (
            f"{submission.title}\n"
            f"{submission.url}\n"
            f"[View on Reddit]({submission.shortlink})"
        )
        self.apobj.notify(
            body=body,
            notify_type=apprise.NotifyType.INFO,
            body_format=apprise.NotifyFormat.MARKDOWN,
        )
        logger.info(f"Notification sent: {submission.id}")

    def autosave_loop(self):
        while self.running:
            time.sleep(AUTOSAVE_INTERVAL)
            self.prune_state()
            self.save_state()

    def perform_catchup(self):
        """
        Searches for up to 5 posts that match the flair.
        Scans up to 500 recent posts to find them.
        """
        if self.processed_posts:
            logger.info("Existing state found. Skipping initial catch-up.")
            return

        logger.info(f"No history found. Searching for up to 5 posts with flair '{FLAIR_KEYWORDS}'...")
        
        found_count = 0
        target_count = 5
        search_limit = 500  # Much higher limit to ensure we find the matches

        try:
            # Use a generator to scan up to 500 posts
            count_scanned = 0
            for submission in self.subreddit.new(limit=search_limit):
                count_scanned += 1
                self.last_stream_activity = time.time()
                
                if not self.flair_matches(submission):
                    continue

                with self.lock:
                    if submission.id in self.processed_posts:
                        continue

                # Send notification
                self.send_notification(submission)

                with self.lock:
                    self.processed_posts[submission.id] = datetime.now(timezone.utc).isoformat()
                
                found_count += 1
                
                # Stop if we found our target
                if found_count >= target_count:
                    break
            
            if found_count < target_count:
                logger.info(f"Catch-up finished: Only found {found_count} matching posts after scanning {count_scanned} submissions.")
            else:
                logger.info(f"Catch-up complete. Found {found_count} matching posts.")
                
        except Exception as e:
            logger.error(f"Error during catch-up: {e}")
            logger.error(traceback.format_exc())

    def run_stream(self):
        logger.info(f"Connecting to r/{SUBREDDIT_NAME} stream...")
        self.last_stream_activity = time.time()
        
        for submission in self.subreddit.stream.submissions(skip_existing=True):
            self.last_stream_activity = time.time()
            
            try:
                if not self.flair_matches(submission):
                    continue

                with self.lock:
                    if submission.id in self.processed_posts:
                        continue

                self.send_notification(submission)

                with self.lock:
                    self.processed_posts[submission.id] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                logger.error(f"Error in stream processing: {e}")
                logger.error(traceback.format_exc())
                raise

    def start(self):
        threading.Thread(target=self.autosave_loop, daemon=True).start()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        
        def handle_exit(sig, frame):
            logger.info("Shutdown signal received.")
            self.running = False
            self.save_state()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)

        self.perform_catchup()

        while self.running:
            try:
                self.run_stream()
            except Exception as e:
                logger.error(f"Stream loop crashed: {e}. Restarting in 10s...")
                time.sleep(10)

if __name__ == "__main__":
    bot = RedditBot()
    bot.start()

