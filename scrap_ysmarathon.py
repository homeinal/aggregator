import os
import hashlib
from playwright.sync_api import sync_playwright

# 저장할 폴더
SAVE_DIR = "captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# 너무 작은 아이콘이나 장식용 이미지는 거르기 위한 기준 (바이트 단위, 3KB)
MIN_IMAGE_SIZE = 3000 

def run_network_sniffer():
    with sync_playwright() as p:
        # 1. 브라우저 열기 (headless=False로 해서 실제로 열리는지 보세요)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("📡 네트워크 감시를 시작합니다...")

        # ==================================================
        # 🌟 핵심 기술: 네트워크 응답(Response) 가로채기 핸들러
        # ==================================================
        def handle_response(response):
            try:
                # 1. 들어온 데이터가 '이미지'인지 확인
                content_type = response.headers.get("content-type", "")
                
                if "image" in content_type:
                    # 2. 이미지 데이터(body) 받기
                    body = response.body()
                    
                    # 3. 너무 작은 파일(아이콘, 점선 등)은 무시
                    if len(body) > MIN_IMAGE_SIZE:
                        # 4. 파일 이름 만들기 (URL에서 따오거나, 겹치면 해시값 사용)
                        url = response.url
                        ext = content_type.split("/")[-1].split(";")[0] # jpeg, png 등 추출
                        if ext == "svg+xml": ext = "svg"
                        
                        # 파일명을 URL의 마지막 부분으로 하되, 너무 길면 자름
                        filename = url.split("/")[-1].split("?")[0]
                        if not filename or len(filename) > 30:
                            # 파일명이 이상하면 데이터 내용으로 고유 이름 생성
                            filename = hashlib.md5(body).hexdigest() + "." + ext
                        
                        # 확장자가 없으면 붙여줌
                        if "." not in filename:
                            filename += f".{ext}"

                        save_path = os.path.join(SAVE_DIR, filename)
                        
                        # 5. 저장
                        with open(save_path, "wb") as f:
                            f.write(body)
                        print(f"   📸 [캡처 성공] {filename} ({len(body)//1024} KB)")
                        
            except Exception as e:
                # 가끔 네트워크 끊김 등으로 에러 날 수 있음 (무시)
                pass

        # 브라우저에게 "응답이 올 때마다 handle_response 함수를 실행해"라고 명령
        page.on("response", handle_response)

        # ==================================================
        # 2. 사이트 접속 (이제 이미지가 로딩되면 자동으로 저장됨)
        # ==================================================
        target_url = "http://ysmarathon.co.kr/ground/notify/1812"
        print(f"🚀 [{target_url}] 접속 중...")
        page.goto(target_url)

        # 3. 충분히 기다리기 (뷰어나 스크립트가 이미지를 로딩할 시간을 줌)
        print("⏳ 이미지가 다 뜰 때까지 5초간 대기합니다...")
        page.wait_for_timeout(5000)
        
        # (선택) 만약 스크롤을 내려야 보인다면 여기서 스크롤
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(3000)

        browser.close()
        print(f"\n🎉 작업 완료! '{SAVE_DIR}' 폴더를 확인해보세요.")

if __name__ == "__main__":
    run_network_sniffer()