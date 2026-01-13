"""
agent_browseruse/browseruse_agent.py

Browser-Use 기반 크롤러 에이전트
- AI 에이전트가 자율적으로 웹을 탐색
- LLM이 직접 브라우저를 제어하며 데이터 추출
"""

import os
import json
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
from browser_use import Agent, Browser

from .schemas import Race, RaceCategory

# .env 파일에서 환경변수 로드 (프로젝트 루트 기준)
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")



def create_llm():
    """
    browser-use와 호환되는 LLM 생성
    - 표준 LangChain ChatOpenAI 사용
    - browser-use가 필요로 하는 provider, model 속성 추가
    """
    # 1. browser-use의 자체 ChatBrowserUse 사용 시도
    try:
        from browser_use import ChatBrowserUse
        return ChatBrowserUse()
    except Exception:
        pass
    
    # 2. 표준 LangChain ChatOpenAI 사용 (monkey-patch로 호환성 추가)
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    
    # browser-use가 필요로 하는 속성들을 동적으로 추가
    # (클래스 상속 대신 인스턴스에 직접 추가하여 structured_output 호환성 유지)
    llm.provider = "openai"  # type: ignore
    llm.model = llm.model_name  # type: ignore
    
    return llm




def get_extraction_task(url: str) -> str:
    """마라톤 데이터 추출 태스크 프롬프트 생성"""
    return f"""
You are a marathon event data extraction agent.

**Starting URL:** {url}

**Your Goal:**
Navigate through this marathon website to find comprehensive event information and extract it into a structured JSON format.

**What to Look For:**
1. **Event Basic Info**: Event name, date (YYYY-MM-DD format), venue, region, organizer, contact phone, email
2. **Race Categories**: For each category (Full/Half/10km/5km etc.), find:
   - Category name (종목명)
   - Registration fee as integer (참가비, e.g., 50000)
   - Start time in HH:mm format (출발시간)
   - Qualification requirements (참가자격)
   - Registration method (접수방식: 선착순/추첨제)

**Navigation Strategy:**
- First visit the main URL
- Look for and click on menu items like: "대회안내", "대회요강", "참가안내", "코스안내", "Info", "등록"
- Find fee/price tables and schedule information
- Do NOT click on: login, gallery, photo, result, record, ranking, mypage

**Output Format:**
Return ONLY valid JSON (no markdown, no explanation):
{{
  "title": "대회명",
  "event_date": "YYYY-MM-DD",
  "region": "지역",
  "venue": "장소",
  "organizer": "주최사",
  "phone": "연락처",
  "email": "이메일",
  "website": "{url}",
  "general_guide": "대회 개요 설명",
  "categories": [
    {{
      "name": "종목명",
      "fee": 50000,
      "start_time": "08:00",
      "qualification": "참가자격",
      "application_method": "선착순"
    }}
  ]
}}

After gathering all information, output the JSON and stop.
"""


class BrowserUseAgent:
    """
    Browser-Use 기반 마라톤 크롤러 에이전트
    
    AI 에이전트가 자율적으로 웹사이트를 탐색하고
    마라톤 대회 정보를 구조화된 형태로 추출
    """
    
    def __init__(self, api_key: Optional[str] = None, headless: bool = True):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
            headless: 브라우저 헤드리스 모드 여부
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            os.environ["OPENAI_API_KEY"] = self.api_key
        
        self.headless = headless
        self._llm = None
    
    def _get_llm(self):
        """LLM 인스턴스 반환 (지연 로딩)"""
        if self._llm is None:
            self._llm = create_llm()
        return self._llm
    
    async def process_site(self, url: str) -> Optional[Race]:
        """
        단일 사이트 크롤링 메인 워크플로우
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            Race 객체 또는 None
        """
        print(f"\n{'='*60}")
        print(f"🌐 Browser-Use 크롤링: {url}")
        print(f"{'='*60}")
        
        browser = None
        try:
            # 1. Browser 초기화 (browser-use 0.11.x는 직접 파라미터 전달)
            print("📍 Step 1: 브라우저 초기화")
            browser = Browser(
                headless=self.headless,
                disable_security=True,  # 일부 사이트 호환성
            )
            
            # 2. Agent 초기화
            print("🤖 Step 2: AI 에이전트 초기화")
            
            agent = Agent(
                task=get_extraction_task(url),
                llm=self._get_llm(),
                browser=browser,
            )
            
            # 3. 에이전트 실행
            print("🔄 Step 3: 에이전트 실행 중...")
            history = await agent.run(max_steps=15)
            print("✅ 에이전트 실행 완료")
            
            # 4. 결과 추출
            print("📦 Step 4: 결과 추출")
            result_str = self._extract_result(history)
            
            if not result_str:
                print("❌ 결과 추출 실패: 응답 없음")
                return None
            
            # 5. JSON 파싱
            print("🔍 Step 5: JSON 파싱")
            data = self._parse_json(result_str)
            
            if not data:
                print("❌ JSON 파싱 실패")
                return None
            
            # 6. Pydantic 모델로 변환
            print("✅ Step 6: 데이터 검증")
            data["source_url"] = url
            data["website"] = data.get("website") or url
            
            race = self._convert_to_race(data)
            print(f"   ✅ 대회명: {race.title}")
            print(f"   ✅ 종목 수: {len(race.categories)}개")
            
            return race
            
        except Exception as e:
            print(f"❌ 크롤링 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
    
    def _extract_result(self, history) -> Optional[str]:
        """에이전트 실행 결과에서 텍스트 추출"""
        if not history:
            return None
        
        # 다양한 결과 형식 처리
        if hasattr(history, 'final_result'):
            result = history.final_result()
            if result:
                return str(result)
        
        if hasattr(history, 'result'):
            return str(history.result)
        
        return str(history)
    
    def _parse_json(self, text: str) -> Optional[dict]:
        """텍스트에서 JSON 추출 및 파싱"""
        if not text or "{" not in text:
            return None
        
        try:
            # JSON 블록 찾기
            start = text.find("{")
            end = text.rfind("}") + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON 파싱 오류: {e}")
        
        return None
    
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
                        application_method=cat_data.get("application_method"),
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
        )
        
        # race_id 업데이트
        for cat in race.categories:
            cat.race_id = race.id
        
        return race
