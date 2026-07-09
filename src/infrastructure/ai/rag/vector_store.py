"""
src/infrastructure/ai/rag/vector_store.py

pgvector 기반 벡터 저장소 (Repository 패턴)
- asyncpg 비동기 커넥션 풀
- HNSW 인덱스 기반 코사인 유사도 검색
- 문서 CRUD
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
from pgvector.asyncpg import register_vector

from src.config.settings import get_settings
from src.infrastructure.ai.rag.pdf_parser import Chunk, ParsedPDF

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 결과 데이터 타입
# ──────────────────────────────────────────────────────────────────────────────

class SearchResult:
    """유사도 검색 단일 결과"""
    __slots__ = ("content", "page_number", "filename",
                 "document_id", "chunk_index", "score")

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return {s: getattr(self, s) for s in self.__slots__}


# ──────────────────────────────────────────────────────────────────────────────
# 벡터 스토어
# ──────────────────────────────────────────────────────────────────────────────

class VectorStore:
    """
    pgvector 기반 문서/청크 저장소.

    FastAPI lifespan에서 싱글톤으로 생성 후 의존성으로 주입.
    """

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._settings = get_settings()

    # ── 라이프사이클 ──────────────────────────────────────────────────────

    async def connect(self) -> None:
        """DB 커넥션 풀 초기화 (앱 startup 시 1회 호출)"""
        self._pool = await asyncpg.create_pool(
            self._settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            init=self._register_vector,
        )
        logger.info("VectorStore DB 커넥션 풀 연결 완료")

    async def disconnect(self) -> None:
        """커넥션 풀 해제 (앱 shutdown 시 호출)"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("VectorStore DB 커넥션 풀 해제")

    @staticmethod
    async def _register_vector(conn: asyncpg.Connection) -> None:
        """각 커넥션에 pgvector 타입 등록"""
        await register_vector(conn)

    def _pool_required(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "VectorStore.connect()를 먼저 호출해야 합니다. "
                "FastAPI lifespan 설정을 확인하세요."
            )
        return self._pool

    # ── 문서 저장 ─────────────────────────────────────────────────────────

    async def find_by_hash(self, file_hash: str) -> Optional[int]:
        """동일 파일 존재 여부 확인 → document_id 또는 None"""
        pool = self._pool_required()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM rag_documents "
                "WHERE file_hash = $1 AND is_active = TRUE",
                file_hash,
            )
        return row["id"] if row else None

    async def save_document(
        self,
        parsed: ParsedPDF,
        embeddings: List[List[float]],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """
        ParsedPDF + 임베딩을 트랜잭션으로 저장.

        Returns:
            생성된 document_id
        """
        if len(parsed.chunks) != len(embeddings):
            raise ValueError(
                f"청크 수({len(parsed.chunks)})와 임베딩 수({len(embeddings)}) 불일치"
            )

        pool = self._pool_required()

        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1) 문서 메타데이터
                doc_id: int = await conn.fetchval(
                    """
                    INSERT INTO rag_documents
                        (filename, file_hash, file_size, page_count,
                         chunk_count, description, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    parsed.filename,
                    parsed.file_hash,
                    parsed.file_size,
                    parsed.page_count,
                    parsed.chunk_count,
                    description,
                    tags or [],
                )

                # 2) 청크 + 임베딩 배치 INSERT
                rows = [
                    (
                        doc_id,
                        chunk.chunk_index,
                        chunk.page_number,
                        chunk.char_start,
                        chunk.char_end,
                        chunk.content,
                        chunk.token_count,
                        embeddings[i],
                    )
                    for i, chunk in enumerate(parsed.chunks)
                ]

                await conn.executemany(
                    """
                    INSERT INTO rag_chunks
                        (document_id, chunk_index, page_number,
                         char_start, char_end, content, token_count, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    rows,
                )

        logger.info(
            "문서 저장 완료: doc_id=%d | 파일=%s | 청크=%d개",
            doc_id, parsed.filename, len(parsed.chunks),
        )
        return doc_id

    # ── 벡터 검색 ─────────────────────────────────────────────────────────

    async def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_ids: Optional[List[int]] = None,
        score_threshold: float = 0.25,
    ) -> List[SearchResult]:
        """
        코사인 유사도 기반 청크 검색.

        Args:
            query_embedding:  쿼리 임베딩 벡터
            top_k:            반환할 최대 결과 수
            document_ids:     특정 문서로 범위 제한 (None이면 전체)
            score_threshold:  최소 유사도 (0~1)

        Returns:
            유사도 내림차순 SearchResult 목록
        """
        pool = self._pool_required()

        # document_ids 필터 조건 동적 구성
        if document_ids:
            filter_sql = "AND c.document_id = ANY($3::int[])"
            params = [query_embedding, top_k, document_ids]
        else:
            filter_sql = ""
            params = [query_embedding, top_k]

        sql = f"""
            SELECT
                c.content,
                c.page_number,
                c.chunk_index,
                c.document_id,
                d.filename,
                1 - (c.embedding <=> $1::vector) AS score
            FROM rag_chunks  c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE d.is_active = TRUE
              {filter_sql}
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = [
            SearchResult(
                content=row["content"],
                page_number=row["page_number"],
                filename=row["filename"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                score=float(row["score"]),
            )
            for row in rows
            if float(row["score"]) >= score_threshold
        ]

        logger.debug("유사도 검색 완료: %d개 결과 (top_k=%d)", len(results), top_k)
        return results

    # ── 문서 관리 ─────────────────────────────────────────────────────────

    async def list_documents(self) -> List[Dict[str, Any]]:
        """활성 문서 목록 조회"""
        pool = self._pool_required()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id, filename, file_size, page_count,
                    chunk_count, description, tags,
                    uploaded_at
                FROM rag_documents
                WHERE is_active = TRUE
                ORDER BY uploaded_at DESC
                """
            )
        return [dict(row) for row in rows]

    async def delete_document(self, document_id: int) -> bool:
        """소프트 삭제 (is_active = FALSE)"""
        pool = self._pool_required()
        async with pool.acquire() as conn:
            tag = await conn.execute(
                "UPDATE rag_documents SET is_active = FALSE WHERE id = $1",
                document_id,
            )
        success = tag.split()[-1] != "0"
        if success:
            logger.info("문서 삭제: doc_id=%d", document_id)
        return success

    async def log_query(
        self,
        question: str,
        doc_ids: Optional[List[int]],
        chunks_found: int,
        top_score: Optional[float],
        latency_ms: int,
    ) -> None:
        """RAG 질의 로그 저장 (선택적, 오류 무시)"""
        pool = self._pool_required()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO rag_query_logs
                        (question, doc_ids_used, chunks_found, top_score, latency_ms)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    question,
                    doc_ids or [],
                    chunks_found,
                    top_score,
                    latency_ms,
                )
        except Exception as e:
            logger.warning("질의 로그 저장 실패 (무시): %s", e)
