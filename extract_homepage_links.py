"""
extract_homepage_links.py

roadrun.csv의 각 URL에서 "홈페이지:" 링크를 추출하여 CSV로 저장
http/https로 시작하는 실제 URL만 추출
"""

import asyncio
import csv
from playwright.async_api import async_playwright


async def extract_homepage_links():
    """각 URL에서 홈페이지 링크 추출"""
    
    # CSV 읽기
    urls = []
    with open("urls/roadrun.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("source_url", "").strip()
            if url:
                urls.append(url)
    
    print(f"📂 총 {len(urls)}개 URL 로드됨\n")
    
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for idx, url in enumerate(urls, 1):
            print(f"[{idx}/{len(urls)}] {url}")
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(500)
                
                homepage_url = None
                
                # 테이블 행에서 "홈페이지" 찾기
                rows = await page.query_selector_all("tr")
                for row in rows:
                    text = await row.inner_text()
                    if "홈페이지" in text:
                        # 이 행에서 http로 시작하는 링크만 찾기
                        links = await row.query_selector_all("a")
                        for link in links:
                            href = await link.get_attribute("href")
                            if href and (href.startswith("http://") or href.startswith("https://")):
                                homepage_url = href
                                break
                        if homepage_url:
                            break
                
                if homepage_url:
                    print(f"   ✅ 홈페이지: {homepage_url}")
                    results.append({"source_url": url, "homepage_url": homepage_url})
                else:
                    print(f"   ⚠️  홈페이지 링크 없음")
                    results.append({"source_url": url, "homepage_url": ""})
                    
            except Exception as e:
                print(f"   ❌ 오류: {e}")
                results.append({"source_url": url, "homepage_url": ""})
            
            await asyncio.sleep(0.3)
        
        await browser.close()
    
    # 결과 CSV 저장
    output_file = "urls/homepage_links.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source_url", "homepage_url"])
        writer.writeheader()
        writer.writerows(results)
    
    found = sum(1 for r in results if r["homepage_url"])
    print(f"\n{'='*60}")
    print(f"✅ 완료! 결과 저장: {output_file}")
    print(f"   - 총 URL: {len(results)}개")
    print(f"   - 홈페이지 발견: {found}개")
    print(f"   - 홈페이지 없음: {len(results) - found}개")


if __name__ == "__main__":
    asyncio.run(extract_homepage_links())
