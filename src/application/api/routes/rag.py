"""
src/application/api/routes/rag.py

PDF RAG FastAPI 라우터
- 의존성 주입: app.state.rag (RAGService 싱글톤)
- 엔드포인트: upload / query / documents / delete
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from src.core.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG - 문서 검색"])

# ── 의존성 헬퍼 ───────────────────────────────────────────────────────────────

def _rag(request: Request) -> RAGService:
    """app.state.rag에서 RAGService 싱글톤을 꺼냄"""
    svc: RAGService = getattr(request.app.state, "rag", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAGService가 초기화되지 않았습니다.",
        )
    return svc


# ── 스키마 ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question:     str                         = Field(..., min_length=1, max_length=1000)
    document_ids: Optional[List[int]]         = Field(None, description="검색 대상 문서 ID (None=전체)")
    top_k:        int                         = Field(5, ge=1, le=20)
    chat_history: Optional[List[dict]]        = Field(None, description="이전 대화 히스토리")


class SourceInfo(BaseModel):
    filename:    str
    page_number: int
    content:     str
    score:       float


class QueryResponse(BaseModel):
    answer:        str
    sources:       List[SourceInfo]
    found_context: bool
    latency_ms:    int


class UploadResponse(BaseModel):
    status:      str   # "created" | "duplicate"
    document_id: int
    filename:    str
    page_count:  int
    chunk_count: int
    message:     str


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="PDF 업로드 & 인덱싱",
    description=(
        "PDF 파일을 업로드하고 벡터 인덱스를 생성합니다.\n"
        "- SHA256 해시 기반 중복 업로드 방지\n"
        "- 최대 파일 크기: 50MB\n"
        "- 중복 파일이면 200 OK 반환 (201 아님)"
    ),
)
async def upload_pdf(
    request:     Request,
    file:        UploadFile = File(..., description="PDF 파일"),
    description: Optional[str] = None,
    tags:        Optional[str] = None,   # 콤마 구분 문자열 → 리스트 변환
):
    # 파일 형식 검증
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF 파일(.pdf)만 업로드 가능합니다.",
        )

    file_bytes = await file.read()

    # 파일 크기 제한 (50MB)
    MAX_BYTES = 50 * 1024 * 1024
    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기 제한 초과 (최대 50MB, 현재 {len(file_bytes) // 1024 // 1024}MB)",
        )

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    try:
        result = await _rag(request).ingest_pdf(
            file_bytes=file_bytes,
            filename=file.filename,
            description=description,
            tags=tag_list or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception("PDF 업로드 처리 중 예외")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # 중복이면 200, 신규이면 201
    http_status = status.HTTP_200_OK if result.status == "duplicate" else status.HTTP_201_CREATED
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=result.__dict__,
        status_code=http_status,
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="RAG 질의응답",
    description="질문을 입력하면 업로드된 문서를 검색하여 LLM이 답변을 생성합니다.",
)
async def query_rag(request: Request, body: QueryRequest):
    try:
        result = await _rag(request).query(
            question=body.question,
            document_ids=body.document_ids,
            top_k=body.top_k,
            chat_history=body.chat_history,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.exception("RAG 질의 처리 중 예외")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return QueryResponse(
        answer=result.answer,
        sources=[s.__dict__ for s in result.sources],
        found_context=result.found_context,
        latency_ms=result.latency_ms,
    )


@router.get(
    "/documents",
    summary="업로드된 문서 목록",
)
async def list_documents(request: Request):
    """인덱싱된 PDF 문서 목록을 반환합니다."""
    return await _rag(request).list_documents()


@router.delete(
    "/documents/{document_id}",
    summary="문서 삭제",
    status_code=status.HTTP_200_OK,
)
async def delete_document(request: Request, document_id: int):
    """특정 문서와 관련 청크를 소프트 삭제합니다."""
    deleted = await _rag(request).delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문서 ID {document_id}를 찾을 수 없습니다.",
        )
    return {"message": f"문서 {document_id} 삭제 완료"}
