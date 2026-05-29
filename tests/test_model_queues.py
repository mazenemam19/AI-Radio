import unittest
import os
import sys

# Ensure we can import ai_client
sys.path.append(os.getcwd())

class TestModelQueues(unittest.TestCase):
    def test_queues_defined(self):
        from ai_client import PROD_WRITER_QUEUE, TEST_WRITER_QUEUE
        
        self.assertIn("llama-3.3-70b-versatile", PROD_WRITER_QUEUE)
        self.assertIn("gemini-3.5-flash", PROD_WRITER_QUEUE)
        self.assertEqual(len(PROD_WRITER_QUEUE), 6)
        
        self.assertEqual(len(TEST_WRITER_QUEUE), 5)
        self.assertIn("gemini-3.1-flash-lite", TEST_WRITER_QUEUE)

if __name__ == "__main__":
    unittest.main()
