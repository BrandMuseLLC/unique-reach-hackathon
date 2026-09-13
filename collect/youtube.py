"""Quota-bounded, resumable YouTube Data API v3 collection into a local SQLite checkpoint.

Only public channel, video and top-level comment metadata is read. Commenter channel IDs are
salted and hashed before storage; the salt and database stay in the ignored data/ directory and
are never published. Built aggregates (see aggregate.py) contain membership counts only.

YouTube API Services terms limit retention of API data: refresh or delete local collection
databases within 30 days.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

API = "https://www.googleapis.com/youtube/v3/"
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}
DISABLED_REASONS = {"commentsDisabled", "forbidden"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY, handle TEXT, title TEXT NOT NULL, topic TEXT NOT NULL,
    subscribers INTEGER, uploads TEXT, status TEXT NOT NULL DEFAULT 'resolved', country TEXT);
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, title TEXT, description TEXT,
    published_at TEXT, views INTEGER, comment_count INTEGER, duration TEXT, audio_language TEXT,
    status TEXT NOT NULL DEFAULT 'pending', next_page_token TEXT, collected INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS authors (
    channel_id TEXT NOT NULL, author_key TEXT NOT NULL, comments INTEGER NOT NULL,
    PRIMARY KEY (channel_id, author_key));
CREATE TABLE IF NOT EXISTS video_authors (
    video_id TEXT NOT NULL, author_key TEXT NOT NULL, PRIMARY KEY (video_id, author_key));
CREATE TABLE IF NOT EXISTS failures (subject TEXT PRIMARY KEY, reason TEXT NOT NULL);
"""


class QuotaExhausted(RuntimeError):
    pass


class ApiError(RuntimeError):
    def __init__(self, status: int, reason: str):
        super().__init__("YouTube API HTTP %d (%s)" % (status, reason or "unknown"))
        self.status = status
        self.reason = reason


def urllib_transport(url: str) -> tuple[int, dict]:
    try:
        with urlopen(url, timeout=30) as response:  # nosec B310 - fixed https API host
            return response.status, json.load(response)
    except HTTPError as exc:
        try:
            return exc.code, json.load(exc)
        except ValueError:
            return exc.code, {}


@dataclass
class Client:
    """Rotates API keys on quota errors and counts units. Keys and URLs are never logged."""

    keys: list[str]
    transport: Callable[[str], tuple[int, dict]] = urllib_transport
    sleep: Callable[[float], None] = time.sleep
    units: dict[int, int] = field(default_factory=dict)
    key_index: int = 0

    def __post_init__(self):
        self.keys = [k.strip() for k in self.keys if k.strip()]
        if not self.keys:
            raise ValueError("Set YOUTUBE_API_KEYS (comma-separated) to collect.")

    def get(self, resource: str, **params) -> dict:
        attempts = 0
        while True:
            if self.key_index >= len(self.keys):
                raise QuotaExhausted("All API keys hit their quota; resume after the Pacific-midnight reset.")
            query = urlencode({**params, "key": self.keys[self.key_index]})
            try:
                status, body = self.transport(API + resource + "?" + query)
            except (URLError, TimeoutError, OSError):
                status, body = 599, {}
            self.units[self.key_index] = self.units.get(self.key_index, 0) + 1
            if status == 200:
                return body
            errors = (body.get("error") or {}).get("errors") or [{}]
            reason = errors[0].get("reason", "")
            if status == 403 and reason in QUOTA_REASONS:
                self.key_index += 1
                continue
            if status >= 500 and attempts < 3:
                attempts += 1
                self.sleep(2 ** attempts)
                continue
            raise ApiError(status, reason)


def connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    for table, column in (("channels", "country"), ("videos", "audio_language")):  # databases from earlier runs
        if column not in {r[1] for r in db.execute("PRAGMA table_info(%s)" % table)}:
            db.execute("ALTER TABLE %s ADD COLUMN %s TEXT" % (table, column))
    if db.execute("SELECT v FROM meta WHERE k='salt'").fetchone() is None:
        db.execute("INSERT INTO meta VALUES ('salt', ?)", (secrets.token_hex(32),))
        db.commit()
    return db


def author_key(db: sqlite3.Connection, author_channel_id: str) -> str:
    salt = db.execute("SELECT v FROM meta WHERE k='salt'").fetchone()[0]
    return hashlib.sha256((salt + author_channel_id).encode()).hexdigest()[:32]


def read_seeds(path: str) -> list[tuple[str, str]]:
    """CSV lines of `@handle_or_UCid,topic`. Blank lines and # comments are ignored."""
    seeds = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 2 or not all(parts):
                raise ValueError("Seed lines must be `@handle,Topic`: %r" % line)
            seeds.append((parts[0], parts[1]))
    return seeds


