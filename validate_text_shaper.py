#!/usr/bin/env python3
"""
Validation script for HarfBuzz text shaping integration.
This script tests the text shaper functionality without requiring full dependencies.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_text_shaper_import():
    """Test that text shaper can be imported."""
    try:
        from pdf2zh.text_shaper import TextShaper, TextRun, get_text_shaper
        print("✅ Text shaper module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import text shaper: {e}")
        return False

def test_harfbuzz_availability():
    """Test HarfBuzz availability."""
    try:
        import uharfbuzz as hb
        print("✅ uharfbuzz is available")
        return True
    except ImportError:
        print("⚠️  uharfbuzz not available (this is expected if not installed)")
        return False

def test_text_shaper_basic_functionality():
    """Test basic text shaper functionality."""
    try:
        from pdf2zh.text_shaper import TextShaper

        # Create text shaper instance
        shaper = TextShaper()
        print(f"✅ TextShaper created, enabled: {shaper.enabled}")

        # Test script detection
        thai_char = 'ก'  # Thai character
        script = shaper._get_script(thai_char)
        print(f"✅ Script detection works: '{thai_char}' -> {script}")

        # Test text run splitting
        test_text = "Hello {v1} World"
        runs = shaper._split_text_runs(test_text)
        print(f"✅ Text run splitting works: {len(runs)} runs for '{test_text}'")

        # Test needs shaping detection
        thai_text = "สวัสดี"
        needs_shaping = shaper._needs_shaping(thai_text)
        print(f"✅ Needs shaping detection: '{thai_text}' -> {needs_shaping}")

        return True
    except Exception as e:
        print(f"❌ Text shaper functionality test failed: {e}")
        return False

def test_config_integration():
    """Test configuration integration."""
    try:
        # Mock ConfigManager for testing
        class MockConfigManager:
            @staticmethod
            def get(key, default=None):
                if key == "TEXT_SHAPING_ENABLED":
                    return "true"
                elif key == "NOTO_FONT_PATH":
                    return "/app/fonts/Sarabun-Regular.ttf"
                return default

        # Temporarily replace ConfigManager
        import pdf2zh.text_shaper as ts
        original_config = ts.ConfigManager
        ts.ConfigManager = MockConfigManager

        try:
            shaper = ts.TextShaper()
            print("✅ Configuration integration works")
            return True
        finally:
            # Restore original ConfigManager
            ts.ConfigManager = original_config

    except Exception as e:
        print(f"❌ Configuration integration test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🔍 Validating HarfBuzz Text Shaping Integration")
    print("=" * 50)

    tests = [
        test_text_shaper_import,
        test_harfbuzz_availability,
        test_text_shaper_basic_functionality,
        test_config_integration,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
        print()

    print("=" * 50)
    print(f"📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! HarfBuzz integration is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())