"""
agent_crawler/ocr_crawler_implementation.py

완전한 OCR 통합 크롤러 구현 예시
- OCRImageProcessor: 이미지 필터링 및 OCR 전담
- EnhancedCrawlerAgent: 메인 크롤러 (OCR 통합)
"""

import asyncio
import random
import os
import re
import json
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from pathlib import Path

from google.cloud import vision
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

# 확장 스키마 import
from .enhanced_schemas import (
    Race, RaceCategory, RegistrationInfo, RegistrationMethod,
    OCRResult, OCRDataCollection, ImagePriority,
    DataSource, ExtractionMetadata
)
from .content_cleaner import ContentCleaner
from .link_selector import LinkSelector
from .llm_client import LLMClient, FEW_SHOT_EXAMPLE_INPUT, FEW_SHOT_EXAMPLE_OUTPUT


# ==============================================================================
# 이미지 필터링 결과
# ==============================================================================

@dataclass
class FilteredImages:
    """필터링된 이미지 분류 결과"""
    high_priority: List[str] = field(default_factory=list)
    medium_priority: List[str] = field(default_factory=list)
    low_priority: List[str] = field(default_factory=list)
    
    @property
    def all_images(self) -> List[str]:
        """모든 이미지 URL (우선순위순)"""
        return self.high_priority + self.medium_priority + self.low_priority
    
    @property
    def total_count(self) -> int:
        """총 이미지 수"""
        return len(self.high_priority) + len(self.medium_priority) + len(self.low_priority)


# ==============================================================================
# OCR 이미지 프로세서
# ==============================================================================

