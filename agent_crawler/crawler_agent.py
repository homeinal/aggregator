"""
agent_crawler/crawler_agent.py

메인 크롤러 에이전트 (최적화 버전)
- Anti-bot: 랜덤 User-Agent, 랜덤 딜레이
- html2text 기반 Markdown 변환
- 휴리스틱 링크 필터링
"""

import asyncio
import random
import os
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urljoin

from google.cloud import vision
from playwright.async_api import async_playwright, Browser, Page

from .schemas import Race, RaceCategory
from .content_cleaner import ContentCleaner
from .link_selector import LinkSelector
from .llm_client import LLMClient


# 랜덤 User-Agent 풀
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class CrawlerAgent:
    """
    지능형 탐색 크롤러 에이전트 (최적화 버전)
    
    Optimizations:
    - Anti-bot: 랜덤 User-Agent, 랜덤 딜레이
    - Token: html2text Markdown 변환
    - Cost: 휴리스틱 링크 사전 필터링
    - OCR: Google Cloud Vision API Integration
    """
    
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API 키
            model_name: 사용할 LLM 모델명
        """
        self.llm = LLMClient(api_key, model_name)
        self.link_selector = LinkSelector(self.llm)
        self.cleaner = ContentCleaner()
        self.browser: Optional[Browser] = None
        
        # Google Cloud Vision 설정
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("my_key.json")
    
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
    
    def _get_random_user_agent(self) -> str:
        """랜덤 User-Agent 반환"""
        return random.choice(USER_AGENTS)
    
    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """랜덤 지연 (봇 탐지 우회)"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def process_site(self, url: str) -> Optional[tuple]:
        """
        단일 사이트 크롤링 메인 워크플로우
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            (Race 객체, merged_context) 튜플 또는 None
        """
        print(f"\n{'='*60}")
        print(f"🌐 사이트 크롤링: {url}")
        print(f"{'='*60}")
        
        try:
            # 랜덤 User-Agent로 브라우저 컨텍스트 생성
            context = await self.browser.new_context(
                user_agent=self._get_random_user_agent(),
                viewport={"width": 1280, "height": 720},
                locale="ko-KR",
            )
            page = await context.new_page()
            
            # 1. 메인 페이지 접속
            print("📍 Step 1: 메인 페이지 접속")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 랜덤 딜레이 (봇 탐지 우회)
            await self._random_delay(1.5, 2.5)
            
            # networkidle 대기
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass  # 타임아웃 무시
            
            main_html = await page.content()
            # 이미지 URL도 함께 추출
            main_text, main_image_urls = self.cleaner.extract_main_content(main_html)
            print(f"   ✅ 메인 페이지 로드 ({len(main_text)} 문자, {len(main_image_urls)}개 이미지 발견)")
            
            # 2. 유의미한 링크 선별 (휴리스틱 + LLM)
            print("🔗 Step 2: 링크 분석 및 선별")
            sub_links = await self.link_selector.select_valuable_links(page, url, max_count=4)
            print(f"   ✅ {len(sub_links)}개 서브 페이지 선별")
            for link in sub_links:
                print(f"      - {link[:60]}...")
            
            # 3. 서브 페이지 비동기 방문
            sub_texts = []
            sub_image_urls = []
            if sub_links:
                print("📄 Step 3: 서브 페이지 크롤링")
                # 텍스트와 이미지 URL 리스트를 함께 반환받음
                sub_texts, sub_image_urls = await self._crawl_subpages(context, sub_links)
                print(f"   ✅ {len(sub_texts)}개 서브 페이지 콘텐츠 수집")
            
            # 4. 이미지 OCR 처리
            print("👁️ Step 4: 이미지 OCR 및 분석")
            all_image_urls = main_image_urls + sub_image_urls
            ocr_results = await self._process_images_with_ocr(context, url, all_image_urls)
            print(f"   ✅ {len(ocr_results)}개 이미지 자막 추출 완료")

            # 5. 컨텍스트 병합
            print("📦 Step 5: 컨텍스트 병합")
            # OCR 텍스트도 컨텍스트에 포함하면 좋겠지만, 토큰 제한 고려하여 별도 필드로 저장
            # 필요하다면 merged_context에 추가할 수도 있음
            merged_context = self._merge_contexts(main_text, sub_texts)
            
            # OCR 결과를 컨텍스트 하단에 부록으로 추가해주면 LLM이 참조하기 좋음
            if ocr_results:
                merged_context += "\n\n[OCR 분석 결과]\n"
                for res in ocr_results:
                    merged_context += f"이미지({res['url']}): {res['text'][:200]}...\n"
            
            print(f"   ✅ 총 {len(merged_context)} 문자")
            
            # 6. LLM으로 데이터 추출 (Few-shot)
            print("🤖 Step 6: LLM 데이터 추출")
            race_data = self.llm.extract_race_data(merged_context, url)
            
            # OCR 결과를 데이터에 주입
            race_data['content_images'] = ocr_results
            
            # 7. Pydantic 모델로 변환 (Validator 자동 적용)
            print("✅ Step 7: 데이터 검증")
            race = self._convert_to_race(race_data)
            print(f"   ✅ 대회명: {race.title}")
            print(f"   ✅ 종목 수: {len(race.categories)}개")
            
            await context.close()
            return (race, merged_context)
            
        except Exception as e:
            print(f"❌ 크롤링 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _process_images_with_ocr(self, context, base_url: str, image_urls: List[str]) -> List[dict]:
        """이미지 다운로드 및 Google Vision OCR 수행"""
        results = []
        # 중복 제거 및 상위 5개만 처리 (API 비용 절약)
        unique_urls = list(set(image_urls))[:5]
        
        # Google Vision Client
        try:
            client = vision.ImageAnnotatorClient()
        except Exception as e:
            print(f"⚠️ Google Vision Client 초기화 실패: {e}")
            return []

        for img_url in unique_urls:
            full_url = urljoin(base_url, img_url)
            # 확장자 필터링
            if not any(full_url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                continue
            
            try:
                # Playwright Request Context를 사용하여 이미지 다운로드 (세션/쿠키 유지)
                # context.request 사용
                response = await context.request.get(full_url, timeout=10000)
                if response.status != 200:
                    continue
                    
                image_content = await response.body()
                
                # Vision API 호출 (동기 함수이므로 to_thread 사용 권장)
                def call_vision_api(content):
                    image = vision.Image(content=content)
                    return client.text_detection(image=image)
                
                api_response = await asyncio.to_thread(call_vision_api, image_content)
                
                if api_response.error.message:
                    print(f"   ⚠️ OCR API Error ({full_url}): {api_response.error.message}")
                    continue
                
                texts = api_response.text_annotations
                if texts:
                    extracted_text = texts[0].description
                    # 결과 저장
                    results.append({
                        "url": full_url,
                        "text": extracted_text
                    })
                    print(f"   ✨ OCR 성공 ({len(extracted_text)}자): {full_url}")
                
            except Exception as e:
                print(f"   ⚠️ 이미지 처리 실패 ({full_url}): {e}")
                
        return results

    async def _crawl_subpages(
        self, 
        context, 
        urls: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        여러 서브 페이지를 비동기로 크롤링
        Returns: (texts, image_urls)
        """
        async def fetch_page(url: str) -> Tuple[str, List[str]]:
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                html = await page.content()
                await page.close()
                return self.cleaner.extract_main_content(html)
            except Exception as e:
                print(f"      ⚠️  서브 페이지 오류: {e}")
                return "", []
        
        tasks = [fetch_page(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        texts = [res[0] for res in results if res[0]]
        images = []
        for res in results:
            images.extend(res[1])
            
        return texts, images
    
    def _merge_contexts(self, main_text: str, sub_texts: List[str]) -> str:
        """메인 + 서브 페이지 텍스트 병합"""
        parts = ["[메인 페이지]\n" + self.cleaner.truncate_text(main_text, 4000)]
        
        for i, text in enumerate(sub_texts, 1):
            parts.append(f"\n[서브 페이지 {i}]\n" + self.cleaner.truncate_text(text, 2000))
        
        return "\n".join(parts)
    
    def _convert_to_race(self, data: dict) -> Race:
        """딕셔너리를 Race 모델로 변환 (Validator 자동 적용)"""
        # categories 처리
        categories = []
        
        for cat_data in data.get("categories", []):
            if isinstance(cat_data, dict) and cat_data.get("name"):
                try:
                    cat = RaceCategory(
                        name=cat_data.get("name", ""),
                        fee=cat_data.get("fee"),
                        start_time=cat_data.get("start_time"),
                        qualification=cat_data.get("qualification"),
                        notes=cat_data.get("notes"),
                    )
                    categories.append(cat)
                except Exception:
                    pass
        
        # Race 생성 (Validator 자동 적용)
        race = Race(
            title=data.get("title", "Unknown"),
            source_url=data.get("source_url", ""),
            website=data.get("website"),
            event_date=data.get("event_date"),
            region=data.get("region"),
            venue=data.get("venue"),
            organizer=data.get("organizer"),
            organizer_rep=data.get("organizer_rep"),
            phone=data.get("phone"),
            email=data.get("email"),
            image_url=data.get("image_url"),
            general_guide=data.get("general_guide"),
            categories=categories,
            content_images=data.get("content_images", [])
        )
        
        # race_id 업데이트
        for cat in race.categories:
            cat.race_id = race.id
        
        return race
