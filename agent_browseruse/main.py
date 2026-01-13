"""
agent_browseruse/main.py

메인 엔트리포인트
- CSV 파일에서 URL 로드
- 각 URL에 대해 BrowserUseAgent 실행
- 결과 JSON 저장
"""

import asyncio
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_browseruse.browseruse_agent import BrowserUseAgent
from agent_browseruse.schemas import Race


# ==========================================
# 설정
# ==========================================
DEFAULT_CSV = "urls/urls.csv"
OUTPUT_FILE = "browseruse_results.json"


def load_urls(csv_path: str) -> List[str]:
    """CSV에서 homepage_url 컬럼 로드"""
    urls = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # homepage_url 또는 url 컬럼 지원
            url = row.get("homepage_url", "").strip() or row.get(" homepage_url", "").strip()
            if not url:
                url = row.get("url", "").strip()
            
            if url and url.startswith("http"):
                urls.append(url)
    
    return urls


def save_results(races: List[Race], output_path: str):
    """결과를 JSON으로 저장"""
    data = []
    
    for race in races:
        race_dict = race.model_dump(mode="json")
        
        # datetime을 문자열로 변환
        if race_dict.get("event_date"):
            race_dict["event_date"] = str(race_dict["event_date"])
        
        for cat in race_dict.get("categories", []):
            for key in ["next_registration_at", "next_registration_end_at", 
                       "next_payment_at", "next_payment_end_at"]:
                if cat.get(key):
                    cat[key] = str(cat[key])
        
        data.append(race_dict)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 결과 저장: {output_path}")


async def run_crawler(urls: List[str], limit: Optional[int] = None, headless: bool = True):
    """
    크롤러 메인 실행 함수
    
    Args:
        urls: 크롤링할 URL 리스트
        limit: 최대 처리 개수
        headless: 브라우저 헤드리스 모드
    """
    target_urls = urls[:limit] if limit else urls
    total = len(target_urls)
    
    print(f"\n🤖 Browser-Use Agent Crawler")
    print(f"{'='*60}")
    print(f"📊 총 {total}개 URL 처리 예정")
    print(f"🖥️  Headless 모드: {headless}")
    print(f"{'='*60}")
    
    results: List[Race] = []
    errors: List[str] = []
    
    agent = BrowserUseAgent(headless=headless)
    
    for idx, url in enumerate(target_urls, 1):
        print(f"\n[{idx}/{total}] 처리 중...")
        
        try:
            race = await agent.process_site(url)
            
            if race:
                results.append(race)
                print(f"   ✅ 성공: {race.title}")
            else:
                errors.append(url)
                print(f"   ❌ 실패: 데이터 없음")
                
        except Exception as e:
            errors.append(url)
            print(f"   ❌ 오류: {e}")
        
        # 다음 URL 전 대기 (서버 부하 방지)
        if idx < total:
            await asyncio.sleep(3)
    
    # 결과 저장
    save_results(results, OUTPUT_FILE)
    
    # 요약
    print(f"\n{'='*60}")
    print(f"📊 크롤링 완료 요약")
    print(f"{'='*60}")
    print(f"   ✅ 성공: {len(results)}개")
    print(f"   ❌ 실패: {len(errors)}개")
    if total > 0:
        print(f"   📊 성공률: {len(results)/total*100:.1f}%")
    
    if errors:
        print(f"\n⚠️  실패한 URL:")
        for url in errors[:5]:
            print(f"   - {url}")
        if len(errors) > 5:
            print(f"   ... 외 {len(errors)-5}개")


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(
        description="Browser-Use Agent Crawler - AI 에이전트 기반 마라톤 크롤러"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=DEFAULT_CSV,
        help=f"URL CSV 파일 경로 (기본값: {DEFAULT_CSV})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 최대 URL 수"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="브라우저 헤드리스 모드 (기본값: False, 브라우저 창 표시)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API 키 (또는 OPENAI_API_KEY 환경변수)"
    )
    
    args = parser.parse_args()
    
    # API 키 확인
    import os
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("\n🔑 OpenAI API 키를 입력하세요:")
        api_key = input("> ").strip()
        
        if not api_key:
            print("❌ API 키가 필요합니다.")
            sys.exit(1)
        
        os.environ["OPENAI_API_KEY"] = api_key
    
    # URL 로드
    try:
        urls = load_urls(args.csv)
        print(f"📂 {len(urls)}개 URL 로드됨 ({args.csv})")
    except FileNotFoundError:
        print(f"❌ CSV 파일을 찾을 수 없습니다: {args.csv}")
        sys.exit(1)
    
    if not urls:
        print("❌ URL이 없습니다. CSV 파일을 확인하세요.")
        sys.exit(1)
    
    # 크롤러 실행
    asyncio.run(run_crawler(urls, args.limit, args.headless))


if __name__ == "__main__":
    main()
