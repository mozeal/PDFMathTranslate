#!/usr/bin/env python3
"""
Test script for Thai text shaping implementation.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_text_shaper_basic():
    """Test basic text shaper functionality."""
    print("Testing Text Shaper Basic Functionality")
    print("=" * 50)

    try:
        from pdf2zh.text_shaper import get_text_shaper

        shaper = get_text_shaper()
        print(f"✅ Text shaper created successfully")
        print(f"   - Enabled: {shaper.enabled}")

        # Test Thai text detection
        thai_text = "สวัสดี"
        needs_shaping = shaper._needs_shaping(thai_text)
        print(f"   - Thai text '{thai_text}' needs shaping: {needs_shaping}")

        # Test script detection
        for char in thai_text:
            script = shaper._get_script(char)
            print(f"   - Character '{char}' -> Script: {script}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_converter_integration():
    """Test converter integration."""
    print("\nTesting Converter Integration")
    print("=" * 40)

    try:
        from pdf2zh.converter import TranslateConverter
        from pdf2zh.text_shaper import get_text_shaper

        # Test that converter can use text shaper
        shaper = get_text_shaper()

        # Test the shape_text_run method exists
        if hasattr(TranslateConverter, '_shape_text_run'):
            print("✅ Converter has _shape_text_run method")
        else:
            print("❌ Converter missing _shape_text_run method")
            return False

        # Test font path method
        if hasattr(TranslateConverter, '_get_font_path'):
            print("✅ Converter has _get_font_path method")
        else:
            print("❌ Converter missing _get_font_path method")
            return False

        print("✅ Converter integration looks good")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_configuration():
    """Test configuration handling."""
    print("\nTesting Configuration")
    print("=" * 30)

    try:
        # Test config file exists
        config_path = "config/config.json"
        if os.path.exists(config_path):
            print(f"✅ Config file exists: {config_path}")

            import json
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Check for text shaping settings
            if "TEXT_SHAPING_ENABLED" in config:
                print(f"✅ TEXT_SHAPING_ENABLED: {config['TEXT_SHAPING_ENABLED']}")
            else:
                print("⚠️  TEXT_SHAPING_ENABLED not in config")

            if "NOTO_FONT_PATH" in config:
                print(f"✅ NOTO_FONT_PATH: {config['NOTO_FONT_PATH']}")
            else:
                print("⚠️  NOTO_FONT_PATH not in config")

        else:
            print(f"⚠️  Config file not found: {config_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests."""
    print("🔍 Testing Thai Text Shaping Implementation")
    print("=" * 60)

    tests = [
        test_text_shaper_basic,
        test_converter_integration,
        test_configuration,
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

    print("=" * 60)
    print(f"📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Implementation looks good.")
        print("\n💡 Next steps:")
        print("1. Install uharfbuzz: pip install uharfbuzz")
        print("2. Test with actual Thai text in a PDF")
        print("3. Check debug logs for HarfBuzz shaping activity")
        return 0
    else:
        print("⚠️  Some tests failed. Check implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())