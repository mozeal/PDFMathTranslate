"""
Text shaping module using HarfBuzz for complex script rendering.

This module provides text shaping capabilities for languages that require
complex text layout, such as Thai, Arabic, Indic scripts, etc.
"""

import logging
import re
import unicodedata
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass
from functools import lru_cache

try:
    import uharfbuzz as hb

    HARFBUZZ_AVAILABLE = True
except ImportError:
    HARFBUZZ_AVAILABLE = False
    logging.warning("uharfbuzz not available. Complex text shaping will be disabled.")

from pdf2zh.config import ConfigManager

log = logging.getLogger(__name__)


@dataclass
class GlyphInfo:
    """Information about a shaped glyph."""

    glyph_id: int
    cluster: int
    x_advance: float
    y_advance: float
    x_offset: float
    y_offset: float


@dataclass
class ShapedText:
    """Result of text shaping operation."""

    glyphs: List[GlyphInfo]
    total_advance: float
    success: bool

    def get_cluster_info(self) -> Dict[int, List[GlyphInfo]]:
        """Group glyphs by cluster for complex positioning."""
        clusters = {}
        for glyph in self.glyphs:
            if glyph.cluster not in clusters:
                clusters[glyph.cluster] = []
            clusters[glyph.cluster].append(glyph)
        return clusters


class TextRun(NamedTuple):
    """A run of text with consistent properties."""

    text: str
    start_index: int
    end_index: int
    script: str
    direction: str = "ltr"


