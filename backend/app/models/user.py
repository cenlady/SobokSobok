# -*- coding: utf-8 -*-
# 파일 역할: [공통/인증 도메인] 사용자(User) · 프로필(UserProfile) · 즐겨찾기(Favorite) ORM 모델 정의

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.core.database import Base


class User(Base):
    """
    [공통 영역] 사용자 (인증 및 계정 정보)
    - 역할: JWT 토큰 발급 및 구글 OAuth 연동을 위한 기본 계정 테이블
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False, comment="이메일 (아이디)")
    hashed_password = Column(String(255), nullable=True, comment="암호화된 비밀번호 (구글 OAuth 사용 시 NULL 가능)")
    is_active = Column(Boolean, default=True, nullable=False, comment="활성화 여부")

    # Google OAuth2.0 캘린더 연동 토큰 저장용 컬럼 (이재혁 도메인 연동)
    google_access_token = Column(String(255), nullable=True, comment="Google API Access Token")
    google_refresh_token = Column(String(255), nullable=True, comment="Google API Refresh Token (영구 일정 연동에 사용)")
    google_token_expires_at = Column(DateTime(timezone=True), nullable=True, comment="Google Access Token 만료 일시")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="수정일시")

    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    """
    [공통 영역] 사용자 프로필 (추천 입력값)

    설계 원칙: 이 테이블만 읽으면 추천 엔진의 입력(RecommendationProfileRequest)을
    그대로 재구성할 수 있어야 한다. 그래서 컬럼이 추천 요청의 필드와 1:1로 대응한다.

    범위(min/max)를 JSON이 아니라 타입 있는 컬럼으로 둔 이유:
      - 프로필은 스키마가 고정된 데이터라 JSON의 유연성이 필요 없다.
      - 컬럼이면 DB가 타입과 CHECK 제약을 강제해준다(잘못된 범위를 애초에 못 넣는다).
    추천 서비스는 이 범위를 SQL로 질의하지 않고 파이썬에서 점수 계산에만 쓰므로,
    조회 성능 때문에 굳이 다른 형태를 고를 이유도 없다.
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="사용자 ID 참조",
    )

    # ── 표시용 ──
    owner_name = Column(String(50), nullable=True, comment="사장님 성함")
    store_name = Column(String(200), nullable=True, comment="상호명")

    # ── 지역 → RecommendationProfileRequest.region ──
    region_sido = Column(String(50), nullable=True, comment="시/도 (예: 서울특별시)")
    region_sigungu = Column(String(50), nullable=True, comment="시/군/구 (예: 마포구)")

    # ── 태그 → RecommendationProfileRequest.*_tags ──
    industry_tags = Column(ARRAY(String), nullable=False, server_default="{}", comment="업종 태그 (예: ['restaurant'])")
    business_status_tags = Column(ARRAY(String), nullable=False, server_default="{}", comment="사업 상태 태그 (예: ['small_business'])")
    need_tags = Column(ARRAY(String), nullable=False, server_default="{}", comment="관심 분야 태그 (예: ['funding'])")

    # ── 범위 → RecommendationProfileRequest.employees / annual_sales_krw / business_age_years ──
    #    상한 NULL = "제한 없음" ("10억 이상", "7년 이상"). 0으로 채우면 안 된다.
    employees_min = Column(Integer, nullable=True, comment="상시 근로자 수 하한")
    employees_max = Column(Integer, nullable=True, comment="상시 근로자 수 상한 (NULL=제한 없음)")
    # 원 단위라 Integer(상한 약 21억)로는 넘친다. 10억 매출이 이미 경계에 붙는다.
    annual_sales_min = Column(BigInteger, nullable=True, comment="연매출 하한 (원)")
    annual_sales_max = Column(BigInteger, nullable=True, comment="연매출 상한 (원, NULL=제한 없음)")
    business_age_min = Column(Integer, nullable=True, comment="업력 하한 (년)")
    business_age_max = Column(Integer, nullable=True, comment="업력 상한 (년, NULL=제한 없음)")

    # ── 사용자가 고른 선택지 원문 (마이페이지 표시용) ──
    #    범위만 저장하면 "2억 ~ 5억"을 역산해야 하는데, 선택지 경계가 바뀌면 역매핑이 깨진다.
    industry_label = Column(String(50), nullable=True, comment="예: 음식점업")
    business_status_label = Column(String(50), nullable=True, comment="예: 운영 중인 소상공인")
    annual_sales_label = Column(String(50), nullable=True, comment="예: 2억 ~ 5억")
    employees_label = Column(String(50), nullable=True, comment="예: 상시 1~4인")
    business_age_label = Column(String(50), nullable=True, comment="예: 1~3년")

    # ── 온보딩 완료 시각. NULL이면 아직 온보딩을 안 마쳤다는 뜻 ──
    #    구글 콜백이 신규 유저마다 빈 프로필을 만들기 때문에 "행이 있는가"로는 판정할 수 없다.
    onboarded_at = Column(DateTime(timezone=True), nullable=True, comment="온보딩 완료 시각 (NULL=미완료)")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profile")

    __table_args__ = (
        CheckConstraint(
            "employees_min IS NULL OR employees_max IS NULL OR employees_min <= employees_max",
            name="ck_user_profiles_employees_range",
        ),
        CheckConstraint(
            "annual_sales_min IS NULL OR annual_sales_max IS NULL OR annual_sales_min <= annual_sales_max",
            name="ck_user_profiles_sales_range",
        ),
        CheckConstraint(
            "business_age_min IS NULL OR business_age_max IS NULL OR business_age_min <= business_age_max",
            name="ck_user_profiles_age_range",
        ),
    )


