"""
src/infrastructure/ai/rag/pdf_parser.py

PDF 파싱 & 청킹 모듈
- PyMuPDF(fitz) 기반 텍스트 추출
- 오버랩 슬라이딩 윈도우 청킹
- SHA256 해시 기반 중복 파일 탐지
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False
    logger.error(
        "PyMuPDF 미설치. 'poetry add pymupdf' 실행 필요."
    )


# ──────────────────────────────────────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """파싱된 청크 단위"""
    chunk_index: int
    page_number: int
    content:     str
    char_start:  int = 0
    char_end:    int = 0

    @property
    def token_count(self) -> int:
        """대략적인 토큰 수 (한국어 고려: 글자 수 / 1.5)"""
        return int(len(self.content) / 1.5)


@dataclass
class ParsedPDF:
    """PDF 파싱 결과"""
    filename:   str
    file_hash:  str
    file_size:  int
    page_count: int
    chunks:     List[Chunk] = field(default_factory=list)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


# ──────────────────────────────────────────────────────────────────────────────
# PDF 파서
# ──────────────────────────────────────────────────────────────────────────────

class PDFParser:
    """
    PDF → 텍스트 추출 → 오버랩 청킹

    Args:
        chunk_size:    청크당 최대 문자 수 (기본 600)
                       PLC 매뉴얼은 전문 용어가 많아 약간 크게 설정
        chunk_overlap: 청크 간 오버랩 문자 수 (기본 120) - 문맥 유지
    """

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 120):
        if not _FITZ_AVAILABLE:
            raise ImportError("PyMuPDF를 설치해야 합니다: poetry add pymupdf")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap은 chunk_size보다 작아야 합니다.")

        self.chunk_size    = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse(self, file_bytes: bytes, filename: str) -> ParsedPDF:
        """
        PDF 바이트 → ParsedPDF 반환

        Args:
            file_bytes: PDF raw bytes (FastAPI UploadFile.read())
            filename:   원본 파일명
        """
        file_hash = self._sha256(file_bytes)
        file_size = len(file_bytes)

        pages_text: list[tuple[int, str]] = []

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = doc.page_count
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                text = self._clean_text(text)
                if text:
                    pages_text.append((page_num + 1, text))  # 1-indexed

        chunks = self._build_chunks(pages_text)

        logger.info(
            "PDF 파싱 완료 | 파일=%s | 페이지=%d | 청크=%d",
            filename, page_count, len(chunks),
        )

        return ParsedPDF(
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            page_count=page_count,
            chunks=chunks,
        )

    # ── 내부 메서드 ─────────────────────────────────────────────────────────

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _clean_text(text: str) -> str:
        """PDF 추출 텍스트 정제"""
        # 연속 공백/탭 → 단일 공백
        text = re.sub(r"[ \t]+", " ", text)
        # 3개 이상 연속 개행 → 2개
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 하이픈 개행 합성 (단어 분리 복원)
        text = re.sub(r"-\n(\w)", r"\1", text)
        return text.strip()

    def _build_chunks(
        self, pages_text: list[tuple[int, str]]
    ) -> list[Chunk]:
        """페이지별 텍스트를 전역 청크 목록으로 변환"""
        chunks: list[Chunk] = []
        chunk_index = 0

        for page_num, text in pages_text:
            for chunk in self._split_page(text, page_num):
                chunk.chunk_index = chunk_index
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    def _split_page(self, text: str, page_num: int) -> list[Chunk]:
        """단일 페이지 텍스트를 chunk_size 기준으로 슬라이딩 분할"""
        results: list[Chunk] = []
        total = len(text)
        start = 0

        while start < total:
            end = min(start + self.chunk_size, total)

            # 단어/문장 경계에서 자르기 (문장 > 공백 순 우선)
            if end < total:
                # 문장 끝(. ! ?)에서 자르기 우선
                sentence_end = max(
                    text.rfind(".", start, end),
                    text.rfind("!", start, end),
                    text.rfind("?", start, end),
                    text.rfind("\n", start, end),
                )
                if sentence_end > start + self.chunk_size // 2:
                    end = sentence_end + 1
                else:
                    # 단어 경계
                    word_end = text.rfind(" ", start, end)
                    if word_end > start:
                        end = word_end

            content = text[start:end].strip()
            if content:
                results.append(
                    Chunk(
                        chunk_index=0,     # 추후 전역 인덱스로 덮어씀
                        page_number=page_num,
                        content=content,
                        char_start=start,
                        char_end=end,
                    )
                )

            # 다음 시작 위치 (오버랩 적용)
            next_start = end - self.chunk_overlap
            if next_start <= start:
                next_start = start + 1
            start = next_start

        return results
