import os
import time
import requests
from playwright.sync_api import sync_playwright

# 저장할 폴더
SAVE_DIR = "playwright_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def download_images_with_playwright(url):
    with sync_playwright() as p:
        # 1. 브라우저 열기
        browser = p.chromium.launch(headless=False) # 과정을 보려면 False, 안 보려면 True
        page = browser.new_page()
        
        print(f"🕵️  [{url}] 접속 중...")
        page.goto(url)
        
        # ==================================================
        # 🌟 핵심 기술: 바닥까지 스크롤 내려서 이미지 깨우기
        # ==================================================
        print("⬇️  이미지 로딩을 위해 스크롤을 내립니다...")
        previous_height = page.viewport_size['height']
        
        # 5번 정도 스크롤을 뚝뚝 끊어서 내립니다 (사이트마다 조절 필요)
        for _ in range(5):
            page.mouse.wheel(0, 1000) # 마우스 휠을 아래로 1000만큼 굴림
            time.sleep(1) # 로딩 기다리기 (중요!)
            
        # (혹은 page.evaluate("window.scrollTo(0, document.body.scrollHeight)") 로 한방에 갈 수도 있음)
        
        # ==================================================
        # 2. 이미지 찾기
        # ==================================================
        # '.view_con img'는 아까 그 마라톤 사이트 기준입니다.
        # 일반 사이트라면 그냥 'img' 라고 쓰면 됩니다.
        images = page.locator(".view_con img").all()
        
        print(f"✨ 총 {len(images)}개의 이미지 요소를 찾았습니다.")

        for i, img in enumerate(images):
            # src 속성 가져오기
            src = img.get_attribute("src")
            
            if src:
                # http로 시작하지 않는 상대 경로(../img/a.jpg) 처리
                if not src.startswith("http"):
                    # 현재 페이지 URL과 합쳐줍니다.
                    # (Playwright는 urljoin 같은 게 내장되어 있진 않아서 수동으로 하거나 urllib을 씁니다)
                    # 여기선 간단히 보여드리기 위해 패스하거나, requests 때처럼 urljoin을 씁니다.
                    from urllib.parse import urljoin
                    src = urljoin(page.url, src)

                print(f"   [{i+1}] 다운로드: {src}")
                
                # 3. 다운로드 (requests 사용)
                # Playwright 안에서 파일을 쓰는 것보다, 주소만 따서 requests로 받는 게 제일 편합니다.
                try:
                    img_data = requests.get(src).content
                    filename = f"{SAVE_DIR}/image_{i+1}.jpg"
                    
                    with open(filename, "wb") as f:
                        f.write(img_data)
                except Exception as e:
                    print(f"   ❌ 다운로드 실패: {e}")
            
        browser.close()
        print("🎉 모든 작업 완료!")

if __name__ == "__main__":
    # 아까 그 사이트 주소
    target_url = "http://ysmarathon.co.kr/ground/notify/1812" 
    download_images_with_playwright(target_url)