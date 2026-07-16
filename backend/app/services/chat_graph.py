import uuid
from collections.abc import Iterator
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.model_errors import ModelResponseError
from app.models.chat import ChatMessage, ChatSession
from app.services.chat_rag import (
    build_conversation_context,
    build_focused_attribute_answer,
    build_out_of_scope_answer,
    build_policy_selection_answer,
    build_recommendation_follow_up_answer,
    generate_chat_answer,
    generate_chat_answer_stream,
    infer_intent_tags,
    record_chat_turn,
    retrieve_policy_chunk_sources,
    retrieve_policy_document_sources,
    resolve_session_policy_context,
)
from app.services.policy_title_matcher import resolve_policy_title_from_db


class PolicyChatState(TypedDict, total=False):
    """한 번의 정책 챗봇 요청에서 노드 사이에 전달되는 상태."""

    db: Session
    query: str
    limit: Optional[int]
    requested_policy_id: Optional[uuid.UUID]
    selected_policy_id: Optional[uuid.UUID]
    session: ChatSession
    recent_messages: List[ChatMessage]
    model_mode: Optional[str]
    stream_response: bool
    context_policy_id: Optional[uuid.UUID]
    recommendation_follow_up: bool
    response_data: Dict[str, Any]
    answer: str


class PolicyChatEvent(TypedDict):
    event: Literal["meta", "token", "done"]
    data: Dict[str, Any]


def _resolve_request(state: PolicyChatState) -> Dict[str, Any]:
    follow_up_answer = build_recommendation_follow_up_answer(
        state["query"],
        state["recent_messages"],
    )
    if follow_up_answer:
        return {
            "context_policy_id": None,
            "recommendation_follow_up": True,
            "response_data": {
                "query": state["query"],
                "expanded_query": state["query"],
                "intent_tags": ["recommendation_follow_up"],
                "response_mode": "answer",
                "candidates": [],
                "sources": [],
            },
            "answer": follow_up_answer,
        }

    return {
        "context_policy_id": state.get("requested_policy_id"),
        "recommendation_follow_up": False,
    }


def _route_after_context(state: PolicyChatState) -> Literal["match_title", "retrieve", "update_context"]:
    if state.get("response_data") is not None:
        return "update_context"
    if state.get("context_policy_id") is not None:
        return "retrieve"
    return "match_title"


def _match_policy_title(state: PolicyChatState) -> Dict[str, Any]:
    resolution = resolve_policy_title_from_db(state["db"], state["query"])
    if resolution.status == "matched":
        return {"context_policy_id": resolution.policy_id}
    if resolution.status == "ambiguous":
        return {
            "response_data": {
                "query": state["query"],
                "expanded_query": state["query"],
                "intent_tags": infer_intent_tags(None, None, state["query"]),
                "response_mode": "policy_selection",
                "candidates": list(resolution.candidates),
                "sources": [],
            }
        }
    return {}


def _route_after_title_match(state: PolicyChatState) -> Literal["retrieve", "resolve_session", "update_context"]:
    if state.get("response_data") is not None:
        return "update_context"
    if state.get("context_policy_id") is not None:
        return "retrieve"
    return "resolve_session"


def _resolve_session_context(state: PolicyChatState) -> Dict[str, Any]:
    return {
        "context_policy_id": resolve_session_policy_context(
            state["query"],
            session=state["session"],
            recent_messages=state["recent_messages"],
            selected_policy_id=state.get("selected_policy_id"),
        )
    }


def _retrieve_sources(state: PolicyChatState) -> Dict[str, Any]:
    context_policy_id = state.get("context_policy_id")
    if context_policy_id is not None:
        response_data = retrieve_policy_document_sources(
            db=state["db"],
            query=state["query"],
            limit=state.get("limit"),
            policy_id=context_policy_id,
        )
    else:
        response_data = retrieve_policy_chunk_sources(
            db=state["db"],
            query=state["query"],
            limit=state.get("limit"),
            policy_id=None,
            model_mode=state.get("model_mode"),
        )
    return {"response_data": response_data}


