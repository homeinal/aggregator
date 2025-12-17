import os
from google.cloud import vision
import io

# ==========================================
# 🔑 설정 영역
# ==========================================
# 1. 아까 다운받은 JSON 키 파일 이름
KEY_FILE = "my_key.json" 
# 2. 이미지가 있는 폴더
IMAGE_FOLDER = "captured_images"
# ==========================================

def detect_text_google():
    print("✨ Google Cloud Vision(미슐랭 셰프)을 모셔옵니다...")

    # 1. 인증 처리 (열쇠 등록)
    if not os.path.exists(KEY_FILE):
        print(f"❌ '{KEY_FILE}' 파일이 없습니다! 구글 콘솔에서 받은 키를 이 폴더에 넣어주세요.")
        return
    
    # 환경변수에 키 경로 등록 (구글 라이브러리가 알아서 읽어감)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_FILE

    # 2. 클라이언트 생성
    client = vision.ImageAnnotatorClient()

    if not os.path.exists(IMAGE_FOLDER):
        print("❌ 이미지 폴더가 없습니다.")
        return

    files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    for filename in files:
        full_path = os.path.join(IMAGE_FOLDER, filename)
        print("-" * 50)
        print(f"🖼️  [분석 중] {filename}")

        try:
            # 3. 이미지 파일을 메모리로 읽기
            with io.open(full_path, 'rb') as image_file:
                content = image_file.read()

            image = vision.Image(content=content)

            # 4. 구글 서버에 전송해서 텍스트 추출 (TEXT_DETECTION 기능)
            response = client.text_detection(image=image)
            
            # 에러 체크
            if response.error.message:
                print(f"   ❌ API 에러: {response.error.message}")
                continue

            # 5. 결과 받아오기
            # text_annotations[0]에는 전체 텍스트가 덩어리로 들어있습니다.
            texts = response.text_annotations
            
            if texts:
                print("📝 [추출된 텍스트]:")
                # 전체 문맥을 고려한 텍스트 덩어리 출력
                print(texts[0].description)
                
                # (상세 정보가 필요하면 아래 주석 해제)
                # print(f"   (언어: {texts[0].locale})")
            else:
                print("   💨 텍스트 없음")

        except Exception as e:
            print(f"   ⚠️ 에러 발생: {e}")

if __name__ == "__main__":
    detect_text_google()