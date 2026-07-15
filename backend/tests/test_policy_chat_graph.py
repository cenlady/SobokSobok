import uuid
from unittest.mock import Mock

from app.models.chat import ChatSession
import app.services.chat_graph as chat_graph


def _session(*, active_policy_id=None) -> ChatSession:
    return ChatSession(
        id=uuid.uuid4(),
        user_id=1,
        active_policy_id=active_policy_id,
    )


def _retrieval(query: str, *, response_mode: str = "answer"):
    return {
        "query": query,
        "expanded_query": query,
        "intent_tags": ["general"],
        "response_mode": response_mode,
        "candidates": [],
        "sources": [
            {
                "policy_id": str(uuid.uuid4()),
                "policy_title": "소상공인 지원",
                "chunk_text": "지원 내용",
                "metadata": {"intent_tags": ["general"]},
            }
        ] if response_mode == "answer" else [],
    }


def _patch_common(monkeypatch):
    monkeypatch.setattr(chat_graph, "build_recommendation_follow_up_answer", Mock(return_value=None))
    monkeypatch.setattr(chat_graph, "build_focused_attribute_answer", Mock(return_value=None))
    monkeypatch.setattr(chat_graph, "record_chat_turn", Mock())


def test_main_chat_uses_global_chunk_retrieval(monkeypatch):
    _patch_common(monkeypatch)
    session = _session(active_policy_id=uuid.uuid4())
    global_retrieve = Mock(return_value=_retrieval("지원 정책 알려줘"))
    document_retrieve = Mock(side_effect=AssertionError("메인 채팅은 상세 문서를 조회하면 안 됩니다."))
    monkeypatch.setattr(chat_graph, "resolve_session_policy_context", Mock(return_value=None))
    monkeypatch.setattr(chat_graph, "retrieve_policy_chunk_sources", global_retrieve)
    monkeypatch.setattr(chat_graph, "retrieve_policy_document_sources", document_retrieve)
    monkeypatch.setattr(chat_graph, "generate_chat_answer", Mock(return_value="정책 답변"))

    response = chat_graph.run_policy_chat(
        db=object(),
        query="지원 정책 알려줘",
        limit=6,
        requested_policy_id=None,
        selected_policy_id=None,
        session=session,
        recent_messages=[],
        model_mode="cloud",
    )

    assert response["answer"] == "정책 답변"
    assert response["context_policy_id"] is None
    assert session.active_policy_id is None
    global_retrieve.assert_called_once()
    chat_graph.record_chat_turn.assert_called_once()


def test_policy_detail_chat_uses_parent_documents_and_keeps_context(monkeypatch):
    _patch_common(monkeypatch)
    policy_id = uuid.uuid4()
    session = _session()
    document_retrieve = Mock(return_value=_retrieval("지원 대상은?"))
    global_retrieve = Mock(side_effect=AssertionError("상세 채팅은 전역 청크를 조회하면 안 됩니다."))
    monkeypatch.setattr(chat_graph, "retrieve_policy_document_sources", document_retrieve)
    monkeypatch.setattr(chat_graph, "retrieve_policy_chunk_sources", global_retrieve)
    monkeypatch.setattr(chat_graph, "generate_chat_answer", Mock(return_value="상세 정책 답변"))

    response = chat_graph.run_policy_chat(
        db=object(),
        query="지원 대상은?",
        limit=6,
        requested_policy_id=policy_id,
        selected_policy_id=None,
        session=session,
        recent_messages=[],
        model_mode="local",
    )

    assert response["answer"] == "상세 정책 답변"
    assert response["context_policy_id"] == str(policy_id)
    assert response["active_policy_id"] == str(policy_id)
    assert session.active_policy_id == policy_id
    document_retrieve.assert_called_once()
    chat_graph.record_chat_turn.assert_called_once()


def test_out_of_scope_route_skips_llm(monkeypatch):
    _patch_common(monkeypatch)
    session = _session()
    monkeypatch.setattr(chat_graph, "resolve_session_policy_context", Mock(return_value=None))
    monkeypatch.setattr(
        chat_graph,
        "retrieve_policy_chunk_sources",
        Mock(return_value=_retrieval("오늘 날씨 어때?", response_mode="out_of_scope")),
    )
    monkeypatch.setattr(chat_graph, "build_out_of_scope_answer", Mock(return_value="정책 외 질문 안내"))
    monkeypatch.setattr(
        chat_graph,
        "generate_chat_answer",
        Mock(side_effect=AssertionError("정책 외 질문은 LLM을 호출하면 안 됩니다.")),
    )

    response = chat_graph.run_policy_chat(
        db=object(),
        query="오늘 날씨 어때?",
        limit=6,
        requested_policy_id=None,
        selected_policy_id=None,
        session=session,
        recent_messages=[],
        model_mode="cloud",
    )

    assert response["response_mode"] == "out_of_scope"
    assert response["answer"] == "정책 외 질문 안내"


def test_stream_graph_emits_meta_tokens_and_done_in_order(monkeypatch):
    _patch_common(monkeypatch)
    session = _session()
    monkeypatch.setattr(chat_graph, "resolve_session_policy_context", Mock(return_value=None))
    monkeypatch.setattr(
        chat_graph,
        "retrieve_policy_chunk_sources",
        Mock(return_value=_retrieval("지원 내용 알려줘")),
    )
    monkeypatch.setattr(chat_graph, "generate_chat_answer_stream", Mock(return_value=iter(("지원 ", "답변"))))

    events = list(
        chat_graph.stream_policy_chat(
            db=object(),
            query="지원 내용 알려줘",
            limit=6,
            requested_policy_id=None,
            selected_policy_id=None,
            session=session,
            recent_messages=[],
            model_mode="cloud",
        )
    )

    assert [event["event"] for event in events] == ["meta", "token", "token", "done"]
    assert events[1]["data"]["text"] == "지원 "
    assert events[2]["data"]["text"] == "답변"
    assert events[3]["data"]["answer"] == "지원 답변"
    chat_graph.record_chat_turn.assert_called_once()
