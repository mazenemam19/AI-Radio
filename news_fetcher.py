"""
news_fetcher.py — AI Radio Echo
Fetches headlines from RSS feeds (BBC, Reuters, Guardian) and HackerNews API.

Source limits:   5 items per RSS feed, 10 items from HackerNews.
Deduplication:   exact headline match OR ≥3 significant keyword overlaps.
Significant word: length > 4 AND not in the 20-word stop list.
feedparser:      always via requests (10s timeout) — never feedparser.parse(url).
HTMLStripper:    defined once at module level, not inside any loop.
"""

import random
import re
from html.parser import HTMLParser
from typing import Optional

import feedparser
import requests

# ── HTML Stripper (module-level singleton pattern) ────────────────────────────

class HTMLStripper(HTMLParser):
    """Lightweight HTML-to-text converter."""

    def __init__(self) -> None:
        super().__init__()
        self._fed: list[str] = []

    def handle_data(self, d: str) -> None:
        self._fed.append(d)

    def get_data(self) -> str:
        return " ".join(self._fed).strip()

    def reset(self) -> None:
        super().reset()
        self._fed = []


# Module-level instance — never instantiated inside a loop.
_html_stripper = HTMLStripper()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    _html_stripper.reset()
    _html_stripper.feed(text)
    return _html_stripper.get_data()


# ── Stop list (exactly 20 words per spec) ─────────────────────────────────────

_STOP_WORDS: frozenset[str] = frozenset({
    "about", "after", "also", "been", "from",
    "have", "into", "more", "over", "says",
    "that", "their", "this", "they", "were",
    "when", "which", "will", "with", "would",
})


def _significant_words(text: str) -> set[str]:
    """Words with len > 4 that are not in the stop list."""
    return {
        w for w in re.findall(r"[a-zA-Z]+", text.lower())
        if len(w) > 4 and w not in _STOP_WORDS
    }


# ── Deduplication ─────────────────────────────────────────────────────────────

def _is_duplicate(headline: str, history: list[str]) -> bool:
    """
    Returns True if the headline should be skipped.

    Criteria (per spec):
      - Exact headline match (case-insensitive, stripped).
      - 3 or more significant keyword overlaps. (2 is too aggressive — spec note.)
    """
    norm = headline.strip().lower()
    new_sig = _significant_words(headline)

    for prev in history:
        if prev.strip().lower() == norm:
            return True
        if len(new_sig & _significant_words(prev)) >= 3:
            return True
    return False


# ── RSS helper ────────────────────────────────────────────────────────────────

def _fetch_rss(
    url: str,
    source_name: str,
    limit: int,
    history: list[str],
) -> tuple[list[dict], bool]:
    """
    Fetch up to `limit` unique items from an RSS feed.

    Uses requests (10s timeout) + feedparser.parse(content).
    Never calls feedparser.parse(url) directly.

    Returns (items, success_flag).
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as exc:
        print(f"[NEWS] RSS source '{source_name}' failed: {exc}")
        return [], False

    items: list[dict] = []
    # Overfetch to allow deduplication headroom
    for entry in feed.entries[: limit * 4]:
        headline = _strip_html(getattr(entry, "title", "")).strip()
        if not headline:
            continue
        if _is_duplicate(headline, history):
            continue

        items.append({
            "headline": headline,
            "source": source_name,
            "url": getattr(entry, "link", ""),
            "summary": _strip_html(getattr(entry, "summary", ""))[:500],
        })
        history.append(headline)

        if len(items) >= limit:
            break

    return items, True


# ── HackerNews ────────────────────────────────────────────────────────────────

def _fetch_hackernews(limit: int, history: list[str]) -> tuple[list[dict], bool]:
    """
    Fetch top stories from the HackerNews Firebase API.
    Fetches story IDs first, then individual story details.

    Returns (items, success_flag).
    """
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10,
        )
        resp.raise_for_status()
        story_ids: list[int] = resp.json()[: limit * 4]
    except Exception as exc:
        print(f"[NEWS] HackerNews top-stories list failed: {exc}")
        return [], False

    items: list[dict] = []
    for story_id in story_ids:
        if len(items) >= limit:
            break
        try:
            item_resp = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                timeout=10,
            )
            item_resp.raise_for_status()
            item = item_resp.json() or {}
        except Exception:
            continue

        headline = (item.get("title") or "").strip()
        if not headline:
            continue
        if _is_duplicate(headline, history):
            continue

        items.append({
            "headline": headline,
            "source": "HackerNews",
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
            "summary": (
                f"HackerNews — {item.get('score', 0)} points, "
                f"{item.get('descendants', 0)} comments"
            ),
        })
        history.append(headline)

    return items, True


# ── Source registry ───────────────────────────────────────────────────────────

_RSS_SOURCES: list[tuple[str, str]] = [
    ("BBC",      "http://feeds.bbci.co.uk/news/rss.xml"),
    ("Guardian", "https://www.theguardian.com/world/rss"),
    ("Ars",      "https://feeds.arstechnica.com/arstechnica/index"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("NASA",     "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
]


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_news(history: list[str]) -> list[dict]:
    """
    Fetch and deduplicate news from all sources.

    Args:
        history: List of previously-seen headlines (modified in-place during
                 this call to cross-deduplicate between sources).

    Returns:
        List of dicts with keys: headline, source, url, summary.
        Empty list if all sources fail; caller treats this as "no news today".

    Behaviour on partial failures (per spec):
        - If ALL sources fail: print a warning, return [].
        - If SOME sources fail: print which ones failed, continue with successes.
    """
    all_items: list[dict] = []
    failed_sources: list[str] = []
    total_sources = len(_RSS_SOURCES) + 1  # RSS + HackerNews

    for name, url in _RSS_SOURCES:
        items, success = _fetch_rss(url, name, limit=5, history=history)
        if not success:
            failed_sources.append(name)
        else:
            all_items.extend(items)
            print(f"[NEWS] {name}: {len(items)} item(s) fetched.")

    hn_items, hn_success = _fetch_hackernews(limit=10, history=history)
    if not hn_success:
        failed_sources.append("HackerNews")
    else:
        all_items.extend(hn_items)
        print(f"[NEWS] HackerNews: {len(hn_items)} item(s) fetched.")

    if failed_sources:
        if len(failed_sources) == total_sources:
            print(
                "[NEWS] WARNING: All news sources failed. "
                "Returning empty list."
            )
        else:
            print(f"[NEWS] Some sources failed: {', '.join(failed_sources)}")

    # Randomise the order of items so the 'primary' source varies in DB metadata
    random.shuffle(all_items)
    return all_items
