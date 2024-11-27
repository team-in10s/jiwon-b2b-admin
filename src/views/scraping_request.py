import streamlit as st
from src.utils.auth_helper import require_auth
from src.services.webhook_service import WebhookService
import time

# WebhookService 인스턴스 생성 (URL 없이)
webhook_service = WebhookService()

@require_auth
def show_scraping_page():
    st.title("사람인 스크래핑 요청")
    
    # 세션 상태 초기화
    if "scraping_requested" not in st.session_state:
        st.session_state.scraping_requested = False
    if "request_time" not in st.session_state:
        st.session_state.request_time = None

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("이 페이지에서는 사람인 인재풀에 대한 스크래핑을 요청할 수 있습니다.")
        st.write("요청 버튼을 클릭하면 자동으로 RPA 작업이 시작됩니다.")

    with col2:
        if not st.session_state.scraping_requested:
            if st.button("스크래핑 요청", use_container_width=True):
                response = webhook_service.send_scraping_request()
                
                if response["success"]:
                    st.session_state.scraping_requested = True
                    st.session_state.request_time = time.time()
                    st.success(response["message"])
                    time.sleep(1)
                    # 모니터링 페이지로 자동 이동
                    st.session_state.current_page = "monitoring"
                    st.rerun()
                else:
                    st.error(response["message"])
        else:
            # 비활성화된 버튼 표시
            st.button("스크래핑 요청", disabled=True, use_container_width=True)
            
            # 경과 시간 표시
            elapsed_time = int(time.time() - st.session_state.request_time)
            st.info(f"마지막 요청 후 경과 시간: {elapsed_time}초")
            
            # 새로운 요청 활성화 버튼
            if st.button("새로운 요청하기", use_container_width=True):
                st.session_state.scraping_requested = False
                st.rerun()

    # 도움말 섹션
    with st.expander("도움말"):
        st.markdown("""
        ### 스크래핑 요청 프로세스
        1. '스크래핑 요청' 버튼을 클릭하면 RPA 작업이 시작됩니다.
        2. 요청이 완료되면 자동으로 모니터링 페이지로 이동합니다.
        3. 한 번 요청한 후에는 버튼이 비활성화되며, 새로운 요청을 하려면 '새로운 요청하기' 버튼을 클릭해야 합니다.
        
        ### 주의사항
        - 스크래핑 요청은 한 번에 하나만 진행할 수 있습니다.
        - 이전 요청이 완료되기 전에 새로운 요청을 하면 작업이 중복될 수 있습니다.
        """)
