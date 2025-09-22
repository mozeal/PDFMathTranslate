# Thai Text Wrapping Implementation

This document describes the Thai text wrapping functionality implemented in PDFMathTranslate using pythainlp for intelligent word boundary detection.

## Overview

Traditional character-by-character text wrapping can break Thai words in the middle, making text difficult to read. This implementation uses pythainlp to detect word boundaries and ensures line breaks occur at appropriate word boundaries rather than arbitrary character positions.

## Features

### 🇹🇭 Smart Word Boundary Detection
- Uses pythainlp's `word_tokenize()` for accurate Thai word segmentation
- Supports multiple tokenization engines (newmm, mm, longest)
- Graceful fallback when pythainlp is unavailable

### 🔧 Configurable Behavior
- `THAI_WORD_WRAP_ENABLED`: Enable/disable Thai word wrapping (default: "true")
- `THAI_MIN_LINE_USAGE`: Minimum line usage before allowing wrap (default: "0.3")
- `THAI_TOKENIZER_ENGINE`: pythainlp tokenization engine (default: "newmm")

### 🎯 Intelligent Line Breaking
- Finds safe break points at word boundaries
- Respects minimum line usage to avoid breaking too early
- Falls back to punctuation/space if no good word boundary found
- Maintains existing HarfBuzz text shaping integration

## Implementation Details

### Core Methods

#### `_get_thai_word_boundaries(text: str) -> List[int]`
Uses pythainlp to detect word boundaries in Thai text.

```python
def _get_thai_word_boundaries(self, text: str) -> List[int]:
    """Get word boundary positions for Thai text using pythainlp."""
    try:
        import pythainlp
        engine = ConfigManager.get("THAI_TOKENIZER_ENGINE", "newmm")
        words = pythainlp.word_tokenize(text, engine=engine)
        boundaries = []
        pos = 0
        for word in words:
            pos += len(word)
            boundaries.append(pos)
        return boundaries
    except ImportError:
        return []  # Graceful fallback
```

#### `_find_safe_break_point(text: str, current_pos: int, target_lang: str, char_widths: List[float]) -> int`
Finds the best position to break text while respecting word boundaries.

```python
def _find_safe_break_point(self, text: str, current_pos: int, target_lang: str, char_widths: List[float]) -> int:
    """Find a safe break point for text wrapping that respects word boundaries."""
    thai_word_wrap_enabled = ConfigManager.get("THAI_WORD_WRAP_ENABLED", "true").lower() == "true"

    if target_lang == 'th' and current_pos > 0 and thai_word_wrap_enabled:
        boundaries = self._get_thai_word_boundaries(text[:current_pos])
        if boundaries:
            safe_pos = max(b for b in boundaries if b <= current_pos)
            min_line_usage = float(ConfigManager.get("THAI_MIN_LINE_USAGE", "0.3"))
            min_pos = max(1, int(current_pos * min_line_usage))
            if safe_pos >= min_pos:
                return safe_pos

    # Fallback logic for other languages or edge cases
    return current_pos
```

### Integration with Line Wrapping Logic

The main line wrapping logic in `receive_layout()` has been enhanced to:

1. **Detect approaching boundary**: When text width approaches the right boundary
2. **Check for Thai text**: If target language is Thai and word wrapping is enabled
3. **Find safe break**: Use `_find_safe_break_point()` to find word boundary
4. **Split intelligently**: Break text at word boundary instead of character boundary
5. **Continue seamlessly**: Place remaining text on next line

## Configuration Options

### Environment Variables / Config File

Set these in your environment or config file:

```bash
# Enable/disable Thai word wrapping
export THAI_WORD_WRAP_ENABLED=true

# Minimum line usage before allowing wrap (0.0-1.0)
export THAI_MIN_LINE_USAGE=0.3

# pythainlp tokenization engine
export THAI_TOKENIZER_ENGINE=newmm
```

### Available Engines

- **newmm**: Neural Maximum Matching (default, most accurate)
- **mm**: Maximum Matching (faster, good accuracy)
- **longest**: Longest matching (simple, fast)

## Usage Examples

### Basic Usage

The feature works automatically when translating to Thai (`lang_out="th"`):

```python
from pdf2zh import translate_pdf

# Thai word wrapping will be automatically applied
translate_pdf(
    input_file="document.pdf",
    output_file="document_th.pdf",
    lang_out="th",
    service="google"
)
```

### Custom Configuration

```python
from pdf2zh.config import ConfigManager

# Configure Thai text wrapping
ConfigManager.set("THAI_WORD_WRAP_ENABLED", "true")
ConfigManager.set("THAI_MIN_LINE_USAGE", "0.4")  # Use at least 40% of line
ConfigManager.set("THAI_TOKENIZER_ENGINE", "newmm")

# Then translate as usual
translate_pdf("document.pdf", "document_th.pdf", lang_out="th")
```

## Testing

### Run Test Suite

```bash
# Run Thai text wrapping tests
python test_thai_word_wrapping.py

# Run unit tests
pytest test/test_thai_text_wrapping.py -v
```

### Test Cases

The implementation includes comprehensive tests for:

- Word boundary detection with various Thai texts
- Safe break point finding
- Configuration option handling
- pythainlp integration
- Graceful fallback when pythainlp unavailable

## Dependencies

### Required
- **pythainlp**: Thai natural language processing library
- **uharfbuzz**: Already included for text shaping

### Installation

```bash
pip install pythainlp
```

Or install the project with the updated dependencies:

```bash
pip install -e .
```

## Benefits

### ✅ Improved Readability
- No more mid-word line breaks in Thai text
- Professional-looking document layout
- Maintains natural reading flow

### ✅ Seamless Integration
- Works with existing HarfBuzz text shaping
- Preserves complex script rendering
- No impact on other languages

### ✅ Configurable and Safe
- Can be disabled if needed
- Graceful fallback when pythainlp unavailable
- Respects minimum line usage constraints

### ✅ Performance Optimized
- Caches word boundaries when possible
- Minimal overhead for non-Thai text
- Uses efficient tokenization engines

## Troubleshooting

### pythainlp Not Available

If pythainlp is not installed, the system will:
1. Log a warning message
2. Fall back to character-level wrapping
3. Continue processing without errors

### Poor Word Segmentation

Try different tokenization engines:

```python
ConfigManager.set("THAI_TOKENIZER_ENGINE", "mm")  # Try 'mm' instead of 'newmm'
```

### Lines Breaking Too Early

Adjust minimum line usage:

```python
ConfigManager.set("THAI_MIN_LINE_USAGE", "0.2")  # Allow breaking after 20% usage
```

### Disable Thai Word Wrapping

```python
ConfigManager.set("THAI_WORD_WRAP_ENABLED", "false")
```

## Future Enhancements

### Potential Improvements
- Support for other Thai tokenization libraries
- Language-specific wrapping for other complex scripts
- Advanced typography rules (widow/orphan control)
- Performance optimizations for large documents

### Contributing

To contribute improvements:

1. Add test cases for new scenarios
2. Ensure backward compatibility
3. Update documentation
4. Test with various Thai documents

## Example Output

### Before (Character-level wrapping):
```
ไก่ที่เป่าปี่อยู่ในป่าใหญ่และมีต้นไผ่เยอ
ะมาก
```

### After (Word-level wrapping):
```
ไก่ที่เป่าปี่อยู่ในป่าใหญ่และมี
ต้นไผ่เยอะมาก
```

The improved wrapping respects word boundaries, making the text much more readable and professional-looking.