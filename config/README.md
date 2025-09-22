# Configuration Guide

This directory contains configuration files for PDFMathTranslate when running in Docker.

## config.json

The main configuration file that controls translation settings, API keys, and text formatting.

### Font Size and Line Spacing Configuration

You can customize font size and line spacing for different languages by adding these keys to `config.json`:

#### Font Size Scaling
```json
"LANG_FONTSIZE_SCALE_{LANGUAGE}": "scale_factor"
```

#### Line Height 
```json
"LANG_LINEHEIGHT_{LANGUAGE}": "line_height_factor"
```

### Language Codes

| Language | Code | Font Size Key | Line Height Key |
|----------|------|---------------|-----------------|
| Thai | `TH` | `LANG_FONTSIZE_SCALE_TH` | `LANG_LINEHEIGHT_TH` |
| Chinese | `ZH` | `LANG_FONTSIZE_SCALE_ZH` | `LANG_LINEHEIGHT_ZH` |
| Japanese | `JA` | `LANG_FONTSIZE_SCALE_JA` | `LANG_LINEHEIGHT_JA` |
| Korean | `KO` | `LANG_FONTSIZE_SCALE_KO` | `LANG_LINEHEIGHT_KO` |
| English | `EN` | `LANG_FONTSIZE_SCALE_EN` | `LANG_LINEHEIGHT_EN` |

### Value Guidelines

**Font Size Scale**:
- `"0.8"` = Smaller text (80% of original)
- `"1.0"` = Normal size (100%)  
- `"1.2"` = Larger text (120% of original)

**Line Height**:
- `"1.0"` = Tight spacing
- `"1.3"` = Normal spacing
- `"1.8"` = Loose spacing (80% more space)

### Example Configuration

```json
{
    "PDF2ZH_LANG_FROM": "English",
    "PDF2ZH_LANG_TO": "Thai",
    "NOTO_FONT_PATH": "/app/fonts/Sarabun-Regular.ttf",
    "LANG_FONTSIZE_SCALE_TH": "0.8",
    "LANG_LINEHEIGHT_TH": "1.8",
    "LANG_FONTSIZE_SCALE_EN": "1.0",
    "LANG_LINEHEIGHT_EN": "1.1",
    "translators": [
        {
            "name": "openai",
            "envs": {
                "OPENAI_API_KEY": "your-api-key-here",
                "OPENAI_MODEL": "gpt-4o-mini"
            }
        }
    ]
}
```

### Applying Changes

After editing `config.json`, restart the Docker container:

```bash
docker-compose restart
```

The new font size and line spacing settings will be applied to all subsequent translations.