class OCRImageProcessor:
    """이미지 필터링 및 OCR 전담 클래스"""
    
    # 포스터 관련 키워드
    POSTER_KEYWORDS = ["poster", "banner", "main", "대회", "마라톤", "행사"]
    
    # 무시할 이미지 패턴
    IGNORE_PATTERNS = ["logo", "icon", "avatar", "profile", "button", "arrow"]
    
    def __init__(self):
        """OCR 프로세서 초기화"""
        self.vision_client: Optional[vision.ImageAnnotatorClient] = None
        self._init_vision_client()
    
    def _init_vision_client(self):
        """Google Cloud Vision 클라이언트 초기화"""
        try:
            # 환경 변수에서 인증 정보 로드
            credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                credentials_path = os.path.abspath("my_key.json")
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
            self.vision_client = vision.ImageAnnotatorClient()
            print("   ✅ Google Vision Client 초기화 완료")
        except Exception as e:
            print(f"   ⚠️ Google Vision Client 초기화 실패: {e}")
            self.vision_client = None
    
    async def filter_images(self, page: Page, base_url: str) -> FilteredImages:
        """
        페이지에서 이미지를 추출하고 우선순위 분류
        
        Args:
            page: Playwright Page 객체
            base_url: 기준 URL
            
        Returns:
            FilteredImages: 분류된 이미지 URL
        """
        result = FilteredImages()
        
        try:
            # JavaScript로 이미지 정보 수집
            images_info = await page.evaluate('''() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs.map(img => ({
                    src: img.src,
                    alt: img.alt || '',
                    width: img.clientWidth,
                    height: img.clientHeight,
                    inMain: !!img.closest('main, article, .content, #content'),
                    className: img.className || ''
                })).filter(img => img.src && img.width > 0 && img.height > 0);
            }''')
            
            for img in images_info:
                url = img['src']
                if not url.startswith('http'):
                    url = urljoin(base_url, url)
                
                # 무시할 패턴 체크
                url_lower = url.lower()
                if any(p in url_lower for p in self.IGNORE_PATTERNS):
                    continue
                
                width = img['width']
                height = img['height']
                alt = img.get('alt', '').lower()
                in_main = img.get('inMain', False)
                
                # 우선순위 결정
                priority = self._determine_priority(url, width, height, alt, in_main)
                
                if priority == ImagePriority.HIGH:
                    result.high_priority.append(url)
                elif priority == ImagePriority.MEDIUM:
                    result.medium_priority.append(url)
                elif priority == ImagePriority.LOW:
                    result.low_priority.append(url)
            
            print(f"   📸 이미지 분류: HIGH={len(result.high_priority)}, "
                  f"MEDIUM={len(result.medium_priority)}, LOW={len(result.low_priority)}")
                  
        except Exception as e:
            print(f"   ⚠️ 이미지 필터링 오류: {e}")
        
        return result
    
    def _determine_priority(
        self, 
        url: str, 
        width: int, 
        height: int, 
        alt: str,
        in_main: bool
    ) -> Optional[ImagePriority]:
        """이미지 우선순위 결정"""
        url_lower = url.lower()
        
        # 크기 기준 먼저 체크
        if width < 200 or height < 200:
            return None  # 너무 작음
        
        # 고우선순위 조건
        is_large = width >= 400 and height >= 300
        has_poster_keyword = any(k in url_lower or k in alt for k in self.POSTER_KEYWORDS)
        
        if is_large and (has_poster_keyword or in_main):
            return ImagePriority.HIGH
        
        if is_large or has_poster_keyword:
            return ImagePriority.HIGH
        
        # 중간 우선순위
        if in_main or any(k in alt for k in ["코스", "course", "map"]):
            return ImagePriority.MEDIUM
        
        # 저우선순위
        return ImagePriority.LOW
    
    async def perform_ocr(
        self,
        context: BrowserContext,
        image_urls: List[str],
        max_images: int = 5
    ) -> List[OCRResult]:
        """
        이미지 OCR 수행
        
        Args:
            context: Playwright BrowserContext
            image_urls: OCR할 이미지 URL 목록
            max_images: 최대 처리 이미지 수
            
        Returns:
            List[OCRResult]: OCR 결과 목록
        """
        if not self.vision_client:
            print("   ⚠️ Vision Client가 초기화되지 않음")
            return []
        
        results = []
        unique_urls = list(dict.fromkeys(image_urls))[:max_images]
        
        for img_url in unique_urls:
            # 지원 확장자 체크
            if not any(img_url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                continue
            
            try:
                # 이미지 다운로드
                response = await context.request.get(img_url, timeout=10000)
                if response.status != 200:
                    continue
                
                image_content = await response.body()
                
                # Vision API 호출
                def call_vision(content):
                    image = vision.Image(content=content)
                    return self.vision_client.text_detection(image=image)
                
                api_response = await asyncio.to_thread(call_vision, image_content)
                
                if api_response.error.message:
                    print(f"   ⚠️ OCR 오류 ({img_url}): {api_response.error.message}")
                    continue
                
                texts = api_response.text_annotations
                if texts:
                    raw_text = texts[0].description
                    cleaned_text = self._cleanup_ocr_text(raw_text)
                    
                    results.append(OCRResult(
                        image_url=img_url,
                        raw_text=raw_text,
                        cleaned_text=cleaned_text,
                        confidence=0.9 if len(raw_text) > 50 else 0.5
                    ))
                    print(f"   ✨ OCR 성공 ({len(raw_text)}자): {img_url[:50]}...")
                
            except Exception as e:
                print(f"   ⚠️ 이미지 처리 실패 ({img_url}): {e}")
        
        return results
    
    def _cleanup_ocr_text(self, text: str) -> str:
        """OCR 텍스트 정제"""
        # 불필요한 문자 제거
        text = re.sub(r'[^\w\s가-힣a-zA-Z0-9\n.,:()\-/·•@]', '', text)
        
        # 연속 공백 제거
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 연속 개행 정리
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 중요 키워드 태깅
        keywords = ['접수', '신청', '대회', '마라톤', '선착순', '추첨', '참가비']
        for kw in keywords:
            if kw in text:
                # 해당 줄 전체를 [IMPORTANT] 태그로 표시 (프롬프트 참조용 설명)
                pass  # 실제로는 프롬프트에서 처리
        
        return text.strip()


# ==============================================================================
# 향상된 크롤러 에이전트
# ==============================================================================

class EnhancedCrawlerAgent:
    """OCR 통합 향상된 크롤러 에이전트"""
    
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ]
    
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API 키
            model_name: 사용할 LLM 모델명
        """
        self.llm = LLMClient(api_key, model_name)
        self.link_selector = LinkSelector(self.llm)
        self.cleaner = ContentCleaner()
        self.ocr_processor = OCRImageProcessor()
        self.browser: Optional[Browser] = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()
    
    async def crawl_and_extract(self, url: str, url_id: str = "unknown") -> Optional[Tuple[Race, str]]:
        """
        전체 크롤링 및 추출 파이프라인
        
        Args:
            url: 크롤링할 URL
            url_id: URL 식별자 (결과 저장용)
            
        Returns:
            (Race 객체, merged_context) 또는 None
        """
        print(f"\n{'='*60}")
        print(f"🌐 Enhanced Crawling: {url}")
        print(f"{'='*60}")
        
        try:
            context = await self.browser.new_context(
                user_agent=random.choice(self.USER_AGENTS),
                viewport={"width": 1280, "height": 720},
                locale="ko-KR",
            )
            page = await context.new_page()
            
            # Step 1: 메인 페이지 로드
            print("📍 Step 1: 메인 페이지 로드")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            main_html = await page.content()
            main_text, _ = self.cleaner.extract_main_content(main_html)
            
            # Step 2: 이미지 필터링
            print("📸 Step 2: 이미지 필터링")
            filtered_images = await self.ocr_processor.filter_images(page, url)
            
            # Step 3: 서브 페이지 탐색
            print("🔗 Step 3: 서브 페이지 탐색")
            sub_links = await self.link_selector.select_valuable_links(page, url, max_count=4)
            sub_texts, sub_images = await self._crawl_subpages(context, sub_links)
            
            # 서브 페이지 이미지 병합
            all_high_priority = filtered_images.high_priority + [
                img for img in sub_images if img not in filtered_images.all_images
            ]
            
            # Step 4: OCR 수행
            print("👁️ Step 4: OCR 수행")
            # 고우선순위 먼저, 그 다음 중간 우선순위
            ocr_targets = all_high_priority[:3] + filtered_images.medium_priority[:2]
            ocr_results = await self.ocr_processor.perform_ocr(context, ocr_targets, max_images=5)
            
            # OCRDataCollection 생성
            ocr_collection = OCRDataCollection(
                results=ocr_results,
                total_images_found=filtered_images.total_count,
                processed_images=len(ocr_results)
            )
            
            # Step 5: 컨텍스트 병합
            print("📦 Step 5: 컨텍스트 병합")
            merged_context = self._merge_contexts(main_text, sub_texts, ocr_collection)
            print(f"   ✅ 총 {len(merged_context)} 문자")
            
            # Step 6: LLM 추출
            print("🤖 Step 6: LLM 데이터 추출")
            race_data = await self._extract_with_llm(merged_context, url)
            
            # Step 7: Race 객체 생성
            print("✅ Step 7: 데이터 검증")
            race = self._build_race_object(race_data, url, ocr_collection)
            
            # Step 8: 결과 저장
            if url_id != "unknown":
                await self._save_results(race, merged_context, url_id)
            
            print(f"   ✅ 대회명: {race.title}")
            print(f"   ✅ 종목 수: {len(race.categories)}개")
            print(f"   ✅ 신뢰도: {race.calculate_confidence():.1%}")
            
            await context.close()
            return (race, merged_context)
            
        except Exception as e:
            print(f"❌ 크롤링 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _crawl_subpages(
        self,
        context: BrowserContext,
        urls: List[str]
    ) -> Tuple[List[str], List[str]]:
        """서브 페이지 크롤링"""
        async def fetch(url: str) -> Tuple[str, List[str]]:
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # 이미지 추출
                images = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('img'))
                        .filter(img => img.clientWidth >= 200 && img.clientHeight >= 200)
                        .map(img => img.src);
                }''')
                
                html = await page.content()
                text, _ = self.cleaner.extract_main_content(html)
                
                await page.close()
                return text, images
            except Exception as e:
                print(f"      ⚠️ 서브 페이지 오류: {e}")
                return "", []
        
        results = await asyncio.gather(*[fetch(url) for url in urls])
        
        texts = [r[0] for r in results if r[0]]
        images = []
        for r in results:
            images.extend(r[1])
        
        return texts, images
    
    def _merge_contexts(
        self,
        main_text: str,
        sub_texts: List[str],
        ocr_collection: OCRDataCollection
    ) -> str:
        """컨텍스트 병합 (OCR 우선)"""
        parts = []
        
        # 1. HTML 텍스트
        parts.append("[메인 페이지 HTML 텍스트]\n" + self.cleaner.truncate_text(main_text, 4000))
        for i, text in enumerate(sub_texts, 1):
            parts.append(f"\n[서브 페이지 {i} HTML 텍스트]\n" + self.cleaner.truncate_text(text, 2000))
        
        # 2. OCR 데이터 (중요도 강조)
        if ocr_collection.results:
            parts.append("\n[IMAGE_OCR_DATA]\n")
            parts.append("⚠️ 아래는 이미지(포스터)에서 추출한 텍스트입니다. "
                        "날짜/시간/접수방법은 이 데이터를 우선하세요.\n")
            
            for r in ocr_collection.results:
                text = r.cleaned_text or r.raw_text
                parts.append(f"--- 이미지: {r.image_url} (신뢰도: {r.confidence:.0%}) ---\n{text}\n")
        
        return "\n".join(parts)
    
    async def _extract_with_llm(self, context: str, source_url: str) -> dict:
        """LLM으로 정보 추출"""
        system_prompt = """당신은 마라톤 대회 정보 추출 전문가입니다.
