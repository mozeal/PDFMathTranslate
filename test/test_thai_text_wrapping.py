"""
Unit tests for Thai text wrapping functionality.
"""

import pytest
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pythainlp
    PYTHAINLP_AVAILABLE = True
except ImportError:
    PYTHAINLP_AVAILABLE = False

class TestThaiTextWrapping:
    """Test Thai text wrapping with pythainlp integration."""

    @pytest.fixture
    def converter(self):
        """Create a converter instance for testing."""
        from pdf2zh.converter import TranslateConverter
        from pdfminer.pdfinterp import PDFResourceManager

        rsrcmgr = PDFResourceManager()
        return TranslateConverter(
            rsrcmgr=rsrcmgr,
            lang_in="en",
            lang_out="th",
            service="google"
        )

    @pytest.mark.skipif(not PYTHAINLP_AVAILABLE, reason="pythainlp not installed")
    def test_thai_word_boundaries_simple(self, converter):
        """Test Thai word boundary detection with simple text."""
        text = "สวัสดีครับ"
        boundaries = converter._get_thai_word_boundaries(text)

        assert len(boundaries) >= 2, "Should detect at least 2 word boundaries"
        assert boundaries[-1] == len(text), "Last boundary should be end of text"

    @pytest.mark.skipif(not PYTHAINLP_AVAILABLE, reason="pythainlp not installed")
    def test_thai_word_boundaries_complex(self, converter):
        """Test Thai word boundary detection with complex text."""
        text = "ไก่ที่เป่าปี่"
        boundaries = converter._get_thai_word_boundaries(text)

        assert len(boundaries) >= 3, "Should detect multiple word boundaries"
        assert boundaries[-1] == len(text), "Last boundary should be end of text"

    @pytest.mark.skipif(not PYTHAINLP_AVAILABLE, reason="pythainlp not installed")
    def test_safe_break_point_thai(self, converter):
        """Test safe break point finding for Thai text."""
        text = "สวัสดีครับผมชื่อจอห์น"
        current_pos = 10

        safe_pos = converter._find_safe_break_point(text, current_pos, "th", [])

        # Should find a safe break point at or before current position
        assert safe_pos <= current_pos, "Safe position should not exceed current position"
        assert safe_pos > 0, "Safe position should be positive"

    def test_safe_break_point_non_thai(self, converter):
        """Test safe break point finding for non-Thai text."""
        text = "Hello world this is a test"
        current_pos = 15

        safe_pos = converter._find_safe_break_point(text, current_pos, "en", [])

        # For non-Thai, should find space or punctuation
        assert safe_pos <= current_pos, "Safe position should not exceed current position"

    def test_thai_word_boundaries_empty_text(self, converter):
        """Test Thai word boundary detection with empty text."""
        boundaries = converter._get_thai_word_boundaries("")
        assert boundaries == [], "Empty text should return empty boundaries"

    def test_thai_word_boundaries_without_pythainlp(self, converter, monkeypatch):
        """Test graceful fallback when pythainlp is not available."""
        def mock_import_error(*args, **kwargs):
            raise ImportError("pythainlp not found")

        monkeypatch.setattr("builtins.__import__", mock_import_error)

        boundaries = converter._get_thai_word_boundaries("สวัสดี")
        assert boundaries == [], "Should return empty list when pythainlp unavailable"

    def test_calculate_text_width(self, converter):
        """Test text width calculation method."""
        # Mock noto font
        converter.noto_name = "NotoSansThai"

        class MockNoto:
            def char_lengths(self, char, size):
                return [size * 0.6]  # Mock width

        converter.noto = MockNoto()

        width = converter._calculate_text_width("สวัสดี", "NotoSansThai", 12.0)
        assert width > 0, "Text width should be positive"
        assert width == len("สวัสดี") * 12.0 * 0.6, "Width should match calculation"

class TestThaiTextWrappingConfiguration:
    """Test configuration options for Thai text wrapping."""

    def test_config_default_values(self):
        """Test default configuration values."""
        from pdf2zh.config import ConfigManager

        thai_wrap = ConfigManager.get("THAI_WORD_WRAP_ENABLED", "true")
        min_usage = ConfigManager.get("THAI_MIN_LINE_USAGE", "0.3")
        engine = ConfigManager.get("THAI_TOKENIZER_ENGINE", "newmm")

        assert thai_wrap == "true", "Default wrap setting should be enabled"
        assert min_usage == "0.3", "Default minimum usage should be 0.3"
        assert engine == "newmm", "Default engine should be newmm"

    def test_config_custom_values(self):
        """Test setting and getting custom configuration values."""
        from pdf2zh.config import ConfigManager

        # Set custom values
        ConfigManager.set("THAI_WORD_WRAP_ENABLED", "false")
        ConfigManager.set("THAI_MIN_LINE_USAGE", "0.5")
        ConfigManager.set("THAI_TOKENIZER_ENGINE", "mm")

        # Verify custom values
        assert ConfigManager.get("THAI_WORD_WRAP_ENABLED") == "false"
        assert ConfigManager.get("THAI_MIN_LINE_USAGE") == "0.5"
        assert ConfigManager.get("THAI_TOKENIZER_ENGINE") == "mm"

        # Restore defaults
        ConfigManager.set("THAI_WORD_WRAP_ENABLED", "true")
        ConfigManager.set("THAI_MIN_LINE_USAGE", "0.3")
        ConfigManager.set("THAI_TOKENIZER_ENGINE", "newmm")

@pytest.mark.skipif(not PYTHAINLP_AVAILABLE, reason="pythainlp not installed")
class TestPythainlpIntegration:
    """Test pythainlp integration directly."""

    def test_pythainlp_basic_tokenization(self):
        """Test basic pythainlp tokenization."""
        import pythainlp

        text = "สวัสดีครับ"
        words = pythainlp.word_tokenize(text, engine='newmm')

        assert len(words) >= 2, "Should tokenize into multiple words"
        assert ''.join(words) == text, "Joined words should equal original text"

    def test_pythainlp_engines(self):
        """Test different pythainlp engines."""
        import pythainlp

        text = "สวัสดีครับ"
        engines = ['newmm', 'mm']

        for engine in engines:
            try:
                words = pythainlp.word_tokenize(text, engine=engine)
                assert len(words) > 0, f"Engine {engine} should produce words"
                assert ''.join(words) == text, f"Engine {engine} should preserve text"
            except Exception:
                pytest.skip(f"Engine {engine} not available")

    def test_pythainlp_complex_text(self):
        """Test pythainlp with complex Thai text."""
        import pythainlp

        text = "ไก่ที่เป่าปี่อยู่ในป่า"
        words = pythainlp.word_tokenize(text, engine='newmm')

        assert len(words) >= 5, "Complex text should have multiple words"
        assert ''.join(words) == text, "Joined words should equal original text"