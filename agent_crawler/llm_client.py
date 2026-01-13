"""
agent_crawler/llm_client.py

LLM 클라이언트 (OpenAI/LangChain) - 최적화 버전
- Few-shot 프롬프팅 적용
- 강화된 출력 형식 지시
"""

import os
import json
from typing import List, Dict, Any, Optional


# Few-shot 예시 (입력/출력)
FEW_SHOT_EXAMPLE_INPUT = """
## 2026 서울 한강마라톤

### 대회개요
- 대회일시: 2026년 4월 19일 (일요일)
- 장소: 서울 여의도 한강공원
- 주최: 서울마라톤협회
- 문의: 02-1234-5678

### 종목 및 참가비
| 종목 | 참가비 | 출발시간 |
|-----|-------|---------|
| 풀코스 | 50,000원 | 08:00 |
| 하프 | 40,000원 | 08:30 |
| 10km | 30,000원 | 09:00 |
"""

FEW_SHOT_EXAMPLE_OUTPUT = """{
  "title": "2026 서울 한강마라톤",
  "event_date": "2026-04-19",
  "region": "서울",
  "venue": "여의도 한강공원",
  "organizer": "서울마라톤협회",
  "phone": "02-1234-5678",
  "email": null,
  "general_guide": "2026년 4월 19일 서울 여의도 한강공원에서 개최되는 마라톤 대회",
  "categories": [
    {"name": "풀코스", "fee": 50000, "start_time": "08:00", "qualification": null},
    {"name": "하프", "fee": 40000, "start_time": "08:30", "qualification": null},
    {"name": "10km", "fee": 30000, "start_time": "09:00", "qualification": null}
  ]
}"""


class LLMClient:
    """OpenAI LLM 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
            model_name: 사용할 LLM 모델명
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
        self.model = model_name
    
    def select_links(self, links: List[Dict[str, str]], max_count: int = 5) -> List[str]:
        """
        LLM으로 유의미한 링크 선별
        
        Args:
            links: [{"text": "링크텍스트", "href": "URL"}, ...]
            max_count: 최대 선택 개수
            
        Returns:
            선별된 URL 리스트
        """
        if not links:
            return []
        
        # 링크 목록을 텍스트로 변환
        links_text = "\n".join([
            f"{i+1}. [{link['text']}] -> {link['href']}"
            for i, link in enumerate(links[:30])  # 최대 30개만 분석
        ])
        
        prompt = f"""마라톤 대회 사이트에서 추출한 링크입니다.
대회 정보 수집에 유용한 링크를 최대 {max_count}개 선택하세요.

**선택 기준:**
- 대회요강, 코스안내, 참가신청, 일정/종목/참가비 정보

**제외:**
- 로그인, 게시판, 사진첩, 결과조회

**링크 목록:**
{links_text}

**응답 (JSON 배열만):**
["URL1", "URL2"]"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_completion_tokens=300,
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            if content.startswith("["):
                return json.loads(content)
            if "```" in content:
                json_start = content.find("[")
                json_end = content.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    return json.loads(content[json_start:json_end])
            return []
            
        except Exception as e:
            print(f"   ⚠️  링크 선별 LLM 오류: {e}")
            return []
    
    def extract_race_data(self, context: str, source_url: str) -> Dict[str, Any]:
        """
        컨텍스트에서 Race 데이터 추출 (Few-shot 프롬프팅)
        
        Args:
            context: 병합된 페이지 텍스트
            source_url: 원본 URL
            
        Returns:
            Race 스키마에 맞는 dict
        """
        system_prompt = """당신은 마라톤 대회 정보 추출 전문가입니다.

**필수 규칙:**
1. 날짜는 반드시 YYYY-MM-DD 형식 (예: 2026-04-19)
2. 금액은 통화 기호/쉼표 없이 Integer (예: 50000)
3. 시간은 HH:mm 형식 (예: 08:30)
4. 없는 정보는 null로 표시
5. JSON만 출력 (설명 없이)"""

        user_prompt = f"""아래 예시를 참고하여 웹사이트 텍스트에서 대회 정보를 추출하세요.

===== 예시 입력 =====
{FEW_SHOT_EXAMPLE_INPUT}

===== 예시 출력 =====
{FEW_SHOT_EXAMPLE_OUTPUT}

===== 실제 웹사이트 텍스트 =====
{context[:10000]}

===== 출력 (JSON만) ====="""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_completion_tokens=2000,
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            if content.startswith("{"):
                data = json.loads(content)
            elif "```" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(content[json_start:json_end])
                else:
                    data = {}
            else:
                data = {}
            
            # source_url 추가
            data["source_url"] = source_url
            data["website"] = source_url
            
            return data
            
        except Exception as e:
            print(f"   ⚠️  데이터 추출 LLM 오류: {e}")
            return {"title": "Unknown", "source_url": source_url}
