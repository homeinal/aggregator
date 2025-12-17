import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

target_url = "https://marathon.jtbc.com/"

print(f"🔎 [{target_url}] 사이트 분석을 시작합니다...\n")

# ==========================================
# 1. Robots.txt 확인하기 (규칙 확인)
# ==========================================
robots_url = urljoin(target_url, "/robots.txt")
try:
    response = requests.get(robots_url, timeout=5)
    
    if response.status_code == 200:
        print(f"✅ robots.txt를 발견했습니다! ({robots_url})")
        print("-" * 40)
        print(response.text.strip()) # 내용 출력
        print("-" * 40)
    else:
        print(f"🤔 robots.txt가 없습니다. (상태 코드: {response.status_code})")
        print("   -> 별도의 크롤링 제한 규칙을 명시하지 않았거나, 숨겨져 있을 수 있습니다.")

except Exception as e:
    print(f"❌ robots.txt 확인 중 에러 발생: {e}")

print("\n" + "=" * 40 + "\n")

# ==========================================
# 2. RSS 피드 확인하기 (구독 채널 확인)
# ==========================================
print("📡 RSS 피드를 찾고 있습니다...")

try:
    # 메인 페이지를 가져와서 분석
    response = requests.get(target_url, timeout=5)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # HTML 헤더(<head>) 안에 숨겨진 RSS 링크 찾기
    # 보통 <link rel="alternate" type="application/rss+xml" ...> 형태로 되어 있습니다.
    rss_links = soup.find_all('link', type='application/rss+xml')
    atom_links = soup.find_all('link', type='application/atom+xml')
    
    found_feeds = rss_links + atom_links
    
    if found_feeds:
        print(f"✅ 총 {len(found_feeds)}개의 피드를 발견했습니다!")
        for link in found_feeds:
            print(f"   - 주소: {link.get('href')} (제목: {link.get('title', '없음')})")
    else:
        print("💨 RSS/Atom 피드 정보를 HTML 헤더에서 찾을 수 없습니다.")
        print("   -> 뉴스 사이트가 아닌 '이벤트 페이지'의 경우 RSS가 없는 경우가 많습니다.")

except Exception as e:
    print(f"❌ 페이지 분석 중 에러 발생: {e}")