"""
domain_crawler.py

재귀적 도메인 크롤러 + LLM 데이터 추출 (Refactored)
- marathon.jtbc.com 도메인 내 모든 페이지 크롤링
- OpenAI LLM으로 Race 및 RaceCategory 스키마에 맞춰 정밀 추출
- results2.json 저장
"""

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from typing import Set, List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from openai import OpenAI

# Pydantic 모델 임포트 (기존 schemas.py 사용)
from agent_crawler.schemas import Race, RaceCategory


# ==========================================
# 로깅 설정
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==========================================
# 설정
# ==========================================
TARGET_DOMAIN = "seoulhalfrun.kr"
MAX_PAGES = 50      # 최대 크롤링 페이지 수
MAX_DEPTH = 3       # 최대 크롤링 깊이
START_URL = f"https://{TARGET_DOMAIN}/"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
]

# 제외할 URL 패턴
EXCLUDE_PATTERNS = [
    r'\.pdf$', r'\.jpg$', r'\.png$', r'\.gif$', r'\.zip$',
    r'login', r'logout', r'admin', r'member',
    r'#', r'javascript:', r'mailto:', r'tel:',
]


# ==========================================
# 콘텐츠 정제
# ==========================================
def clean_html(html: str) -> str:
    """HTML 정제 및 텍스트 추출"""
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 노이즈 태그 제거
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'svg']):
        tag.decompose()
    
    # 텍스트 추출
    text = soup.get_text(separator='\n', strip=True)
    
    # 연속 공백/개행 압축
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    
    return text[:15000]  # 토큰 제한 (조금 더 늘림)


def extract_links(html: str, base_url: str, target_domain: str) -> List[str]:
    """페이지에서 같은 도메인의 링크 추출"""
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        
        # 제외 패턴 체크
        if any(re.search(p, href, re.I) for p in EXCLUDE_PATTERNS):
            continue
        
        # 절대 경로 변환
        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)
        
        # 같은 도메인만 허용 (서브도메인 포함)
        if parsed.netloc == target_domain or parsed.netloc.endswith(f".{target_domain}"):
            # 프래그먼트 제거 및 쿼리 유지
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            links.append(clean_url)
    
    return list(set(links))


