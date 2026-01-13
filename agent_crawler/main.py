"""
agent_crawler/main.py

메인 엔트리포인트
- CSV 파일에서 URL 로드
- 각 URL에 대해 CrawlerAgent 실행
- 결과 JSON 저장
"""

import asyncio
import argparse
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트)
load_dotenv(Path(__file__).parent.parent / ".env")

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_crawler.crawler_agent import CrawlerAgent
from agent_crawler.schemas import Race


# ==========================================
# 설정
# ==========================================
DEFAULT_CSV = "urls/urls.csv"
RESULTS_BASE_DIR = "results"


def load_urls_with_id(csv_path: str) -> List[tuple]:
    """CSV에서 url_id와 homepage_url 컬럼 로드
    
    Returns:
        List[tuple]: [(url_id, homepage_url), ...]
    """
    url_data = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # url_id 컬럼 이름에서 공백 제거
            url_id = row.get("url_id", "").strip()
            if not url_id:
                # 첫 번째 컬럼 키 가져오기 (공백 포함 가능)
                for key in row.keys():
                    if "url_id" in key.replace(" ", "").lower():
                        url_id = row.get(key, "").strip()
                        break
            
            url = row.get("homepage_url", "").strip()
            if not url:
                # 첫 번째 컬럼 키 가져오기 (공백 포함 가능)
                for key in row.keys():
                    if "homepage_url" in key.replace(" ", "").lower():
                        url = row.get(key, "").strip()
                        break
            
            if url_id and url and url.startswith("http"):
                url_data.append((url_id, url))
    
    return url_data



def save_result_by_url_id(race: Race, url_id: str, suffix: str = "", base_dir: str = RESULTS_BASE_DIR):
    """url_id별 디렉토리에 결과를 JSON으로 저장
    
    Args:
        race: Race 객체
        url_id: URL 식별자
        suffix: 파일명 접미사 (예: "5_2" -> data5_2.json)
        base_dir: 결과 저장 기본 디렉토리
    """
    # 디렉토리 생성
    result_dir = Path(base_dir) / url_id
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # Race 데이터 변환
    race_dict = race.model_dump(mode="json")
    
    # datetime을 문자열로 변환
    if race_dict.get("event_date"):
        race_dict["event_date"] = str(race_dict["event_date"])
    
    for cat in race_dict.get("categories", []):
        for key in ["next_registration_at", "next_registration_end_at", 
                   "next_payment_at", "next_payment_end_at"]:
            if cat.get(key):
                cat[key] = str(cat[key])
    
    # JSON 파일 저장
    filename = f"data{suffix}.json"
    output_path = result_dir / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(race_dict, f, ensure_ascii=False, indent=2)
    
    print(f"   📁 저장: {output_path}")
    return output_path


def save_raw_data_by_url_id(raw_data: str, url_id: str, source_url: str, suffix: str = "", base_dir: str = RESULTS_BASE_DIR):
    """url_id별 디렉토리에 원본 HTML 데이터를 JSON으로 저장
    
    Args:
        raw_data: 병합된 HTML/Markdown 컨텐츠
        url_id: URL 식별자
        source_url: 원본 URL
        suffix: 파일명 접미사 (예: "5_2" -> raw_data5_2.json)
        base_dir: 결과 저장 기본 디렉토리
    """
    # 디렉토리 생성
    result_dir = Path(base_dir) / url_id
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # raw_data.json 저장
    raw_data_dict = {
        "url_id": url_id,
        "source_url": source_url,
        "content": raw_data,
        "content_length": len(raw_data)
    }
    
    filename = f"raw_data{suffix}.json"
    output_path = result_dir / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_data_dict, f, ensure_ascii=False, indent=2)
    
    print(f"   📄 Raw 데이터 저장: {output_path}")
    return output_path


def save_results(races: List[Race], output_path: str):
    """결과를 JSON으로 저장 (기존 호환성 유지)"""
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


