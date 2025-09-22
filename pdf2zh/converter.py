import concurrent.futures
import logging
import re
import unicodedata
from enum import Enum
from string import Template
from typing import Dict, List

import numpy as np
from pdfminer.converter import PDFConverter
from pdfminer.layout import LTChar, LTFigure, LTLine, LTPage
from pdfminer.pdffont import PDFCIDFont, PDFUnicodeNotDefined
from pdfminer.pdfinterp import PDFGraphicState, PDFResourceManager
from pdfminer.utils import apply_matrix_pt, mult_matrix
from pymupdf import Font
from tenacity import retry, wait_fixed

from pdf2zh.config import ConfigManager
from pdf2zh.text_shaper import get_text_shaper
from pdf2zh.translator import (
    AnythingLLMTranslator,
    ArgosTranslator,
    AzureOpenAITranslator,
    AzureTranslator,
    BaseTranslator,
    BingTranslator,
    DeepLTranslator,
    DeepLXTranslator,
    DeepseekTranslator,
    DifyTranslator,
    GeminiTranslator,
    GoogleTranslator,
    GrokTranslator,
    GroqTranslator,
    ModelScopeTranslator,
    OllamaTranslator,
    OpenAIlikedTranslator,
    OpenAITranslator,
    QwenMtTranslator,
    SiliconTranslator,
    TencentTranslator,
    XinferenceTranslator,
    ZhipuTranslator,
    X302AITranslator,
)

log = logging.getLogger(__name__)


class PDFConverterEx(PDFConverter):
    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
    ) -> None:
        PDFConverter.__init__(self, rsrcmgr, None, "utf-8", 1, None)

    def begin_page(self, page, ctm) -> None:
        # 重载替换 cropbox
        (x0, y0, x1, y1) = page.cropbox
        (x0, y0) = apply_matrix_pt(ctm, (x0, y0))
        (x1, y1) = apply_matrix_pt(ctm, (x1, y1))
        mediabox = (0, 0, abs(x0 - x1), abs(y0 - y1))
        self.cur_item = LTPage(page.pageno, mediabox)

    def end_page(self, page):
        # 重载返回指令流
        return self.receive_layout(self.cur_item)

    def begin_figure(self, name, bbox, matrix) -> None:
        # 重载设置 pageid
        self._stack.append(self.cur_item)
        self.cur_item = LTFigure(name, bbox, mult_matrix(matrix, self.ctm))
        self.cur_item.pageid = self._stack[-1].pageid

    def end_figure(self, _: str) -> None:
        # 重载返回指令流
        fig = self.cur_item
        assert isinstance(self.cur_item, LTFigure), str(type(self.cur_item))
        self.cur_item = self._stack.pop()
        self.cur_item.add(fig)
        return self.receive_layout(fig)

    def render_char(
        self,
        matrix,
        font,
        fontsize: float,
        scaling: float,
        rise: float,
        cid: int,
        ncs,
        graphicstate: PDFGraphicState,
    ) -> float:
        # 重载设置 cid 和 fon
        try:
            text = font.to_unichr(cid)
            assert isinstance(text, str), str(type(text))
        except PDFUnicodeNotDefined:
            text = self.handle_undefined_char(font, cid)
        textwidth = font.char_width(cid)
        textdisp = font.char_disp(cid)
        item = LTChar(
            matrix,
            font,
            fontsize,
            scaling,
            rise,
            text,
            textwidth,
            textdisp,
            ncs,
            graphicstate,
        )
        self.cur_item.add(item)
        item.cid = cid  # hack 插入原字符编码
        item.font = font  # hack 插入原字符字体
        return item.adv


class Paragraph:
    def __init__(self, y, x, x0, x1, y0, y1, size, brk):
        self.y: float = y  # 初始纵坐标
        self.x: float = x  # 初始横坐标
        self.x0: float = x0  # 左边界
        self.x1: float = x1  # 右边界
        self.y0: float = y0  # 上边界
        self.y1: float = y1  # 下边界
        self.size: float = size  # 字体大小
        self.brk: bool = brk  # 换行标记


