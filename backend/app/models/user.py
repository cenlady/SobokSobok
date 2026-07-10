# -*- coding: utf-8 -*-
# 파일 역할: [공통/인증 도메인] 사용자(User) 및 프로필(UserProfile) ORM 모델 정의

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship

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
    
    # Google OAuth2.0 캘린더 연동 토큰 저장용 컬럼 추가 (이재혁 도메인 연동)
    google_access_token = Column(String(255), nullable=True, comment="Google API Access Token")
    google_refresh_token = Column(String(255), nullable=True, comment="Google API Refresh Token (영구 일정 연동에 사용)")
    google_token_expires_at = Column(DateTime(timezone=True), nullable=True, comment="Google Access Token 만료 일시")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="수정일시")

    # 1:1 관계의 프로필 설정
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base):
    """
    [공통 영역] 사용자 프로필 (추천 및 사전 필터용 세부 정보)
    - 소유자: 공통 사용 (추천 서비스의 필터 연동에 핵심 활용)
    - 역할: 사용자의 업종, 지역, 매출액, 직원수, 선호 가용시간을 저장하여 맞춤 정책 추천에 사용
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, comment="사용자 ID 참조")
    
    # 기획 요건에 맞춘 개인 프로필 파라미터
    industry = Column(JSON, nullable=True, comment="선택 업종 목록 (예: ['음식점업', '제조업'])")
    region = Column(String(255), nullable=True, comment="지역 (예: '서울특별시 마포구')")
    sales = Column(Integer, nullable=True, comment="연간 매출액 (원 단위 등)")
    employees = Column(Integer, nullable=True, comment="상시 근로자 수 (직원 수)")
    available_time_preference = Column(JSON, nullable=True, comment="가용시간 선호 정보 (예: 주말 가능, 야간 등)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profile")
