import json
import hashlib
import os
import datetime
from playwright.sync_api import sync_playwright

# 감시할 사이트와 저장할 파일명
TARGET_URL = "https://marathon.jtbc.com/17/?q=YToyOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjtzOjQ6InBhZ2UiO2k6Mjt9&bmode=view&idx=142336393&t=board"
DB_FILE = "latest_status.json"

def get_page_content():
    """헤드리스 브라우저로 접속해서 텍스트를 가져오는 함수"""
    with sync_playwright() as p:
        # 1. 브라우저 몰래 띄우기 (headless=True면 화면 없이 백그라운드 실행)
        browser = p.chromium.launch(headless=False)
        
        # 2. 새 탭 열기 (사람인 척 User-Agent 설정)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"🕵️  [{TARGET_URL}] 사이트에 잠입 중...")
        page.goto(TARGET_URL)
        
        # 3. 로딩 기다리기 (중요!)
        # 네트워크 활동이 멈출 때까지 기다리거나, 특정 태그가 뜰 때까지 기다립니다.
        page.wait_for_load_state("networkidle")
        
        # 4. 데이터 추출
        # 전체 텍스트를 가져오거나, 특정 부분만 가져올 수 있습니다.
        # 예: body 텍스트 전체 가져오기
        content = page.inner_text("body") 
        
        # 팁: 만약 '공지사항'만 보고 싶다면 page.inner_text(".notice-list") 처럼 CSS 선택자를 씁니다.
        
        browser.close()
        return content
def check_for_changes():
    current_text = get_page_content()
    
    # 1. 맛(Hash) 만들기
    current_hash = hashlib.sha256(current_text.encode('utf-8')).hexdigest()
    
    # 2. 예전 기록 불러오기
    saved_hash = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            saved_hash = data.get("hash", "")

    # 3. 비교
    if saved_hash == "":
        print("📝 첫 실행입니다. 상태를 저장합니다.")
        # [수정됨] 텍스트도 같이 넘깁니다!
        save_status(current_hash, current_text) 
    elif current_hash != saved_hash:
        print("🚨 [변경 감지!] 내용이 달라졌습니다.")
        # [수정됨] 텍스트도 같이 넘깁니다!
        save_status(current_hash, current_text)
    else:
        print("✅ 변경 사항이 없습니다.")
        # (변경이 없어도 원본을 보고 싶다면, 여기서도 덮어쓰기 저장을 해도 됩니다)

def save_status(new_hash, content_text):
    """Hash와 함께 '원본 텍스트'도 저장하는 함수"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data = {
        "last_checked": now,
        "hash": new_hash,
        "content": content_text  # 👈 여기에 원본을 통째로 저장합니다!
    }
    
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"💾 상태(원본 포함) 저장 완료.")

if __name__ == "__main__":
    try:
        check_for_changes()
    except Exception as e:
        print(f"❌ 에러 발생: {e}")