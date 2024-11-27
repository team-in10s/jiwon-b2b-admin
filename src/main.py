import streamlit as st

# 페이지 설정을 가장 먼저 호출
st.set_page_config(
    page_title="B2B Admin System",
    page_icon="🏢",
    layout="wide"
)

from views import (
    show_auth_page,
    show_scraping_page,
    show_monitoring_page,
    show_position_page,
    show_recruitment_page,
    show_ai_filtering_page,
    show_candidate_selection_page,
    show_scout_message_page,
    show_auto_scout_page,
    show_response_page
)

# 페이지 매핑 정의
PAGES = {
    "스크래핑 요청": show_scraping_page,
    "작업 모니터링": show_monitoring_page,
    "포지션 선택": show_position_page,
    "채용 정보 입력": show_recruitment_page,
    "AI 필터링": show_ai_filtering_page,
    "후보자 선택": show_candidate_selection_page,
    "스카우트 메시지": show_scout_message_page,
    "자동화 발송": show_auto_scout_page,
    "응답 관리": show_response_page
}

def init_session_state():
    """세션 상태 초기화"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "current_page" not in st.session_state:
        st.session_state.current_page = "스크래핑 요청"  # 기본 페이지 설정

def main():
    init_session_state()
    
    # 인증 확인
    if not st.session_state.authenticated:
        show_auth_page()
        return
    
    # 인증 후 네비게이션
    st.sidebar.title("메뉴")
    
    # 현재 페이지 선택
    current_page = st.sidebar.radio(
        "페이지 선택",
        options=list(PAGES.keys()),
        index=list(PAGES.keys()).index(st.session_state.current_page)
    )
    
    # 페이지 상태 업데이트
    st.session_state.current_page = current_page
    
    # 페이지 표시
    PAGES[current_page]()
    
    # 로그아웃 버튼
    if st.sidebar.button("로그아웃"):
        st.session_state.authenticated = False
        st.rerun()

if __name__ == "__main__":
    main() 