def _update_session_context(state: PolicyChatState) -> Dict[str, Any]:
    context_policy_id = state.get("context_policy_id")
    response_mode = state["response_data"].get("response_mode", "answer")

    if context_policy_id is not None:
        state["session"].active_policy_id = context_policy_id
    elif response_mode != "out_of_scope" and not state.get("recommendation_follow_up", False):
        # 새 전역 정책 질문은 이전에 선택한 상세 정책 문맥을 해제한다.
        # 추천 결과에 대한 후속 설명은 선택 상태를 바꾸지 않는다.
        state["session"].active_policy_id = None
    return {}


def _response_metadata(state: PolicyChatState) -> Dict[str, Any]:
    session = state["session"]
    context_policy_id = state.get("context_policy_id")
    return {
        **state["response_data"],
        "session_id": str(session.id),
        "context_policy_id": str(context_policy_id) if context_policy_id else None,
        "active_policy_id": str(session.active_policy_id) if session.active_policy_id else None,
    }


def _emit_metadata(state: PolicyChatState) -> Dict[str, Any]:
    if state.get("stream_response", False):
        writer = get_stream_writer()
        writer(PolicyChatEvent(event="meta", data=_response_metadata(state)))
    return {}


def _prepare_answer(state: PolicyChatState) -> Dict[str, Any]:
    if state.get("answer"):
        return {}

    response_data = state["response_data"]
    response_mode = response_data.get("response_mode", "answer")
    if response_mode == "out_of_scope":
        return {"answer": build_out_of_scope_answer(state["query"])}
    if response_mode == "policy_selection":
        return {"answer": build_policy_selection_answer(response_data.get("candidates") or [])}

    if state.get("context_policy_id") is None:
        focused_answer = build_focused_attribute_answer(
            state["query"],
            response_data.get("sources") or [],
            intent_tags=response_data.get("intent_tags") or None,
        )
        if focused_answer:
            return {"answer": focused_answer}
    return {}


def _route_answer(state: PolicyChatState) -> Literal["deliver", "generate"]:
    return "deliver" if state.get("answer") else "generate"


def _deliver_answer(state: PolicyChatState) -> Dict[str, Any]:
    if state.get("stream_response", False):
        writer = get_stream_writer()
        writer(PolicyChatEvent(event="token", data={"text": state["answer"]}))
    return {}


def _generate_answer(state: PolicyChatState) -> Dict[str, Any]:
    sources = state["response_data"].get("sources") or []
    conversation_context = build_conversation_context(state["recent_messages"])

    if not state.get("stream_response", False):
        return {
            "answer": generate_chat_answer(
                state["query"],
                sources,
                conversation_context=conversation_context,
                model_mode=state.get("model_mode"),
            )
        }

    writer = get_stream_writer()
    answer_parts: List[str] = []
    for chunk in generate_chat_answer_stream(
        state["query"],
        sources,
        conversation_context=conversation_context,
        model_mode=state.get("model_mode"),
    ):
        if not chunk:
            continue
        answer_parts.append(chunk)
        writer(PolicyChatEvent(event="token", data={"text": chunk}))

    answer = "".join(answer_parts).strip()
    if not answer:
        raise ModelResponseError("챗봇 모델이 빈 응답을 반환했습니다.")
    return {"answer": answer}


def _persist_turn(state: PolicyChatState) -> Dict[str, Any]:
    answer = state.get("answer", "").strip()
    if not answer:
        raise ModelResponseError("챗봇 모델이 빈 응답을 반환했습니다.")

    response_data = state["response_data"]
    record_chat_turn(
        state["db"],
        session=state["session"],
        query=state["query"],
        answer=answer,
        response_mode=response_data.get("response_mode", "answer"),
        context_policy_id=state.get("context_policy_id"),
        candidates=response_data.get("candidates") or [],
        sources=response_data.get("sources") or [],
    )
    if state.get("stream_response", False):
        writer = get_stream_writer()
        writer(PolicyChatEvent(event="done", data={"answer": answer}))
    return {}


