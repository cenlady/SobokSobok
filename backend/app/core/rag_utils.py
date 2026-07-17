import os
import uuid
import hashlib
import inspect
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.chat import PolicyChunk
from app.core.config import settings
from app.core.model_errors import ModelResponseError, classify_model_exception
from app.core.model_logging import log_model_call


def _validate_embedding_dimensions(
    embeddings: List[List[float]],
    expected_dimensions: int | None,
) -> None:
    if expected_dimensions is None:
        return
    invalid = [len(vector) for vector in embeddings if len(vector) != expected_dimensions]
    if invalid:
        raise ModelResponseError(
            f"임베딩 차원 불일치: expected={expected_dimensions}, actual={invalid[0]}"
        )


def _log_embedding_call(
    *,
    feature: str,
    provider: str,
    model: str,
    texts: List[str],
    embeddings: List[List[float]],
    started: float,
    status: str,
    error_type: str | None = None,
) -> None:
    dimension = len(embeddings[0]) if embeddings else None
    source_module = "app.core.rag_utils"
    source_function = "embed_documents"
    for frame_info in inspect.stack()[2:10]:
        candidate_module = frame_info.frame.f_globals.get("__name__", "")
        if candidate_module not in {"app.core.rag_utils", "app.core.model_provider"}:
            source_module = candidate_module or source_module
            source_function = frame_info.function
            break
    log_model_call(
        feature=feature,
        task="embedding",
        stage="embedding",
        provider=provider,
        model=model,
        source_module=source_module,
        source_function=source_function,
        status=status,
        latency_ms=int((time.perf_counter() - started) * 1000),
        input_type="text_batch",
        input_count=len(texts),
        input_chars=sum(len(text) for text in texts),
        result_count=len(embeddings),
        embedding_dimensions=dimension,
        error_type=error_type,
    )

