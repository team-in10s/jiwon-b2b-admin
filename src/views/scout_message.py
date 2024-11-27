import streamlit as st
from datetime import datetime, timedelta
from src.utils.auth_helper import require_auth
from src.utils.database import (
    get_position_details,
    save_scout_message,
    get_latest_scout_message
)

@require_auth
def show_scout_message_page():
    st.title("스카우트 메시지 작성")
    
    # 필요한 세션 데이터 확인
    required_sessions = [
        "selected_position_id",
        "selected_candidates"
    ]
    
    if not all(key in st.session_state for key in required_sessions):
        st.warning("먼저 후보자 선택을 진행해주세요.")
        return
    
    position_id = st.session_state.selected_position_id
    position_details = get_position_details(position_id)
    
    if not position_details:
        st.error("선택된 포지션 정보를 찾을 수 없습니다.")
        return
    
    # 선택된 후보자 수 표시
    st.info(f"선택된 후보자: {len(st.session_state.selected_candidates)}명")
    
    # 최근 메시지 템플릿 로드
    latest_message = get_latest_scout_message(position_id)
    default_title = latest_message['title'] if latest_message else ""
    default_content = latest_message['content'] if latest_message else ""
    
    # 메시지 작성 폼
    with st.form("scout_message_form"):
        # 제목 입력
        title = st.text_input(
            "제목",
            value=default_title,
            help="스카우트 메시지의 제목을 입력하세요"
        )
        
        # 내용 입력
        content = st.text_area(
            "내용",
            value=default_content,
            height=300,
            help="스카우트 메시지의 내용을 입력하세요"
        )
        
        # 유효 기간 설정
        col1, col2 = st.columns(2)
        with col1:
            min_date = datetime.now().date()
            max_date = min_date + timedelta(days=30)
            valid_until = st.date_input(
                "유효 기간",
                value=min_date + timedelta(days=7),
                min_value=min_date,
                max_value=max_date,
                help="스카우트 제안의 유효 기간을 설정하세요"
            )
        
        # 미리보기
        if title and content:
            with st.expander("메시지 미리보기", expanded=True):
                st.subheader(title)
                st.write("---")
                st.write(content)
                st.caption(f"유효기간: ~ {valid_until.strftime('%Y-%m-%d')}")
        
        # 제출 버튼
        submitted = st.form_submit_button("저장 및 다음 단계로")
    
    if submitted:
        if not title or not content:
            st.error("제목과 내용을 모두 입력해주세요.")
            return
        
        # 메시지 저장
        message_id = save_scout_message(
            position_id=position_id,
            title=title,
            content=content,
            valid_until=valid_until.isoformat()
        )
        
        # 세션에 메시지 정보 저장
        st.session_state.scout_message = {
            'id': message_id,
            'title': title,
            'content': content,
            'valid_until': valid_until.isoformat()
        }
        
        st.success("스카우트 메시지가 저장되었습니다.")
        
        # 다음 단계로 이동
        st.session_state.current_page = "자동화 발송"
        st.rerun()
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 스카우트 메시지 작성 페이지 사용법
        
        1. **메시지 작성**:
           - 제목: 간단명료하게 작성
           - 내용: 상세한 스카우트 제안 내용 작성
           - 유효기간: 제안의 유효 기간 설정 (최대 30일)
        
        2. **템플릿 기능**:
           - 이전에 작성한 메시지가 있다면 자동으로 로드됩니다.
           - 필요에 따라 수정하여 사용할 수 있습니다.
        
        3. **미리보기**:
           - 작성한 메시지가 어떻게 보일지 미리 확인할 수 있습니다.
        
        ### 주의사항
        - 모든 선택된 후보자에게 동일한 메시지가 발송됩니다.
        - 한번 발송된 메시지는 수정할 수 없습니다.
        """)
