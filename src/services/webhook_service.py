import requests
from typing import Dict
import streamlit as st
import os

class WebhookService:
    def __init__(self, webhook_url: str = None):
        # 우선순위: 직접 전달된 URL > secrets > 환경변수
        self.webhook_url = webhook_url or st.secrets.get("WEBHOOK_URL") or os.getenv("WEBHOOK_URL")
        if not self.webhook_url:
            st.warning("Webhook URL이 설정되지 않았습니다. 기능이 제한될 수 있습니다.")

    def send_scraping_request(self) -> Dict:
        """스크래핑 요청을 webhook으로 전송"""
        if not self.webhook_url:
            return {"success": False, "message": "Webhook URL이 설정되지 않았습니다."}
            
        try:
            response = requests.post(
                self.webhook_url,
                json={"action": "start_scraping", "platform": "saramin"}
            )
            response.raise_for_status()
            return {"success": True, "message": "스크래핑 요청이 성공적으로 전송되었습니다."}
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"스크래핑 요청 실패: {str(e)}"} 