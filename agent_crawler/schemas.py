"""
agent_crawler/schemas.py

Pydantic 데이터 모델 정의 (강화된 Validator 포함)
- Race: 대회 메인 정보
- RaceCategory: 종목 정보
- 날짜/금액 자동 정규화
"""

import uuid
import re
from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


def generate_uuid() -> str:
    return str(uuid.uuid4())


class RaceCategory(BaseModel):
    """종목 정보 (1:N 관계)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(default_factory=generate_uuid, description="종목 아이디 (UUID)")
    race_id: str = Field(default="", description="부모 대회 ID")
    name: str = Field(..., description="종목명 (예: 10km, 하프, 풀)")
    fee: Optional[int] = Field(None, description="참가비 (숫자)")
    qualification: Optional[str] = Field(None, description="참가자격")
    start_time: Optional[str] = Field(None, description="출발시간 (HH:mm)")
    registration_start_time: Optional[str] = Field(None, description="접수 시작 시간 (HH:mm)")
    application_method: Optional[str] = Field(None, description="접수 방식 (예: 선착순, 추첨제)")
    notes: Optional[str] = Field(None, description="종목별 특이사항")
    next_registration_at: Optional[datetime] = Field(None, description="접수 시작일")
    next_registration_end_at: Optional[datetime] = Field(None, description="접수 마감일")
    next_payment_at: Optional[datetime] = Field(None, description="결제 시작일")
    next_payment_end_at: Optional[datetime] = Field(None, description="결제 마감일")
    
    @field_validator("fee", mode="before")
    @classmethod
    def parse_fee(cls, v: Any) -> Optional[int]:
        """
        금액 파싱: 문자열/숫자 모두 처리
        "50,000원" -> 50000
        "30000" -> 30000
        """
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            # 숫자만 추출
            digits = re.sub(r'[^\d]', '', v)
            if digits:
                return int(digits)
        return None
    
    @field_validator("start_time", "registration_start_time", mode="before")
    @classmethod
    def parse_start_time(cls, v: Any) -> Optional[str]:
        """시간 정규화: HH:mm 형식"""
        if not v:
            return None
        v_str = str(v).strip()
        # HH:mm 형식 확인
        match = re.search(r'(\d{1,2}):(\d{2})', v_str)
        if match:
            hour, minute = match.groups()
            return f"{int(hour):02d}:{minute}"
        return None


class Race(BaseModel):
    """대회 메인 정보"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(default_factory=generate_uuid, description="대회 아이디")
    title: str = Field(..., description="대회명")
    source_url: str = Field(..., description="수집 대상 원본 URL")
    event_date: Optional[datetime] = Field(None, description="대회 개최일")
    country: Optional[str] = Field("한국", description="개최 국가")
    region: Optional[str] = Field(None, description="지역 (예: 서울, 부산)")
    venue: Optional[str] = Field(None, description="장소 (예: 잠실종합운동장)")
    organizer: Optional[str] = Field(None, description="주최사")
    organizer_rep: Optional[str] = Field(None, description="주최 대표자")
    phone: Optional[str] = Field(None, description="문의 전화번호")
    email: Optional[str] = Field(None, description="문의 이메일")
    website: Optional[str] = Field(None, description="공식 웹사이트 링크")
    image_url: Optional[str] = Field(None, description="대표 이미지/포스터 URL")
    general_guide: Optional[str] = Field(None, description="대회 종합 안내 텍스트")
    is_featured: bool = Field(False, description="추천 여부")
    
    # Nested Categories
    categories: List[RaceCategory] = Field(default_factory=list, description="해당 대회의 종목 리스트")
    
    content_images: List[dict] = Field(default_factory=list, description="OCR 처리된 이미지 정보 및 텍스트")
    
    @field_validator("event_date", mode="before")
    @classmethod
    def parse_event_date(cls, v: Any) -> Optional[datetime]:
        """
        날짜 파싱: 다양한 형식 지원
        YYYY-MM-DD, YYYY.MM.DD, YYYY년 MM월 DD일
        """
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        
        v_str = str(v).strip()
        
        # 다양한 날짜 패턴
        patterns = [
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", None),
            (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", None),
            (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", None),
            (r"(\d{4})/(\d{1,2})/(\d{1,2})", None),
        ]
        
        for pattern, _ in patterns:
            match = re.search(pattern, v_str)
            if match:
                try:
                    year, month, day = match.groups()
                    return datetime(int(year), int(month), int(day))
                except ValueError:
                    continue
        
        return None
    
    @field_validator("phone", mode="before")
    @classmethod
    def parse_phone(cls, v: Any) -> Optional[str]:
        """전화번호 정규화"""
        if not v:
            return None
        # 숫자와 하이픈만 유지
        phone = re.sub(r'[^\d\-]', '', str(v))
        return phone if phone else None
    
    @field_validator("email", mode="before")
    @classmethod
    def parse_email(cls, v: Any) -> Optional[str]:
        """이메일 검증"""
        if not v:
            return None
        v_str = str(v).strip()
        # 간단한 이메일 패턴 확인
        if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v_str):
            return v_str
        return None