def resolve_channels(db: sqlite3.Connection, client: Client, seeds: list[tuple[str, str]]) -> dict:
    resolved, failed = 0, []
    for ident, topic in seeds:
        params = {"part": "snippet,statistics,contentDetails"}
        if re.fullmatch(r"UC[\w-]{22}", ident):
            params["id"] = ident
        else:
            params["forHandle"] = ident if ident.startswith("@") else "@" + ident
        items = client.get("channels", **params).get("items") or []
        if not items:
            failed.append(ident)
            db.execute("INSERT OR REPLACE INTO failures VALUES (?, 'channel_not_found')", ("seed:" + ident,))
            continue
        item = items[0]
        stats = item.get("statistics", {})
        subscribers = None if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0))
        db.execute(
            "INSERT INTO channels (channel_id, handle, title, topic, subscribers, uploads, country) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(channel_id) DO UPDATE SET handle=excluded.handle, title=excluded.title, topic=excluded.topic, "
            "subscribers=excluded.subscribers, uploads=excluded.uploads, country=excluded.country",
            (item["id"], item["snippet"].get("customUrl") or (ident if ident.startswith("@") else None),
             item["snippet"]["title"], topic, subscribers,
             item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"), item["snippet"].get("country")))
        resolved += 1
    db.commit()
    return {"resolved": resolved, "not_found": failed}


def list_videos(db: sqlite3.Connection, client: Client, per_channel: int = 10) -> int:
    added = 0
    for channel in db.execute("SELECT channel_id, uploads FROM channels WHERE status='resolved'").fetchall():
        if not channel["uploads"]:
            db.execute("UPDATE channels SET status='no_uploads' WHERE channel_id=?", (channel["channel_id"],))
            continue
        try:
            items = client.get("playlistItems", part="contentDetails", playlistId=channel["uploads"],
                               maxResults=min(per_channel, 50)).get("items") or []
        except ApiError as exc:
            db.execute("UPDATE channels SET status=? WHERE channel_id=?", ("uploads_" + (exc.reason or str(exc.status)), channel["channel_id"]))
            continue
        ids = [i["contentDetails"]["videoId"] for i in items][:per_channel]
        if ids:
            details = client.get("videos", part="snippet,statistics,contentDetails", id=",".join(ids)).get("items") or []
            for v in details:
                stats = v.get("statistics", {})
                db.execute(
                    "INSERT OR IGNORE INTO videos (video_id, channel_id, title, description, published_at, views, comment_count, duration, status, audio_language) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (v["id"], channel["channel_id"], v["snippet"].get("title"), v["snippet"].get("description"),
                     v["snippet"].get("publishedAt"), int(stats.get("viewCount", 0)),
                     int(stats["commentCount"]) if "commentCount" in stats else None,
                     v.get("contentDetails", {}).get("duration"),
                     "pending" if "commentCount" in stats else "comments_hidden",
                     v["snippet"].get("defaultAudioLanguage") or v["snippet"].get("defaultLanguage")))
                added += 1
        db.execute("UPDATE channels SET status='videos_listed' WHERE channel_id=?", (channel["channel_id"],))
        db.commit()
    return added


def collect_comments(db: sqlite3.Connection, client: Client, max_per_video: int = 500) -> dict:
    """Page top-level comments per video. The page token is committed after every page, so a restart resumes."""
    done = disabled = 0
    for video in db.execute("SELECT * FROM videos WHERE status='pending' ORDER BY channel_id, published_at DESC").fetchall():
        token, collected = video["next_page_token"], video["collected"]
        channel_id = video["channel_id"]
        while collected < max_per_video:
            params = {"part": "snippet", "videoId": video["video_id"], "maxResults": 100, "order": "time", "textFormat": "plainText"}
            if token:
                params["pageToken"] = token
            try:
                body = client.get("commentThreads", **params)
            except ApiError as exc:
                if exc.status == 403 and exc.reason in DISABLED_REASONS or exc.status == 404:
                    db.execute("UPDATE videos SET status='comments_disabled' WHERE video_id=?", (video["video_id"],))
                    db.commit()
                    disabled += 1
                    break
                raise
            for thread in body.get("items") or []:
                snippet = thread["snippet"]["topLevelComment"]["snippet"]
                author = (snippet.get("authorChannelId") or {}).get("value")
                if not author or author == channel_id:
                    continue  # anonymous rows and the creator's own comments are not audience evidence
                key = author_key(db, author)
                db.execute(
                    "INSERT INTO authors VALUES (?,?,1) ON CONFLICT(channel_id, author_key) DO UPDATE SET comments=comments+1",
                    (channel_id, key))
                db.execute("INSERT OR IGNORE INTO video_authors VALUES (?,?)", (video["video_id"], key))
                collected += 1
            token = body.get("nextPageToken")
            finished = not token or collected >= max_per_video
            # Token, count and completion commit together, so a restart never mistakes a finished video for a fresh one.
            db.execute("UPDATE videos SET next_page_token=?, collected=?, status=? WHERE video_id=?",
                       (token, collected, "done" if finished else "pending", video["video_id"]))
            db.commit()
            if finished:
                done += 1
                break
    return {"videos_done": done, "comments_disabled": disabled}
