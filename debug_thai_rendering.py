#!/usr/bin/env python3
"""
Diagnostic script to identify why Thai text is still rendering incorrectly.
"""

import os
import sys
import json

def check_harfbuzz_installation():
    """Check if HarfBuzz is properly installed."""
    print("1. HARFBUZZ INSTALLATION CHECK")
    print("=" * 40)

    try:
        import uharfbuzz as hb
        print("✅ uharfbuzz imported successfully")
        print(f"   Version info: {hb.__name__ if hasattr(hb, '__name__') else 'Available'}")
        return True
    except ImportError as e:
        print(f"❌ uharfbuzz NOT installed: {e}")
        print("   Install with: pip install uharfbuzz")
        return False

def check_configuration():
    """Check project configuration."""
    print("\n2. CONFIGURATION CHECK")
    print("=" * 30)

    config_path = "config/config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            print("✅ Config file found")

            # Check text shaping setting
            shaping_enabled = config.get("TEXT_SHAPING_ENABLED", "false")
            print(f"   TEXT_SHAPING_ENABLED: {shaping_enabled}")

            # Check font path
            font_path = config.get("NOTO_FONT_PATH", "")
            print(f"   NOTO_FONT_PATH: {font_path}")

            # Check if font file exists
            if font_path and os.path.exists(font_path):
                print(f"✅ Font file exists: {font_path}")
            elif font_path:
                print(f"❌ Font file NOT found: {font_path}")
            else:
                print("⚠️  No font path configured")

            return shaping_enabled.lower() == "true", font_path

        except Exception as e:
            print(f"❌ Error reading config: {e}")
            return False, ""
    else:
        print(f"❌ Config file not found: {config_path}")
        return False, ""

def test_font_loading(font_path):
    """Test if the font can be loaded by HarfBuzz."""
    print("\n3. FONT LOADING TEST")
    print("=" * 25)

    if not font_path or not os.path.exists(font_path):
        print("❌ Cannot test - font path invalid")
        return False

    try:
        import uharfbuzz as hb

        # Try to load the font
        with open(font_path, 'rb') as f:
            font_data = f.read()

        face = hb.Face(font_data)
        font = hb.Font(face)
        font.scale = (12 * 64, 12 * 64)  # 12pt size

        print(f"✅ Font loaded successfully")
        print(f"   Font file size: {len(font_data)} bytes")

        # Test with a simple Thai character
        buf = hb.Buffer()
        buf.add_str("ก")  # Simple Thai consonant
        buf.guess_segment_properties()

        hb.shape(font, buf)

        glyph_infos = buf.glyph_infos
        glyph_positions = buf.glyph_positions

        if len(glyph_infos) > 0:
            print(f"✅ Basic shaping works - got {len(glyph_infos)} glyph(s)")
            glyph = glyph_infos[0]
            pos = glyph_positions[0]
            print(f"   Glyph ID: {glyph.codepoint}, Advance: {pos.x_advance/64.0}")
        else:
            print("❌ Shaping failed - no glyphs returned")
            return False

        return True

    except Exception as e:
        print(f"❌ Font loading failed: {e}")
        return False

def test_complex_thai_shaping(font_path):
    """Test complex Thai shaping."""
    print("\n4. COMPLEX THAI SHAPING TEST")
    print("=" * 35)

    if not font_path or not os.path.exists(font_path):
        print("❌ Cannot test - font path invalid")
        return False

    try:
        import uharfbuzz as hb

        # Load font
        with open(font_path, 'rb') as f:
            font_data = f.read()
        face = hb.Face(font_data)
        font = hb.Font(face)
        font.scale = (12 * 64, 12 * 64)

        # Test complex Thai sentence
        test_text = "ไก่ที่เป่าปี่"
        print(f"Testing: '{test_text}'")

        buf = hb.Buffer()
        buf.add_str(test_text)
        buf.guess_segment_properties()
        buf.script = "thai"

        # Enable Thai features
        features = [
            ("liga", True),
            ("kern", True),
            ("mark", True),
            ("mkmk", True),
            ("ccmp", True),
        ]

        hb.shape(font, buf, features)

        glyph_infos = buf.glyph_infos
        glyph_positions = buf.glyph_positions

        print(f"Input: {len(test_text)} characters")
        print(f"Output: {len(glyph_infos)} glyphs")

        if len(glyph_infos) == 0:
            print("❌ No glyphs produced - shaping completely failed")
            return False

        print("\nGlyph Analysis:")
        for i, (info, pos) in enumerate(zip(glyph_infos, glyph_positions)):
            x_advance = pos.x_advance / 64.0
            y_advance = pos.y_advance / 64.0
            x_offset = pos.x_offset / 64.0
            y_offset = pos.y_offset / 64.0

            char_idx = info.cluster if info.cluster < len(test_text) else 0
            char = test_text[char_idx] if char_idx < len(test_text) else '?'

            print(f"  {i:2d}: '{char}' cluster={info.cluster} glyph={info.codepoint}")
            print(f"      advance=({x_advance:.1f}, {y_advance:.1f}) offset=({x_offset:.1f}, {y_offset:.1f})")

        # Check for combining marks with offsets
        marks_with_offsets = 0
        for i, (info, pos) in enumerate(zip(glyph_infos, glyph_positions)):
            if pos.x_offset != 0 or pos.y_offset != 0:
                marks_with_offsets += 1

        print(f"\n✅ Shaping successful!")
        print(f"   Glyphs with positioning offsets: {marks_with_offsets}")

        if marks_with_offsets == 0:
            print("⚠️  WARNING: No glyphs have positioning offsets")
            print("   This might indicate the font doesn't have proper mark positioning")

        return True

    except Exception as e:
        print(f"❌ Complex shaping test failed: {e}")
        return False

