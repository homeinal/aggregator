"""
agent_crawler/schemas.py (OCR 통합 버전)

기존 Race/RaceCategory 모델에 OCR 관련 기능 추가:
- OCRResult: 개별 이미지 OCR 결과
- RegistrationMethod: 접수방법 표준화 Enum
- RegistrationInfo: 접수 정보 상세화
- 기존 모델에 OCR 데이터 필드 추가
"""

import uuid
import re
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ============================================================================
# 새로 추가: OCR 관련 모델
# ============================================================================

class RegistrationMethod(str, Enum):
    """접수 방법 표준화 (새로 추가)"""
    FIRST_COME = "선착순"
    LOTTERY = "추첨식"
    QUALIFICATION = "자격제한"
    MIXED = "혼합형"
    UNKNOWN = "알수없음"


class OCRResult(BaseModel):
    """개별 이미지 OCR 결과 (새로 추가)"""
    model_config = ConfigDict(from_attributes=True)
    
    image_url: str = Field(..., description="이미지 URL")
    image_size: tuple[int, int] = Field(..., description="이미지 크기 (width, height)")
    raw_text: str = Field(..., description="Google Vision API 원본 텍스트")
    cleaned_text: str = Field(..., description="정제된 텍스트")
    confidence: float = Field(ge=0, le=1, description="OCR 신뢰도")
    detected_info_types: List[str] = Field(
        default_factory=list, 
        description="감지된 정보 타입 (registration, date, location, fee 등)"
    )
    extraction_timestamp: datetime = Field(
        default_factory=datetime.now, 
        description="OCR 수행 시각"
    )


class DataSource(BaseModel):
    """데이터 출처 메타데이터 (새로 추가)"""
    model_config = ConfigDict(from_attributes=True)
    
    from_html: bool = Field(False, description="HTML에서 추출된 정보 포함 여부")
    from_ocr: bool = Field(False, description="OCR에서 추출된 정보 포함 여부")
    ocr_confidence: Optional[float] = Field(None, description="평균 OCR 신뢰도")
    conflicting_sources: bool = Field(
        False, 
        description="HTML과 OCR 정보가 충돌하는 경우"
    )


class ExtractionMetadata(BaseModel):
    """추출 메타데이터 (새로 추가)"""
    model_config = ConfigDict(from_attributes=True)
    
    confidence: float = Field(ge=0, le=1, default=0.0, description="전체 추출 신뢰도")
    missing_fields: List[str] = Field(default_factory=list, description="누락된 필수 필드")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지")
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    llm_model: str = Field("gpt-4o-mini", description="사용된 LLM 모델")
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


# ============================================================================
# 기존 모델 유지 + 개선
# ============================================================================

