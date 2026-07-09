import uuid
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, BigInteger, ForeignKey, JSON, UniqueConstraint, Index, func, Float, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.config import settings

class NormalizedPolicy(Base):
    """
    [공유 계약 #2] 정규화 통합 공고 테이블
    - 역할: 데이터 수집 파이프라인(LLM 등)이 크롤링한 원천 데이터를 공통 스키마로 가공하여 단독으로 적재(쓰기)하는 테이블.
    - 소유자: 데이터 수집 파이프라인 모듈
    - 소비자: 전체 도메인 서비스 (추천, 챗봇 RAG, 서류 대조, 일정 관리용으로 모두 이 테이블을 읽음)
    """
    __tablename__ = "normalized_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="정책 고유 UUID")
    source = Column(String(30), nullable=False, comment="원천 사이트 분류 ('sojinong' | 'mois-openapi' 등)")
    source_pk = Column(String(200), nullable=False, comment="원천 사이트의 고유 키 (예: pbanc_sn 등)")
    canonical_key = Column(Text, nullable=False, comment="정책 식별용 표준 키")
    duplicate_group_key = Column(Text, nullable=False, index=True, comment="중복 정책 그룹 바인딩 키")
    title = Column(Text, nullable=False, comment="지원사업명 (제목)")
    summary = Column(Text, nullable=True, comment="지원내용 한줄 요약")
    body = Column(Text, nullable=True, comment="지원내용 상세 본문 (임베딩 대상 원문)")
    organization = Column(Text, nullable=True, comment="소관/수행 기관명")
    support_type = Column(String(100), nullable=True, comment="지원 유형 (금융, 인력, R&D 등)")
    target_text = Column(Text, nullable=True, comment="지원 대상 설명 텍스트")
    support_content = Column(Text, nullable=True, comment="지원 내용 설명 텍스트")
    region_scope = Column(String(20), nullable=False, default="unknown", comment="지역 범위 (national, local, unknown 등)")
    sido = Column(String(50), nullable=True, comment="시/도 명칭 (예: 서울특별시)")
    sigungu = Column(String(50), nullable=True, comment="시/군/구 명칭 (예: 마포구)")
    matched_sidos = Column(JSON, nullable=False, default=list, comment="권역 공고까지 포함한 적용 가능 시/도 리스트")
    region_confidence = Column(Float, nullable=True, comment="지역 추출 신뢰도")
    status = Column(String(30), nullable=True, comment="신청 상태 (접수중, 마감 등)")
    apply_start = Column(DateTime, nullable=True, comment="신청 시작일")
    apply_end = Column(DateTime, nullable=True, comment="신청 마감일")
    apply_url = Column(Text, nullable=True, comment="온라인 신청 외부 링크 주소")
    application_methods = Column(JSON, nullable=False, default=list, comment="신청 방식 태그 리스트 (online, visit, mail 등)")
    contact_points = Column(JSON, nullable=False, default=list, comment="문의 전화번호/연락처 리스트")
    employee_limit_value = Column(Integer, nullable=True, comment="상시 근로자 수 제한값")
    employee_limit_operator = Column(String(10), nullable=True, comment="상시 근로자 수 제한 비교 연산자")
    sales_limit_amount_krw = Column(BigInteger, nullable=True, comment="매출액 제한값 원 단위")
    sales_limit_operator = Column(String(10), nullable=True, comment="매출액 제한 비교 연산자")
    business_age_limit_value = Column(Integer, nullable=True, comment="창업 제한 연차 값")
    business_age_limit_operator = Column(String(10), nullable=True, comment="창업 제한 연차 비교 연산자")
    required_document_count = Column(Integer, nullable=False, default=0, comment="정규화된 필수 제출서류 개수")
    has_required_documents = Column(Boolean, nullable=False, default=False, index=True, comment="필수 제출서류 정규화 여부")
    
    # 구조화 데이터 JSON 컬럼들
    industry_tags = Column(JSON, nullable=False, comment="구조화된 대상 업종 태그 리스트")
    business_status_tags = Column(JSON, nullable=False, comment="구조화된 대상 기업 상태 태그 리스트")
    eligibility = Column(JSON, nullable=False, comment="구조화된 상세 자격 조건 정보 (추천 서비스 활용)")
    required_documents = Column(JSON, nullable=False, comment="구조화된 필요 제출 서류 리스트 (서류 검토 및 일정 관리 연동)")
    
    source_content_hash = Column(Text, nullable=True, comment="원본 데이터 해시")
    normalized_hash = Column(Text, nullable=True, comment="정규화 가공 데이터 해시")
    is_active = Column(Boolean, nullable=False, default=True, index=True, comment="노출 활성화 여부")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="생성일시")
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="수정일시")

    __table_args__ = (
        UniqueConstraint("source", "source_pk", name="uk_normalized_policies_source"),
        Index("idx_normalized_policies_region", "region_scope", "sido", "sigungu"),
        Index("idx_normalized_policies_status_dates", "status", "apply_start", "apply_end"),
        Index("idx_normalized_policies_limits", "employee_limit_value", "sales_limit_amount_krw"),
        Index("idx_normalized_policies_required_docs", "has_required_documents", "required_document_count"),
    )

    # Relationships
    attachments = relationship("PolicyAttachmentLink", back_populates="policy", cascade="all, delete-orphan")
    documents = relationship("PolicyDocument", back_populates="policy", cascade="all, delete-orphan")
    chunks = relationship("PolicyChunk", back_populates="policy", cascade="all, delete-orphan")