class Favorite(Base):
    """
    [공통 영역] 사용자가 저장(즐겨찾기)한 정책

    홈 달력의 마감일 표시, 정책 찾기의 '저장한' 탭, 서류검토의 정책 선택 드롭다운이
    모두 이 테이블 하나를 바라본다.

    정책 스냅샷(제목 등)을 복사해두지 않고 policy_id만 들고 있는 이유:
    정책 내용이 갱신되면 저장 목록도 함께 최신이어야 하기 때문. 조회 시 조인한다.
    """
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="저장한 사용자",
    )
    policy_id = Column(
        UUID(as_uuid=True),
        ForeignKey("normalized_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="저장한 정규화 정책",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="저장 시각")

    user = relationship("User", back_populates="favorites")
    policy = relationship("NormalizedPolicy")

    __table_args__ = (
        # 같은 정책을 두 번 저장하지 못하게. 저장 토글의 멱등성을 DB가 보장한다.
        UniqueConstraint("user_id", "policy_id", name="uk_favorites_user_policy"),
    )


# 구 스키마 정리 SQL. create_all()은 기존 테이블의 컬럼을 추가/변경해주지 않으므로,
# 호환되지 않는 옛 테이블은 create_all() '이전에' 버려서 새 정의로 다시 만들게 한다.
#
# 주의: 무조건 DROP하면 서버가 뜰 때마다 프로필이 전부 날아간다.
# 구 스키마에만 있던 컬럼(available_time_preference)을 지문 삼아, 옛 테이블일 때만 한 번 버린다.
# 새 테이블이 만들어진 뒤에는 이 컬럼이 없으므로 두 번 다시 실행되지 않는다(멱등).
USER_LEGACY_CLEANUP_SQL = [
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'user_profiles'
              AND column_name = 'available_time_preference'
        ) THEN
            DROP TABLE user_profiles CASCADE;
        END IF;
    END $$;
    """,
]


def ensure_user_schema(bind) -> None:
    """구 user_profiles 테이블을 정리한다. 반드시 create_all() 이전에 호출할 것."""
    if not settings.database_url.startswith("postgresql"):
        return
    for statement in USER_LEGACY_CLEANUP_SQL:
        bind.execute(text(statement))
