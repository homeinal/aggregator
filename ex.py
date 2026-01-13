"""
ex.py - browser-use 라이브러리 테스트 (커스텀 클래스 버전)
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from pydantic import ConfigDict

# .env 로드
load_dotenv(Path(__file__).parent / ".env")

print(f"API Key loaded: {os.getenv('OPENAI_API_KEY')[:20]}...")


# 커스텀 클래스 정의 (기존 ChatOpenAI를 상속)
class BrowserUseChatOpenAI(ChatOpenAI):
    # 'extra' 필드를 허용하도록 설정 (정의되지 않은 속성도 추가 가능하게 함)
    model_config = ConfigDict(extra='allow')
    
    # 명시적으로 provider 필드 선언
    provider: str = "openai"


async def test_browser_use():
    from browser_use import Agent, Browser
    
    # 커스텀 클래스로 LLM 인스턴스 생성
    llm = BrowserUseChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
    )
    
    print(f"LLM created: {llm.model_name}, provider: {llm.provider}")
    
    # 간단한 태스크로 테스트
    browser = Browser(headless=False)
    
    agent = Agent(
        task="Go to https://example.com and tell me the page title.",
        llm=llm,
        browser=browser,
    )
    
    print("Running agent...")
    try:
        history = await agent.run(max_steps=5)
        print(f"Agent completed!")
        
        # 결과 추출
        if hasattr(history, 'final_result'):
            result = history.final_result()
            print(f"Final result: {result}")
        if hasattr(history, 'result'):
            print(f"Result: {history.result}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_browser_use())