def _build_policy_chat_graph():
    builder = StateGraph(PolicyChatState)
    builder.add_node("resolve_context", _resolve_request)
    builder.add_node("match_title", _match_policy_title)
    builder.add_node("resolve_session", _resolve_session_context)
    builder.add_node("retrieve", _retrieve_sources)
    builder.add_node("update_context", _update_session_context)
    builder.add_node("emit_metadata", _emit_metadata)
    builder.add_node("prepare_answer", _prepare_answer)
    builder.add_node("deliver_answer", _deliver_answer)
    builder.add_node("generate_answer", _generate_answer)
    builder.add_node("persist_turn", _persist_turn)

    builder.add_edge(START, "resolve_context")
    builder.add_conditional_edges(
        "resolve_context",
        _route_after_context,
        {
            "match_title": "match_title",
            "retrieve": "retrieve",
            "update_context": "update_context",
        },
    )
    builder.add_conditional_edges(
        "match_title",
        _route_after_title_match,
        {
            "retrieve": "retrieve",
            "resolve_session": "resolve_session",
            "update_context": "update_context",
        },
    )
    builder.add_edge("resolve_session", "retrieve")
    builder.add_edge("retrieve", "update_context")
    builder.add_edge("update_context", "emit_metadata")
    builder.add_edge("emit_metadata", "prepare_answer")
    builder.add_conditional_edges(
        "prepare_answer",
        _route_answer,
        {"deliver": "deliver_answer", "generate": "generate_answer"},
    )
    builder.add_edge("deliver_answer", "persist_turn")
    builder.add_edge("generate_answer", "persist_turn")
    builder.add_edge("persist_turn", END)

    # 대화 이력은 기존 PostgreSQL ChatSession/ChatMessage가 영속 저장한다.
    # 별도 checkpointer를 두지 않아 동일 상태를 이중 저장하지 않는다.
    return builder.compile()


policy_chat_graph = _build_policy_chat_graph()


def _initial_state(
    *,
    db: Session,
    query: str,
    limit: Optional[int],
    requested_policy_id: Optional[uuid.UUID],
    selected_policy_id: Optional[uuid.UUID],
    session: ChatSession,
    recent_messages: List[ChatMessage],
    model_mode: Optional[str],
    stream_response: bool,
) -> PolicyChatState:
    return {
        "db": db,
        "query": query,
        "limit": limit,
        "requested_policy_id": requested_policy_id,
        "selected_policy_id": selected_policy_id,
        "session": session,
        "recent_messages": recent_messages,
        "model_mode": model_mode,
        "stream_response": stream_response,
    }


def run_policy_chat(
    *,
    db: Session,
    query: str,
    limit: Optional[int],
    requested_policy_id: Optional[uuid.UUID],
    selected_policy_id: Optional[uuid.UUID],
    session: ChatSession,
    recent_messages: List[ChatMessage],
    model_mode: Optional[str],
) -> Dict[str, Any]:
    final_state = policy_chat_graph.invoke(
        _initial_state(
            db=db,
            query=query,
            limit=limit,
            requested_policy_id=requested_policy_id,
            selected_policy_id=selected_policy_id,
            session=session,
            recent_messages=recent_messages,
            model_mode=model_mode,
            stream_response=False,
        )
    )
    return {**_response_metadata(final_state), "answer": final_state["answer"]}


def stream_policy_chat(
    *,
    db: Session,
    query: str,
    limit: Optional[int],
    requested_policy_id: Optional[uuid.UUID],
    selected_policy_id: Optional[uuid.UUID],
    session: ChatSession,
    recent_messages: List[ChatMessage],
    model_mode: Optional[str],
) -> Iterator[PolicyChatEvent]:
    for part in policy_chat_graph.stream(
        _initial_state(
            db=db,
            query=query,
            limit=limit,
            requested_policy_id=requested_policy_id,
            selected_policy_id=selected_policy_id,
            session=session,
            recent_messages=recent_messages,
            model_mode=model_mode,
            stream_response=True,
        ),
        stream_mode="custom",
        version="v2",
    ):
        if part.get("type") == "custom":
            yield part["data"]
