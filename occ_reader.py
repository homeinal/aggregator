import os
from PIL import Image # 이미지 처리 라이브러리 (Pillow)
import pytesseract    # OCR 라이브러리

# 1. 이미지가 있는 폴더 이름 (아까 저장한 그 폴더)
IMAGE_FOLDER = "captured_images"

def extract_text_from_images():
    print(f"📂 '{IMAGE_FOLDER}' 폴더의 이미지를 해독합니다...\n")
    
    if not os.path.exists(IMAGE_FOLDER):
        print("❌ 폴더가 없습니다. 이미지 수집 코드를 먼저 실행하세요!")
        return

    # 폴더 내의 파일 목록 가져오기
    files = os.listdir(IMAGE_FOLDER)
    
    # 이미지 파일만 골라내기 (jpg, png 등)
    image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]

    if not image_files:
        print("📭 읽을 이미지가 없습니다.")
        return

    for filename in image_files:
        full_path = os.path.join(IMAGE_FOLDER, filename)
        print("-" * 50)
        print(f"🖼️  분석 중: {filename}")
        
        try:
            # 2. 이미지 파일 열기
            img = Image.open(full_path)
            
            # 3. 글자 추출 (lang='kor+eng' -> 한글과 영어를 같이 찾아라)
            # config 옵션은 글자 인식을 더 잘하게 돕는 설정입니다.
            text = pytesseract.image_to_string(img, lang='kor+eng')
            
            # 공백 정리
            clean_text = text.strip()

            if clean_text:
                print("📝 [추출된 텍스트]:")
                print(clean_text)
            else:
                print("🤔 글자를 찾지 못했습니다. (이미지가 너무 흐리거나 글자가 없을 수 있음)")
                
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
            
    print("\n" + "=" * 50)
    print("🎉 모든 이미지 해독 완료!")

if __name__ == "__main__":
    extract_text_from_images()