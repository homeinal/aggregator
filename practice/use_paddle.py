from paddleocr import PaddleOCR
import os
import logging

# 1. 이미지가 있는 폴더
IMAGE_FOLDER = "captured_images"

# 불필요한 로그 끄기
logging.getLogger("ppocr").setLevel(logging.WARNING)

def read_with_paddle():
    print("🥟 PaddleOCR 셰프가 주방에 입장합니다... (모델 로딩 중)")
    
    try:
        # [설정] 여기서 'use_angle_cls=True'를 켜면, 글자가 뒤집혀도 알아서 잡습니다.
        # (show_log 옵션은 삭제했습니다)
        ocr = PaddleOCR(lang='korean', use_angle_cls=True)
    except Exception as e:
        print(f"❌ 모델 로딩 실패: {e}")
        return

    if not os.path.exists(IMAGE_FOLDER):
        print("❌ 폴더가 없습니다.")
        return

    files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not files:
        print("📭 읽을 이미지가 없습니다.")
        return

    for filename in files:
        full_path = os.path.join(IMAGE_FOLDER, filename)
        print("-" * 50)
        print(f"🖼️  [분석 중] {filename}")
        
        try:
            # [핵심 수정] 
            # ❌ cls=True 삭제! (여기서 옵션을 주면 에러가 납니다)
            # ⭕️ 그냥 파일 경로만 줍니다.
            result = ocr.ocr(full_path)
            
        except Exception as e:
            print(f"   ⚠️ OCR 엔진 에러 (건너뜀): {e}")
            continue
        
        # 결과가 비어있으면 패스
        if not result or result[0] is None:
            print("   💨 텍스트 없음")
            continue

        print("📝 [추출된 텍스트]:")
        
        # === 결과 파싱 ===
        try:
            for line in result:
                if not line: continue
                
                for word_info in line:
                    # 안전하게 데이터 꺼내기
                    if isinstance(word_info, list) and len(word_info) == 2:
                        content = word_info[1] # [글자, 점수] 부분
                        
                        if isinstance(content, (list, tuple)) and len(content) >= 2:
                            text = content[0]
                            score = content[1]
                            
                            if isinstance(score, (int, float)) and score > 0.6:
                                print(f" - {text} (정확도: {score:.2f})")
        except Exception as e:
             # 가끔 구조가 다를 때 무시
            pass

if __name__ == "__main__":
    read_with_paddle()