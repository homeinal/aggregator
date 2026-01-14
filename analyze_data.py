"""
analyze_data.py

results/ 폴더 내의 data.json 파일들을 취합하여 통계를 산출합니다.
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

def analyze_crawled_data():
    """크롤링 결과 데이터 분석"""
    
    base_dir = Path("results")
    if not base_dir.exists():
        print("❌ 'results' 디렉토리가 없습니다.")
        return

    # 1. 파일 취합
    races = []
    failed_dirs = []
    
    print(f"📂 '{base_dir}' 디렉토리 스캔 중...")
    
    for item in base_dir.iterdir():
        if item.is_dir():
            data_file = item / "data.json"
            if data_file.exists():
                try:
                    with open(data_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        races.append(data)
                except Exception as e:
                    print(f"⚠️ {item.name}: 로드 실패 ({e})")
            else:
                raw_file = item / "raw_data.json"
                if raw_file.exists():
                    try:
                        with open(raw_file, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                            # title이라도 있으면 가져오기 시도
                            failed_dirs.append({
                                "id": item.name,
                                "url": raw.get("source_url", "Unknown"),
                                "reason": "data.json not created (extraction failed)"
                            })
                    except:
                        failed_dirs.append({"id": item.name, "reason": "Unknown"})
                else:
                    failed_dirs.append({"id": item.name, "reason": "Empty or valid data missing"})

    total_races = len(races)
    
    if total_races == 0:
        print("❌ 분석할 데이터가 없습니다.")
        return

    # 2. 통계 산출
    stats = {
        "completeness": {
            "title": 0,
            "event_date": 0,
            "organizer": 0,
            "contact": 0,
            "registration_method": 0,
            "registration_dates": 0
        },
        "categories": {
            "total_count": 0,
            "races_with_cats": 0,
            "fee_available": 0,
            "start_time_available": 0
        },
        "reg_methods": Counter()
    }
    
    for race in races:
        # 필드 완전성 체크
        if race.get("title") and race.get("title") != "Unknown":
            stats["completeness"]["title"] += 1
            
        if race.get("event_date"):
            stats["completeness"]["event_date"] += 1
            
        if race.get("organizer"):
            stats["completeness"]["organizer"] += 1
            
        contact = race.get("contact") or {}
        # Legacy format check (flat fields)
        phone = race.get("phone") or contact.get("phone")
        email = race.get("email") or contact.get("email")
        if phone or email:
            stats["completeness"]["contact"] += 1
            
        # 접수 정보 (Legacy flat fields check first)
        reg_methods = race.get("registration_method")
        
        # If not flat, check object
        if not reg_methods and race.get("registration"):
            reg_methods = race["registration"].get("method")
            
        if reg_methods:
            stats["completeness"]["registration_method"] += 1
            if isinstance(reg_methods, list):
                for m in reg_methods:
                    stats["reg_methods"][m] += 1
            elif isinstance(reg_methods, str):
                stats["reg_methods"][reg_methods] += 1
                
        # 접수 날짜
        reg_start = race.get("registration_start_date")
        if not reg_start and race.get("registration"):
             reg_start = race["registration"].get("start_datetime")
             
        if reg_start:
            stats["completeness"]["registration_dates"] += 1

        # 카테고리
        cats = race.get("categories", [])
        if cats:
            stats["categories"]["races_with_cats"] += 1
            stats["categories"]["total_count"] += len(cats)
            for cat in cats:
                if cat.get("fee") is not None:
                    stats["categories"]["fee_available"] += 1
                if cat.get("start_time"):
                    stats["categories"]["start_time_available"] += 1

    # 3. 결과 출력
    print("\n" + "=" * 60)
    print(f"📊 수집 데이터 분석 결과 (총 {total_races}개 대회)")
    print("=" * 60)
    
    # (1) 필드 채워짐 정도
    print("\n1️⃣  데이터 충실도 (Completeness)")
    print(f"   - 대회명(Title): {stats['completeness']['title']}/{total_races} ({stats['completeness']['title']/total_races*100:.1f}%)")
    print(f"   - 개최일(Date): {stats['completeness']['event_date']}/{total_races} ({stats['completeness']['event_date']/total_races*100:.1f}%)")
    print(f"   - 주최사(Org): {stats['completeness']['organizer']}/{total_races} ({stats['completeness']['organizer']/total_races*100:.1f}%)")
    print(f"   - 연락처(Contact): {stats['completeness']['contact']}/{total_races} ({stats['completeness']['contact']/total_races*100:.1f}%)")
    print(f"   - 접수방법(Method): {stats['completeness']['registration_method']}/{total_races} ({stats['completeness']['registration_method']/total_races*100:.1f}%)")
    print(f"   - 접수일정(Period): {stats['completeness']['registration_dates']}/{total_races} ({stats['completeness']['registration_dates']/total_races*100:.1f}%)")
    
    # (2) 종목 통계
    print("\n2️⃣  종목(Categories) 통계")
    if total_races > 0:
        avg_cats = stats['categories']['total_count'] / total_races
        print(f"   - 평균 종목 수: {avg_cats:.1f}개")
    print(f"   - 종목 정보 보유 대회: {stats['categories']['races_with_cats']}/{total_races}")
    
    total_cats = stats['categories']['total_count']
    if total_cats > 0:
        print(f"   - 참가비 정보 있음: {stats['categories']['fee_available']}/{total_cats} ({stats['categories']['fee_available']/total_cats*100:.1f}%)") 
    else:
        print("   - 종목 데이터 없음")
        
    # (3) 접수 방법 분포
    print("\n3️⃣  접수 방법 분포")
    if stats['reg_methods']:
        for method, count in stats['reg_methods'].most_common():
            print(f"   - {method}: {count}개")
    else:
        print("   - 데이터 없음")
        
    # (4) 성공/실패 현황
    success_rate = total_races / (total_races + len(failed_dirs)) * 100
    print(f"\n4️⃣  크롤링 성공률: {success_rate:.1f}% ({total_races}/{total_races + len(failed_dirs)})")
    if failed_dirs:
        print("   ⚠️ 실패/누락 목록:")
        for fail in failed_dirs[:5]:
            print(f"     - {fail['id']} ({fail.get('reason')})")
        if len(failed_dirs) > 5:
            print(f"     ... 외 {len(failed_dirs)-5}개")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    analyze_crawled_data()
