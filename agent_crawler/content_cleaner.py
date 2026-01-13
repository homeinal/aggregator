"""
agent_crawler/content_cleaner.py

HTML 콘텐츠 정제기 (최적화 버전)
- html2text로 Markdown 변환 (토큰 절약)
- 불필요한 태그 제거 (script, style, nav, footer)
- 공백/개행 압축
"""

import re
import html2text
from bs4 import BeautifulSoup
from typing import Optional, List, Tuple


class ContentCleaner:
    """HTML 노이즈 제거 및 Markdown 변환"""
    
    # 제거할 태그 목록
    REMOVE_TAGS = [
        'script', 'style', 'nav', 'footer', 'header',
        'aside', 'iframe', 'noscript', 'svg', 'path',
        'meta', 'link', 'button', 'input', 'form',
        'advertisement', 'ad', 'cookie-banner'
    ]
    
    # 제거할 class/id 패턴
    REMOVE_PATTERNS = [
        'nav', 'menu', 'footer', 'header', 'sidebar',
        'banner', 'advertisement', 'cookie', 'popup',
        'modal', 'ad-', 'social', 'share'
    ]
    
    def __init__(self):
        """html2text 컨버터 초기화"""
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = True
        self.h.ignore_emphasis = False
        self.h.body_width = 0  # 줄바꿈 비활성화
        self.h.unicode_snob = True
    
    def clean_content(self, html: str) -> str:
        """
        HTML을 정제하여 Markdown으로 변환 (토큰 최적화)
        
        1. BeautifulSoup으로 불필요한 태그 제거
        2. html2text로 Markdown 변환
        3. 연속 공백/개행 압축
        
        Args:
            html: 원본 HTML 문자열
            
        Returns:
            정제된 Markdown 텍스트
        """
        if not html:
            return ""
        
        # 1. BeautifulSoup으로 노이즈 제거
        soup = BeautifulSoup(html, 'html.parser')
        
        # 불필요한 태그 제거
        for tag in self.REMOVE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 특정 class/id 패턴 제거
        for pattern in self.REMOVE_PATTERNS:
            for element in soup.find_all(class_=re.compile(pattern, re.I)):
                element.decompose()
            for element in soup.find_all(id=re.compile(pattern, re.I)):
                element.decompose()
        
        # 2. html2text로 Markdown 변환
        clean_html = str(soup)
        markdown = self.h.handle(clean_html)
        
        # 3. 공백/개행 압축
        markdown = self._compress_whitespace(markdown)
        
        return markdown.strip()
    
    def _compress_whitespace(self, text: str) -> str:
        """연속된 공백과 개행 압축"""
        # 연속 개행 -> 최대 2개
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 연속 공백 -> 1개
        text = re.sub(r'[ \t]{2,}', ' ', text)
        # 빈 줄의 공백 제거
        text = re.sub(r'\n\s+\n', '\n\n', text)
        return text
    
    def extract_main_content(self, html: str) -> str:
        """
        메인 콘텐츠 영역만 추출 후 Markdown 변환
        
        Args:
            html: 원본 HTML
            
        Returns:
            (메인 콘텐츠 Markdown, 이미지 URL 리스트)
        """
        if not html:
            return "", []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 메인 콘텐츠 영역 셀렉터 시도
        main_selectors = [
            'main',
            'article',
            '.content',
            '#content',
            '.main-content',
            '#main-content',
            '.container',
            '.wrapper',
            '.page-content',
        ]
        
        selected_element = None
        for selector in main_selectors:
            main = soup.select_one(selector)
            if main and len(main.get_text(strip=True)) > 100:
                selected_element = main
                break
        
        # 메인 영역 못 찾으면 body 또는 전체 사용
        if not selected_element:
            selected_element = soup.body if soup.body else soup

        # 이미지 URL 추출 (정제 전에 수행)
        image_urls = []
        if selected_element:
            for img in selected_element.find_all('img'):
                src = img.get('src')
                if src:
                    image_urls.append(src)

        # 콘텐츠 정제 및 마크다운 변환
        markdown = self.clean_content(str(selected_element))
        
        return markdown, image_urls
    
    def truncate_text(self, text: str, max_chars: int = 8000) -> str:
        """
        텍스트 길이 제한 (토큰 절약)
        
        Args:
            text: 원본 텍스트
            max_chars: 최대 문자 수
            
        Returns:
            잘린 텍스트
        """
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n...[truncated]"
