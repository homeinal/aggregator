"""
agent_crawler/enhanced_schemas.py

Pydantic 기반 확장 데이터 모델 (OCR 통합 버전)
- RegistrationMethod: 접수방법 Enum
- OCRResult: 개별 이미지 OCR 결과
- OCRDataCollection: 페이지 전체 OCR 데이터
- RegistrationInfo: 접수 정보 상세
- Race: 완전한 대회 정보 (OCR 통합)
- DataSource: 데이터 출처 메타데이터
- ExtractionMetadata: 추출 품질 지표
"""

import uuid
import re
from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ==============================================================================
# Enums
# ==============================================================================

class RegistrationMethod(str, Enum):
    """접수 방법 Enum"""
    FIRST_COME = "선착순"
    LOTTERY = "추첨식"
    QUALIFICATION = "자격제한"
    MIXED = "혼합"
    UNKNOWN = "미확인"
    
    @classmethod
    def from_text(cls, text: str) -> List["RegistrationMethod"]:
        """텍스트에서 접수 방법 추출"""
        methods = []
        text_lower = text.lower()
        
        # 선착순 키워드
        if any(kw in text_lower for kw in ["선착순", "선착", "first-come", "first come", "마감시까지"]):
            methods.append(cls.FIRST_COME)
        
        # 추첨 키워드
        if any(kw in text_lower for kw in ["추첨", "lottery", "랜덤", "무작위", "당첨", "추첨제"]):
            methods.append(cls.LOTTERY)
        
        # 자격제한 키워드
        if any(kw in text_lower for kw in ["기록 인증", "기록 보유", "자격", "조건 충족", "예선 통과"]):
            methods.append(cls.QUALIFICATION)
        
        return methods if methods else [cls.UNKNOWN]


class ImagePriority(str, Enum):
    """이미지 우선순위"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ==============================================================================
# OCR 관련 모델
# ==============================================================================

class OCRResult(BaseModel):
    """개별 이미지 OCR 결과"""
    model_config = ConfigDict(from_attributes=True)
    
    image_url: str = Field(..., description="이미지 URL")
    raw_text: str = Field("", description="OCR 원본 텍스트")
    cleaned_text: Optional[str] = Field(None, description="정제된 텍스트")
    priority: ImagePriority = Field(ImagePriority.MEDIUM, description="이미지 우선순위")
    width: Optional[int] = Field(None, description="이미지 너비 (px)")
    height: Optional[int] = Field(None, description="이미지 높이 (px)")
    confidence: float = Field(0.0, description="OCR 신뢰도 (0-1)")
    
    @computed_field
    @property
    def text_length(self) -> int:
        """텍스트 길이"""
        return len(self.cleaned_text or self.raw_text)
    
    @computed_field
    @property
    def has_useful_text(self) -> bool:
        """유용한 텍스트가 있는지 여부"""
        text = self.cleaned_text or self.raw_text
        # 최소 20자 이상이고 한글이 포함되어 있으면 유용
        return len(text) >= 20 and bool(re.search(r'[가-힣]', text))


class OCRDataCollection(BaseModel):
    """페이지 전체 OCR 데이터"""
    model_config = ConfigDict(from_attributes=True)
    
    results: List[OCRResult] = Field(default_factory=list, description="OCR 결과 목록")
    total_images_found: int = Field(0, description="발견된 총 이미지 수")
    processed_images: int = Field(0, description="처리된 이미지 수")
    
    @computed_field
    @property
    def combined_text(self) -> str:
        """모든 OCR 텍스트 병합"""
        texts = []
        for r in sorted(self.results, key=lambda x: x.priority.value):
            text = r.cleaned_text or r.raw_text
            if text:
                texts.append(f"--- 이미지: {r.image_url} ---\n{text}")
        return "\n\n".join(texts)
    
    @computed_field
    @property
    def high_priority_text(self) -> str:
        """고우선순위 이미지 텍스트만"""
        texts = []
        for r in self.results:
            if r.priority == ImagePriority.HIGH:
                text = r.cleaned_text or r.raw_text
                if text:
                    texts.append(text)
        return "\n\n".join(texts)


# ==============================================================================
# 접수 정보 모델
# ==============================================================================

class RegistrationInfo(BaseModel):
    """접수 정보 상세"""
    model_config = ConfigDict(from_attributes=True)
    
    start_datetime: Optional[datetime] = Field(None, description="접수 시작 일시")
    end_datetime: Optional[datetime] = Field(None, description="접수 마감 일시")
    method: List[RegistrationMethod] = Field(
        default_factory=lambda: [RegistrationMethod.UNKNOWN],
        description="접수 방법 목록"
    )
    method_detail: Optional[str] = Field(None, description="접수 방법 상세 설명")
    time_specified: bool = Field(False, description="시간이 명시되었는지 여부")
    platform: Optional[str] = Field(None, description="접수 플랫폼 (예: 러너블, 네이버폼)")
    
    @field_validator("start_datetime", "end_datetime", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> Optional[datetime]:
        """다양한 날짜/시간 형식 파싱"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        
        v_str = str(v).strip()
        
        # ISO 8601
        try:
            return datetime.fromisoformat(v_str.replace("Z", "+00:00"))
        except ValueError:
            pass
        
        # 다양한 패턴 시도
        patterns = [
            # 날짜+시간
            (r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})\s*[T ]?(\d{1,2}):(\d{2})", "%Y %m %d %H %M"),
            (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2}):(\d{2})", "%Y %m %d %H %M"),
            (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*오전\s*(\d{1,2})시", "%Y %m %d %H"),
            (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*오후\s*(\d{1,2})시", "%Y %m %d %H PM"),
            # 날짜만
            (r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", "%Y %m %d"),
            (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", "%Y %m %d"),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, v_str)
            if match:
                groups = match.groups()
                try:
                    if "PM" in fmt:
                        # 오후 처리
                        hour = int(groups[3])
                        if hour < 12:
                            hour += 12
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]), hour)
                    elif len(groups) >= 5:
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]), 
                                       int(groups[3]), int(groups[4]))
                    elif len(groups) >= 4:
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]))
                    else:
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                except ValueError:
                    continue
        
        return None
    
    @field_validator("method", mode="before")
    @classmethod
    def parse_method(cls, v: Any) -> List[RegistrationMethod]:
        """접수 방법 파싱"""
        if v is None:
            return [RegistrationMethod.UNKNOWN]
        
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, RegistrationMethod):
                    result.append(item)
                elif isinstance(item, str):
                    # Enum 값으로 변환 시도
                    try:
                        result.append(RegistrationMethod(item))
                    except ValueError:
                        # 텍스트에서 추출
                        result.extend(RegistrationMethod.from_text(item))
            return result if result else [RegistrationMethod.UNKNOWN]
        
        if isinstance(v, str):
            return RegistrationMethod.from_text(v)
        
        return [RegistrationMethod.UNKNOWN]


