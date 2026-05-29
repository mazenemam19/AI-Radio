import unittest
import os
import sys

# Ensure we can import ai_client
sys.path.append(os.getcwd())

class TestModelQueues(unittest.TestCase):
    def test_queues_defined(self):
        from ai_client import PROD_WRITER_QUEUE, TEST_WRITER_QUEUE
        
        self.assertEqual(PROD_WRITER_QUEUE, ["llama-3.3-70b-versatile", "mistral-large-latest"])
        self.assertEqual(TEST_WRITER_QUEUE, ["gemini-3.5-flash", "gemini-3.1-flash-lite"])

if __name__ == "__main__":
    unittest.main()
