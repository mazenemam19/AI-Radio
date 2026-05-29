import unittest
import os
import json
import sqlite3
import sys

# Ensure we can import modules from the parent directory
sys.path.append(os.getcwd())

from db_client import SupabaseDBClient

class TestFieldValidation(unittest.TestCase):
    def setUp(self):
        # Use a temporary test database for SQLite testing
        self.db_path = "test_ai_radio.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Patch the client to use our test db path
        self.client = SupabaseDBClient(env='local')
        self.client.db_path = self.db_path
        self.client._init_sqlite()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_insert_post_handles_missing_fields(self):
        """Verify that insert_post populates defaults for missing optional fields."""
        # Minimum required data from main.py flow
        headline = "Test Headline"
        source = "Test Source"
        topic_tags = []
        my_take = "" # Empty
        post_text = "Social post"
        audio_script = "[]"
        audio_url = "local://test.mp3"
        
        # Attempt to insert with empty/missing fields
        res = self.client.insert_post(
            headline=headline,
            source=source,
            topic_tags=topic_tags,
            my_take=my_take,
            post_text=post_text,
            audio_script=audio_script,
            audio_url=audio_url,
            original_headline=None # Missing
        )
        
        self.assertIsNotNone(res)
        self.assertEqual(res["headline"], headline)
        # Check if original_headline was defaulted to headline
        self.assertEqual(res["original_headline"], headline)
        
        # Check database directly
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT original_headline, my_take FROM memory_log WHERE id = ?", (res["id"],))
        row = cursor.fetchone()
        conn.close()
        
        self.assertEqual(row[0], headline)
        # my_take was empty string, should it have a default if it's empty?
        # Requirement says "ensure original_headline and my_take are never empty"
        self.assertNotEqual(row[1], "", "my_take should not be empty")

if __name__ == "__main__":
    unittest.main()
