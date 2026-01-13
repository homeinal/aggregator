"""
agent_crawler/link_selector.py

LLM 기반 링크 선별기 (최적화 버전)
- 휴리스틱 사전 필터링 (비용 절감)
- LLM은 고가치 후보만 분석
"""

import re
from typing import List, Dict
from urllib.parse import urljoin, urlparse
from playwright.async_api import Page

from .llm_client import LLMClient


class LinkSelector:
    """
    LLM 기반 링크 선별기 (휴리스틱 사전 필터링 적용)
    """
    
    # 🚫 제외 키워드 (즉시 제외)
    BLOCKLIST = [
        'login', 'signin', 'signup', 'sign_up', 'register',
        'logout', 'admin', 'mypage', 'member',
        'photo', 'gallery', 'board', 'bbs',
        'result', 'record', 'ranking', 'certificate',
        'cart', 'payment', 'order',
        'javascript:', 'mailto:', 'tel:',
        '.pdf', '.jpg', '.png', '.gif', '.zip',
        'facebook', 'instagram', 'youtube', 'twitter', 'kakao', 'naver.com',
    ]
    
    # ✅ 우선순위 키워드 (높은 가치)
    ALLOWLIST = [
        'info', 'guide', 'course', 'regi', 'apply',
        '요강', '안내', '소개', '코스', '신청', '접수',
        '일정', '종목', '참가', '대회', '개요',
        'outline', 'schedule', 'entry', 'about',
        'distance', 'fee', 'program',
    ]
    
    # URL 제외 패턴
    EXCLUDE_PATTERNS = [
        r'login', r'signin', r'signup', r'register',
        r'logout', r'cart', r'mypage', r'member',
        r'board', r'bbs', r'gallery', r'photo',
        r'result', r'record', r'ranking',
    ]
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def pre_filter_links(self, links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        휴리스틱 사전 필터링 (LLM 호출 전 비용 절감)
        
        1. Blocklist 키워드 포함 시 즉시 제외
        2. Allowlist 키워드 포함 시 우선순위 부여
        
        Args:
            links: [{"text": "링크텍스트", "href": "URL"}, ...]
            
        Returns:
            필터링된 링크 (Allowlist 우선)
        """
        high_priority = []
        normal = []
        
        for link in links:
            text = link.get("text", "").lower()
            href = link.get("href", "").lower()
            combined = text + " " + href
            
            # 1. Blocklist 체크 (제외)
            if any(blocked in combined for blocked in self.BLOCKLIST):
                continue
            
            # 2. Allowlist 체크 (우선순위)
            if any(allowed in combined for allowed in self.ALLOWLIST):
                high_priority.append(link)
            else:
                normal.append(link)
        
        # 우선순위 링크 + 일반 링크 (최대 20개)
        filtered = high_priority[:10] + normal[:10]
        return filtered[:20]
    
    async def extract_links(self, page: Page, base_url: str) -> List[Dict[str, str]]:
        """
        페이지에서 모든 링크 추출
        """
        links = []
        base_domain = urlparse(base_url).netloc
        
        try:
            elements = await page.query_selector_all("a[href]")
            
            for el in elements:
                try:
                    href = await el.get_attribute("href")
                    text = await el.inner_text()
                    
                    if not href:
                        continue
                    
                    # 상대 경로 -> 절대 경로
                    absolute_url = urljoin(base_url, href)
                    
                    # 같은 도메인만 허용
                    link_domain = urlparse(absolute_url).netloc
                    if link_domain != base_domain:
                        continue
                    
                    # 기본 URL 패턴 제외
                    if self._should_exclude(absolute_url):
                        continue
                    
                    # 텍스트 정리
                    text = text.strip()[:50] if text else ""
                    
                    if text and absolute_url not in [l["href"] for l in links]:
                        links.append({"text": text, "href": absolute_url})
                        
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"   ⚠️  링크 추출 오류: {e}")
        
        return links[:50]  # 최대 50개
    
    def _should_exclude(self, url: str) -> bool:
        """URL이 제외 패턴에 해당하는지 확인"""
        url_lower = url.lower()
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, url_lower):
                return True
        return False
    
    async def select_valuable_links(
        self, 
        page: Page, 
        base_url: str, 
        max_count: int = 5
    ) -> List[str]:
        """
        휴리스틱 + LLM으로 유의미한 링크 선별
        
        1. 전체 링크 추출
        2. 휴리스틱 사전 필터링 (비용 절감)
        3. LLM으로 최종 선별
        
        Args:
            page: Playwright 페이지
            base_url: 기준 URL
            max_count: 최대 선택 개수
            
        Returns:
            선별된 URL 리스트
        """
        # 1. 링크 추출
        all_links = await self.extract_links(page, base_url)
        
        if not all_links:
            return []
        
        # 2. 휴리스틱 사전 필터링 (비용 절감!)
        filtered_links = self.pre_filter_links(all_links)
        print(f"   📊 휴리스틱 필터: {len(all_links)}개 → {len(filtered_links)}개")
        
        if not filtered_links:
            return []
        
        # 3. LLM으로 최종 선별 (필터링된 링크만)
        selected = self.llm.select_links(filtered_links, max_count)
        
        return selected[:max_count]
