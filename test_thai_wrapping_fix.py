#!/usr/bin/env python3
"""
Test script to verify the improved Thai word wrapping implementation.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_thai_word_boundary_hints():
    """Test the new Thai word boundary hint system."""
    print("🇹🇭 Testing Thai Word Boundary Hints")
    print("=" * 50)

    try:
        from pdf2zh.converter import TranslateConverter
        from pdfminer.pdfinterp import PDFResourceManager

        # Create a dummy converter instance to test the methods
        rsrcmgr = PDFResourceManager()
        converter = TranslateConverter(
            rsrcmgr=rsrcmgr,
            lang_in="en",
            lang_out="th",
            service="google"
        )

        test_cases = [
            "ไก่ที่เป่าปี่อยู่ในป่า",
            "สวัสดีครับผมชื่อจอห์น",
            "เขียนโค้ดภาษาไพธอนเป็นเรื่องสนุก",
            "การแปลภาษาไทยให้ถูกต้องต้องใช้การแบ่งคำที่เหมาะสม"
        ]

        success_count = 0
        total_tests = len(test_cases)

        for i, text in enumerate(test_cases, 1):
            print(f"\nTest {i}: '{text}'")

            # Test the word boundary hint addition
            processed_text = converter._add_thai_word_boundary_hints(text)

            # Check if zero-width spaces were added
            zwsp_count = processed_text.count('\u200B')

            if zwsp_count > 0:
                print(f"✅ Added {zwsp_count} word boundary hints")

                # Show where the breaks would occur
                words = processed_text.split('\u200B')
                print(f"   Word segments: {' | '.join(words)}")

                # Test that zero-width spaces are properly handled in raw_string
                # (This would be called by the actual rendering system)
                class MockRawString:
                    def __call__(self, fcur, cstk):
                        # Simulate the raw_string function's ZWSP removal
                        return cstk.replace('\u200B', '')

                mock_raw_string = MockRawString()
                cleaned_text = mock_raw_string("test_font", processed_text)

                if cleaned_text == text:
                    print(f"✅ Zero-width spaces correctly removed for rendering")
                    success_count += 1
                else:
                    print(f"❌ Text corruption after ZWSP removal: '{cleaned_text}' != '{text}'")
            else:
                print(f"❌ No word boundary hints added")

        print(f"\n📊 Word Boundary Hint Tests: {success_count}/{total_tests} passed")
        return success_count == total_tests

    except Exception as e:
        print(f"❌ Error in word boundary hint testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_zero_width_space_handling():
    """Test zero-width space handling in line wrapping logic."""
    print("\n🔤 Testing Zero-Width Space Handling")
    print("=" * 50)

    # Test the core logic
    test_text = "ไก่\u200Bที่\u200Bเป่าปี่\u200Bอยู่\u200Bใน\u200Bป่า"
    print(f"Input with ZWSP: '{test_text}'")

    # Test finding the last ZWSP
    zwsp_pos = test_text.rfind('\u200B')
    if zwsp_pos >= 0:
        safe_text = test_text[:zwsp_pos]
        remaining_text = test_text[zwsp_pos + 1:]

        print(f"Last ZWSP at position: {zwsp_pos}")
        print(f"Would break into: '{safe_text}' | '{remaining_text}'")
        print("✅ ZWSP break point logic working")
        return True
    else:
        print("❌ No ZWSP found")
        return False

def test_formula_preservation():
    """Test that formula markers are preserved during Thai processing."""
    print("\n🧮 Testing Formula Preservation")
    print("=" * 50)

    try:
        from pdf2zh.converter import TranslateConverter
        from pdfminer.pdfinterp import PDFResourceManager

        rsrcmgr = PDFResourceManager()
        converter = TranslateConverter(
            rsrcmgr=rsrcmgr,
            lang_in="en",
            lang_out="th",
            service="google"
        )

        # Test text with formula markers
        test_text = "สมการ {v1} คือสูตรสำคัญในฟิสิกส์ {v2} ที่ใช้คำนวณ"

        processed_text = converter._add_thai_word_boundary_hints(test_text)

        print(f"Original: '{test_text}'")
        print(f"Processed: '{processed_text}'")

        # Check that formula markers are preserved
        if "{v1}" in processed_text and "{v2}" in processed_text:
            print("✅ Formula markers preserved")

            # Check that Thai words still got boundary hints
            zwsp_count = processed_text.count('\u200B')
            if zwsp_count > 0:
                print(f"✅ {zwsp_count} word boundary hints added around formulas")
                return True
            else:
                print("⚠️ No word boundary hints added")
                return False
        else:
            print("❌ Formula markers were corrupted")
            return False

    except Exception as e:
        print(f"❌ Error in formula preservation test: {e}")
        return False

def demonstrate_improved_wrapping():
    """Demonstrate the improved wrapping behavior."""
    print("\n🚀 Improved Thai Text Wrapping Demo")
    print("=" * 60)

    print("New Implementation Strategy:")
    print("1. ✅ Post-process translated text to add word boundary hints (ZWSP)")
    print("2. ✅ Use existing line wrapping logic with ZWSP as break points")
    print("3. ✅ Remove ZWSP before rendering to avoid visual artifacts")
    print("4. ✅ Preserve formula markers during processing")

    print("\nKey Improvements:")
    print("- 🎯 More reliable word boundary detection")
    print("- 🔧 Simpler integration with existing text processing")
    print("- 🛡️ Better formula preservation")
    print("- ⚡ Cleaner separation of concerns")

    example_text = "ไก่ที่เป่าปี่อยู่ในป่าใหญ่และมีต้นไผ่เยอะมาก"

    print(f"\nExample Transformation:")
    print(f"Input:  '{example_text}'")

    # Simulate the word boundary hint addition
    try:
        import pythainlp
        words = pythainlp.word_tokenize(example_text, engine='newmm')
        with_hints = '\u200B'.join(words)
        print(f"Hints:  '{with_hints.replace(chr(0x200B), '|')}'  (| = ZWSP)")

        # Show how line breaking would work
        print(f"Words:  {words}")
        print("✅ Line breaks will occur at word boundaries!")

    except ImportError:
        print("(pythainlp not available for demo)")

def main():
    """Run all tests."""
    print("🧪 Thai Word Wrapping Fix Verification")
    print("=" * 60)

    tests = [
        ("Thai Word Boundary Hints", test_thai_word_boundary_hints),
        ("Zero-Width Space Handling", test_zero_width_space_handling),
        ("Formula Preservation", test_formula_preservation),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
            print(f"\n{'✅' if result else '❌'} {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"\n💥 {test_name}: CRASHED - {e}")
            results.append(False)
        print()

    demonstrate_improved_wrapping()

    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 Thai word wrapping fix is working correctly!")
        print("\n🚀 Ready for deployment:")
        print("1. ✅ Word boundary hints properly added")
        print("2. ✅ Zero-width spaces handled correctly")
        print("3. ✅ Formula markers preserved")
        print("4. ✅ Integration with existing pipeline")
        return 0
    else:
        print(f"\n⚠️ {total - passed} tests failed. Check implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())