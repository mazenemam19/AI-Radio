#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

PROJ_ROOT = Path(__file__).parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from news_fetcher import _is_duplicate  # noqa: E402


class TestTopicBurn(unittest.TestCase):
    def test_subset_keyword_block(self):
        """Short tags in history should block headlines containing them."""
        history = ["NASA", "Ebola"]

        # Should be blocked because 'NASA' is a tag in history
        self.assertTrue(_is_duplicate("NASA Antenna Mishap Reported", history))
        self.assertTrue(_is_duplicate("New NASA Study on Ozone", history))

        # Should be blocked because 'Ebola' is a tag in history
        self.assertTrue(_is_duplicate("Ebola cases rise in Congo", history))

        # Should NOT be blocked (no overlap)
        self.assertFalse(_is_duplicate("Apple releases new iPhone", history))

    def test_standard_overlap_still_works(self):
        """Headlines with 3+ significant word overlap should still be blocked."""
        history = ["The heavy storm causes flooding in London"]
        # sig: heavy, storm, causes, flooding, London

        # 3 overlaps: heavy, storm, London
        self.assertTrue(_is_duplicate("Heavy storm hits London tonight", history))

        # 2 overlaps: storm, London
        self.assertFalse(_is_duplicate("A small storm in London", history))


if __name__ == "__main__":
    unittest.main()