# ==============================================================================
# 데이터 출처 메타데이터
# ==============================================================================

class DataSource(BaseModel):
    """데이터 출처 추적"""
    model_config = ConfigDict(from_attributes=True)
    
    from_html: bool = Field(False, description="HTML에서 추출됨")
    from_ocr: bool = Field(False, description="OCR에서 추출됨")
    ocr_image_url: Optional[str] = Field(None, description="OCR 소스 이미지 URL")
    ocr_confidence: float = Field(0.0, description="OCR 신뢰도")
    conflict_detected: bool = Field(False, description="HTML/OCR 충돌 감지됨")
    conflict_resolution: Optional[str] = Field(None, description="충돌 해결 방법")


class ExtractionMetadata(BaseModel):
    """추출 품질 지표"""
    model_config = ConfigDict(from_attributes=True)
    
    confidence: float = Field(0.0, description="전체 신뢰도 (0-1)")
    missing_fields: List[str] = Field(default_factory=list, description="누락된 필드 목록")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지 목록")
    extraction_time: Optional[datetime] = Field(None, description="추출 시간")
    llm_model: Optional[str] = Field(None, description="사용된 LLM 모델")
    
    @computed_field
    @property
    def quality_level(self) -> str:
        """품질 수준"""
        if self.confidence >= 0.8:
            return "HIGH"
        elif self.confidence >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"


# ==============================================================================
# 종목 정보
# ==============================================================================

