# Specification: Engagement Sync (Pure Static Bake)

## Overview
Implement a high-performance synchronization system for YouTube metrics (Plays/Likes) using 100% Python and static delivery. This architecture prioritizes stability, security (Zero-Secret Frontend), and infinite scalability.

## Functional Requirements

### 1. High-Performance Batch Sync (Python)
- Implement `sync_engagement_stats(db_client)` to fetch stats in batches of **50 IDs per request** (YouTube API limit).
- Update the `plays` and `likes` columns for the last **1000 episodes** in the Supabase database.
- Integrate this routine into `main.py` (Step 0) and provide a standalone `sync_engagement.py`.

### 2. Static Telemetry Bake (Python)
- Refactor `sync_config.py` to:
    1. Fetch up to **1000 episodes** (unlimited archive support).
    2. Calculate station-wide aggregates: `total_plays`, `total_likes`, and `episode_count`.
    3. Embed these aggregates into the root of `config.json`.

### 3. CRT Dashboard Integration (JS/HTML/CSS)
- **Status Bar:** Update `app.js` to read the global telemetry from `config.json` and display it in the CRT status bar.
- **Episode Cards:** Update the card template to display "▶ Views" and "❤ Likes" counters using data from `config.json`.
- **Styling:** Implement glowing, alphabetized CSS for the new telemetry elements.

## Non-Functional Requirements
- **Stability:** 100% static delivery ensures the dashboard never breaks due to API "cold starts" or database connection limits.
- **Performance:** Batching reduces the sync time from minutes to <3 seconds.
- **Security:** YouTube/Supabase keys remain server-side only.

## Acceptance Criteria
- Running `main.py` refreshes all engagement stats in the database.
- The dashboard displays the full history (up to 1000 episodes).
- The CRT status bar correctly reflects the total station engagement.
