# OCR 통합 마라톤 크롤러 - 구현 가이드

## 📁 파일 구조

```
agent_crawler/
├── __init__.py
├── crawler_agent.py           # 기존 크롤러 (유지 또는 교체)
├── content_cleaner.py         # HTML 정제
├── link_selector.py           # 링크 선별
├── llm_client.py              # LLM 클라이언트
├── schemas.py                 # 기존 스키마
├── enhanced_schemas.py        # [NEW] 확장 스키마
├── ocr_crawler_implementation.py  # [NEW] OCR 통합 크롤러
├── race_extraction_prompts.md # [NEW] 프롬프트 모음
└── main.py                    # 엔트리포인트
```

---

## 🔧 구현 6단계

### Step 1: 의존성 설치

```bash
pip install google-cloud-vision>=3.5.0 aiohttp>=3.9.0 pillow>=10.1.0
```

`requirements.txt`에 추가:
```
google-cloud-vision>=3.5.0
aiohttp>=3.9.0
pillow>=10.1.0
```

### Step 2: 환경 설정

`.env` 파일:
```env
OPENAI_API_KEY=sk-xxx
GOOGLE_APPLICATION_CREDENTIALS=/path/to/my_key.json
```

### Step 3: 스키마 통합

옵션 A - 기존 스키마 교체:
```python
# agent_crawler/schemas.py
from .enhanced_schemas import *
```

옵션 B - 별도 사용 (권장):
```python
# 필요한 곳에서 import
from agent_crawler.enhanced_schemas import Race, RegistrationInfo
```

### Step 4: 크롤러 교체/업그레이드

옵션 A - 새 크롤러 사용:
```python
# main.py에서
from agent_crawler.ocr_crawler_implementation import EnhancedCrawlerAgent

async with EnhancedCrawlerAgent(api_key) as agent:
    result = await agent.crawl_and_extract(url, url_id)
```

옵션 B - 기존 크롤러 확장:
```python
# crawler_agent.py에 OCRImageProcessor 추가
from .ocr_crawler_implementation import OCRImageProcessor
```

### Step 5: 프롬프트 적용

`llm_client.py`의 `extract_race_data` 메서드에서:
- `race_extraction_prompts.md` 섹션 3.1의 System Prompt 사용
- Few-shot 예시 유지

### Step 6: 테스트 실행

```bash
python agent_crawler/main.py --limit 1
```

---

## 🧪 테스트 계획

### 단위 테스트

```python
# tests/test_enhanced_schemas.py
import pytest
from agent_crawler.enhanced_schemas import RegistrationInfo, RegistrationMethod

def test_registration_method_from_text():
    methods = RegistrationMethod.from_text("선착순 마감")
    assert RegistrationMethod.FIRST_COME in methods

def test_datetime_parsing():
    reg = RegistrationInfo(start_datetime="2024년 10월 1일 오전 10시")
    assert reg.start_datetime.hour == 10
```

### 통합 테스트

```python
# tests/test_ocr_crawler.py
import pytest
from agent_crawler.ocr_crawler_implementation import EnhancedCrawlerAgent

@pytest.mark.asyncio
async def test_crawl_and_extract():
    async with EnhancedCrawlerAgent(api_key) as agent:
        result = await agent.crawl_and_extract("http://example.com", "test_1")
        assert result is not None
        race, context = result
        assert race.title != "Unknown"
```

---

## 📊 모니터링 스크립트

### 신뢰도 분석

```python
from pathlib import Path
import json

def analyze_confidence():
    confidences = []
    for data_file in Path('results').glob('*/data.json'):
        with open(data_file) as f:
            data = json.load(f)
            conf = data.get('extraction_metadata', {}).get('confidence', 0)
            confidences.append(conf)
    
    print(f"평균 신뢰도: {sum(confidences)/len(confidences):.1%}")
    print(f"최소: {min(confidences):.1%}")
    print(f"최대: {max(confidences):.1%}")
```

### 접수 정보 추출률

```python
def analyze_registration_extraction():
    total = extracted_method = extracted_time = 0
    
    for data_file in Path('results').glob('*/data.json'):
        total += 1
        with open(data_file) as f:
            data = json.load(f)
            reg = data.get('registration', {})
            if reg.get('method'):
                extracted_method += 1
            if reg.get('start_datetime'):
                extracted_time += 1
    
    print(f"접수방법 추출률: {extracted_method/total:.1%}")
    print(f"접수시간 추출률: {extracted_time/total:.1%}")
```

---

## 🚀 배포 체크리스트

- [ ] 의존성 설치 확인
- [ ] Google Cloud 인증 파일 배치
- [ ] 환경 변수 설정
- [ ] 테스트 URL로 단일 실행 확인
- [ ] 결과 파일 구조 확인 (data.json, raw_data.json, ocr/)
- [ ] 에러 로그 확인

---

## 💡 최적화 팁

### 비용 절감

1. **이미지 제한**: 고우선순위 이미지만 OCR (최대 3개)
2. **캐싱**: 동일 이미지 재처리 방지
3. **배치 처리**: Vision API 비동기 활용

### 성능 개선

1. **병렬 처리**: OCR과 서브페이지 크롤링 동시 실행
2. **타임아웃 단축**: 응답 없는 이미지 빠르게 스킵
3. **메모리 관리**: 큰 이미지 처리 후 즉시 해제

---

## 🐛 알려진 이슈 및 해결

### Issue 1: OCR 결과 없음

**원인**: Vision API 키 설정 오류 또는 네트워크 문제
**해결**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
python -c "from google.cloud import vision; print(vision.ImageAnnotatorClient())"
```

### Issue 2: 날짜 파싱 실패

**원인**: 지원되지 않는 날짜 형식
**해결**: `enhanced_schemas.py`의 `parse_datetime`에 패턴 추가

### Issue 3: 접수 방법 "미확인"

**원인**: 키워드 불일치
**해결**: `RegistrationMethod.from_text()`에 키워드 추가

---

## 📂 결과 파일 예시

### data.json
```json
{
  "id": "uuid-xxx",
  "title": "제20회 여수해양마라톤",
  "event_date": "2026-01-11",
  "registration": {
    "start_datetime": "2025-12-01T00:00:00",
    "method": ["선착순"],
    "time_specified": false
  },
  "categories": [
    {"name": "풀코스", "fee": 40000, "start_time": "09:30"}
  ],
  "extraction_metadata": {
    "confidence": 0.85,
    "quality_level": "HIGH"
  }
}
```

### ocr/image_1.json
```json
{
  "image_url": "http://example.com/poster.jpg",
  "raw_text": "제20회 여수해양마라톤...",
  "cleaned_text": "제20회 여수해양마라톤\n대회일시: 2026년 1월 11일",
  "confidence": 0.92
}
```
