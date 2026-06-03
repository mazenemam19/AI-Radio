#!/usr/bin/env python3
"""
tests/test_rebranding_style.py
Verifies the rebranding design tokens in style.css.
"""

import unittest
from pathlib import Path

class TestRebrandingStyle(unittest.TestCase):
    def setUp(self):
        self.css_path = Path("style.css")
        self.css_content = self.css_path.read_text(encoding="utf-8")

    def test_design_tokens(self):
        """Should contain the new 'Echo Deep' color palette."""
        tokens = {
            "--primary": "#1E293B",
            "--secondary": "#334155",
            "--accent": "#10B981",
            "--text-hi": "#0F172A",
            "--bg": "#F8FAFC"
        }
        for token, value in tokens.items():
            with self.subTest(token=token):
                self.assertIn(f"{token}: {value}", self.css_content, f"Missing or incorrect design token: {token}")

    def test_typography(self):
        """Should use 'Casual Tech' typography."""
        self.assertIn("Space Grotesk", self.css_content, "Missing Space Grotesk heading font")
        self.assertIn("Inter", self.css_content, "Missing Inter body font")

if __name__ == "__main__":
    unittest.main()