class RaceCategory(BaseModel):
    """종목 정보"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(default_factory=generate_uuid, description="종목 ID (UUID)")
    race_id: str = Field(default="", description="부모 대회 ID")
    name: str = Field(..., description="종목명 (예: 10km, 하프, 풀)")
    fee: Optional[int] = Field(None, description="참가비 (숫자)")
    qualification: Optional[str] = Field(None, description="참가자격")
    start_time: Optional[str] = Field(None, description="출발시간 (HH:mm)")
    registration_start_time: Optional[str] = Field(None, description="접수 시작 시간 (HH:mm)")
    application_method: Optional[str] = Field(None, description="접수 방식 (예: 선착순, 추첨제)")
    notes: Optional[str] = Field(None, description="종목별 특이사항")
    
    @field_validator("fee", mode="before")
    @classmethod
    def parse_fee(cls, v: Any) -> Optional[int]:
        """금액 파싱"""
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            digits = re.sub(r'[^\d]', '', v)
            if digits:
                return int(digits)
        return None
    
    @field_validator("start_time", "registration_start_time", mode="before")
    @classmethod
    def parse_time(cls, v: Any) -> Optional[str]:
        """시간 정규화: HH:mm 형식"""
        if not v:
            return None
        v_str = str(v).strip()
        match = re.search(r'(\d{1,2}):(\d{2})', v_str)
        if match:
            hour, minute = match.groups()
            return f"{int(hour):02d}:{minute}"
        return None


# ==============================================================================
# 메인 Race 모델 (OCR 통합)
# ==============================================================================

class Race(BaseModel):
    """대회 메인 정보 (OCR 통합 버전)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(default_factory=generate_uuid, description="대회 ID")
    title: str = Field(..., description="대회명")
    source_url: str = Field(..., description="수집 원본 URL")
    event_date: Optional[datetime] = Field(None, description="대회 개최일")
    
    # 위치 정보
    country: str = Field("한국", description="개최 국가")
    region: Optional[str] = Field(None, description="지역 (예: 서울, 부산)")
    venue: Optional[str] = Field(None, description="장소 (예: 잠실종합운동장)")
    address: Optional[str] = Field(None, description="상세 주소")
    
    # 주최 정보
    organizer: Optional[str] = Field(None, description="주최사")
    organizer_rep: Optional[str] = Field(None, description="주최 대표자")
    
    # 연락처
    phone: Optional[str] = Field(None, description="문의 전화번호")
    email: Optional[str] = Field(None, description="문의 이메일")
    website: Optional[str] = Field(None, description="공식 웹사이트")
    
    # 이미지
    image_url: Optional[str] = Field(None, description="대표 이미지/포스터 URL")
    
    # 안내
    general_guide: Optional[str] = Field(None, description="대회 종합 안내")
    is_featured: bool = Field(False, description="추천 여부")
    
    # 접수 정보 (확장)
    registration: Optional[RegistrationInfo] = Field(None, description="접수 정보")
    
    # 종목
    categories: List[RaceCategory] = Field(default_factory=list, description="종목 리스트")
    
    # OCR 데이터
    ocr_data: Optional[OCRDataCollection] = Field(None, description="OCR 수집 데이터")
    content_images: List[dict] = Field(default_factory=list, description="OCR 처리된 이미지 (레거시 호환)")
    
    # 메타데이터
    data_source: Optional[DataSource] = Field(None, description="데이터 출처")
    extraction_metadata: Optional[ExtractionMetadata] = Field(None, description="추출 메타데이터")
    
    @field_validator("event_date", mode="before")
    @classmethod
    def parse_event_date(cls, v: Any) -> Optional[datetime]:
        """대회일 파싱"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        
        v_str = str(v).strip()
        
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
        phone = re.sub(r'[^\d\-]', '', str(v))
        return phone if phone else None
    
    @field_validator("email", mode="before")
    @classmethod
    def parse_email(cls, v: Any) -> Optional[str]:
        """이메일 검증"""
        if not v:
            return None
        v_str = str(v).strip()
        if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v_str):
            return v_str
        return None
    
    def calculate_confidence(self) -> float:
        """신뢰도 자동 계산"""
        score = 0.0
        
        # 필수 필드 (각 0.2)
        if self.title and self.title != "Unknown":
            score += 0.2
        if self.event_date:
            score += 0.2
        
        # 접수 정보 (각 0.15)
        if self.registration:
            if self.registration.start_datetime:
                score += 0.15
            if self.registration.method and RegistrationMethod.UNKNOWN not in self.registration.method:
                score += 0.15
        
        # 기타 정보 (각 0.1)
        if self.venue:
            score += 0.1
        if self.categories:
            score += 0.1
        if self.organizer:
            score += 0.1
        
        return min(score, 1.0)
    
    def to_legacy_format(self) -> dict:
        """기존 시스템 호환 형식으로 변환"""
        data = self.model_dump(mode="json")
        
        # datetime을 문자열로
        if data.get("event_date"):
            data["event_date"] = str(data["event_date"])
        
        # registration 필드 평탄화
        if data.get("registration"):
            reg = data["registration"]
            data["registration_start_date"] = reg.get("start_datetime")
            data["registration_end_date"] = reg.get("end_datetime")
            data["registration_method"] = [m for m in reg.get("method", [])]
        
        # 불필요한 확장 필드 제거
        for key in ["ocr_data", "data_source", "extraction_metadata", "registration"]:
            data.pop(key, None)
        
        return data
