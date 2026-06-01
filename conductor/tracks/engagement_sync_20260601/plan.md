# Implementation Plan: Engagement Sync (Pure Static Bake)

## Phase 1: High-Performance Sync (Backend)
- [x] Task: Create `tests/test_engagement_sync.py` with batch mocks (YouTube/Supabase)
- [x] Task: Implement `get_youtube_stats_batch(video_ids)` in `publisher.py`
- [x] Task: Implement `sync_engagement_stats(db_client)` with batching logic
- [~] Task: Integrate `sync_engagement_stats` into `main.py` (Step 0)
- [ ] Task: Conductor - User Manual Verification 'Phase 1: High-Performance Sync' (Protocol in workflow.md)

## Phase 2: Telemetry Bake (Automation)
- [ ] Task: Update `sync_config.py` to calculate total station aggregates (Plays/Likes/Count)
- [ ] Task: Update `sync_config.py` to fetch up to 1000 episodes for the archive
- [ ] Task: Verify the baked `config.json` contains valid telemetry root fields
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Telemetry Bake' (Protocol in workflow.md)

## Phase 3: CRT Dashboard (Frontend)
- [ ] Task: Update `app.js` to read and display telemetry from the baked `config.json`
- [ ] Task: Update the episode card template in `app.js` with glowing counters
- [ ] Task: Refactor `style.css` with alphabetized, high-fidelity CRT styling for new metrics
- [ ] Task: Conductor - User Manual Verification 'Phase 3: CRT Dashboard' (Protocol in workflow.md)
