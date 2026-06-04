#!/usr/bin/env python3
"""
tests/test_engagement_sync.py — AI Radio Echo
Verifies the YouTube batch statistics fetching and database synchronization logic.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# ── Import Fix ────────────────────────────────────────────────────────────────
PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

# Completely mock discovery and auth to avoid environment issues
mock_discovery = MagicMock()
mock_creds = MagicMock()
mock_auth = MagicMock()

sys.modules["googleapiclient"] = MagicMock()
sys.modules["googleapiclient.discovery"] = mock_discovery
sys.modules["google"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.credentials"] = mock_creds
sys.modules["google.auth"] = MagicMock()
sys.modules["google.auth.transport"] = MagicMock()
sys.modules["google.auth.transport.requests"] = mock_auth

import publisher # noqa: E402

class TestEngagementSync(unittest.TestCase):
    @patch("os.environ.get")
    def test_get_youtube_stats_batch_success(self, mock_env):
        """Should return a mapping of video_id to stats for a batch of IDs."""
        # 1. Setup environment mocks
        mock_env.side_effect = lambda k, default="": {
            "YOUTUBE_CLIENT_ID": "fake_id",
            "YOUTUBE_CLIENT_SECRET": "fake_secret",
            "YOUTUBE_REFRESH_TOKEN": "fake_token"
        }.get(k, default)

        # 2. Setup YouTube API mocks
        mock_youtube = MagicMock()
        mock_discovery.build.return_value = mock_youtube
        
        mock_response = {
            "items": [
                {"id": "v1", "statistics": {"viewCount": "100", "likeCount": "10"}},
                {"id": "v2", "statistics": {"viewCount": "200", "likeCount": "20"}}
            ]
        }
        mock_youtube.videos().list().execute.return_value = mock_response
        
        # 3. Execute
        results = publisher.get_youtube_stats_batch(["v1", "v2"])
        
        # 4. Verify
        self.assertEqual(results["v1"]["plays"], 100)
        self.assertEqual(results["v1"]["likes"], 10)
        self.assertEqual(results["v2"]["plays"], 200)
        self.assertEqual(results["v2"]["likes"], 20)

    @patch("publisher.get_youtube_stats_batch")
    def test_sync_engagement_stats_batch_logic(self, mock_get_batch):
        """Should handle batching of IDs and multiple database updates, including id=0."""
        mock_db = MagicMock()
        
        # 1. Mock 60 episodes
        mock_episodes = []
        for i in range(60):
            mock_episodes.append({
                "id": i,
                "video_url": f"https://www.youtube.com/watch?v=v{i}"
            })
        mock_db.fetch_recent_memory.return_value = mock_episodes
        
        # 2. Mock batch results
        def side_effect(ids):
            return {vid: {"plays": 100, "likes": 5} for vid in ids}
        mock_get_batch.side_effect = side_effect
        
        # 3. Execute
        publisher.sync_engagement_stats(mock_db)
        
        # 4. Verify
        self.assertEqual(mock_get_batch.call_count, 2)
        self.assertEqual(mock_db.update_post_stats.call_count, 60)

    @patch("sqlite3.connect")
    def test_db_client_update_stats_sqlite(self, mock_connect):
        """Should execute correct SQL for SQLite update."""
        from db_client import DBClient
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        db = DBClient("local")
        db.update_post_stats(123, 500, 50)
        
        mock_conn.execute.assert_called_with(
            "UPDATE memory_log SET plays = ?, likes = ? WHERE id = ?",
            (500, 50, 123)
        )

if __name__ == "__main__":
    unittest.main()