class EmbeddingModel(ABC):
    """
    RAG에 사용되는 임베딩 모델 인터페이스.
    각 도메인 개발자는 이 인터페이스를 구현한 클래스를 주입하여 각자 다른 임베딩 모델을 사용할 수 있습니다.
    """
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트 문장을 임베딩하여 벡터 리스트를 반환합니다."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """여러 문서들을 일괄 임베딩하여 벡터 리스트의 리스트를 반환합니다."""
        pass


class OpenAIEmbeddingModel(EmbeddingModel):
    """
    OpenAI API를 사용하는 임베딩 모델 구현체.
    기본 모델: text-embedding-3-small (1536차원) 또는 text-embedding-ada-002 (1536차원)
    """
    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: str = None,
        expected_dimensions: int | None = None,
        feature: str = "chat",
        timeout_seconds: float | None = None,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAIEmbeddingModel을 사용하려면 'openai' 패키지가 필요합니다. requirements.txt를 확인해 주세요.")
        
        self.model_name = model_name
        self.expected_dimensions = expected_dimensions
        self.feature = feature
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            timeout=timeout_seconds or settings.LLM_EMBEDDING_TIMEOUT_SECONDS,
        )
    def embed_text(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        started = time.perf_counter()
        embeddings: List[List[float]] = []
        clean_texts = [t.replace("\n", " ") for t in texts]
        request: Dict[str, Any] = {"input": clean_texts, "model": self.model_name}
        if self.expected_dimensions is not None and self.model_name.startswith("text-embedding-3"):
            request["dimensions"] = self.expected_dimensions
        try:
            response = self.client.embeddings.create(**request)
            embeddings = [item.embedding for item in response.data]
            _validate_embedding_dimensions(embeddings, self.expected_dimensions)
            _log_embedding_call(
                feature=self.feature,
                provider="openai",
                model=self.model_name,
                texts=texts,
                embeddings=embeddings,
                started=started,
                status="success",
            )
            return embeddings
        except Exception as exc:
            _log_embedding_call(
                feature=self.feature,
                provider="openai",
                model=self.model_name,
                texts=texts,
                embeddings=embeddings,
                started=started,
                status="error",
                error_type=type(exc).__name__,
            )
            raise classify_model_exception(
                exc,
                feature=self.feature,
                task="embedding",
                provider="openai",
                model=self.model_name,
            ) from exc


class GeminiEmbeddingModel(EmbeddingModel):
    """
    Google GenAI SDK를 사용하는 임베딩 모델 구현체.
    기본 모델: text-embedding-004 (768차원 또는 1536차원)
    """
    def __init__(
        self,
        model_name: str = "text-embedding-004",
        api_key: str = None,
        expected_dimensions: int | None = None,
        feature: str = "chat",
        timeout_seconds: float | None = None,
    ):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("GeminiEmbeddingModel을 사용하려면 'google-genai' 패키지가 필요합니다. requirements.txt를 확인해 주세요.")
        
        self.model_name = model_name
        self.expected_dimensions = expected_dimensions
        self.feature = feature
        # Client 생성 시 GEMINI_API_KEY 환경변수를 기본적으로 탐색합니다.
        self.client = genai.Client(
            api_key=api_key or os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(
                timeout=int(
                    (timeout_seconds or settings.LLM_EMBEDDING_TIMEOUT_SECONDS) * 1000
                )
            ),
        )

    def embed_text(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        started = time.perf_counter()
        embeddings: List[List[float]] = []
        try:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=texts,
            )
            embeddings = [emb.values for emb in response.embeddings]
            _validate_embedding_dimensions(embeddings, self.expected_dimensions)
            _log_embedding_call(
                feature=self.feature,
                provider="gemini",
                model=self.model_name,
                texts=texts,
                embeddings=embeddings,
                started=started,
                status="success",
            )
            return embeddings
        except Exception as exc:
            _log_embedding_call(
                feature=self.feature,
                provider="gemini",
                model=self.model_name,
                texts=texts,
                embeddings=embeddings,
                started=started,
                status="error",
                error_type=type(exc).__name__,
            )
            raise classify_model_exception(
                exc,
                feature=self.feature,
                task="embedding",
                provider="gemini",
                model=self.model_name,
            ) from exc


class OllamaEmbeddingModel(EmbeddingModel):
    """
    로컬에 설치된 Ollama를 사용하는 임베딩 모델 구현체.
    기본 모델: bge-m3:latest (1024차원, 다국어)

    nomic-embed-text(768차원)는 영어 중심이라 한국어 정책 문서의 의미 유사도가
    떨어져 기본값을 bge-m3로 둔다. bge-m3는 컨텍스트가 8192 토큰이므로 그보다
    긴 문서는 호출 전에 청킹해야 뒷부분이 잘리지 않는다.
    """
    def __init__(
        self,
        model_name: str = "bge-m3:latest",
        base_url: str = None,
        expected_dimensions: int | None = None,
        feature: str = "chat",
        timeout_seconds: float | None = None,
    ):
        import httpx
        self.model_name = model_name
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.expected_dimensions = expected_dimensions
        self.feature = feature
        self.client = httpx.Client(
            timeout=timeout_seconds or settings.LLM_EMBEDDING_TIMEOUT_SECONDS
        )

    def embed_text(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # /api/embed는 input에 리스트를 받아 한 번의 요청으로 배치 임베딩한다.
        started = time.perf_counter()
        embeddings: List[List[float]] = []
        clean_texts = [text_val.replace("\n", " ") for text_val in texts]
        try:
            response = self.client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model_name, "input": clean_texts}
            )
            response.raise_for_status()
            payload = response.json()
            if "embeddings" in payload:
                embeddings = payload["embeddings"]
            else:
                # 구버전 Ollama 호환 fallback
                embeddings = [self._embed_text_legacy(text_val) for text_val in clean_texts]
            _validate_embedding_dimensions(embeddings, self.expected_dimensions)
            _log_embedding_call(
                feature=self.feature,
                provider="ollama",
                model=self.model_name,
                texts=texts,
                embeddings=embeddings,
                started=started,
                status="success",
            )
            return embeddings
        except Exception as exc:
            _log_embedding_call(
                feature=self.feature,
                provider="ollama",
                model=self.model_name,
                texts=texts,
                embeddings=embeddings,
                started=started,
                status="error",
                error_type=type(exc).__name__,
            )
            raise classify_model_exception(
                exc,
                feature=self.feature,
                task="embedding",
                provider="ollama",
                model=self.model_name,
            ) from exc

    def _embed_text_legacy(self, text: str) -> List[float]:
        response = self.client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model_name, "input": text.replace("\n", " ")}
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]


class SimpleTextSplitter:
    """
    텍스트를 지정한 문자 수 및 오버랩(겹침) 기준으로 분할해 주는 기본 청커.

    chunk_size는 목표가 아니라 최대 길이입니다. 분할 결과 마지막에 오버랩으로
    이미 포함된 짧은 꼬리가 생기면 중복을 제거하고, 합칠 수 있는 경우 앞 청크에
    합쳐 검색용 청크가 지나치게 짧아지지 않도록 합니다.
    """
    def __init__(
        self,
        chunk_size: int = 280,
        chunk_overlap: int = 40,
        min_chunk_size: int = settings.CHAT_MIN_CHUNK_SIZE,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size는 양수여야 합니다.")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap은 0 이상 chunk_size 미만이어야 합니다.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = max(0, min(min_chunk_size, chunk_size))

    def _coalesce_short_tail(self, chunks: List[str]) -> List[str]:
        """마지막에 생긴 중복/짧은 꼬리 청크를 안전하게 정리합니다."""
        if len(chunks) < 2 or self.min_chunk_size <= 0:
            return chunks

        tail = chunks[-1].strip()
        previous = chunks[-2].strip()
        if not tail or len(tail) >= self.min_chunk_size:
            return chunks

        # 오버랩 때문에 마지막 조각이 앞 청크에 이미 들어 있으면 제거합니다.
        if tail in previous:
            return [*chunks[:-1]]

        # 새 내용인 짧은 꼬리는 최대 길이를 넘지 않을 때만 합칩니다.
        merged = f"{previous} {tail}".strip()
        if len(merged) <= self.chunk_size:
            return [*chunks[:-2], merged]

        # 정보 손실을 막기 위해 합칠 수 없는 새 내용은 별도 청크로 보존합니다.
        return chunks

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        # LangChain은 자연스러운 문단/문장 경계를 최대한 유지해 주므로 챗봇 RAG 청킹에 우선 사용합니다.
        # 의존성이 없는 개발 환경에서는 아래 기본 문자 단위 splitter로 안전하게 fallback됩니다.
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", ". ", "。", "? ", "! ", " ", ""],
            )
            chunks = [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
            return self._coalesce_short_tail(chunks)
        except ImportError:
            pass
        
        chunks = []
        start = 0
        normalized_text = text.strip()
        text_len = len(normalized_text)

        while start < text_len:
            end = start + self.chunk_size
            chunk = normalized_text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start += (self.chunk_size - self.chunk_overlap)
            if start >= text_len or (self.chunk_size - self.chunk_overlap) <= 0:
                break
                
        return self._coalesce_short_tail(chunks)


def create_embedding_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> EmbeddingModel:
    """
    설정값 기반으로 챗봇 RAG 임베딩 모델을 생성합니다.
    - provider: openai | gemini | ollama
    - provider/model_name을 생략하면 챗봇의 기본 cloud 임베딩 설정을 사용합니다.
    """
    from app.core.model_provider import get_embedding_model

    return get_embedding_model("chat", provider=provider, model_name=model_name)


def upsert_policy_chunks(
    db: Session,
    policy_id: uuid.UUID,
    document_id: uuid.UUID,
    text_content: str,
    embedding_model: EmbeddingModel,
    model_name_log: str,
    model_mode: str = "cloud",
    chunk_size: int = settings.CHAT_CHUNK_SIZE,
    chunk_overlap: int = settings.CHAT_CHUNK_OVERLAP,
    metadata_base: Optional[Dict[str, Any]] = None,
    embedding_context: Optional[str] = None,
) -> int:
    """
    [챗봇 RAG 영역] 텍스트 본문을 청킹하고 임베딩한 뒤 policy_chunks 테이블에 저장합니다.
    - 기존 해당 document_id의 청크가 존재할 경우 중복 방지를 위해 삭제 후 다시 생성(재빌드)합니다.
    """
    # 1) 기존 해당 문서의 청크 일괄 삭제
    db.query(PolicyChunk).filter(PolicyChunk.document_id == document_id).delete()
    db.flush()

    # 2) 청커 기동 및 텍스트 쪼개기
    splitter = SimpleTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_text(text_content)
    if not chunks:
        return 0

    # 3) 임베딩 벡터 생성
    embedding_inputs = [
        f"{embedding_context}\n청크 본문:\n{chunk_text}" if embedding_context else chunk_text
        for chunk_text in chunks
    ]
    embeddings = embedding_model.embed_documents(embedding_inputs)
    
    from app.core.model_provider import normalize_model_mode

    selected_mode = normalize_model_mode(model_mode) or "cloud"

    # 4) 데이터베이스 삽입
    for i, (chunk_text, vector) in enumerate(zip(chunks, embeddings)):
        chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        chunk_metadata = {
            **(metadata_base or {}),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "length": len(chunk_text),
            "embedding_input_strategy": "document_context_section_plus_chunk" if embedding_context else "chunk_only",
        }
        
        vector_values: Dict[str, Any]
        if selected_mode == "local":
            vector_values = {
                "embedding_ollama": vector,
                "embedding_ollama_model": model_name_log,
            }
        else:
            vector_values = {
                "embedding_openai": vector,
                "embedding_openai_model": model_name_log,
            }

        db_chunk = PolicyChunk(
            policy_id=policy_id,
            document_id=document_id,
            chunk_index=i,
            chunk_text=chunk_text,
            chunk_hash=chunk_hash,
            chunk_metadata=chunk_metadata,
            embedding_status="success",
            embedding_model=model_name_log,
            created_at=func.now(),
            **vector_values,
        )
        db.add(db_chunk)
    
    db.commit()
    return len(chunks)


def search_policy_chunks(
    db: Session,
    query: str,
    embedding_model: EmbeddingModel,
    embedding_column: Any,
    limit: int = 5,
    policy_id: Optional[uuid.UUID] = None,
) -> List[Tuple[PolicyChunk, float]]:
    """
    [챗봇 RAG 영역] 쿼리를 임베딩하여 policy_chunks 테이블에서 코사인 유사도가 가장 높은 청크를 검색합니다.
    - 반환값: (PolicyChunk 객체, cosine_similarity_score)의 튜플 리스트
    """
    query_vector = embedding_model.embed_text(query)
    
    # pgvector의 cosine_distance를 기반으로 정렬하며, 점수는 1 - cosine_distance로 변환
    distance_expr = embedding_column.cosine_distance(query_vector)
    
    search_query = (
        db.query(
            PolicyChunk,
            (1 - distance_expr).label("similarity")
        )
        .filter(
            PolicyChunk.embedding_status == "success",
            embedding_column.isnot(None),
        )
    )

    if policy_id is not None:
        search_query = search_query.filter(PolicyChunk.policy_id == policy_id)

    results = search_query.order_by(distance_expr).limit(limit).all()
    
    return [(row[0], float(row[1])) for row in results]


def search_generic_vectors(
    db: Session,
    model_class: Type[Any],
    query: str,
    embedding_model: EmbeddingModel,
    embedding_column: Any,
    limit: int = 5
) -> List[Tuple[Any, float]]:
    """
    [범용 헬퍼] 각 도메인별(추천, 서류 검토, 일정 관리 등)로 정의한 개별 벡터 테이블 클래스를 타겟으로 유사도 검색을 수행합니다.
    - OpenAI/Ollama처럼 차원이 다른 벡터를 섞지 않도록 검색 컬럼을 반드시 명시합니다.
    """
    query_vector = embedding_model.embed_text(query)
    
    # pgvector cosine_distance 정렬 계산
    distance_expr = embedding_column.cosine_distance(query_vector)
    
    results = db.query(
        model_class,
        (1 - distance_expr).label("similarity")
    ).order_by(distance_expr).limit(limit).all()
    
    return [(row[0], float(row[1])) for row in results]