HTML 텍스트와 이미지 OCR 결과(IMAGE_OCR_DATA)를 분석하여 구조화된 JSON을 생성하세요.

**핵심 원칙:**
1. **정보 충돌 시**: 이미지(OCR) 데이터 우선
2. **접수 방법**: '선착순', '추첨', 'Lottery' 등 키워드 → registration.method
3. **접수 시간**: 날짜+시간 형식 → registration.start_datetime (ISO 8601)
4. **대회명**: 포스터의 가장 큰 텍스트 고려

**데이터 포맷:**
- 날짜시간: YYYY-MM-DDTHH:mm:ss
- 금액: 숫자만
- 없는 정보: null
- JSON만 출력"""

        user_prompt = f"""아래 정보에서 대회 데이터를 추출하세요.

===== 예시 =====
[입력]
{FEW_SHOT_EXAMPLE_INPUT}

[출력]
{FEW_SHOT_EXAMPLE_OUTPUT}

===== 분석 대상 =====
{context[:12000]}

===== 출력 (JSON만) ====="""

        try:
            def call_llm():
                return self.llm.client.chat.completions.create(
                    model=self.llm.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_completion_tokens=2500,
                )
            
            response = await asyncio.to_thread(call_llm)
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            if content.startswith("{"):
                data = json.loads(content)
            elif "```" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                data = json.loads(content[json_start:json_end]) if json_start >= 0 else {}
            else:
                data = {}
            
            data["source_url"] = source_url
            return data
            
        except Exception as e:
            print(f"   ⚠️ LLM 추출 오류: {e}")
            return {"title": "Unknown", "source_url": source_url}
    
    def _build_race_object(
        self,
        data: dict,
        source_url: str,
        ocr_collection: OCRDataCollection
    ) -> Race:
        """Race 객체 생성"""
        # 접수 정보 생성
        reg_data = data.get("registration", {})
        registration = None
        if reg_data:
            registration = RegistrationInfo(
                start_datetime=reg_data.get("start_datetime"),
                end_datetime=reg_data.get("end_datetime"),
                method=reg_data.get("method", []),
                method_detail=reg_data.get("method_detail"),
                time_specified=reg_data.get("time_specified", False),
                platform=reg_data.get("platform")
            )
        
        # 종목 생성
        categories = []
        for cat_data in data.get("categories", []):
            if isinstance(cat_data, dict) and cat_data.get("name"):
                try:
                    categories.append(RaceCategory(
                        name=cat_data.get("name", ""),
                        fee=cat_data.get("fee"),
                        start_time=cat_data.get("start_time"),
                        qualification=cat_data.get("qualification"),
                    ))
                except Exception:
                    pass
        
        # 데이터 출처 메타데이터
        data_source = DataSource(
            from_html=True,
            from_ocr=len(ocr_collection.results) > 0,
            ocr_confidence=sum(r.confidence for r in ocr_collection.results) / max(len(ocr_collection.results), 1)
        )
        
        # Race 생성
        race = Race(
            title=data.get("title") or data.get("race_name") or "Unknown",
            source_url=source_url,
            website=data.get("website") or source_url,
            event_date=data.get("event_date"),
            region=data.get("region") or data.get("location", {}).get("region"),
            venue=data.get("venue") or data.get("location", {}).get("venue"),
            organizer=data.get("organizer"),
            phone=data.get("phone") or data.get("contact", {}).get("phone"),
            email=data.get("email") or data.get("contact", {}).get("email"),
            general_guide=data.get("general_guide"),
            registration=registration,
            categories=categories,
            ocr_data=ocr_collection,
            data_source=data_source,
            extraction_metadata=ExtractionMetadata(
                confidence=0.0,  # 나중에 계산
                llm_model=self.llm.model
            )
        )
        
        # 신뢰도 계산
        if race.extraction_metadata:
            race.extraction_metadata.confidence = race.calculate_confidence()
        
        # race_id 업데이트
        for cat in race.categories:
            cat.race_id = race.id
        
        return race
    
    async def _save_results(self, race: Race, context: str, url_id: str):
        """결과 저장"""
        base_dir = Path("results") / url_id
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # data.json (레거시 호환)
        data_path = base_dir / "data.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(race.to_legacy_format(), f, ensure_ascii=False, indent=2, default=str)
        print(f"   📁 저장: {data_path}")
        
        # raw_data.json
        raw_path = base_dir / "raw_data.json"
        raw_data = {
            "url_id": url_id,
            "source_url": race.source_url,
            "content": context,
            "content_length": len(context)
        }
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        print(f"   📄 저장: {raw_path}")
        
        # OCR 결과 개별 저장
        if race.ocr_data and race.ocr_data.results:
            ocr_dir = base_dir / "ocr"
            ocr_dir.mkdir(exist_ok=True)
            
            for i, ocr_result in enumerate(race.ocr_data.results):
                ocr_file = ocr_dir / f"image_{i+1}.json"
                with open(ocr_file, "w", encoding="utf-8") as f:
                    json.dump(ocr_result.model_dump(), f, ensure_ascii=False, indent=2)
            print(f"   🖼️ OCR 저장: {ocr_dir}")
