from bs4 import BeautifulSoup
import requests


headers = {
    # 브라우저 정보 (User-Agent)
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    
    # 어디서 왔는지 (Referer): "저 구글에서 검색해서 왔는데요?"라고 핑계 대기
    'Referer': 'https://www.google.com/',
    
    # 어떤 언어를 쓰는지: "저 한국어 쓰는 사람입니다"
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    
    # 어떤 문서를 원하는지
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
}

url="https://marathon.jtbc.com/"

response=requests.get(url, headers=headers)
print(response.text)
soup=BeautifulSoup(response.text, 'html.parser')
print(soup.select('.article-title'))
images= soup.find_all('img')
print(images)

