"""
browser_use_crawler.py

browser-use 라이브러리를 활용한 지능형 마라톤 사이트 크롤러
- LLM(GPT-4o)이 브라우저를 자율적으로 탐색
- 3개 마라톤 사이트에서 Race/RaceCategory 데이터 추출
- 결과를 browser_use_results.json에 저장
"""

import asyncio
import json
import os
from typing import List, Optional

from pydantic import BaseModel, Field
from browser_use import Agent, Browser


# ==========================================
# LLM 래퍼 (browser-use 호환)
# ==========================================
def create_llm():
    """
    browser-use와 호환되는 LLM 생성
    - ChatBrowserUse (Cloud API) 또는
    - OpenAI 직접 사용
    """
    try:
        # browser-use의 자체 ChatBrowserUse 사용 시도
        from browser_use import ChatBrowserUse
        return ChatBrowserUse()
    except Exception:
        pass
    
    # OpenAI 직접 사용 (browser-use의 래퍼 클래스 사용)
    try:
        from browser_use.llms.openai import ChatOpenAI as BrowserUseOpenAI
        return BrowserUseOpenAI(model="gpt-4o", temperature=0.1)
    except Exception:
        pass
    
    # 최후의 수단: langchain 래퍼에 provider 속성 추가
    from langchain_openai import ChatOpenAI
    
    class CompatibleChatOpenAI(ChatOpenAI):
        provider: str = "openai"
    
    return CompatibleChatOpenAI(model="gpt-4o", temperature=0.1)


# ==========================================
# Pydantic 스키마 정의
# ==========================================
class RaceCategory(BaseModel):
    """종목 정보"""
    name: str = Field(..., description="종목명 (예: Full, 10km, 5km)")
    fee: Optional[int] = Field(None, description="참가비 (정수)")
    start_time: Optional[str] = Field(None, description="출발시간 (HH:mm)")
    registration_start_time: Optional[str] = Field(None, description="접수 시작 시간 (HH:mm)")
    application_method: Optional[str] = Field(None, description="접수 방식 (선착순/추첨제)")
    qualification: Optional[str] = Field(None, description="참가 자격")


class Race(BaseModel):
    """대회 정보"""
    title: str = Field(..., description="대회명")
    event_date: Optional[str] = Field(None, description="대회일 (YYYY-MM-DD)")
    venue: Optional[str] = Field(None, description="장소")
    organizer: Optional[str] = Field(None, description="주최사")
    phone: Optional[str] = Field(None, description="연락처")
    website: Optional[str] = Field(None, description="웹사이트 URL")
    categories: List[RaceCategory] = Field(default_factory=list, description="종목 리스트")


# ==========================================
# 타겟 웹사이트 목록
# ==========================================
TARGET_URLS = [
    "https://marathon.jtbc.com/",
    "http://ynmarathon.kr/",
    "https://seoulhalfrun.kr/",
]


# ==========================================
# 에이전트 태스크 정의
# ==========================================
def get_agent_task(url: str) -> str:
    return f"""
You are a marathon event data extraction agent.

**Starting URL:** {url}

**Your Goal:**
Navigate through this marathon website to find comprehensive event information and extract it into a structured JSON format.

**What to Look For:**
1. **Event Basic Info**: Event name, date, venue, organizer, contact phone
2. **Race Categories**: For each category (Full/Half/10km/5km etc.), find:
   - Category name
   - Registration fee (as integer, e.g., 50000)
   - Start time (HH:mm format)
   - Qualification requirements

**Navigation Strategy:**
- Visit the URL first
- Click on menu items like: "대회안내", "대회요강", "참가안내", "Info", "등록"
- Find fee/price tables
- Do NOT click on login, gallery, or result pages

**Output Format (JSON only):**
{{
  "title": "대회명",
  "event_date": "YYYY-MM-DD",
  "venue": "장소",
  "organizer": "주최사",
  "phone": "연락처",
  "website": "{url}",
  "categories": [
    {{"name": "Full", "fee": 50000, "start_time": "09:00", "qualification": "만 18세 이상"}}
  ]
}}

After gathering all information, output the JSON and stop.
"""


# ==========================================
# 메인 크롤링 함수
# ==========================================
async def crawl_marathon_site(url: str, llm) -> Optional[dict]:
    """
    browser-use Agent로 단일 사이트 크롤링
    """
    print(f"\n{'='*60}")
    print(f"🌐 크롤링: {url}")
    print(f"{'='*60}")
    
    browser = None
    try:
        # Browser 초기화
        browser = Browser(headless=False)
        
        # Agent 초기화
        agent = Agent(
            task=get_agent_task(url),
            llm=llm,
            browser=browser,
        )
        
        # 에이전트 실행
        history = await agent.run(max_steps=15)
        
        print(f"✅ 에이전트 실행 완료")
        
        # 결과에서 최종 메시지 추출
        result_str = None
        if history:
            if hasattr(history, 'final_result'):
                result_str = history.final_result()
            elif hasattr(history, 'result'):
                result_str = str(history.result)
            else:
                result_str = str(history)
        
        # 결과 파싱
        if result_str and "{" in result_str:
            try:
                start = result_str.find("{")
                end = result_str.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(result_str[start:end])
                    data["source_url"] = url
                    return data
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON 파싱 실패: {e}")
                
        return None
        
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass


async def main():
    """메인 함수: 3개 사이트 순차 크롤링"""
    print("\n" + "=" * 60)
    print("🕷️ Browser-Use Marathon Crawler")
    print("=" * 60)
    
    # API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n🔑 OpenAI API 키를 입력하세요:")
        api_key = input("> ").strip()
        os.environ["OPENAI_API_KEY"] = api_key
    
    # LLM 생성
    llm = create_llm()
    print(f"📦 LLM 초기화: {type(llm).__name__}")
    
    # 결과 수집
    all_results = []
    
    for url in TARGET_URLS:
        result = await crawl_marathon_site(url, llm)
        if result:
            try:
                race = Race(**result)
                all_results.append(race.model_dump(mode="json"))
                print(f"   ✅ 추출 성공: {race.title} ({len(race.categories)}개 종목)")
            except Exception as e:
                print(f"   ⚠️ 데이터 검증 실패: {e}")
                all_results.append(result)
        
        await asyncio.sleep(3)
    
    # 결과 저장
    output_file = "browser_use_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ 저장 완료: {output_file} ({len(all_results)}개 대회)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
