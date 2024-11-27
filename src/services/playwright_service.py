from playwright.async_api import async_playwright
import asyncio
from typing import Dict, List
import streamlit as st

class PlaywrightService:
    def __init__(self):
        self.progress_callback = None
        self.error_callback = None
    
    async def send_scout_message(self, candidate: Dict, message: Dict) -> bool:
        """단일 후보자에게 스카우트 메시지 발송"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 사람인 페이지 접속
                await page.goto(candidate.get('page_url', '#'))
                
                # 메시지 입력
                await page.fill("#scout_title", message['title'])
                await page.fill("#scout_content", message['content'])
                
                # 발송 버튼 클릭
                await page.click("#send_scout_button")
                
                # 발송 완료 확인
                success = await page.wait_for_selector(".success_message", timeout=10000)
                
                await browser.close()
                return bool(success)
                
        except Exception as e:
            if self.error_callback:
                self.error_callback(f"발송 실패 ({candidate['name']}): {str(e)}")
            return False

    async def process_candidates(self, candidates: List[Dict], message: Dict):
        """모든 후보자에게 순차적으로 메시지 발송"""
        total = len(candidates)
        success_count = 0
        
        for idx, candidate in enumerate(candidates, 1):
            if self.progress_callback:
                self.progress_callback(idx, total)
            
            success = await self.send_scout_message(candidate, message)
            if success:
                success_count += 1
            
            # 서버 부하 방지를 위한 딜레이
            await asyncio.sleep(2)
        
        return success_count 