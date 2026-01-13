"""
agent_browseruse/__init__.py

Browser-Use 기반 지능형 탐색 크롤러
AI 에이전트가 자율적으로 웹을 탐색하고 데이터를 추출
"""

from .schemas import Race, RaceCategory
from .browseruse_agent import BrowserUseAgent

__all__ = ["Race", "RaceCategory", "BrowserUseAgent"]