class TextShaper:
    """HarfBuzz-based text shaper for complex scripts."""

    # Scripts that benefit from complex shaping
    COMPLEX_SCRIPTS = {
        "Thai",
        "Laoo",
        "Khmer",
        "Myanmar",  # Southeast Asian
        "Arabic",
        "Hebrew",
        "Syriac",  # Middle Eastern
        "Devanagari",
        "Bengali",
        "Gurmukhi",
        "Gujarati",
        "Oriya",
        "Tamil",
        "Telugu",
        "Kannada",
        "Malayalam",
        "Sinhala",  # Indic
        "Tibetan",
        "Mongolian",  # Central Asian
    }

    # Formula pattern to preserve during shaping
    FORMULA_PATTERN = re.compile(r"\{v\d+\}")

    def __init__(self):
        # Enable text shaping with HarfBuzz
        self.enabled = (
            HARFBUZZ_AVAILABLE
            and ConfigManager.get("TEXT_SHAPING_ENABLED", "true").lower() == "true"
        )
        self._font_cache: Dict[str, hb.Font] = {}
        self._face_cache: Dict[str, hb.Face] = {}

        if self.enabled:
            log.info("Text shaping enabled with HarfBuzz")
        else:
            log.info("Text shaping disabled")

    @lru_cache(maxsize=1000)
    def _get_script(self, char: str) -> str:
        """Get Unicode script for a character."""
        try:
            script = unicodedata.name(char).split()[0] if char else "Latin"
            # Normalize script names to match our COMPLEX_SCRIPTS set
            script_mapping = {
                "THAI": "Thai",
                "ARABIC": "Arabic",
                "HEBREW": "Hebrew",
                "DEVANAGARI": "Devanagari",
                "BENGALI": "Bengali",
                "MYANMAR": "Myanmar",
                "KHMER": "Khmer",
                "LAO": "Laoo",
                "TIBETAN": "Tibetan",
                "MONGOLIAN": "Mongolian"
            }
            return script_mapping.get(script, script)
        except (ValueError, IndexError):
            # Fallback to Unicode range detection for Thai
            if char and 0x0E00 <= ord(char) <= 0x0E7F:
                return "Thai"
            return "Latin"

    def _needs_shaping(self, text: str) -> bool:
        """Check if text contains characters that need complex shaping."""
        if not self.enabled:
            log.debug(f"🚫 Text shaping disabled - skipping '{text}'")
            return False

        if not text:
            log.debug("🚫 Empty text - no shaping needed")
            return False

        # Check if any character belongs to a complex script
        complex_chars = []
        for char in text:
            script = self._get_script(char)
            if script in self.COMPLEX_SCRIPTS:
                complex_chars.append(f"{char}({script})")

        if complex_chars:
            # Use INFO level for Thai text detection to make it more visible
            if any(0x0E00 <= ord(char) <= 0x0E7F for char in text):
                log.info(f"🇹🇭 Thai text detected: '{text}' - will use HarfBuzz shaping")
            else:
                log.debug(f"🔤 Text '{text}' needs shaping - complex chars: {', '.join(complex_chars)}")
            return True
        else:
            log.debug(f"📝 Text '{text}' is simple script - no shaping needed")
            return False

    def _split_text_runs(self, text: str) -> List[TextRun]:
        """Split text into runs with consistent script properties."""
        if not text:
            return []

        runs = []
        current_script = None
        current_start = 0

        for i, char in enumerate(text):
            # Skip formula markers
            if self.FORMULA_PATTERN.match(text[i : i + 5]):
                # End current run if exists
                if current_script is not None:
                    runs.append(
                        TextRun(
                            text=text[current_start:i],
                            start_index=current_start,
                            end_index=i,
                            script=current_script,
                        )
                    )

                # Find end of formula marker
                formula_match = self.FORMULA_PATTERN.match(text[i:])
                if formula_match:
                    formula_end = i + len(formula_match.group(0))
                    runs.append(
                        TextRun(
                            text=text[i:formula_end],
                            start_index=i,
                            end_index=formula_end,
                            script="Formula",
                        )
                    )
                    current_script = None
                    current_start = formula_end
                    i = formula_end - 1  # Will be incremented by loop
                continue

            char_script = self._get_script(char)

            # Start new run if script changes
            if current_script != char_script:
                if current_script is not None:
                    runs.append(
                        TextRun(
                            text=text[current_start:i],
                            start_index=current_start,
                            end_index=i,
                            script=current_script,
                        )
                    )
                current_script = char_script
                current_start = i

        # Add final run
        if current_script is not None:
            runs.append(
                TextRun(
                    text=text[current_start:],
                    start_index=current_start,
                    end_index=len(text),
                    script=current_script,
                )
            )

        return runs

    def _load_font(self, font_path: str, font_size: float) -> Optional[hb.Font]:
        """Load and cache a HarfBuzz font."""
        cache_key = f"{font_path}:{font_size}"

        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        try:
            # Load font face
            if font_path not in self._face_cache:
                with open(font_path, "rb") as f:
                    font_data = f.read()
                face = hb.Face(font_data)
                self._face_cache[font_path] = face
            else:
                face = self._face_cache[font_path]

            # Create font with size
            font = hb.Font(face)
            font.scale = (int(font_size * 64), int(font_size * 64))  # 26.6 fixed point

            self._font_cache[cache_key] = font
            return font

        except Exception as e:
            log.warning(f"Failed to load font {font_path}: {e}")
            return None

    def _shape_run(self, text_run: TextRun, font: hb.Font) -> ShapedText:
        """Shape a single text run using HarfBuzz."""
        try:
            # Create buffer
            buf = hb.Buffer()
            buf.add_str(text_run.text)
            buf.guess_segment_properties()

            # Set script if known
            if text_run.script in self.COMPLEX_SCRIPTS:
                script_map = {
                    "Thai": "thai",
                    "Arabic": "arab",
                    "Hebrew": "hebr",
                    "Devanagari": "deva",
                    "Bengali": "beng",
                    "Tamil": "taml",
                    "Telugu": "telu",
                    "Kannada": "knda",
                    "Malayalam": "mlym",
                    "Gujarati": "gujr",
                    "Gurmukhi": "guru",
                    "Oriya": "orya",
                    "Sinhala": "sinh",
                    "Myanmar": "mymr",
                    "Khmer": "khmr",
                    "Laoo": "lao ",
                    "Tibetan": "tibt",
                    "Mongolian": "mong",
                }
                if text_run.script in script_map:
                    buf.script = script_map[text_run.script]

            # Set direction
            if text_run.direction == "rtl":
                buf.direction = "rtl"
            else:
                buf.direction = "ltr"

            # Enable advanced OpenType features for better Thai shaping
            features = {}
            if text_run.script == "Thai":
                # Enable essential Thai shaping features
                features.update({
                    "liga": True,  # Ligatures
                    "kern": True,  # Kerning
                    "mark": True,  # Mark positioning
                    "mkmk": True,  # Mark-to-mark positioning (essential for Thai)
                    "ccmp": True,  # Glyph composition/decomposition
                })

            # Shape the text with features
            if features:
                hb.shape(font, buf, features)
            else:
                hb.shape(font, buf)

            # Extract glyph information
            glyph_infos = buf.glyph_infos
            glyph_positions = buf.glyph_positions

            glyphs = []
            total_advance = 0.0

            for info, pos in zip(glyph_infos, glyph_positions):
                glyph = GlyphInfo(
                    glyph_id=info.codepoint,
                    cluster=info.cluster,
                    x_advance=pos.x_advance / 64.0,  # Convert from 26.6 fixed point
                    y_advance=pos.y_advance / 64.0,
                    x_offset=pos.x_offset / 64.0,
                    y_offset=pos.y_offset / 64.0,
                )
                glyphs.append(glyph)
                total_advance += glyph.x_advance

            return ShapedText(glyphs=glyphs, total_advance=total_advance, success=True)

        except Exception as e:
            log.warning(f"Text shaping failed for run '{text_run.text}': {e}")
            return ShapedText(glyphs=[], total_advance=0.0, success=False)

    def shape_text(
        self, text: str, font_path: str, font_size: float
    ) -> Optional[ShapedText]:
        """
        Shape text using HarfBuzz.

        Args:
            text: Text to shape
            font_path: Path to font file
            font_size: Font size in points

        Returns:
            ShapedText object with glyph information, or None if shaping not needed
        """
        log.debug(f"🎯 shape_text called: '{text}' (font: {font_path}, size: {font_size})")

        if not self._needs_shaping(text):
            log.debug(f"⏭️ No shaping needed for '{text}' - returning None")
            return None

        font = self._load_font(font_path, font_size)
        if not font:
            log.debug(f"❌ Failed to load font '{font_path}' for text '{text}'")
            return None

        # Split text into runs
        runs = self._split_text_runs(text)

        # Shape each run
        all_glyphs = []
        total_advance = 0.0
        success = True

        for run in runs:
            if run.script == "Formula":
                # Skip formula markers - they will be handled separately
                continue

            shaped = self._shape_run(run, font)
            if not shaped.success:
                success = False
                break

            all_glyphs.extend(shaped.glyphs)
            total_advance += shaped.total_advance

        return ShapedText(
            glyphs=all_glyphs, total_advance=total_advance, success=success
        )

    def get_text_advance(
        self, text: str, font_path: str, font_size: float
    ) -> Optional[float]:
        """
        Get the total advance width of shaped text.

        Args:
            text: Text to measure
            font_path: Path to font file
            font_size: Font size in points

        Returns:
            Total advance width in points, or None if shaping not needed
        """
        shaped = self.shape_text(text, font_path, font_size)
        return shaped.total_advance if shaped and shaped.success else None

    def get_character_positions(
        self, text: str, font_path: str, font_size: float
    ) -> Optional[List[Dict]]:
        """
        Get detailed positioning information for each character in shaped text.

        Args:
            text: Text to shape
            font_path: Path to font file
            font_size: Font size in points

        Returns:
            List of character position dictionaries with x_advance, x_offset, y_offset
        """
        shaped = self.shape_text(text, font_path, font_size)
        if not shaped or not shaped.success:
            return None

        # Group glyphs by cluster
        clusters = shaped.get_cluster_info()

        # Build character position list
        positions = []

        for char_idx in range(len(text)):
            if char_idx in clusters:
                cluster_glyphs = clusters[char_idx]

                # Calculate cluster advance (sum of all glyph advances in cluster)
                cluster_advance = sum(g.x_advance for g in cluster_glyphs)

                # For the base character, use the full cluster advance
                # For combining marks, use zero advance (they position relative to base)
                positions.append(
                    {
                        "x_advance": cluster_advance,
                        "x_offset": cluster_glyphs[0].x_offset,
                        "y_offset": cluster_glyphs[0].y_offset,
                        "glyphs": cluster_glyphs,
                    }
                )
            else:
                # Character not in any cluster (shouldn't happen with proper shaping)
                positions.append(
                    {"x_advance": 0.0, "x_offset": 0.0, "y_offset": 0.0, "glyphs": []}
                )

        return positions


# Global text shaper instance
_text_shaper = None


def get_text_shaper() -> TextShaper:
    """Get the global text shaper instance."""
    global _text_shaper
    if _text_shaper is None:
        _text_shaper = TextShaper()
    return _text_shaper