# ==========================================
# LLM 추출 (업데이트됨)
# ==========================================
class LLMExtractor:
    """OpenAI LLM 기반 데이터 추출"""
    
    # 업데이트된 시스템 프롬프트: 중첩 구조 명시
    SYSTEM_PROMPT = """You are an expert Data Engineer specializing in marathon event data extraction.

Your task is to extract structured event data from the provided text into a strict JSON format.

### Output Structure (JSON)
The output must be a single JSON object with the following fields:

1. **Root Fields (Common Info)**
   - `title`: Event name (String)
   - `event_date`: Main event date (YYYY-MM-DD)
   - `organizer`: Organizer name (String)
   - `phone`: Contact phone number (String)
   - `email`: Contact email (String)
   - `website`: Official website URL (String)
   - `venue`: Event location/venue (String)
   - `region`: City or region (e.g., Seoul, Busan) (String)
   - `general_guide`: Summary of general rules, refund policies, etc. (String)
   - `categories`: ARRAY of Category objects (see below)

2. **Categories (Nested Objects)**
   For each sub-event (e.g., Full Course, 10km, 5km), create an object with:
   - `name`: Category name (e.g., "Full Course", "10K") (String)
   - `fee`: Registration fee (Integer, no currency symbols)
   - `qualification`: Eligibility rules (String)
   - `start_time`: Departure time in HH:mm format (String)
   - `registration_start_time`: Registration open time in HH:mm format (String)
   - `application_method`: Method of application (e.g., "First-come First-served", "Lottery") (String)
   - `notes`: Specific instructions (String)
   - `next_registration_at`: Registration start date (ISO 8601 datetime or YYYY-MM-DD)
   - `next_registration_end_at`: Registration end date (ISO 8601 datetime or YYYY-MM-DD)
   - `next_payment_at`: Payment start date
   - `next_payment_end_at`: Payment end date

### Rules
- If a specific field is missing, use `null`.
- If registration dates apply to the whole event, copy them to ALL categories.
- Fees MUST be integers (e.g., 50000, not "50,000 KRW").
- Dates MUST be YYYY-MM-DD.
"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # 모델 변경 가능
    
    def extract(self, content: str, url: str) -> Optional[Dict[str, Any]]:
        """LLM으로 Race 데이터 추출"""
        if len(content.strip()) < 100:  # 내용이 너무 짧으면 패스
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract data from this text:\n\n{content[:14000]}"}
                ],
                temperature=0.1,  # 정밀도 높임
                response_format={"type": "json_object"},  # JSON 모드 강제
                max_tokens=2000,
            )
            
            result = response.choices[0].message.content.strip()
            data = json.loads(result)
            
            # 메타데이터 추가
            data["source_url"] = url
            if not data.get("website"):
                data["website"] = url
                
            return data
            
        except Exception as e:
            logger.warning(f"LLM 추출 오류 ({url}): {e}")
            return None


# ==========================================
# 도메인 크롤러
# ==========================================
class DomainCrawler:
    """재귀적 도메인 크롤러"""
    
    def __init__(self, api_key: str):
        self.visited: Set[str] = set()
        self.to_visit: List[str] = []
        self.extracted_data: List[Dict] = []
        self.llm = LLMExtractor(api_key)
        self.page_count = 0
    
    async def crawl(self, start_url: str) -> List[Dict]:
        """크롤링 시작"""
        logger.info(f"🚀 크롤링 시작: {start_url}")
        
        self.to_visit.append(start_url)
        
        async with async_playwright() as p:
            # 브라우저 런칭
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="ko-KR",
            )
            
            # 페이지 생성
            page = await context.new_page()
            
            # Anti-bot
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            while self.to_visit and self.page_count < MAX_PAGES:
                url = self.to_visit.pop(0)
                
                if url in self.visited:
                    continue
                
                self.visited.add(url)
                self.page_count += 1
                
                logger.info(f"[{self.page_count}/{MAX_PAGES}] 방문: {url}")
                
                try:
                    # 페이지 로드
                    html = await self._fetch_page(page, url)
                    if not html:
                        continue
                    
                    # 링크 발견 & 큐 추가
                    new_links = extract_links(html, url, TARGET_DOMAIN)
                    for link in new_links:
                        if link not in self.visited and link not in self.to_visit:
                            self.to_visit.append(link)
                    
                    # 콘텐츠 정제 & LLM 추출
                    content = clean_html(html)
                    
                    # 의미 있는 콘텐츠가 있을 때만 LLM 호출
                    if len(content) > 200:
                        data = self.llm.extract(content, url)
                        if data and data.get("title"):
                            # 유효한 데이터만 저장
                            self.extracted_data.append(data)
                            cat_count = len(data.get("categories", []))
                            logger.info(f"   ✅ 추출 성공: {data['title']} (종목: {cat_count}개)")
                    
                except Exception as e:
                    logger.error(f"   ❌ 처리 오류: {e}")
                
                # 서버 부하 방지 딜레이
                await asyncio.sleep(random.uniform(1.0, 3.0))
            
            await browser.close()
        
        logger.info(f"\n🏁 크롤링 완료. 총 {len(self.extracted_data)}개 데이터 추출됨.")
        return self.extracted_data
    
    async def _fetch_page(self, page, url: str) -> Optional[str]:
        """페이지 가져오기 (재시도 로직 없음, 단순 대기)"""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 동적 렌더링 대기
            await asyncio.sleep(1.0)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            return await page.content()
        except Exception as e:
            logger.warning(f"   페이지 로드 실패: {e}")
            return None


# ==========================================
# 데이터 변환 및 저장
# ==========================================
def convert_to_race_model(data: Dict) -> Optional[Race]:
    """
    딕셔너리를 Pydantic Race 모델로 변환 (Validator 자동 적용)
    """
    try:
        # RaceCategory 객체 리스트 생성
        categories = []
        for cat_data in data.get("categories", []):
            if not isinstance(cat_data, dict):
                continue
                
            # 필수 필드 체크 (name)
            if not cat_data.get("name"):
                continue
                
            try:
                # Pydantic 모델 생성 (자동 검증)
                category = RaceCategory(
                    id="", # default factory가 처리하지만 명시적 빈값도 가능
                    race_id="", # 나중에 설정
                    name=str(cat_data.get("name")),
                    fee=cat_data.get("fee"), # validator가 int 변환
                    qualification=cat_data.get("qualification"),
                    start_time=cat_data.get("start_time"),
                    registration_start_time=cat_data.get("registration_start_time"),
                    application_method=cat_data.get("application_method"),
                    notes=cat_data.get("notes"),
                    next_registration_at=cat_data.get("next_registration_at"),
                    next_registration_end_at=cat_data.get("next_registration_end_at"),
                    next_payment_at=cat_data.get("next_payment_at"),
                    next_payment_end_at=cat_data.get("next_payment_end_at"),
                )
                categories.append(category)
            except Exception as e:
                logger.warning(f"   ⚠️ 카테고리 변환 오류: {e}")
                continue

        # Race 객체 생성
        race = Race(
            id="", # default factory
            title=str(data.get("title") or "Unknown Event"),
            source_url=str(data.get("source_url") or ""),
            event_date=data.get("event_date"), # validator
            country="Korea",
            region=data.get("region"),
            venue=data.get("venue"),
            organizer=data.get("organizer"),
            phone=data.get("phone"), # validator
            email=data.get("email"), # validator
            website=data.get("website"),
            general_guide=data.get("general_guide"),
            categories=categories
        )
        
        # 부모 ID 연결
        for cat in race.categories:
            cat.race_id = race.id
            
        return race
        
    except Exception as e:
        logger.error(f"Race 모델 변환 실패: {e}")
        return None


async def main():
    print("\n" + "=" * 60)
    print("🕷️  Refactored Domain Crawler")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n🔑 OpenAI API 키를 입력하세요:")
        api_key = input("> ").strip()
        if not api_key:
            print("API Key required.")
            return

    crawler = DomainCrawler(api_key)
    
    # 1. 크롤링 및 LLM 추출
    raw_data_list = await crawler.crawl(START_URL)
    
    # 2. Pydantic 모델 변환
    valid_races = []
    seen_titles = set()
    
    for raw_data in raw_data_list:
        race_model = convert_to_race_model(raw_data)
        if race_model:
            # 제목 중복 제거 (간단한 로직)
            if race_model.title in seen_titles:
                continue
            
            seen_titles.add(race_model.title)
            valid_races.append(race_model)
    
    # 3. JSON 저장 (Serialization)
    output_data = []
    for r in valid_races:
        # model_dump(mode='json')은 datetime 등을 str로 자동변환
        output_data.append(r.model_dump(mode='json'))
    
    with open("results4.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 저장 완료: results4.json ({len(valid_races)}개 유효 대회)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
