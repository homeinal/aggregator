"""
analyze_data.py

results.json의 categories 필드 채워짐 정도(Completeness) 분석
"""

import json
from pathlib import Path


def analyze_categories():
    """results.json의 카테고리 데이터 분석"""
    
    file_path = Path("results.json")
    
    # 1. 파일 로드 (예외 처리)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ JSON 형식 오류: {e}")
        return
    
    if not isinstance(data, list):
        print("❌ 데이터가 리스트 형태가 아닙니다.")
        return
    
    # 2. 통계 산출
    total_races = len(data)
    races_with_categories = 0
    total_categories = 0
    valid_registration_at = 0
    valid_fee = 0
    
    for race in data:
        categories = race.get("categories", [])
        
        # (1) 카테고리 보유 대회 수
        if categories and len(categories) > 0:
            races_with_categories += 1
        
        for cat in categories:
            # (2) 전체 카테고리 수
            total_categories += 1
            
            # (3) 접수일 유효 데이터 수
            if cat.get("next_registration_at") is not None:
                valid_registration_at += 1
            
            # (4) 참가비 유효 데이터 수 (0 포함)
            if cat.get("fee") is not None:
                valid_fee += 1
    
    # 3. 결과 출력
    print("\n" + "=" * 60)
    print("📊 Categories 데이터 채워짐 분석 (Data Completeness)")
    print("=" * 60)
    
    # (1) 카테고리 보유 대회 수
    pct1 = (races_with_categories / total_races * 100) if total_races > 0 else 0
    print(f"\n1️⃣  카테고리 보유 대회 수: {races_with_categories}/{total_races} ({pct1:.2f}%)")
    
    # (2) 전체 카테고리 수
    print(f"2️⃣  전체 카테고리 수: {total_categories}개")
    
    # (3) 접수일 유효 데이터 수
    pct3 = (valid_registration_at / total_categories * 100) if total_categories > 0 else 0
    print(f"3️⃣  접수일 정보 있음: {valid_registration_at}/{total_categories} ({pct3:.2f}%)")
    
    # (4) 참가비 유효 데이터 수
    pct4 = (valid_fee / total_categories * 100) if total_categories > 0 else 0
    print(f"4️⃣  참가비 정보 있음: {valid_fee}/{total_categories} ({pct4:.2f}%)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    analyze_categories()
