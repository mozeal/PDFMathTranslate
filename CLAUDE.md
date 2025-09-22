# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PDFMathTranslate (pdf2zh) is a Python tool for translating PDF scientific papers while preserving formulas, charts, tables of contents, and annotations. It supports multiple translation services and provides both command-line and GUI interfaces.

## Development Commands

### Testing
```bash
pytest test/
```

### Code Quality
```bash
# Code formatting (must pass)
black --check --diff --color pdf2zh/ test/

# Linting (must pass)
flake8 --ignore E203,E261,E501,W503,E741 pdf2zh/ test/

# Pre-commit hooks (runs black and flake8)
pre-commit run --all-files
```

### Building
```bash
# Build package
python -m build

# Install in development mode
pip install -e .

# Install with development dependencies
pip install -e .[dev]
```

### Version Management
```bash
# Bump version (uses bumpver)
bumpver update --patch  # or --minor, --major
```

## Architecture

### Core Components

1. **pdf2zh/pdf2zh.py** - Main CLI entry point with argument parsing
2. **pdf2zh/high_level.py** - High-level translation functions and orchestration
3. **pdf2zh/converter.py** - PDF conversion logic using TranslateConverter
4. **pdf2zh/translator.py** - Translation service implementations (Google, DeepL, OpenAI, etc.)
5. **pdf2zh/doclayout.py** - Document layout parsing using ONNX models
6. **pdf2zh/cache.py** - Translation caching system
7. **pdf2zh/gui.py** - Gradio-based web interface
8. **pdf2zh/backend.py** - Flask backend for API operations
9. **pdf2zh/mcp_server.py** - MCP (Model Context Protocol) server implementation
10. **pdf2zh/text_shaper.py** - HarfBuzz-based text shaping for complex scripts

### Translation Pipeline

1. **Document Parsing** - Uses pdfminer.six and PyMuPDF for PDF extraction
2. **Layout Analysis** - DocLayout-YOLO ONNX model for structure detection
3. **Text Extraction** - Preserves mathematical formulas and formatting
4. **Translation** - Supports 15+ translation services with caching
5. **Text Shaping** - HarfBuzz integration for complex script rendering (Thai, Arabic, Indic)
6. **Document Reconstruction** - Generates bilingual and mono-lingual outputs with proper text layout

### Translation Services Supported

- Google Translate, DeepL, OpenAI, Azure OpenAI
- Ollama, Xinference (local models)
- Bing, Azure Translator, Tencent, Baidu
- Gemini, Claude, Deepseek, and others

## Code Style

- Uses Black for formatting (88 character line length)
- Flake8 for linting with specific ignores: E203,E261,E501,W503,E741
- Pre-commit hooks enforce code quality
- Type hints preferred where applicable

## Key Dependencies

- **pdfminer.six==20250416** - PDF parsing (pinned version)
- **pymupdf<1.25.3** - PDF manipulation
- **gradio<5.36** - Web UI (version pinned due to bug)
- **babeldoc>=0.1.22, <0.3.0** - Alternative backend
- **onnx/onnxruntime** - Layout detection models
- **tenacity** - Retry logic for API calls
- **uharfbuzz>=0.51.0** - HarfBuzz text shaping for complex scripts (Thai, Arabic, Indic)

## Configuration

- **pdf2zh/config.py** - ConfigManager for settings
- **pyproject.toml** - Project metadata and dependencies
- **.pre-commit-config.yaml** - Code quality hooks
- Environment variables for HuggingFace endpoints and API keys

### Text Shaping Configuration

Text shaping for complex scripts (Thai, Arabic, Indic) can be configured via:

- **TEXT_SHAPING_ENABLED** - Enable/disable HarfBuzz text shaping (default: true)
- **NOTO_FONT_PATH** - Path to font file for text shaping (required for complex scripts)

Example configuration:
```bash
export TEXT_SHAPING_ENABLED=true
export NOTO_FONT_PATH=/path/to/NotoSansThai-Regular.ttf
```

## Testing

Tests are located in `test/` directory:
- `test_translator.py` - Translation service tests
- `test_converter.py` - PDF conversion tests
- `test_doclayout.py` - Layout detection tests
- `test_cache.py` - Caching functionality tests
- `test_text_shaper.py` - Text shaping functionality tests

## Important Notes

- Requires Python 3.10-3.12
- Downloads AI models (DocLayout-YOLO) on first run
- Supports both local and remote PDF processing
- Can run in MCP mode for integration with AI assistants
- GUI mode runs on port 7860 by default