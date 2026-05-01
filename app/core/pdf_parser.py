"""
PDF 解析器 - 从 PDF 文件提取文本并分块
"""

import os
import re
import hashlib
from typing import Optional
import fitz  # PyMuPDF


class PDFParser:
    """PDF 解析器，按章节/页面分块"""

    def __init__(self):
        self.chunk_size = 500  # 字符数阈值

    def extract_pages(self, pdf_path: str) -> list[dict]:
        """
        提取 PDF 每页文本
        Returns: [{page_num, text, title}, ...]
        """
        pages = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                # 清理空白字符
                text = self._clean_text(text)
                if text.strip():
                    pages.append({
                        "page_num": page_num + 1,
                        "text": text,
                        "title": self._extract_page_title(page, text)
                    })
            doc.close()
        except Exception as e:
            print(f"PDF 读取失败 {pdf_path}: {e}")
        return pages

    def _extract_page_title(self, page, text: str) -> Optional[str]:
        """尝试从页面提取标题（第一个大字号文本行）"""
        try:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            size = span.get("size", 0)
                            font = span.get("font", "")
                            # 大字号或加粗可能是标题
                            if size > 14 or "bold" in font.lower():
                                title = span.get("text", "").strip()
                                if title and len(title) < 100:
                                    return title
        except:
            pass
        # fallback: 第一行
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) < 100:
                return line
        return None

    def _clean_text(self, text: str) -> str:
        """清理 PDF 提取的文本"""
        if not text:
            return ""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()

    def chunk_by_size(self, pages: list[dict]) -> list[dict]:
        """
        按字符数阈值分块（简单策略）
        合并多页直到达到 chunk_size
        """
        chunks = []
        current_chunk = {"text": "", "page_start": 1, "page_end": 1}
        current_text = ""

        for p in pages:
            text = p["text"]
            if not text.strip():
                continue

            # 如果加上这页会超过阈值，且当前 chunk 不为空
            if len(current_text) + len(text) > self.chunk_size and current_text:
                # 保存当前 chunk
                current_chunk["text"] = current_text.strip()
                if current_chunk["text"]:
                    chunks.append(current_chunk)

                # 开始新 chunk
                current_chunk = {
                    "text": text[:self.chunk_size],
                    "page_start": p["page_num"],
                    "page_end": p["page_num"]
                }
                current_text = text[:self.chunk_size]
            else:
                # 合并到当前 chunk
                if current_text:
                    current_text += "\n"
                current_text += text
                current_chunk["page_end"] = p["page_num"]

        # 保存最后一个 chunk
        if current_text.strip():
            current_chunk["text"] = current_text.strip()
            chunks.append(current_chunk)

        return chunks

    def chunk_by_headings(self, pages: list[dict]) -> list[dict]:
        """
        尝试按标题章节分块（更智能）
        识别大字号或特定格式的标题行来切分
        """
        chunks = []
        current_chunk_lines = []
        current_page_start = 1

        for p in pages:
            lines = p["text"].split('\n')
            page_start = p["page_num"]

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 检测标题行（短行、大字号、或以特定格式开头）
                is_heading = self._is_heading_line(line)

                if is_heading and current_chunk_lines:
                    # 保存当前 chunk
                    text = '\n'.join(current_chunk_lines).strip()
                    if text:
                        chunks.append({
                            "text": text,
                            "page_start": current_page_start,
                            "page_end": page_start - 1
                        })
                    current_chunk_lines = []
                    current_page_start = page_start

                current_chunk_lines.append(line)

        # 保存最后一个 chunk
        if current_chunk_lines:
            text = '\n'.join(current_chunk_lines).strip()
            if text:
                chunks.append({
                    "text": text,
                    "page_start": current_page_start,
                    "page_end": pages[-1]["page_num"] if pages else 1
                })

        return chunks

    def _is_heading_line(self, line: str) -> bool:
        """判断是否为章节标题行"""
        # 短行（通常是标题特征）
        if len(line) > 60 or len(line) < 3:
            return False

        # 以数字开头（1. 2.3.1 等）
        if re.match(r'^\d+[\.\、]', line):
            return True

        # 全大写或特定模式
        if line.isupper() and len(line) > 5:
            return True

        # 包含"第X章"、"第X节"等
        if re.search(r'第[一二三四五六七八九十\d]+[章节部分篇]', line):
            return True

        # 以特定符号结尾（常见于目录标题）
        if line.endswith('：') or line.endswith(':'):
            return True

        return False

    def parse_file(self, pdf_path: str, use_heading_chunk: bool = False) -> list[dict]:
        """
        解析 PDF 文件，返回 chunk 列表
        use_heading_chunk: True=按标题分块，False=按字符数分块
        """
        pages = self.extract_pages(pdf_path)
        if not pages:
            return []

        if use_heading_chunk:
            chunks = self.chunk_by_headings(pages)
        else:
            chunks = self.chunk_by_size(pages)

        # 生成 chunk ID
        for i, chunk in enumerate(chunks):
            chunk_id = self._compute_chunk_id(pdf_path, i)
            chunk["chunk_index"] = i
            chunk["chunk_id"] = chunk_id

        return chunks

    def _compute_chunk_id(self, pdf_path: str, index: int) -> str:
        """计算 chunk ID"""
        base = f"{pdf_path}-{index}"
        return hashlib.md5(base.encode()).hexdigest()[:16]


def find_pdf_files(directory: str) -> list[str]:
    """
    递归查找目录下所有 PDF 文件
    """
    pdfs = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith('.pdf'):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        parser = PDFParser()

        if os.path.isdir(path):
            pdfs = find_pdf_files(path)
            print(f"找到 {len(pdfs)} 个 PDF 文件:")
            for p in pdfs:
                print(f"  {p}")
        elif os.path.isfile(path):
            chunks = parser.parse_file(path)
            print(f"解析成功，共 {len(chunks)} 个 chunk:")
            for c in chunks[:3]:
                print(f"  [{c['page_start']}-{c['page_end']}] {c['text'][:80]}...")
        else:
            print(f"路径不存在: {path}")