"""
src/application/ui/pages/rag_page.py

PDF RAG Streamlit 페이지 컴포넌트.

app.py에서 호출:
    from src.application.ui.pages.rag_page import render_rag_page
    render_rag_page()

또는 pages/ 폴더에 두면 Streamlit 멀티페이지로 자동 인식.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import httpx
import streamlit as st

# settings에서 API 주소 가져오기 (직접 환경변수로도 대체 가능)
try:
    from src.config.settings import get_settings
    _API_BASE = get_settings().API_BASE_URL
except Exception:
    _API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_RAG_URL = f"{_API_BASE}/rag"
_TIMEOUT = 120.0


# ══════════════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════════════

def render_rag_page() -> None:
    """RAG 페이지 전체 렌더 (app.py에서 호출)"""
    st.title("📚 문서 기반 AI 검색 (RAG)")
    st.caption(
        "PLC 매뉴얼, 운영 절차서 등 PDF를 업로드하고 "
        "자연어로 질문하면 AI가 문서 내용을 기반으로 답변합니다."
    )

    _init_session_state()

    # 2열 레이아웃: 왼쪽 사이드(문서 관리) / 오른쪽 메인(채팅)
    left, right = st.columns([1, 2], gap="large")

    with left:
        _render_upload_panel()
        st.divider()
        _render_document_panel()

    with right:
        _render_chat_panel()


# ══════════════════════════════════════════════════════════════════════════════
# 세션 상태
# ══════════════════════════════════════════════════════════════════════════════

def _init_session_state() -> None:
    defaults = {
        "rag_messages": [],          # [{"role", "content", "sources"?}]
        "rag_selected_docs": [],     # 검색 대상 document_id 목록
        "rag_docs_cache": None,      # 문서 목록 캐시
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# 왼쪽: PDF 업로드 패널
# ══════════════════════════════════════════════════════════════════════════════

def _render_upload_panel() -> None:
    st.subheader("📤 문서 업로드")

    uploaded = st.file_uploader(
        "PDF 파일 선택",
        type=["pdf"],
        help="최대 50MB. PLC 매뉴얼, 운영 절차서 등 텍스트 레이어가 있는 PDF",
        key="rag_file_uploader",
    )

    col1, col2 = st.columns(2)
    with col1:
        description = st.text_input("설명 (선택)", placeholder="예: PLC 운영 매뉴얼 v2.3")
    with col2:
        tags_input = st.text_input("태그 (선택)", placeholder="PLC,운영,매뉴얼")

    if uploaded and st.button("🔍 인덱싱 시작", type="primary", use_container_width=True):
        _do_upload(uploaded, description, tags_input)


def _do_upload(file, description: str, tags_raw: str) -> None:
    with st.spinner(f"📖 '{file.name}' 파싱 및 임베딩 생성 중..."):
        try:
            params = {}
            if description:
                params["description"] = description
            if tags_raw:
                params["tags"] = tags_raw

            resp = httpx.post(
                f"{_RAG_URL}/upload",
                files={"file": (file.name, file.getvalue(), "application/pdf")},
                params=params,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            r = resp.json()

            if r.get("status") == "duplicate":
                st.warning(
                    f"⚠️ **중복 파일**\n\n"
                    f"'{file.name}'은 이미 인덱싱되어 있습니다. "
                    f"(문서 ID: {r['document_id']})"
                )
            else:
                st.success(
                    f"✅ **인덱싱 완료!**\n\n"
                    f"- 파일: `{r['filename']}`\n"
                    f"- 페이지: {r['page_count']}p\n"
                    f"- 청크: {r['chunk_count']}개"
                )
                # 캐시 초기화 → 문서 목록 재로드
                st.session_state.rag_docs_cache = None
                st.rerun()

        except httpx.ConnectError:
            st.error("❌ API 서버에 연결할 수 없습니다. 서버 상태를 확인하세요.")
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", str(e))
            st.error(f"❌ 업로드 실패: {detail}")
        except Exception as e:
            st.error(f"❌ 오류: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# 왼쪽: 문서 목록 / 선택 / 삭제
# ══════════════════════════════════════════════════════════════════════════════

def _render_document_panel() -> None:
    st.subheader("📂 인덱싱된 문서")

    # 문서 목록 로드 (캐시 활용)
    if st.session_state.rag_docs_cache is None:
        st.session_state.rag_docs_cache = _fetch_documents()

    docs: List[Dict] = st.session_state.rag_docs_cache or []

    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄", help="목록 새로고침"):
            st.session_state.rag_docs_cache = None
            st.rerun()
    with col_info:
        st.caption(f"총 {len(docs)}개 문서")

    if not docs:
        st.info("업로드된 문서가 없습니다.\nPDF를 업로드하면 여기에 표시됩니다.")
        return

    st.caption("🔍 검색 범위 선택 (미선택 시 전체 문서 검색)")

    selected_ids = []
    for doc in docs:
        c1, c2 = st.columns([5, 1])
        with c1:
            checked = st.checkbox(
                f"📄 {doc['filename']}",
                key=f"doc_{doc['id']}",
                help=(
                    f"페이지: {doc.get('page_count', '?')}p | "
                    f"청크: {doc.get('chunk_count', '?')}개 | "
                    f"업로드: {str(doc.get('uploaded_at', ''))[:10]}"
                ),
            )
            if doc.get("description"):
                st.caption(f"  └ {doc['description']}")
            if checked:
                selected_ids.append(doc["id"])
        with c2:
            if st.button("🗑️", key=f"del_{doc['id']}", help="삭제"):
                _do_delete(doc["id"], doc["filename"])

    st.session_state.rag_selected_docs = selected_ids


def _fetch_documents() -> List[Dict]:
    try:
        resp = httpx.get(f"{_RAG_URL}/documents", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"문서 목록 로드 실패: {e}")
        return []


def _do_delete(doc_id: int, filename: str) -> None:
    with st.spinner(f"'{filename}' 삭제 중..."):
        try:
            resp = httpx.delete(f"{_RAG_URL}/documents/{doc_id}", timeout=10.0)
            resp.raise_for_status()
            st.success(f"✅ '{filename}' 삭제 완료")
            st.session_state.rag_docs_cache = None
            st.rerun()
        except Exception as e:
            st.error(f"❌ 삭제 실패: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# 오른쪽: 채팅 인터페이스
# ══════════════════════════════════════════════════════════════════════════════

def _render_chat_panel() -> None:
    # 헤더: 검색 범위 표시 + 초기화 버튼
    selected = st.session_state.rag_selected_docs
    scope_text = (
        f"🔍 선택된 문서 {len(selected)}개 검색 중"
        if selected else
        "🔍 전체 문서 검색 중"
    )
    h_col1, h_col2 = st.columns([4, 1])
    with h_col1:
        st.subheader(f"💬 질의응답 — {scope_text}")
    with h_col2:
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.rag_messages = []
            st.rerun()

    # 메시지 히스토리 표시
    for msg in st.session_state.rag_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # 출처 표시 (assistant 메시지에만)
            if msg["role"] == "assistant" and msg.get("sources"):
                sources = msg["sources"]
                latency = msg.get("latency_ms", 0)
                with st.expander(
                    f"📎 참고 문서 {len(sources)}개 | ⏱️ {latency}ms",
                    expanded=False,
                ):
                    for i, src in enumerate(sources, 1):
                        st.markdown(
                            f"**{i}. {src['filename']}** — {src['page_number']}페이지 "
                            f"*(유사도: {src['score']:.1%})*"
                        )
                        st.caption(src["content"])
                        if i < len(sources):
                            st.divider()

    # 입력창
    user_input = st.chat_input(
        "예: 'PLC 비상 정지 절차를 알려주세요' / '수위 경보 기준값은?'",
        key="rag_chat_input",
    )

    if user_input:
        _handle_query(user_input)


def _handle_query(question: str) -> None:
    """사용자 질문 처리"""
    # 사용자 메시지 즉시 표시
    st.session_state.rag_messages.append({"role": "user", "content": question})

    # API 히스토리 구성 (role + content만, 최근 12개)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.rag_messages[-13:-1]
        if m["role"] in ("user", "assistant")
    ]

    with st.spinner("🔍 문서 검색 및 답변 생성 중..."):
        try:
            payload = {
                "question":     question,
                "document_ids": st.session_state.rag_selected_docs or None,
                "top_k":        5,
                "chat_history": history,
            }
            resp = httpx.post(
                f"{_RAG_URL}/query",
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            r = resp.json()

            st.session_state.rag_messages.append({
                "role":         "assistant",
                "content":      r["answer"],
                "sources":      r.get("sources", []),
                "found_context": r.get("found_context", False),
                "latency_ms":   r.get("latency_ms", 0),
            })

        except httpx.ConnectError:
            st.session_state.rag_messages.append({
                "role":    "assistant",
                "content": "❌ API 서버에 연결할 수 없습니다.",
                "sources": [],
            })
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", str(e))
            st.session_state.rag_messages.append({
                "role":    "assistant",
                "content": f"❌ 오류: {detail}",
                "sources": [],
            })
        except Exception as e:
            st.session_state.rag_messages.append({
                "role":    "assistant",
                "content": f"❌ 예외 발생: {str(e)}",
                "sources": [],
            })

    st.rerun()


# ── 단독 실행 지원 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(
        page_title="RAG 문서 검색",
        page_icon="📚",
        layout="wide",
    )
    render_rag_page()
