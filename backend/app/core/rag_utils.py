import os
import uuid
import hashlib
from abc import ABC, abstractmethod
from typing import List, Type, Tuple, Any

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.models.chat import PolicyChunk

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
    def __init__(self, model_name: str = "text-embedding-3-small", api_key: str = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAIEmbeddingModel을 사용하려면 'openai' 패키지가 필요합니다. requirements.txt를 확인해 주세요.")
        
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def embed_text(self, text: str) -> List[float]:
        # 개행 문자를 공백으로 치환하여 임베딩 품질 향상
        response = self.client.embeddings.create(
            input=[text.replace("\n", " ")],
            model=self.model_name
        )
        return response.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        clean_texts = [t.replace("\n", " ") for t in texts]
        response = self.client.embeddings.create(
            input=clean_texts,
            model=self.model_name
        )
        return [item.embedding for item in response.data]


class GeminiEmbeddingModel(EmbeddingModel):
    """
    Google GenAI SDK를 사용하는 임베딩 모델 구현체.
    기본 모델: text-embedding-004 (768차원 또는 1536차원)
    """
    def __init__(self, model_name: str = "text-embedding-004", api_key: str = None):
        try:
            from google import genai
        except ImportError:
            raise ImportError("GeminiEmbeddingModel을 사용하려면 'google-genai' 패키지가 필요합니다. requirements.txt를 확인해 주세요.")
        
        self.model_name = model_name
        # Client 생성 시 GEMINI_API_KEY 환경변수를 기본적으로 탐색합니다.
        self.client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))

    def embed_text(self, text: str) -> List[float]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text
        )
        return response.embeddings[0].values

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=texts
        )
        return [emb.values for emb in response.embeddings]


class OllamaEmbeddingModel(EmbeddingModel):
    """
    로컬에 설치된 Ollama를 사용하는 임베딩 모델 구현체.
    기본 모델: bge-m3 (1024차원, 다국어)

    nomic-embed-text(768차원)는 영어 중심이라 한국어 정책 문서의 의미 유사도가
    떨어져 기본값을 bge-m3로 둔다. bge-m3는 컨텍스트가 8192 토큰이므로 그보다
    긴 문서는 호출 전에 청킹해야 뒷부분이 잘리지 않는다.
    """
    def __init__(self, model_name: str = "bge-m3", base_url: str = "http://localhost:11434"):
        import httpx
        self.model_name = model_name
        self.base_url = base_url
        self.client = httpx.Client(timeout=60.0)

    def embed_text(self, text: str) -> List[float]:
        # 최신 /api/embed 엔드포인트 사용 (레거시 /api/embeddings 대체).
        # 요청 필드는 input, 응답은 embeddings(배열)로 바뀌었다.
        response = self.client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model_name, "input": text.replace("\n", " ")}
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # /api/embed는 input에 리스트를 받아 한 번의 요청으로 배치 임베딩한다
        # (레거시 /api/embeddings는 단건만 가능해 루프가 필요했음).
        clean_texts = [t.replace("\n", " ") for t in texts]
        response = self.client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model_name, "input": clean_texts}
        )
        response.raise_for_status()
        return response.json()["embeddings"]


class SimpleTextSplitter:
    """
    텍스트를 지정한 문자 수 및 오버랩(겹침) 기준으로 분할해 주는 기본 청커.
    """
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            
            start += (self.chunk_size - self.chunk_overlap)
            if start >= text_len or (self.chunk_size - self.chunk_overlap) <= 0:
                break
                
        return chunks


def upsert_policy_chunks(
    db: Session,
    policy_id: uuid.UUID,
    document_id: uuid.UUID,
    text_content: str,
    embedding_model: EmbeddingModel,
    model_name_log: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
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
    embeddings = embedding_model.embed_documents(chunks)
    
    # 4) 데이터베이스 삽입
    for i, (chunk_text, vector) in enumerate(zip(chunks, embeddings)):
        chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        
        db_chunk = PolicyChunk(
            policy_id=policy_id,
            document_id=document_id,
            chunk_index=i,
            chunk_text=chunk_text,
            chunk_hash=chunk_hash,
            chunk_metadata={
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "length": len(chunk_text)
            },
            embedding_status="success",
            embedding_model=model_name_log,
            embedding=vector,
            created_at=func.now()
        )
        db.add(db_chunk)
    
    db.commit()
    return len(chunks)


def search_policy_chunks(
    db: Session,
    query: str,
    embedding_model: EmbeddingModel,
    limit: int = 5
) -> List[Tuple[PolicyChunk, float]]:
    """
    [챗봇 RAG 영역] 쿼리를 임베딩하여 policy_chunks 테이블에서 코사인 유사도가 가장 높은 청크를 검색합니다.
    - 반환값: (PolicyChunk 객체, cosine_similarity_score)의 튜플 리스트
    """
    query_vector = embedding_model.embed_text(query)
    
    # pgvector의 cosine_distance를 기반으로 정렬하며, 점수는 1 - cosine_distance로 변환
    distance_expr = PolicyChunk.embedding.cosine_distance(query_vector)
    
    results = db.query(
        PolicyChunk,
        (1 - distance_expr).label("similarity")
    ).order_by(distance_expr).limit(limit).all()
    
    return [(row[0], float(row[1])) for row in results]


def search_generic_vectors(
    db: Session,
    model_class: Type[Any],
    query: str,
    embedding_model: EmbeddingModel,
    limit: int = 5
) -> List[Tuple[Any, float]]:
    """
    [범용 헬퍼] 각 도메인별(추천, 서류 검토, 일정 관리 등)로 정의한 개별 벡터 테이블 클래스를 타겟으로 유사도 검색을 수행합니다.
    - 조건: model_class는 반드시 pgvector Column인 'embedding' 필드를 소유하고 있어야 합니다.
    - 예시: search_generic_vectors(db, ReviewVector, "제출서류 질문", model)
    """
    query_vector = embedding_model.embed_text(query)
    
    # pgvector cosine_distance 정렬 계산
    distance_expr = model_class.embedding.cosine_distance(query_vector)
    
    results = db.query(
        model_class,
        (1 - distance_expr).label("similarity")
    ).order_by(distance_expr).limit(limit).all()
    
    return [(row[0], float(row[1])) for row in results]