# fmt: off
class TranslateConverter(PDFConverterEx):
    def __init__(
        self,
        rsrcmgr,
        vfont: str = None,
        vchar: str = None,
        thread: int = 0,
        layout={},
        lang_in: str = "",
        lang_out: str = "",
        service: str = "",
        noto_name: str = "",
        noto: Font = None,
        envs: Dict = None,
        prompt: Template = None,
        ignore_cache: bool = False,
    ) -> None:
        super().__init__(rsrcmgr)
        self.vfont = vfont
        self.vchar = vchar
        self.thread = thread
        self.layout = layout
        self.noto_name = noto_name
        self.noto = noto
        self.text_shaper = get_text_shaper()
        self.translator: BaseTranslator = None
        # e.g. "ollama:gemma2:9b" -> ["ollama", "gemma2:9b"]
        param = service.split(":", 1)
        service_name = param[0]
        service_model = param[1] if len(param) > 1 else None
        if not envs:
            envs = {}
        for translator in [GoogleTranslator, BingTranslator, DeepLTranslator, DeepLXTranslator, OllamaTranslator, XinferenceTranslator, AzureOpenAITranslator,
                           OpenAITranslator, ZhipuTranslator, ModelScopeTranslator, SiliconTranslator, GeminiTranslator, AzureTranslator, TencentTranslator, DifyTranslator, AnythingLLMTranslator, ArgosTranslator, GrokTranslator, GroqTranslator, DeepseekTranslator, OpenAIlikedTranslator, QwenMtTranslator, X302AITranslator]:
            if service_name == translator.name:
                self.translator = translator(lang_in, lang_out, service_model, envs=envs, prompt=prompt, ignore_cache=ignore_cache)
        if not self.translator:
            raise ValueError("Unsupported translation service")

    def _get_font_path(self, font_name: str) -> str:
        """Get font file path for text shaping."""
        if font_name == self.noto_name:
            # Use the Noto font path from config
            noto_path = ConfigManager.get("NOTO_FONT_PATH")
            if noto_path:
                return noto_path

        # For other fonts, we would need to map them to actual font files
        # For now, fallback to the Noto fon
        noto_path = ConfigManager.get("NOTO_FONT_PATH")
        return noto_path if noto_path else ""

    def _shape_text_run(self, text: str, font_name: str, font_size: float, scaled_font_size: float) -> List[Dict]:
        """
        Shape a text run and return detailed glyph positioning information.

        Args:
            text: Text to shape
            font_name: Font identifier
            font_size: Original font size
            scaled_font_size: Scaled font size for rendering

        Returns:
            List of glyph dictionaries with positioning information
        """
        # Try HarfBuzz shaping first for complex scripts
        font_path = self._get_font_path(font_name)

        # Check if text needs complex shaping
        needs_shaping = self.text_shaper._needs_shaping(text) if self.text_shaper.enabled else False

        if font_path and self.text_shaper.enabled and len(text) > 0:
            log.debug(f"🔍 Checking text '{text}' (font: {font_name}, needs_shaping: {needs_shaping})")

            shaped_text = self.text_shaper.shape_text(text, font_path, scaled_font_size)
            if shaped_text and shaped_text.success:
                # Convert HarfBuzz glyphs to our format
                glyphs = []
                for glyph in shaped_text.glyphs:
                    glyphs.append({
                        'glyph_id': glyph.glyph_id,
                        'cluster': glyph.cluster,
                        'x_advance': glyph.x_advance,
                        'y_advance': glyph.y_advance,
                        'x_offset': glyph.x_offset,
                        'y_offset': glyph.y_offset,
                        'char_index': glyph.cluster if glyph.cluster < len(text) else 0
                    })
                log.info(f"🇹🇭 THAI SHAPING SUCCESS: '{text}' -> {len(glyphs)} glyphs (advance: {shaped_text.total_advance:.2f}pt)")

                # Log detailed glyph information for Thai text
                if any(0x0E00 <= ord(ch) <= 0x0E7F for ch in text):  # Contains Thai characters
                    log.info(f"🔤 Thai glyph details:")
                    for i, glyph in enumerate(glyphs[:6]):  # Show first 6 glyphs
                        log.info(f"   [{i}] ID:{glyph['glyph_id']}, cluster:{glyph['cluster']}, "
                                f"advance:{glyph['x_advance']:.1f}, offset:({glyph['x_offset']:.1f},{glyph['y_offset']:.1f})")
                    if len(glyphs) > 6:
                        log.info(f"   ... and {len(glyphs)-6} more glyphs")

                return glyphs
            else:
                log.debug(f"❌ HarfBuzz shaping failed for '{text}' - falling back to simple processing")
        else:
            # Log why HarfBuzz wasn't used
            reasons = []
            if not font_path:
                reasons.append("no font path")
            if not self.text_shaper.enabled:
                reasons.append("text shaper disabled")
            if len(text) == 0:
                reasons.append("empty text")

            log.debug(f"⚠️ Skipping HarfBuzz for '{text}' ({', '.join(reasons)}) - using fallback")

        # Fallback: create simple glyph list for character-by-character processing
        glyphs = []
        for i, ch in enumerate(text):
            if font_name == self.noto_name and self.noto:
                advance = self.noto.char_lengths(ch, scaled_font_size)[0]
            elif hasattr(self, 'fontmap') and font_name in self.fontmap:
                advance = self.fontmap[font_name].char_width(ord(ch)) * scaled_font_size
            else:
                # Default advance when no font info available
                advance = scaled_font_size * 0.6  # Rough estimate

            glyphs.append({
                'glyph_id': ord(ch),
                'cluster': i,
                'x_advance': advance,
                'y_advance': 0.0,
                'x_offset': 0.0,
                'y_offset': 0.0,
                'char_index': i
            })

        # Log fallback info more prominently for Thai text
        if any(0x0E00 <= ord(ch) <= 0x0E7F for ch in text):  # Contains Thai characters
            log.warning(f"⚠️ THAI FALLBACK: '{text}' using simple processing instead of HarfBuzz (needs_shaping: {needs_shaping})")
        else:
            log.debug(f"📏 Fallback processing for '{text}': {len(glyphs)} glyphs (needs_shaping: {needs_shaping})")
        return glyphs

    def receive_layout(self, ltpage: LTPage):
        # 段落
        sstk: list[str] = []            # 段落文字栈
        pstk: list[Paragraph] = []      # 段落属性栈
        vbkt: int = 0                   # 段落公式括号计数
        # 公式组
        vstk: list[LTChar] = []         # 公式符号组
        vlstk: list[LTLine] = []        # 公式线条组
        vfix: float = 0                 # 公式纵向偏移
        # 公式组栈
        var: list[list[LTChar]] = []    # 公式符号组栈
        varl: list[list[LTLine]] = []   # 公式线条组栈
        varf: list[float] = []          # 公式纵向偏移栈
        vlen: list[float] = []          # 公式宽度栈
        # 全局
        lstk: list[LTLine] = []         # 全局线条栈
        xt: LTChar = None               # 上一个字符
        xt_cls: int = -1                # 上一个字符所属段落，保证无论第一个字符属于哪个类别都可以触发新段落
        vmax: float = ltpage.width / 4  # 行内公式最大宽度
        ops: str = ""                   # 渲染结果

        def vflag(font: str, char: str):    # 匹配公式（和角标）字体
            if isinstance(font, bytes):     # 不一定能 decode，直接转 str
                try:
                    font = font.decode('utf-8')  # 尝试使用 UTF-8 解码
                except UnicodeDecodeError:
                    font = ""
            font = font.split("+")[-1]      # 字体名截断
            if re.match(r"\(cid:", char):
                return True
            # 基于字体名规则的判定
            if self.vfont:
                if re.match(self.vfont, font):
                    return True
            else:
                if re.match(                                            # latex 字体
                    r"(CM[^R]|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Ital|.*Sym|.*Math)",
                    font,
                ):
                    return True
            # 基于字符集规则的判定
            if self.vchar:
                if re.match(self.vchar, char):
                    return True
            else:
                if (
                    char
                    and char != " "                                     # 非空格
                    and (
                        unicodedata.category(char[0])
                        in ["Lm", "Mn", "Sk", "Sm", "Zl", "Zp", "Zs"]   # 文字修饰符、数学符号、分隔符号
                        or ord(char[0]) in range(0x370, 0x400)          # 希腊字母
                    )
                ):
                    return True
            return False

        ############################################################
        # A. 原文档解析
        for child in ltpage:
            if isinstance(child, LTChar):
                cur_v = False
                layout = self.layout[ltpage.pageid]
                # ltpage.height 可能是 fig 里面的高度，这里统一用 layout.shape
                h, w = layout.shape
                # 读取当前字符在 layout 中的类别
                cx, cy = np.clip(int(child.x0), 0, w - 1), np.clip(int(child.y0), 0, h - 1)
                cls = layout[cy, cx]
                # 锚定文档中 bullet 的位置
                if child.get_text() == "•":
                    cls = 0
                # 判定当前字符是否属于公式
                if (                                                                                        # 判定当前字符是否属于公式
                    cls == 0                                                                                # 1. 类别为保留区域
                    or (cls == xt_cls and len(sstk[-1].strip()) > 1 and child.size < pstk[-1].size * 0.79)  # 2. 角标字体，有 0.76 的角标和 0.799 的大写，这里用 0.79 取中，同时考虑首字母放大的情况
                    or vflag(child.fontname, child.get_text())                                              # 3. 公式字体
                    or (child.matrix[0] == 0 and child.matrix[3] == 0)                                      # 4. 垂直字体
                ):
                    cur_v = True
                # 判定括号组是否属于公式
                if not cur_v:
                    if vstk and child.get_text() == "(":
                        cur_v = True
                        vbkt += 1
                    if vbkt and child.get_text() == ")":
                        cur_v = True
                        vbkt -= 1
                if (                                                        # 判定当前公式是否结束
                    not cur_v                                               # 1. 当前字符不属于公式
                    or cls != xt_cls                                        # 2. 当前字符与前一个字符不属于同一段落
                    # or (abs(child.x0 - xt.x0) > vmax and cls != 0)        # 3. 段落内换行，可能是一长串斜体的段落，也可能是段内分式换行，这里设个阈值进行区分
                    # 禁止纯公式（代码）段落换行，直到文字开始再重开文字段落，保证只存在两种情况
                    # A. 纯公式（代码）段落（锚定绝对位置）sstk[-1]=="" -> sstk[-1]=="{v*}"
                    # B. 文字开头段落（排版相对位置）sstk[-1]!=""
                    or (sstk[-1] != "" and abs(child.x0 - xt.x0) > vmax)    # 因为 cls==xt_cls==0 一定有 sstk[-1]==""，所以这里不需要再判定 cls!=0
                ):
                    if vstk:
                        if (                                                # 根据公式右侧的文字修正公式的纵向偏移
                            not cur_v                                       # 1. 当前字符不属于公式
                            and cls == xt_cls                               # 2. 当前字符与前一个字符属于同一段落
                            and child.x0 > max([vch.x0 for vch in vstk])    # 3. 当前字符在公式右侧
                        ):
                            vfix = vstk[0].y0 - child.y0
                        if sstk[-1] == "":
                            xt_cls = -1 # 禁止纯公式段落（sstk[-1]=="{v*}"）的后续连接，但是要考虑新字符和后续字符的连接，所以这里修改的是上个字符的类别
                        sstk[-1] += f"{{v{len(var)}}}"
                        var.append(vstk)
                        varl.append(vlstk)
                        varf.append(vfix)
                        vstk = []
                        vlstk = []
                        vfix = 0
                # 当前字符不属于公式或当前字符是公式的第一个字符
                if not vstk:
                    if cls == xt_cls:               # 当前字符与前一个字符属于同一段落
                        if child.x0 > xt.x1 + 1:    # 添加行内空格
                            sstk[-1] += " "
                        elif child.x1 < xt.x0:      # 添加换行空格并标记原文段落存在换行
                            sstk[-1] += " "
                            pstk[-1].brk = True
                    else:                           # 根据当前字符构建一个新的段落
                        sstk.append("")
                        pstk.append(Paragraph(child.y0, child.x0, child.x0, child.x0, child.y0, child.y1, child.size, False))
                if not cur_v:                                               # 文字入栈
                    if (                                                    # 根据当前字符修正段落属性
                        child.size > pstk[-1].size                          # 1. 当前字符比段落字体大
                        or len(sstk[-1].strip()) == 1                       # 2. 当前字符为段落第二个文字（考虑首字母放大的情况）
                    ) and child.get_text() != " ":                          # 3. 当前字符不是空格
                        pstk[-1].y -= child.size - pstk[-1].size            # 修正段落初始纵坐标，假设两个不同大小字符的上边界对齐
                        pstk[-1].size = child.size
                    sstk[-1] += child.get_text()
                else:                                                       # 公式入栈
                    if (                                                    # 根据公式左侧的文字修正公式的纵向偏移
                        not vstk                                            # 1. 当前字符是公式的第一个字符
                        and cls == xt_cls                                   # 2. 当前字符与前一个字符属于同一段落
                        and child.x0 > xt.x0                                # 3. 前一个字符在公式左侧
                    ):
                        vfix = child.y0 - xt.y0
                    vstk.append(child)
                # 更新段落边界，因为段落内换行之后可能是公式开头，所以要在外边处理
                pstk[-1].x0 = min(pstk[-1].x0, child.x0)
                pstk[-1].x1 = max(pstk[-1].x1, child.x1)
                pstk[-1].y0 = min(pstk[-1].y0, child.y0)
                pstk[-1].y1 = max(pstk[-1].y1, child.y1)
                # 更新上一个字符
                xt = child
                xt_cls = cls
            elif isinstance(child, LTFigure):   # 图表
                pass
            elif isinstance(child, LTLine):     # 线条
                layout = self.layout[ltpage.pageid]
                # ltpage.height 可能是 fig 里面的高度，这里统一用 layout.shape
                h, w = layout.shape
                # 读取当前线条在 layout 中的类别
                cx, cy = np.clip(int(child.x0), 0, w - 1), np.clip(int(child.y0), 0, h - 1)
                cls = layout[cy, cx]
                if vstk and cls == xt_cls:      # 公式线条
                    vlstk.append(child)
                else:                           # 全局线条
                    lstk.append(child)
            else:
                pass
        # 处理结尾
        if vstk:    # 公式出栈
            sstk[-1] += f"{{v{len(var)}}}"
            var.append(vstk)
            varl.append(vlstk)
            varf.append(vfix)
        log.debug("\n==========[VSTACK]==========\n")
        for id, v in enumerate(var):  # 计算公式宽度
            l = max([vch.x1 for vch in v]) - v[0].x0
            log.debug(f'< {l:.1f} {v[0].x0:.1f} {v[0].y0:.1f} {v[0].cid} {v[0].fontname} {len(varl[id])} > v{id} = {"".join([ch.get_text() for ch in v])}')
            vlen.append(l)

        ############################################################
        # B. 段落翻译
        log.debug("\n==========[SSTACK]==========\n")

        @retry(wait=wait_fixed(1))
        def worker(s: str):  # 多线程翻译
            if not s.strip() or re.match(r"^\{v\d+\}$", s):  # 空白和公式不翻译
                return s
            try:
                new = self.translator.translate(s)
                return new
            except BaseException as e:
                if log.isEnabledFor(logging.DEBUG):
                    log.exception(e)
                else:
                    log.exception(e, exc_info=False)
                raise e
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.thread
        ) as executor:
            news = list(executor.map(worker, sstk))

        ############################################################
        # C. 新文档排版
        def raw_string(fcur: str, cstk: str):  # 编码字符串
            if fcur == self.noto_name:
                # Apply HarfBuzz shaping for Thai text to get proper glyph IDs
                if (self.text_shaper.enabled and
                    cstk and any(0x0E00 <= ord(ch) <= 0x0E7F for ch in cstk)):

                    try:
                        log.info(f"🇹🇭 GLYPH SHAPING: '{cstk}' with HarfBuzz")

                        # Get font path and shape text
                        font_path = self._get_font_path(fcur)
                        if font_path:
                            # Use a reasonable font size for shaping (doesn't affect glyph IDs)
                            shaped = self.text_shaper.shape_text(cstk, font_path, 12.0)

                            if shaped and shaped.success:
                                # Use HarfBuzz glyph IDs instead of default glyph lookup
                                glyph_codes = []
                                for glyph in shaped.glyphs:
                                    glyph_codes.append("%04x" % glyph.glyph_id)

                                log.info(f"✅ HarfBuzz glyphs: {len(glyph_codes)} glyphs")
                                return "".join(glyph_codes)
                            else:
                                log.debug(f"❌ HarfBuzz shaping failed, using fallback")

                    except Exception as e:
                        log.warning(f"⚠️ Error in glyph shaping: {e}")

                # Fallback to original glyph lookup
                return "".join(["%04x" % self.noto.has_glyph(ord(c)) for c in cstk])

            elif isinstance(self.fontmap[fcur], PDFCIDFont):  # 判断编码长度
                return "".join(["%04x" % ord(c) for c in cstk])
            else:
                return "".join(["%02x" % ord(c) for c in cstk])

        # 根据目标语言获取默认行距
        LANG_LINEHEIGHT_MAP = {
            "zh-cn": 1.4, "zh-tw": 1.4, "zh-hans": 1.4, "zh-hant": 1.4, "zh": 1.4,
            "ja": 1.1, "ko": 1.2, "en": 1.2, "ar": 1.0, "ru": 0.8, "uk": 0.8, "ta": 0.8,
            "th": 1.5  # Increased line spacing for Thai
        }

        # Check for custom line height from environment/config
        target_lang = self.translator.lang_out.lower()
        env_line_height_key = f"LANG_LINEHEIGHT_{target_lang.upper().replace('-', '_')}"
        custom_line_height = ConfigManager.get(env_line_height_key)

        log.info(f"🔍 DEBUG: Checking line height for language '{target_lang}'")
        log.info(f"🔍 DEBUG: Looking for config key: {env_line_height_key}")
        log.info(f"🔍 DEBUG: Config value found: {custom_line_height}")

        if custom_line_height:
            try:
                default_line_height = float(custom_line_height)
                log.info(f"✅ DEBUG: Using custom line height: {default_line_height}")
            except (ValueError, TypeError):
                default_line_height = LANG_LINEHEIGHT_MAP.get(target_lang, 1.1)
                log.warning(f"⚠️  DEBUG: Invalid line height value, using default: {default_line_height}")
        else:
            default_line_height = LANG_LINEHEIGHT_MAP.get(target_lang, 1.1) # 小语种默认1.1
            log.info(f"📝 DEBUG: No custom line height, using default: {default_line_height}")

        # 根据目标语言获取字体大小缩放比例
        LANG_FONTSIZE_SCALE = {
            "th": 0.7,  # Reduce Thai font size to 90%
        }

        # Check for custom font size scale from environment/config
        env_fontsize_key = f"LANG_FONTSIZE_SCALE_{target_lang.upper().replace('-', '_')}"
        custom_font_scale = ConfigManager.get(env_fontsize_key)

        log.info(f"🔍 DEBUG: Checking font scale for language '{target_lang}'")
        log.info(f"🔍 DEBUG: Looking for config key: {env_fontsize_key}")
        log.info(f"🔍 DEBUG: Config value found: {custom_font_scale}")

        if custom_font_scale:
            try:
                font_size_scale = float(custom_font_scale)
                log.info(f"✅ DEBUG: Using custom font scale: {font_size_scale}")
            except (ValueError, TypeError):
                font_size_scale = LANG_FONTSIZE_SCALE.get(target_lang, 1.0)
                log.warning(f"⚠️  DEBUG: Invalid font scale value, using default: {font_size_scale}")
        else:
            font_size_scale = LANG_FONTSIZE_SCALE.get(target_lang, 1.0)
            log.info(f"📝 DEBUG: No custom font scale, using default: {font_size_scale}")

        log.info(f"🎨 DEBUG: Final settings - Font Scale: {font_size_scale}, Line Height: {default_line_height}")

        _x, _y = 0, 0
        ops_list = []

        def gen_op_txt(font, size, x, y, rtxt):
            scaled_size = size * font_size_scale
            if font_size_scale != 1.0:
                log.debug(f"📏 DEBUG: Scaling font from {size:.2f} to {scaled_size:.2f} (scale: {font_size_scale})")

            return f"/{font} {scaled_size:f} Tf 1 0 0 1 {x:f} {y:f} Tm [<{rtxt}>] TJ "

        def gen_op_line(x, y, xlen, ylen, linewidth):
            return f"ET q 1 0 0 1 {x:f} {y:f} cm [] 0 d 0 J {linewidth:f} w 0 0 m {xlen:f} {ylen:f} l S Q BT "

        for id, new in enumerate(news):
            x: float = pstk[id].x                       # 段落初始横坐标
            y: float = pstk[id].y                       # 段落初始纵坐标
            x0: float = pstk[id].x0                     # 段落左边界
            x1: float = pstk[id].x1                     # 段落右边界
            height: float = pstk[id].y1 - pstk[id].y0   # 段落高度
            size: float = pstk[id].size                 # 段落字体大小
            brk: bool = pstk[id].brk                    # 段落换行标记
            cstk: str = ""                              # 当前文字栈
            fcur: str = None                            # 当前字体 ID
            lidx = 0                                    # 记录换行次数
            tx = x
            fcur_ = fcur
            ptr = 0
            log.debug(f"< {y} {x} {x0} {x1} {size} {brk} > {sstk[id]} | {new}")

            ops_vals: list[dict] = []

            while ptr < len(new):
                vy_regex = re.match(
                    r"\{\s*v([\d\s]+)\}", new[ptr:], re.IGNORECASE
                )  # 匹配 {vn} 公式标记
                mod = 0  # 文字修饰符
                if vy_regex:  # 加载公式
                    ptr += len(vy_regex.group(0))
                    try:
                        vid = int(vy_regex.group(1).replace(" ", ""))
                        adv = vlen[vid]
                    except Exception:
                        continue  # 翻译器可能会自动补个越界的公式标记
                    if var[vid][-1].get_text() and unicodedata.category(var[vid][-1].get_text()[0]) in ["Lm", "Mn", "Sk"]:  # 文字修饰符
                        mod = var[vid][-1].width
                else:  # 加载文字 - Process text with complex script support
                    ch = new[ptr]
                    fcur_ = None
                    try:
                        if self.fontmap["tiro"].to_unichr(ord(ch)) == ch:
                            fcur_ = "tiro"  # 默认拉丁字体
                    except Exception:
                        pass
                    if fcur_ is None:
                        fcur_ = self.noto_name  # 默认非拉丁字体

                    # Calculate advancement using scaled font size for proper line width calculation
                    scaled_size_for_width = size * font_size_scale

                    # Try complex text processing for Thai and other complex scripts (temporarily disabled - causes layout issues)
                    if False and fcur_ == self.noto_name and self.text_shaper.enabled and ptr < len(new):
                        # Collect the LONGEST possible text run for optimal shaping
                        text_run = ch
                        lookahead_ptr = ptr + 1

                        # Aggressively collect characters - shape entire sentences when possible
                        # Only stop for: formula markers, font changes, or end of text
                        while lookahead_ptr < len(new):
                            # Check for formula marker
                            if re.match(r"\{\s*v([\d\s]+)\}", new[lookahead_ptr:], re.IGNORECASE):
                                break

                            next_ch = new[lookahead_ptr]
                            next_fcur = None
                            try:
                                if self.fontmap["tiro"].to_unichr(ord(next_ch)) == next_ch:
                                    next_fcur = "tiro"
                            except Exception:
                                pass
                            if next_fcur is None:
                                next_fcur = self.noto_name

                            # Stop if font changes
                            if next_fcur != fcur_:
                                break

                            text_run += next_ch
                            lookahead_ptr += 1

                        # Check if this text run contains complex scripts that need shaping
                        if self.text_shaper._needs_shaping(text_run):
                            # Process the entire run with HarfBuzz - this enables proper contextual shaping
                            glyphs = self._shape_text_run(text_run, fcur_, size, scaled_size_for_width)

                            log.debug(f"🔤 Processing complex script sentence: '{text_run}' ({len(text_run)} chars) -> {len(glyphs)} glyphs")

                            # Generate text operations using cluster-based rendering
                            # Group glyphs by cluster to render complete character units
                            clusters = {}
                            total_advance = 0.0

                            # Group glyphs by cluster
                            for glyph in glyphs:
                                cluster = glyph['cluster']
                                if cluster not in clusters:
                                    clusters[cluster] = {
                                        'chars': '',
                                        'base_advance': 0.0,
                                        'x_offset': 0.0,
                                        'y_offset': 0.0,
                                        'char_indices': []
                                    }

                                char_idx = glyph['char_index']
                                if char_idx < len(text_run):
                                    char = text_run[char_idx]

                                    # Build complete character string for this cluster
                                    if char_idx not in clusters[cluster]['char_indices']:
                                        clusters[cluster]['chars'] += char
                                        clusters[cluster]['char_indices'].append(char_idx)

                                    # Track the main advance (from base characters)
                                    char_category = unicodedata.category(char)
                                    if char_category not in ['Mn', 'Mc', 'Me']:  # Not a combining mark
                                        clusters[cluster]['base_advance'] += glyph['x_advance']

                                    # Use positioning from the first glyph in cluster for offset
                                    if len(clusters[cluster]['char_indices']) == 1:
                                        clusters[cluster]['x_offset'] = glyph['x_offset']
                                        clusters[cluster]['y_offset'] = glyph['y_offset']

                            # Generate one text operation per cluster
                            current_x = x
                            for cluster_id in sorted(clusters.keys()):
                                cluster_data = clusters[cluster_id]

                                if cluster_data['chars']:
                                    # Position the complete cluster
                                    cluster_x = current_x + cluster_data['x_offset']
                                    cluster_y = cluster_data['y_offset']

                                    # Create single text operation for the complete character cluster
                                    ops_vals.append({
                                        "type": OpType.TEXT,
                                        "font": fcur_,
                                        "size": size,
                                        "x": cluster_x,
                                        "dy": cluster_y,
                                        "rtxt": raw_string(fcur_, cluster_data['chars']),
                                        "lidx": lidx
                                    })

                                    log.debug(f"🔤 Cluster {cluster_id}: '{cluster_data['chars']}' at x={cluster_x:.2f}, y_offset={cluster_y:.2f}, advance={cluster_data['base_advance']:.2f}")

                                    # Advance to next cluster position
                                    current_x += cluster_data['base_advance']
                                    total_advance += cluster_data['base_advance']

                            # Update main x position and pointer
                            x = current_x
                            ptr = lookahead_ptr  # Skip past the processed run
                            adv = 0  # No additional advancement needed
                            fcur = fcur_

                            # Clear text buffer since we processed the run directly
                            cstk = ""
                            continue

                    # Standard character processing (fallback or non-complex scripts)
                    if fcur_ == self.noto_name:
                        adv = self.noto.char_lengths(ch, scaled_size_for_width)[0]
                    else:
                        adv = self.fontmap[fcur_].char_width(ord(ch)) * scaled_size_for_width

                    if font_size_scale != 1.0:
                        if fcur_ == self.noto_name:
                            original_adv = self.noto.char_lengths(ch, size)[0]
                        else:
                            original_adv = self.fontmap[fcur_].char_width(ord(ch)) * size
                        log.debug(f"📐 DEBUG: Char '{ch}' width scaled from {original_adv:.2f} to {adv:.2f}")

                    ptr += 1
                if (                                # 输出文字缓冲区
                    fcur_ != fcur                   # 1. 字体更新
                    or vy_regex                     # 2. 插入公式
                    or (adv > 0 and x + adv > x1 + 0.1 * scaled_size_for_width)    # 3. 到达右边界（可能一整行都被符号化，这里需要考虑浮点误差）
                ):
                    if cstk:
                        ops_vals.append({
                            "type": OpType.TEXT,
                            "font": fcur,
                            "size": size,
                            "x": tx,
                            "dy": 0,
                            "rtxt": raw_string(fcur, cstk),
                            "lidx": lidx
                        })
                        cstk = ""
                if brk and x + adv > x1 + 0.1 * size:  # 到达右边界且原文段落存在换行
                    x = x0
                    lidx += 1
                if vy_regex:  # 插入公式
                    fix = 0
                    if fcur is not None:  # 段落内公式修正纵向偏移
                        fix = varf[vid]
                    for vch in var[vid]:  # 排版公式字符
                        vc = chr(vch.cid)
                        ops_vals.append({
                            "type": OpType.TEXT,
                            "font": self.fontid[vch.font],
                            "size": vch.size,
                            "x": x + vch.x0 - var[vid][0].x0,
                            "dy": fix + vch.y0 - var[vid][0].y0,
                            "rtxt": raw_string(self.fontid[vch.font], vc),
                            "lidx": lidx
                        })
                        if log.isEnabledFor(logging.DEBUG):
                            lstk.append(LTLine(0.1, (_x, _y), (x + vch.x0 - var[vid][0].x0, fix + y + vch.y0 - var[vid][0].y0)))
                            _x, _y = x + vch.x0 - var[vid][0].x0, fix + y + vch.y0 - var[vid][0].y0
                    for l in varl[vid]:  # 排版公式线条
                        if l.linewidth < 5:  # hack 有的文档会用粗线条当图片背景
                            ops_vals.append({
                                "type": OpType.LINE,
                                "x": l.pts[0][0] + x - var[vid][0].x0,
                                "dy": l.pts[0][1] + fix - var[vid][0].y0,
                                "linewidth": l.linewidth,
                                "xlen": l.pts[1][0] - l.pts[0][0],
                                "ylen": l.pts[1][1] - l.pts[0][1],
                                "lidx": lidx
                            })
                else:  # 插入文字缓冲区
                    if not cstk:  # 单行开头
                        tx = x
                        if x == x0 and ch == " ":  # 消除段落换行空格
                            adv = 0
                        else:
                            cstk += ch
                    else:
                        cstk += ch
                adv -= mod # 文字修饰符
                fcur = fcur_
                x += adv
                if log.isEnabledFor(logging.DEBUG):
                    lstk.append(LTLine(0.1, (_x, _y), (x, y)))
                    _x, _y = x, y
            # 处理结尾
            if cstk:
                ops_vals.append({
                    "type": OpType.TEXT,
                    "font": fcur,
                    "size": size,
                    "x": tx,
                    "dy": 0,
                    "rtxt": raw_string(fcur, cstk),
                    "lidx": lidx
                })

            line_height = default_line_height
            original_line_height = line_height

            while (lidx + 1) * size * line_height > height and line_height >= 1:
                line_height -= 0.05

            if line_height != original_line_height:
                log.debug(f"📐 DEBUG: Line height auto-adjusted from {original_line_height:.2f} to {line_height:.2f} to fit content")
            else:
                log.debug(f"📐 DEBUG: Using line height: {line_height:.2f}")

            for vals in ops_vals:
                if vals["type"] == OpType.TEXT:
                    ops_list.append(gen_op_txt(vals["font"], vals["size"], vals["x"], vals["dy"] + y - vals["lidx"] * size * line_height, vals["rtxt"]))
                elif vals["type"] == OpType.LINE:
                    ops_list.append(gen_op_line(vals["x"], vals["dy"] + y - vals["lidx"] * size * line_height, vals["xlen"], vals["ylen"], vals["linewidth"]))

        for l in lstk:  # 排版全局线条
            if l.linewidth < 5:  # hack 有的文档会用粗线条当图片背景
                ops_list.append(gen_op_line(l.pts[0][0], l.pts[0][1], l.pts[1][0] - l.pts[0][0], l.pts[1][1] - l.pts[0][1], l.linewidth))

        ops = f"BT {''.join(ops_list)}ET "
        return ops


class OpType(Enum):
    TEXT = "text"
    LINE = "line"
