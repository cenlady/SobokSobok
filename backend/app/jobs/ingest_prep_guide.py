import sys
from app.core.database import SessionLocal
from app.models.normalized_policy import PolicyDocument

def fetch_prep_source_documents():
    """
    [이재혁 - 일정 관리 RAG 1단계]
    - policy_documents 테이블에서 스케줄 역산 및 접수 처리에 필요한 4가지 타입의 단락만 골라내어 조회합니다.
    - 대상 타입: 'application'(접수), 'deadline'(마감), 'procedure'(절차), 'requirements'(서류)
    """
    db = SessionLocal()
    target_types = ["application", "deadline", "procedure", "requirements"]
    
    try:
        # 지정된 4가지 타입의 문서만 필터링하여 조회
        docs = (
            db.query(PolicyDocument)
            .filter(PolicyDocument.document_type.in_(target_types))
            .all()
        )
        print(f"[Prep-RAG] Successfully fetched {len(docs)} target document sections for scheduling.", flush=True)
        
        # 조회된 데이터 일부 출력 (정상 가동 및 데이터 포맷 검증용)
        for idx, doc in enumerate(docs[:5]):
            print(f"--- Document #{idx+1} ---", flush=True)
            print(f"ID: {doc.id}", flush=True)
            print(f"Policy ID: {doc.policy_id}", flush=True)
            print(f"Type: {doc.document_type}", flush=True)
            print(f"Title: {doc.title}", flush=True)
            print(f"Text Snippet: {doc.text[:100]}...", flush=True)
            
        return docs
    except Exception as e:
        print(f"[Prep-RAG] Error fetching document sections: {e}", file=sys.stderr, flush=True)
        return []
    finally:
        db.close()

if __name__ == "__main__":
    print("[Prep-RAG] Starting 1st step: Verification of target document extraction...", flush=True)
    fetch_prep_source_documents()