class AttachmentFile(Base):
    """
    [공유] 첨부파일 상세 정보 및 텍스트 데이터 테이블
    - 역할: 다운로드된 첨부파일의 물리적 위치 정보와 OCR 등으로 추출된 텍스트 본문을 보관합니다.
    - 소비자: 서류 검토 서비스 (서류 요건 검토 시 이 파일의 extracted_text와 policy_documents를 비교함)
    """
    __tablename__ = "attachment_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_hash = Column(String(255), nullable=False, unique=True, comment="파일 무결성 검증용 SHA-256 해시")
    storage_path = Column(Text, nullable=False, comment="로컬 스토리지 또는 S3에 저장된 물리 경로")
    original_file_name = Column(Text, nullable=True, comment="원본파일명")
    content_type = Column(String(100), nullable=True, comment="파일 MIME 타입 (pdf, hwp 등)")
    file_size = Column(BigInteger, nullable=True, comment="파일 크기 (Byte 단위)")
    extracted_text = Column(Text, nullable=True, comment="OCR 또는 텍스트 파서를 통해 추출된 파일 내용")
    extraction_status = Column(String(30), nullable=False, default="pending", comment="텍스트 추출 상태 (pending, success, failed)")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    policy_links = relationship("PolicyAttachmentLink", back_populates="file", cascade="all, delete-orphan")


class PolicyAttachmentLink(Base):
    """
    [공유] 공고 - 첨부파일 N:M 관계 매핑 테이블
    - 역할: 하나의 공고에 달린 여러 첨부파일 및 하나의 공통 양식 파일이 여러 공고에 걸쳐지는 관계를 중계합니다.
    """
    __tablename__ = "policy_attachment_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, index=True, comment="정규화 공고 UUID 참조")
    attachment_file_id = Column(UUID(as_uuid=True), ForeignKey("attachment_files.id", ondelete="CASCADE"), nullable=False, index=True, comment="첨부파일 UUID 참조")
    source_file_id = Column(Text, nullable=True, comment="크롤링 소스 사이트 기준의 첨부파일 고유 키")
    original_file_name = Column(Text, nullable=True, comment="원본파일명")
    display_order = Column(Integer, nullable=False, default=0, comment="사용자 화면 노출 정렬 순서")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("policy_id", "attachment_file_id", name="uk_policy_attachment_links"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy", back_populates="attachments")
    file = relationship("AttachmentFile", back_populates="policy_links")


class PolicyDocument(Base):
    """
    [공유] 정책 서류/요건 상세 문서 분할 테이블
    - 역할: 정규화 공고(NormalizedPolicy)에서 특정 세부 조건이나 안내 부분만 문서(Document) 단위로 분할하여 기록합니다.
    - 활용: 이 텍스트들을 chunks로 쪼개어 임베딩하여 벡터 테이블로 보관합니다.
    """
    __tablename__ = "policy_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("normalized_policies.id", ondelete="CASCADE"), nullable=False, index=True, comment="정규화 공고 UUID 참조")
    document_type = Column(String(30), nullable=False, comment="문서 유형 (예: eligibility_criteria, submission_guide 등)")
    source_ref = Column(Text, nullable=True, comment="원본 내 참조 위치 (특정 섹션 번호 등)")
    title = Column(Text, nullable=True, comment="해당 요건 문서 제목")
    text = Column(Text, nullable=False, comment="분할 요건 텍스트 원문")
    text_hash = Column(Text, nullable=False, comment="요건 텍스트 해시")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("policy_id", "document_type", "text_hash", name="uk_policy_documents_hash"),
    )

    # Relationships
    policy = relationship("NormalizedPolicy", back_populates="documents")
    chunks = relationship("PolicyChunk", back_populates="document", cascade="all, delete-orphan")


NORMALIZED_POLICY_SCHEMA_SQL = [
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS matched_sidos JSON NOT NULL DEFAULT '[]'::json",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS region_confidence DOUBLE PRECISION",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS application_methods JSON NOT NULL DEFAULT '[]'::json",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS contact_points JSON NOT NULL DEFAULT '[]'::json",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS employee_limit_value INTEGER",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS employee_limit_operator VARCHAR(10)",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS sales_limit_amount_krw BIGINT",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS sales_limit_operator VARCHAR(10)",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS business_age_limit_value INTEGER",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS business_age_limit_operator VARCHAR(10)",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS required_document_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE normalized_policies ADD COLUMN IF NOT EXISTS has_required_documents BOOLEAN NOT NULL DEFAULT false",
    "CREATE INDEX IF NOT EXISTS idx_normalized_policies_limits ON normalized_policies (employee_limit_value, sales_limit_amount_krw, business_age_limit_value)",
    "CREATE INDEX IF NOT EXISTS idx_normalized_policies_required_docs ON normalized_policies (has_required_documents, required_document_count)",
    "CREATE INDEX IF NOT EXISTS idx_normalized_policies_matched_sidos_gin ON normalized_policies USING gin ((matched_sidos::jsonb))",
    "CREATE INDEX IF NOT EXISTS idx_normalized_policies_application_methods_gin ON normalized_policies USING gin ((application_methods::jsonb))",
    "CREATE INDEX IF NOT EXISTS idx_normalized_policies_industry_tags_gin ON normalized_policies USING gin ((industry_tags::jsonb))",
    "CREATE INDEX IF NOT EXISTS idx_normalized_policies_business_status_tags_gin ON normalized_policies USING gin ((business_status_tags::jsonb))",
]


def ensure_normalized_policy_schema(bind) -> None:
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in NORMALIZED_POLICY_SCHEMA_SQL:
        bind.execute(text(statement))
