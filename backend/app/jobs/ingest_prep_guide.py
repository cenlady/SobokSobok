# -*- coding: utf-8 -*-
# 파일 역할: [일정 관리 도메인] 4대 일정 단락(접수/마감/절차/서류)을 추출하여 로컬 Ollama(bge-m3)로 임베딩한 뒤 DB(prep_vectors)에 적재하는 배치 잡 스크립트

import sys
from app.core.database import SessionLocal
from app.models.normalized_policy import PolicyDocument
from app.models.prep import PrepVector
from app.core.rag_utils import OllamaEmbeddingModel

def build_prep_vectors():
    """
    [이재혁 - 일정 관리 RAG 2단계 - 로컬 Ollama 버전]
    - policy_documents 테이블에서 4가지 타입(application, deadline, procedure, requirements)의 text를 가져옵니다.
    - 로컬 Ollama에 켜진 'bge-m3' (1024차원) 임베딩 모델로 벡터화하여 prep_vectors 테이블에 저장합니다.
    """
    db = SessionLocal()
    target_types = ["application", "deadline", "procedure", "requirements"]
    
    try:
        # 1) 원천 데이터 조회
        docs = (
            db.query(PolicyDocument)
            .filter(PolicyDocument.document_type.in_(target_types))
            .all()
        )
        if not docs:
            print("[Prep-RAG] No source document sections found to embed.", flush=True)
            return
            
        print(f"[Prep-RAG] Found {len(docs)} documents. Clearing old prep_vectors...", flush=True)
        
        # 2) 기존 일정 가이드 KB 데이터 삭제 (재빌드)
        db.query(PrepVector).delete()
        db.flush()

        # 3) 임베딩 대상 텍스트 추출
        texts_to_embed = []
        docs_to_save = []
        for doc in docs:
            if doc.text and doc.text.strip():
                texts_to_embed.append(doc.text)
                docs_to_save.append(doc)

        if not texts_to_embed:
            print("[Prep-RAG] No non-empty text found to embed.", flush=True)
            return

        # 4) 로컬 Ollama bge-m3 모델 설정
        # (도커 컨테이너 외부의 호스트 PC에 켜진 올라마에 접근하기 위해 host.docker.internal을 사용)
        print(f"[Prep-RAG] Connecting to local Ollama (bge-m3) to embed {len(texts_to_embed)} sections...", flush=True)
        embedding_model = OllamaEmbeddingModel(
            model_name="bge-m3",
            base_url="http://host.docker.internal:11434"
        )
        
        # 5) 일괄 임베딩 호출
        embeddings = embedding_model.embed_documents(texts_to_embed)

        # 6) 데이터베이스 적재 (prep_vectors)
        success_count = 0
        for doc, vector in zip(docs_to_save, embeddings):
            db_vector = PrepVector(
                document_name=doc.title or doc.document_type,
                guide_text=doc.text,
                embedding=vector
            )
            db.add(db_vector)
            success_count += 1

        db.commit()
        print(f"[Prep-RAG] Successfully built and saved {success_count} vectors (bge-m3, 1024dim) to prep_vectors!", flush=True)

    except Exception as e:
        db.rollback()
        print(f"[Prep-RAG] Exception occurred during embedding/insert: {e}", file=sys.stderr, flush=True)
        print(f"[Prep-RAG] Please ensure Ollama is running on your host PC and you have pulled the 'bge-m3' model (ollama pull bge-m3).", file=sys.stderr, flush=True)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("[Prep-RAG] Starting 2nd step: Local Ollama (bge-m3) RAG embedding and database insertion...", flush=True)
    build_prep_vectors()