class RaceCategory(BaseModel):
    """종목 정보 (1:N 관계) - 기존 유지 + 접수방법 개선"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(default_factory=generate_uuid, description="종목 아이디 (UUID)")
    race_id: str = Field(default="", description="부모 대회 ID")
    name: str = Field(..., description="종목명 (예: 10km, 하프, 풀)")
    fee: Optional[int] = Field(None, description="참가비 (숫자)")
    qualification: Optional[str] = Field(None, description="참가자격")
    start_time: Optional[str] = Field(None, description="출발시간 (HH:mm)")
    registration_start_time: Optional[str] = Field(None, description="접수 시작 시간 (HH:mm)")
    
    # 🆕 개선: application_method를 표준화된 Enum으로 변경 (선택적)
    application_method: Optional[str] = Field(
        None, 
        description="접수 방식 (예: 선착순, 추첨제) - 표준값 권장"
    )
    application_method_detail: Optional[str] = Field(
        None, 
        description="접수 방식 상세 설명 (원문)"
    )
    
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
    
    # 🆕 추가: 날짜/시간 파싱 개선
    @field_validator(
        "next_registration_at", 
        "next_registration_end_at",
        "next_payment_at",
        "next_payment_end_at",
        mode="before"
    )
    @classmethod
    def parse_datetime_fields(cls, v: Any) -> Optional[datetime]:
        """
        다양한 날짜/시간 형식 파싱
        - "2024년 10월 1일 10시"
        - "2024-10-01 10:00"
        - "10월 1일 오전 10시"
        """
        if v is None or isinstance(v, datetime):
            return v
        
        if not isinstance(v, str):
            v = str(v)
        
        v_str = v.strip()
        
        # 패턴 1: ISO 형식
        if 'T' in v_str or '+' in v_str:
            try:
                return datetime.fromisoformat(v_str.replace('Z', '+00:00'))
            except:
                pass
        
        # 패턴 2: 한글 형식 "YYYY년 MM월 DD일 HH시"
        match = re.search(
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시', 
            v_str
        )
        if match:
            year, month, day, hour = match.groups()
            # 오전/오후 처리
            hour_int = int(hour)
            if '오후' in v_str and hour_int != 12:
                hour_int += 12
            elif '오전' in v_str and hour_int == 12:
                hour_int = 0
            try:
                return datetime(int(year), int(month), int(day), hour_int)
            except ValueError:
                pass
        
        # 패턴 3: "YYYY-MM-DD HH:mm"
        match = re.search(
            r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})\s+(\d{1,2}):(\d{2})', 
            v_str
        )
        if match:
            year, month, day, hour, minute = match.groups()
            try:
                return datetime(
                    int(year), int(month), int(day), 
                    int(hour), int(minute)
                )
            except ValueError:
                pass
        
        # 패턴 4: "MM월 DD일 HH시" (현재 연도 추정)
        match = re.search(r'(\d{1,2})월\s*(\d{1,2})일.*?(\d{1,2})시', v_str)
        if match:
            month, day, hour = match.groups()
            current_year = datetime.now().year
            hour_int = int(hour)
            if '오후' in v_str and hour_int != 12:
                hour_int += 12
            try:
                return datetime(current_year, int(month), int(day), hour_int)
            except ValueError:
                pass
        
        return None
    
    # 🆕 추가: 접수 방법 표준화
    @field_validator("application_method", mode="before")
    @classmethod
    def standardize_application_method(cls, v: Any) -> Optional[str]:
        """
        접수 방법 표준화
        - "선착순", "선착" → "선착순"
        - "추첨", "래플" → "추첨식"
        - "자격", "제한" → "자격제한"
        """
        if not v:
            return None
        
        v_str = str(v).lower()
        
        # 키워드 매칭
        if any(kw in v_str for kw in ['선착순', '선착', '빠른순', '조기마감']):
            return RegistrationMethod.FIRST_COME.value
        
        if any(kw in v_str for kw in ['추첨', '래플', 'raffle', '당첨']):
            return RegistrationMethod.LOTTERY.value
        
        if any(kw in v_str for kw in ['자격', '제한', '초청', 'invitation']):
            return RegistrationMethod.QUALIFICATION.value
        
        # 혼합형 판별
        has_first = any(kw in v_str for kw in ['선착', '선착순'])
        has_lottery = any(kw in v_str for kw in ['추첨', '래플'])
        if has_first and has_lottery:
            return RegistrationMethod.MIXED.value
        
        # 매칭되지 않으면 원본 반환 (또는 UNKNOWN)
        return v if v else RegistrationMethod.UNKNOWN.value


class Race(BaseModel):
    """대회 메인 정보 - 기존 유지 + OCR 필드 추가"""
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
    
    # 기존 필드
    categories: List[RaceCategory] = Field(
        default_factory=list, 
        description="해당 대회의 종목 리스트"
    )
    
    # 🆕 OCR 관련 필드 추가
    content_images: List[dict] = Field(
        default_factory=list, 
        description="OCR 처리된 이미지 정보 및 텍스트"
    )
    
    ocr_results: List[OCRResult] = Field(
        default_factory=list,
        description="개별 이미지 OCR 상세 결과"
    )
    
    data_source: Optional[DataSource] = Field(
        None,
        description="데이터 출처 메타데이터 (HTML/OCR 구분)"
    )
    
    extraction_metadata: Optional[ExtractionMetadata] = Field(
        None,
        description="추출 품질 메타데이터"
    )
    
    raw_html_text: Optional[str] = Field(
        None, 
        description="원본 HTML 텍스트 (디버깅용)"
    )
    
    # 기존 validator들 유지
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
    
    # 🆕 추가: 신뢰도 자동 계산
    @model_validator(mode='after')
    def calculate_confidence(self):
        """
        추출 신뢰도 자동 계산
        - 필수 필드: title, event_date (60점)
        - 우선순위 필드: categories, venue (30점)
        - 선택 필드: phone, email 등 (10점)
        """
        if not self.extraction_metadata:
            self.extraction_metadata = ExtractionMetadata()
        
        score = 0
        max_score = 100
        
        # 필수 필드 (60점)
        if self.title:
            score += 30
        if self.event_date:
            score += 30
        
        # 우선순위 필드 (30점)
        if self.categories and len(self.categories) > 0:
            score += 15
            # 종목에 접수 정보가 있으면 추가 점수
            if any(c.next_registration_at for c in self.categories):
                score += 5
        if self.venue:
            score += 10
        
        # 선택 필드 (10점)
        if self.phone:
            score += 3
        if self.email:
            score += 3
        if self.website:
            score += 4
        
        self.extraction_metadata.confidence = min(score / max_score, 1.0)
        
        # 누락 필드 체크
        missing = []
        if not self.title:
            missing.append('title')
        if not self.event_date:
            missing.append('event_date')
        if not self.categories or len(self.categories) == 0:
            missing.append('categories')
        if not any(c.next_registration_at for c in self.categories):
            missing.append('registration_datetime')
        if not any(c.application_method for c in self.categories):
            missing.append('application_method')
        
        self.extraction_metadata.missing_fields = missing
        
        return self


# ============================================================================
# 유틸리티 함수
# ============================================================================

def merge_html_and_ocr_data(html_race: Race, ocr_race: Race) -> Race:
    """
    HTML에서 추출한 데이터와 OCR에서 추출한 데이터를 병합
    OCR 데이터를 우선하되, 누락된 정보는 HTML로 보완
    """
    # OCR이 더 신뢰도가 높으므로 기본값으로 사용
    merged = ocr_race.model_copy(deep=True)
    
    # HTML에만 있는 정보 보완
    if not merged.email and html_race.email:
        merged.email = html_race.email
        if merged.data_source:
            merged.data_source.from_html = True
    
    if not merged.website and html_race.website:
        merged.website = html_race.website
        if merged.data_source:
            merged.data_source.from_html = True
    
    if not merged.phone and html_race.phone:
        merged.phone = html_race.phone
        if merged.data_source:
            merged.data_source.from_html = True
    
    # 충돌 감지
    if merged.data_source and html_race.event_date and ocr_race.event_date:
        if html_race.event_date.date() != ocr_race.event_date.date():
            merged.data_source.conflicting_sources = True
            if merged.extraction_metadata:
                merged.extraction_metadata.warnings.append(
                    f"날짜 불일치: HTML={html_race.event_date.date()}, "
                    f"OCR={ocr_race.event_date.date()}"
                )
    
    return merged


# ============================================================================
# 테스트용 예시
# ============================================================================

if __name__ == "__main__":
    # 테스트 데이터
    test_category = {
        "name": "풀코스",
        "fee": "50,000원",
        "application_method": "선착순 마감",
        "next_registration_at": "2024년 10월 1일 10시"
    }
    
    category = RaceCategory.model_validate(test_category)
    print(f"종목: {category.name}")
    print(f"참가비: {category.fee}원")
    print(f"접수방법: {category.application_method}")
    print(f"접수시작: {category.next_registration_at}")
    
    test_race = {
        "title": "2024 서울 마라톤",
        "source_url": "https://example.com",
        "event_date": "2024-11-17",
        "categories": [test_category],
        "data_source": {
            "from_ocr": True,
            "ocr_confidence": 0.92
        }
    }
    
    race = Race.model_validate(test_race)
    print(f"\n대회: {race.title}")
    print(f"신뢰도: {race.extraction_metadata.confidence:.2%}")
    print(f"누락 필드: {race.extraction_metadata.missing_fields}")