async def run_crawler(api_key: str, url_data: List[tuple], limit: Optional[int] = None, model: str = "gpt-4o-mini", suffix: str = ""):
    """
    크롤러 메인 실행 함수
    
    Args:
        api_key: OpenAI API 키
        url_data: (url_id, homepage_url) 튜플 리스트
        limit: 최대 처리 개수
        model: 사용할 LLM 모델명
        suffix: 출력 파일명 접미사
    """
    target_data = url_data[:limit] if limit else url_data
    total = len(target_data)
    
    print(f"\n🏃 Intelligent Navigation Agent Crawler")
    print(f"{'='*60}")
    print(f"📊 총 {total}개 URL 처리 예정")
    print(f"🧠 모델: {model}")
    print(f"📁 결과 저장 위치: {RESULTS_BASE_DIR}/[url_id]/data{suffix}.json")
    print(f"{'='*60}")
    
    results: List[tuple] = []  # (url_id, Race)
    errors: List[tuple] = []   # (url_id, url, error_msg)
    
    async with CrawlerAgent(api_key, model_name=model) as agent:
        for idx, (url_id, url) in enumerate(target_data, 1):
            print(f"\n[{idx}/{total}] URL ID: {url_id} 처리 중...")
            print(f"   🔗 {url}")
            
            try:
                result = await agent.process_site(url)
                
                if result:
                    race, raw_context = result
                    
                    # Raw 데이터 먼저 저장
                    save_raw_data_by_url_id(raw_context, url_id, url, suffix)
                    
                    # url_id별 디렉토리에 저장
                    save_result_by_url_id(race, url_id, suffix)
                    results.append((url_id, race))
                    print(f"   ✅ 성공: {race.title}")
                else:
                    errors.append((url_id, url, "데이터 없음"))
                    print(f"   ❌ 실패: 데이터 없음")
                    
            except Exception as e:
                errors.append((url_id, url, str(e)))
                print(f"   ❌ 오류: {e}")
            
            # 다음 URL 전 대기 (서버 부하 방지)
            if idx < total:
                await asyncio.sleep(2)
    
    # 요약
    print(f"\n{'='*60}")
    print(f"📊 크롤링 완료 요약")
    print(f"{'='*60}")
    print(f"   ✅ 성공: {len(results)}개")
    print(f"   ❌ 실패: {len(errors)}개")
    if total > 0:
        print(f"   📊 성공률: {len(results)/total*100:.1f}%")
    
    # 저장된 파일 목록
    if results:
        print(f"\n📁 저장된 파일:")
        for url_id, race in results:
            print(f"   - {RESULTS_BASE_DIR}/{url_id}/data{suffix}.json ({race.title})")
    
    if errors:
        print(f"\n⚠️  실패한 URL:")
        for url_id, url, error in errors[:5]:
            print(f"   - [{url_id}] {url}: {error}")
        if len(errors) > 5:
            print(f"   ... 외 {len(errors)-5}개")


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(
        description="Intelligent Navigation Agent Crawler"
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
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API 키 (또는 OPENAI_API_KEY 환경변수)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="사용할 LLM 모델명 (예: gpt-4o, gpt-3.5-turbo)"
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="출력 파일명 접미사 (예: 5_2 -> data5_2.json)"
    )
    
    args = parser.parse_args()
    
    # API 키 확인 (.env에서 자동 로드됨)
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("\n🔑 OpenAI API 키를 입력하세요:")
        api_key = input("> ").strip()
        
        if not api_key:
            print("❌ API 키가 필요합니다.")
            sys.exit(1)
    
    # URL 로드
    try:
        url_data = load_urls_with_id(args.csv)
        print(f"📂 {len(url_data)}개 URL 로드됨 ({args.csv})")
        for url_id, url in url_data:
            print(f"   - [{url_id}] {url}")
    except FileNotFoundError:
        print(f"❌ CSV 파일을 찾을 수 없습니다: {args.csv}")
        sys.exit(1)
    
    # 크롤러 실행
    asyncio.run(run_crawler(api_key, url_data, args.limit, args.model, args.suffix))


if __name__ == "__main__":
    main()
