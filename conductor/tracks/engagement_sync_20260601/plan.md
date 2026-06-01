# Implementation Plan: Engagement Sync (Pure Static Bake)

## Phase 1: High-Performance Sync (Backend) [checkpoint: a0b5c0d]
- [x] Task: Create `tests/test_engagement_sync.py` with batch mocks (YouTube/Supabase) 2230430
- [x] Task: Implement `get_youtube_stats_batch(video_ids)` in `publisher.py` 2230430
- [x] Task: Implement `sync_engagement_stats(db_client)` with batching logic 2230430
- [x] Task: Integrate `sync_engagement_stats` into `main.py` (Step 0) 2230430
- [x] Task: Conductor - User Manual Verification 'Phase 1: High-Performance Sync' (Protocol in workflow.md) 2230430


## Phase 2: Telemetry Bake (Automation) [checkpoint: bde4579]
- [x] Task: Update `sync_config.py` to calculate total station aggregates (Plays/Likes/Count) 5773773
- [x] Task: Update `sync_config.py` to fetch up to 1000 episodes for the archive 5773773
- [x] Task: Verify the baked `config.json` contains valid telemetry root fields 5773773
- [x] Task: Conductor - User Manual Verification 'Phase 2: Telemetry Bake' (Protocol in workflow.md) 5773773

## Phase 3: CRT Dashboard (Frontend)
- [x] Task: Update `app.js` to read and display telemetry from the baked `config.json` 46a3913
- [x] Task: Update the episode card template in `app.js` with glowing counters 46a3913
- [x] Task: Refactor `style.css` with alphabetized, high-fidelity CRT styling for new metrics 46a3913
- [x] Task: Conductor - User Manual Verification 'Phase 3: CRT Dashboard' (Protocol in workflow.md) 46a3913