def check_text_shaper_integration():
    """Test the text shaper integration."""
    print("\n5. TEXT SHAPER INTEGRATION TEST")
    print("=" * 40)

    try:
        # Add current directory to path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        from pdf2zh.text_shaper import get_text_shaper

        shaper = get_text_shaper()
        print(f"✅ Text shaper created")
        print(f"   Enabled: {shaper.enabled}")

        if not shaper.enabled:
            print("❌ Text shaper is DISABLED")
            print("   Reasons could be:")
            print("   - HarfBuzz not available")
            print("   - TEXT_SHAPING_ENABLED=false")
            return False

        # Test script detection
        thai_text = "ไก่ที่เป่าปี่"
        needs_shaping = shaper._needs_shaping(thai_text)
        print(f"   Thai text needs shaping: {needs_shaping}")

        if not needs_shaping:
            print("❌ Text shaper doesn't think Thai text needs shaping")
            return False

        print("✅ Text shaper integration looks correct")
        return True

    except Exception as e:
        print(f"❌ Text shaper integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def diagnose_likely_issues():
    """Diagnose most likely issues."""
    print("\n6. LIKELY ISSUES DIAGNOSIS")
    print("=" * 35)

    print("Most common reasons Thai text still renders wrong:")
    print()
    print("❌ ISSUE 1: HarfBuzz not installed")
    print("   Solution: pip install uharfbuzz")
    print()
    print("❌ ISSUE 2: Font doesn't support Thai mark positioning")
    print("   Solution: Use a proper Thai font with OpenType features")
    print("   Recommended: Noto Sans Thai, Sarabun, THSarabunNew")
    print()
    print("❌ ISSUE 3: Text shaper disabled in config")
    print("   Solution: Set TEXT_SHAPING_ENABLED=true")
    print()
    print("❌ ISSUE 4: Font path incorrect or file missing")
    print("   Solution: Verify NOTO_FONT_PATH points to valid font file")
    print()
    print("❌ ISSUE 5: Implementation not being used")
    print("   Solution: Check debug logs for '🔤 Processing complex script'")
    print("   If missing, the code path isn't being executed")
    print()
    print("❌ ISSUE 6: Character encoding issues")
    print("   Solution: Ensure Thai text is properly UTF-8 encoded")

def main():
    """Run all diagnostic tests."""
    print("🔍 THAI RENDERING DIAGNOSTIC")
    print("=" * 50)

    # Run diagnostic tests
    harfbuzz_ok = check_harfbuzz_installation()
    shaping_enabled, font_path = check_configuration()

    if harfbuzz_ok and font_path:
        font_ok = test_font_loading(font_path)
        if font_ok:
            complex_ok = test_complex_thai_shaping(font_path)
        else:
            complex_ok = False
    else:
        font_ok = False
        complex_ok = False

    integration_ok = check_text_shaper_integration()

    # Summary
    print("\n" + "=" * 50)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 50)

    issues = []
    if not harfbuzz_ok:
        issues.append("HarfBuzz not installed")
    if not shaping_enabled:
        issues.append("Text shaping disabled in config")
    if not font_path:
        issues.append("No font path configured")
    if font_path and not os.path.exists(font_path):
        issues.append("Font file not found")
    if not font_ok:
        issues.append("Font loading failed")
    if not complex_ok:
        issues.append("Complex Thai shaping failed")
    if not integration_ok:
        issues.append("Text shaper integration failed")

    if issues:
        print("❌ ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
        print("\nFIX THESE ISSUES TO ENABLE PROPER THAI RENDERING")
    else:
        print("✅ ALL TESTS PASSED - Implementation should work!")
        print("If Thai text still renders wrong, check:")
        print("1. Debug logs for '🔤 Processing complex script'")
        print("2. PDF viewer Thai font support")
        print("3. Input text encoding")

    diagnose_likely_issues()

if __name__ == "__main__":
    main()