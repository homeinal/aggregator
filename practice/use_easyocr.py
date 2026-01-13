import easyocr
import os

# 1. 이미지가 있는 폴더
IMAGE_FOLDER = "captured_images"

def read_with_easyocr():
    print("🚀 EasyOCR 모델을 로딩 중입니다... (처음엔 시간 좀 걸려요)")
    
    # gpu=False: 맥북이나 일반 노트북이면 False가 안정적입니다. (NVIDIA 그래픽카드 있으면 True)
    reader = easyocr.Reader(['ko', 'en'], gpu=False) 

    if not os.path.exists(IMAGE_FOLDER):
        print("❌ 폴더가 없습니다.")
        return

    files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    for filename in files:
        full_path = os.path.join(IMAGE_FOLDER, filename)
        print(f"\n🖼️  [분석 중] {filename}")
        
        # detail=0: 텍스트만 리스트로 쫙 뽑아줍니다.
        # detail=1: 위치 좌표와 정확도까지 줍니다.
        results = reader.readtext(full_path) 

        print("📝 [결과]:")
        for (bbox, text, prob) in results:
            # 정확도가 30% 이상인 것만 출력
            if prob > 0.3:
                print(f" - {text} (정확도: {prob:.2f})")

if __name__ == "__main__":
    read_with_easyocr()