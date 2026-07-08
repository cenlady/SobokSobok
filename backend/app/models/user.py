from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship

from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Google OAuth 등 외부 소셜 로그인 연동을 위해 nullable 허용
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # 기획 요건: 업종/지역/매출/직원수 + 가용시간 선호
    industry = Column(JSON, nullable=True)                  # 예: ["음식점업", "제조업"]
    region = Column(String(255), nullable=True)             # 예: "서울특별시 마포구"
    sales = Column(Integer, nullable=True)                  # 매출액 상한선 등
    employees = Column(Integer, nullable=True)              # 직원 수
    available_time_preference = Column(JSON, nullable=True) # 가용시간 선호 정보 (요일/시간대 등 자유 형식)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profile")
