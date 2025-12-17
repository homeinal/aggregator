import json
import os

file_path = "latest_status.json"

if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"⏰ 확인 시간: {data.get('last_checked')}")
    print(f"🔑 해시 값: {data.get('hash')}")
    print("-" * 50)
    print("📜 [수집된 원본 내용]")
    print("-" * 50)
    
    # 원본 내용 출력
    content = data.get('content', '원본 내용이 없습니다.')
    
    # 내용이 너무 길면 500자만 보여주기 (터미널 도배 방지)
    if len(content) > 500:
        print(content[:500] + "\n\n... (내용이 너무 길어서 생략함) ...")
    else:
        print(content)
        
    print("-" * 50)
else:
    print("파일이 없습니다. monitor 코드를 먼저 실행하세요.")