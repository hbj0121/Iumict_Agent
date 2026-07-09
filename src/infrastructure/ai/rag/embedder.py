"""
src/infrastructure/ai/rag/embedder.py

임베딩 생성 클라이언트
- LM Studio 로컬 임베딩 모델 (nomic-embed-text, 768차원) 기본 사용
- settings.py의 EMBEDDING_PROVIDER에 따라 OpenAI로 전환 가능
- 배치 처리로 API 호출 최소화
"""
from __future__ import annotations

import logging
from typing import List

import httpx

# settings.py에서 중앙 설정 가져옴
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    텍스트 → 임베딩 벡터 변환 클라이언트.

    settings.py의 값으로 동작:
        EMBEDDING_PROVIDER : "lmstudio" | "openai"
        EMBEDDING_MODEL    : 모델 식별자
        EMBEDDING_DIM      : 벡터 차원수
        LM_STUDIO_BASE_URL : LM Studio API 주소
        OPENAI_API_KEY     : OpenAI 사용 시
    """

    def __init__(self):
        self._settings = get_settings()

    # ── 공개 인터페이스 ────────────────────────────────────────────────────

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        텍스트 배치 임베딩.

        Args:
            texts: 임베딩할 텍스트 목록

        Returns:
            각 텍스트에 대응하는 float 벡터 목록
        """
        if not texts:
            return []

        s = self._settings
        if s.EMBEDDING_PROVIDER == "openai":
            return await self._call_openai(texts)
        return await self._call_lmstudio(texts)

    async def embed_query(self, query: str) -> List[float]:
        """단일 쿼리 임베딩 (검색 시 사용)"""
        results = await self.embed_texts([query])
        return results[0] if results else []

    @property
    def dimension(self) -> int:
        return self._settings.EMBEDDING_DIM

    # ── LM Studio ─────────────────────────────────────────────────────────

    async def _call_lmstudio(self, texts: List[str]) -> List[List[float]]:
        s = self._settings
        url = f"{s.LM_STUDIO_BASE_URL}/embeddings"

        payload = {
            "model": s.EMBEDDING_MODEL,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            embeddings = [item["embedding"] for item in data["data"]]
            logger.debug(
                "LM Studio 임베딩 완료: %d개, 차원=%d",
                len(embeddings), len(embeddings[0]),
            )
            return embeddings

        except httpx.ConnectError as e:
            logger.error(
                "LM Studio 연결 실패 (%s). "
                "LM Studio를 실행하고 임베딩 모델(nomic-embed-text)을 로드하세요.",
                url,
            )
            raise ConnectionError(
                f"LM Studio 임베딩 서버에 연결할 수 없습니다: {url}"
            ) from e

    # ── OpenAI ────────────────────────────────────────────────────────────

    async def _call_openai(self, texts: List[str]) -> List[List[float]]:
        s = self._settings
        if not s.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

        headers = {
            "Authorization": f"Bearer {s.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": s.EMBEDDING_MODEL or "text-embedding-3-small",
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        embeddings = [item["embedding"] for item in data["data"]]
        logger.debug("OpenAI 임베딩 완료: %d개", len(embeddings))
        return embeddings
