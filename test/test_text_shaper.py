"""
Tests for the text shaper module.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from pdf2zh.text_shaper import TextShaper, TextRun, get_text_shaper


class TestTextShaper(unittest.TestCase):
    """Test cases for TextShaper class."""

    def setUp(self):
        """Set up test fixtures."""
        self.text_shaper = TextShaper()

    def test_get_script(self):
        """Test script detection for different characters."""
        # Test Latin characters
        self.assertEqual(self.text_shaper._get_script("a"), "Latin")
        self.assertEqual(self.text_shaper._get_script("A"), "Latin")

        # Test Thai characters
        thai_char = "ก"  # Thai letter ko kai
        script = self.text_shaper._get_script(thai_char)
        self.assertIn("Thai", script)

        # Test Arabic characters
        arabic_char = "ا"  # Arabic letter alef
        script = self.text_shaper._get_script(arabic_char)
        self.assertIn("Arabic", script)

    def test_needs_shaping(self):
        """Test complex script detection."""
        # Disable text shaper to test logic
        with patch.object(self.text_shaper, "enabled", False):
            self.assertFalse(self.text_shaper._needs_shaping("Hello World"))

        # Enable text shaper
        with patch.object(self.text_shaper, "enabled", True):
            # Test Latin text (should not need shaping)
            self.assertFalse(self.text_shaper._needs_shaping("Hello World"))

            # Test Thai text (should need shaping)
            thai_text = "สวัสดีครับ"  # "Hello" in Thai
            # Mock the _get_script method to return Thai
            with patch.object(self.text_shaper, "_get_script", return_value="Thai"):
                self.assertTrue(self.text_shaper._needs_shaping(thai_text))

    def test_split_text_runs(self):
        """Test text run splitting."""
        # Test mixed script text
        mixed_text = "Hello สวัสดี World"

        # Mock script detection
        def mock_get_script(char):
            if ord(char) >= 0x0E00 and ord(char) <= 0x0E7F:  # Thai range
                return "Thai"
            return "Latin"

        with patch.object(self.text_shaper, "_get_script", side_effect=mock_get_script):
            runs = self.text_shaper._split_text_runs(mixed_text)

            # Should have multiple runs for different scripts
            self.assertGreater(len(runs), 1)

            # Check that each run has the expected properties
            for run in runs:
                self.assertIsInstance(run, TextRun)
                self.assertIsInstance(run.text, str)
                self.assertIsInstance(run.start_index, int)
                self.assertIsInstance(run.end_index, int)
                self.assertIsInstance(run.script, str)

    def test_split_text_runs_with_formulas(self):
        """Test text run splitting with formula markers."""
        text_with_formula = "Hello {v1} World"
        runs = self.text_shaper._split_text_runs(text_with_formula)

        # Should have runs for text and formula
        formula_runs = [run for run in runs if run.script == "Formula"]
        self.assertEqual(len(formula_runs), 1)
        self.assertEqual(formula_runs[0].text, "{v1}")

    @patch("pdf2zh.text_shaper.HARFBUZZ_AVAILABLE", True)
    def test_shape_text_without_font(self):
        """Test text shaping when font loading fails."""
        with patch.object(self.text_shaper, "_load_font", return_value=None):
            result = self.text_shaper.shape_text("สวัสดี", "/fake/font.ttf", 12.0)
            self.assertIsNone(result)

    @patch("pdf2zh.text_shaper.HARFBUZZ_AVAILABLE", False)
    def test_text_shaper_disabled_when_harfbuzz_unavailable(self):
        """Test that text shaper is disabled when HarfBuzz is not available."""
        shaper = TextShaper()
        self.assertFalse(shaper.enabled)

    def test_get_text_advance_fallback(self):
        """Test get_text_advance with fallback to None."""
        # When shaping is not needed, should return None
        result = self.text_shaper.get_text_advance("Hello", "/fake/font.ttf", 12.0)
        self.assertIsNone(result)

    @patch("pdf2zh.text_shaper.HARFBUZZ_AVAILABLE", True)
    def test_font_caching(self):
        """Test that fonts are cached properly."""
        # Create a temporary font file for testing
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as temp_font:
            temp_font.write(b"fake font data")
            temp_font_path = temp_font.name

        try:
            # Mock HarfBuzz objects
            with (
                patch("pdf2zh.text_shaper.hb.Face") as mock_face,
                patch("pdf2zh.text_shaper.hb.Font") as mock_font,
            ):

                mock_face_instance = Mock()
                mock_font_instance = Mock()
                mock_face.return_value = mock_face_instance
                mock_font.return_value = mock_font_instance

                # Load font twice
                font1 = self.text_shaper._load_font(temp_font_path, 12.0)
                font2 = self.text_shaper._load_font(temp_font_path, 12.0)

                # Should return the same cached instance
                self.assertIs(font1, font2)

                # Face should only be created once
                mock_face.assert_called_once()
        finally:
            # Clean up
            if os.path.exists(temp_font_path):
                os.unlink(temp_font_path)


class TestTextShaperIntegration(unittest.TestCase):
    """Integration tests for text shaper."""

    def test_get_text_shaper_singleton(self):
        """Test that get_text_shaper returns a singleton."""
        shaper1 = get_text_shaper()
        shaper2 = get_text_shaper()
        self.assertIs(shaper1, shaper2)

    def test_thai_text_example(self):
        """Test with real Thai text example."""
        thai_text = "สวัสดีครับ ผมชื่อ จอห์น"  # "Hello, my name is John" in Thai

        shaper = get_text_shaper()

        # Even if shaping fails, it should not raise an exception
        try:
            result = shaper.shape_text(thai_text, "/fake/font.ttf", 14.0)
            # Result might be None if font loading fails, and that's OK
            if result is not None:
                self.assertIsInstance(result.success, bool)
        except Exception as e:
            self.fail(f"Text shaping should not raise exception: {e}")

    @patch("pdf2zh.text_shaper.ConfigManager")
    def test_configuration_integration(self):
        """Test configuration integration."""
        # Test with shaping enabled
        with patch("pdf2zh.text_shaper.ConfigManager.get", return_value="true"):
            shaper = TextShaper()
            if hasattr(shaper, "enabled"):
                # Only test if HarfBuzz is available
                expected = getattr(shaper, "enabled", False)
                self.assertIsInstance(expected, bool)

        # Test with shaping disabled
        with patch("pdf2zh.text_shaper.ConfigManager.get", return_value="false"):
            shaper = TextShaper()
            if hasattr(shaper, "enabled"):
                self.assertFalse(shaper.enabled)


if __name__ == "__main__":
    unittest.main()
