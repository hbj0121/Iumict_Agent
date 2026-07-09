"""
src/infrastructure/ai/llm_client.py

LLM 호출 클라이언트 (LM Studio / OpenAI 호환)
- RAG 답변 생성, 일반 챗봇 등 여러 서비스에서 공용 사용
- 스트리밍 / 논-스트리밍 모두 지원
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LM Studio(OpenAI 호환) LLM 클라이언트.

    싱글톤으로 생성 후 여러 서비스에서 공유.
    """

    def __init__(self):
        self._s = get_settings()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str:
        """
        LLM chat completion (non-streaming).

        Args:
            messages:    [{"role": "system"|"user"|"assistant", "content": str}]
            max_tokens:  최대 출력 토큰 수
            temperature: 생성 다양성 (RAG는 0.1 권장)

        Returns:
            LLM 응답 텍스트
        """
        url = f"{self._s.LM_STUDIO_BASE_URL}/chat/completions"
        payload = {
            "model":       self._s.LLM_MODEL,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "stream":      False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            return data["choices"][0]["message"]["content"].strip()

        except httpx.ConnectError:
            msg = (
                f"⚠️ LLM 서버 연결 실패 ({url})\n"
                "LM Studio가 실행 중이고 모델이 로드되어 있는지 확인하세요."
            )
            logger.error(msg)
            return msg

        except httpx.HTTPStatusError as e:
            logger.error("LLM HTTP 오류: %s", e)
            return f"⚠️ LLM 응답 오류: {e.response.status_code}"

        except Exception as e:
            logger.exception("LLM 호출 중 예외")
            return f"⚠️ LLM 처리 오류: {str(e)}"

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        LLM chat completion (streaming).

        Yields:
            텍스트 델타 조각 (Server-Sent Events 파싱)
        """
        url = f"{self._s.LM_STUDIO_BASE_URL}/chat/completions"
        payload = {
            "model":       self._s.LLM_MODEL,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "stream":      True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            import json
                            delta = json.loads(chunk)
                            content = (
                                delta.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if content:
                                yield content
                        except Exception:
                            continue
