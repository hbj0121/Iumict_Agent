"""
src/core/services/rag_service.py

RAG 비즈니스 서비스 (core/services 레이어)
- PDF 인제스트 파이프라인: 파싱 → 임베딩 → 저장
- 질의 파이프라인: 임베딩 → 검색 → LLM 답변
- 문서 관리: 목록 / 삭제

infrastructure 레이어(pdf_parser, embedder, vector_store, llm_client)를
orchestration하는 비즈니스 로직 계층.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.config.settings import get_settings
from src.infrastructure.ai.llm_client import LLMClient
from src.infrastructure.ai.rag.embedder import EmbeddingClient
from src.infrastructure.ai.rag.pdf_parser import PDFParser
from src.infrastructure.ai.rag.vector_store import SearchResult, VectorStore

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 결과 데이터 클래스 (API 레이어로 반환)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class IngestResult:
    status:      str          # "created" | "duplicate"
    document_id: int
    filename:    str
    page_count:  int
    chunk_count: int
    message:     str = ""


@dataclass
class RAGSource:
    filename:    str
    page_number: int
    content:     str          # 미리보기 (300자)
    score:       float


@dataclass
class RAGAnswer:
    answer:        str
    sources:       List[RAGSource] = field(default_factory=list)
    found_context: bool = False
    latency_ms:    int  = 0


# ──────────────────────────────────────────────────────────────────────────────
# RAG 서비스
# ──────────────────────────────────────────────────────────────────────────────

class RAGService:
    """
    RAG 전체 파이프라인 서비스.

    FastAPI lifespan에서 싱글톤으로 생성:
        rag_service = RAGService()
        await rag_service.startup()
        app.state.rag = rag_service
    """

    def __init__(self):
        s = get_settings()
        self._parser    = PDFParser(
            chunk_size=s.RAG_CHUNK_SIZE,
            chunk_overlap=s.RAG_CHUNK_OVERLAP,
        )
        self._embedder  = EmbeddingClient()
        self._store     = VectorStore()
        self._llm       = LLMClient()
        self._settings  = s

    async def startup(self) -> None:
        await self._store.connect()
        logger.info("RAGService 시작 완료")

    async def shutdown(self) -> None:
        await self._store.disconnect()
        logger.info("RAGService 종료")

    # ── PDF 인제스트 ──────────────────────────────────────────────────────

    async def ingest_pdf(
        self,
        file_bytes:  bytes,
        filename:    str,
        description: Optional[str] = None,
        tags:        Optional[List[str]] = None,
    ) -> IngestResult:
        """
        PDF 업로드 → 파싱 → 임베딩 → 저장 원스탑 파이프라인.

        중복 파일(SHA256 해시 기준)은 재처리 없이 즉시 반환.
        """
        # 1) 파싱
        parsed = self._parser.parse(file_bytes, filename)

        # 2) 중복 체크
        existing_id = await self._store.find_by_hash(parsed.file_hash)
        if existing_id:
            logger.info("중복 파일 감지: %s → doc_id=%d", filename, existing_id)
            return IngestResult(
                status="duplicate",
                document_id=existing_id,
                filename=filename,
                page_count=parsed.page_count,
                chunk_count=parsed.chunk_count,
                message="동일한 파일이 이미 인덱싱되어 있습니다.",
            )

        if not parsed.chunks:
            raise ValueError(
                f"PDF에서 텍스트를 추출할 수 없습니다: {filename}\n"
                "스캔 PDF이거나 텍스트 레이어가 없는 파일일 수 있습니다."
            )

        # 3) 청크 임베딩 (배치 처리)
        texts      = [c.content for c in parsed.chunks]
        embeddings = await self._embedder.embed_texts(texts)

        # 4) DB 저장
        doc_id = await self._store.save_document(
            parsed, embeddings,
            description=description,
            tags=tags,
        )

        return IngestResult(
            status="created",
            document_id=doc_id,
            filename=filename,
            page_count=parsed.page_count,
            chunk_count=parsed.chunk_count,
            message=f"'{filename}' 인덱싱 완료 ({parsed.chunk_count}개 청크)",
        )

    # ── RAG 질의 ─────────────────────────────────────────────────────────

    async def query(
        self,
        question:     str,
        document_ids: Optional[List[int]] = None,
        top_k:        Optional[int]        = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> RAGAnswer:
        """
        질문 → 관련 청크 검색 → LLM 답변 생성.

        Args:
            question:     사용자 질문
            document_ids: 검색 대상 문서 ID 제한 (None이면 전체)
            top_k:        반환 청크 수 (None이면 settings 기본값)
            chat_history: 멀티턴 대화 히스토리

        Returns:
            RAGAnswer (answer, sources, found_context, latency_ms)
        """
        s     = self._settings
        top_k = top_k or s.RAG_TOP_K
        t0    = time.monotonic()

        # 1) 쿼리 임베딩
        query_vec = await self._embedder.embed_query(question)

        # 2) 유사도 검색
        results: List[SearchResult] = await self._store.similarity_search(
            query_embedding=query_vec,
            top_k=top_k,
            document_ids=document_ids,
            score_threshold=s.RAG_SCORE_THRESHOLD,
        )

        latency_ms = int((time.monotonic() - t0) * 1000)

        # 관련 문서 없음
        if not results:
            await self._store.log_query(
                question=question,
                doc_ids=document_ids,
                chunks_found=0,
                top_score=None,
                latency_ms=latency_ms,
            )
            return RAGAnswer(
                answer=(
                    "📭 업로드된 문서에서 질문과 관련된 내용을 찾지 못했습니다.\n\n"
                    "**가능한 원인:**\n"
                    "- 관련 PDF가 아직 업로드되지 않았습니다\n"
                    "- 유사도 임계값이 너무 높습니다 (현재: "
                    f"{s.RAG_SCORE_THRESHOLD})\n"
                    "- 질문을 다른 표현으로 시도해보세요"
                ),
                sources=[],
                found_context=False,
                latency_ms=latency_ms,
            )

        # 3) LLM 프롬프트 구성 및 답변 생성
        context = self._build_context(results)
        answer  = await self._generate_answer(
            question=question,
            context=context,
            chat_history=chat_history or [],
        )

        latency_ms = int((time.monotonic() - t0) * 1000)

        # 4) 질의 로그
        await self._store.log_query(
            question=question,
            doc_ids=document_ids,
            chunks_found=len(results),
            top_score=max(r.score for r in results),
            latency_ms=latency_ms,
        )

        sources = [
            RAGSource(
                filename=r.filename,
                page_number=r.page_number,
                content=r.content[:300] + ("..." if len(r.content) > 300 else ""),
                score=round(r.score, 4),
            )
            for r in results
        ]

        return RAGAnswer(
            answer=answer,
            sources=sources,
            found_context=True,
            latency_ms=latency_ms,
        )

    # ── 문서 관리 ─────────────────────────────────────────────────────────

    async def list_documents(self) -> List[Dict[str, Any]]:
        docs = await self._store.list_documents()
        # datetime 직렬화
        for doc in docs:
            if hasattr(doc.get("uploaded_at"), "isoformat"):
                doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        return docs

    async def delete_document(self, document_id: int) -> bool:
        return await self._store.delete_document(document_id)

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_context(results: List[SearchResult]) -> str:
        """검색 결과 → LLM 프롬프트용 컨텍스트 문자열"""
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[참고 {i}: {r.filename} {r.page_number}페이지 "
                f"(유사도 {r.score:.0%})]\n{r.content}"
            )
        return "\n\n" + ("─" * 50) + "\n\n".join(parts)

    async def _generate_answer(
        self,
        question:     str,
        context:      str,
        chat_history: List[Dict[str, str]],
    ) -> str:
        """LLM으로 RAG 기반 답변 생성"""
        system_prompt = (
            "당신은 스마트 배수지(Smart Water Reservoir) 관리 시스템의 "
            "전문 AI 어시스턴트입니다.\n"
            "아래 '참고 문서' 내용을 기반으로만 질문에 답변하세요.\n"
            "문서에 없는 내용은 '문서에 해당 내용이 없습니다'라고 명확히 밝히세요.\n"
            "답변에는 반드시 출처(파일명, 페이지)를 포함하세요.\n"
            "답변은 한국어로 작성하고 명확하고 실용적으로 서술하세요.\n\n"
            f"참고 문서:\n{context}"
        )

        messages = [{"role": "system", "content": system_prompt}]

        # 멀티턴: 최근 6턴 (12개 메시지) 유지
        for turn in chat_history[-12:]:
            if turn.get("role") in ("user", "assistant"):
                messages.append(turn)

        messages.append({"role": "user", "content": question})

        return await self._llm.chat(
            messages=messages,
            max_tokens=1024,
            temperature=0.1,    # RAG는 낮은 temperature로 사실 기반 답변
        )
