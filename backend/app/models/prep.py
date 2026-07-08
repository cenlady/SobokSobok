import uuid
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.core.database import Base

class PrepVector(Base):
    """
    [서류 준비 가이드 영역] 서류 준비 가이드 KB(지식베이스) 및 준비 일정 벡터 테이블
    - 역할: 개별 구비 서류명 ➔ 발급 방법/소요 기간/팁 등의 지식 가이드 텍스트와 그 임베딩 데이터를 보관합니다.
    - 소유자: 서류 준비 및 일정 관리 서비스
    """
    __tablename__ = "prep_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_name = Column(String(255), nullable=False, index=True, comment="가이드 대상 서류명")
    guide_text = Column(Text, nullable=True, comment="해당 서류 발급 소요기간, 준비 방법, 팁 설명 텍스트")
    
    # pgvector 임베딩 벡터 (차원은 settings.EMBEDDING_DIM으로 관리)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False, comment="[pgvector] 가이드 KB 검색용 임베딩 벡터값")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
