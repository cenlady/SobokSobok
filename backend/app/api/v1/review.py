from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from app.core.database import get_db

# 담당: 이충헌 (파일 검토 · 프론트)
# 업로드 서류(PDF/JPG) OCR → review_vectors → 정책 required_documents·eligibility_text와 RAG 대조
router = APIRouter()


@router.post("/", summary="파일 검토 (PDF/JPG → OCR → RAG 대조 → 부족·보완점)")
async def review(
    file: UploadFile = File(...),
    policy_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    업로드한 정책 지원 서류를 대상 정책의 요건과 대조해 부족·보완점을 진단합니다.
    TODO(이충헌): OCR/텍스트 추출 → review_vectors 임베딩 →
      required_documents·eligibility_text 와 RAG 대조 → LLM 진단.
    """
    return {
        "document_type": None,
        "missing_items": [],
        "improvement_points": [],
        "overall": "",
    }
