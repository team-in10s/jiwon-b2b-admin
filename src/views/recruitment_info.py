import streamlit as st
from datetime import datetime
from psycopg2.extras import RealDictCursor
from src.utils.auth_helper import require_auth
from src.utils.database import (
    get_position_details, 
    get_latest_prompt, 
    save_prompt,
    get_db_connection,
    get_latest_recruitment_info,
    save_recruitment_info
)

@require_auth
def show_recruitment_page():
    st.title("채용 정보 입력")
    
    # 선택된 포지션 확인
    if "selected_position_id" not in st.session_state:
        st.warning("먼저 포지션을 선택해주세요.")
        return
    
    position_id = st.session_state.selected_position_id
    position_details = get_position_details(position_id)
    
    if not position_details:
        st.error("선택된 포지션 정보를 찾을 수 없습니다.")
        return
    
    # 포지션 정보 표시
    st.subheader(f"선택된 포지션: {position_details['pool_name']}")
    
    # 최근 채용 정보 로드
    latest_info = get_latest_recruitment_info(position_id)
    
    # 입력 폼
    with st.form("recruitment_form", clear_on_submit=False):
        # 채용공고 입력
        job_description = st.text_area(
            "채용공고",
            value=latest_info['job_description'],
            height=200,
            help="채용공고 전문을 입력하세요"
        )
        
        # 기타정보(녹음내용) 입력
        additional_info = st.text_area(
            "기타정보(녹음내용)",
            value=latest_info['additional_info'],
            height=150,
            help="인터뷰나 미팅에서 얻은 추가 정보를 입력하세요"
        )
        
        # 제출 버튼
        submitted = st.form_submit_button("저장 및 다음 단계로")
    
    if submitted:
        if not job_description:
            st.error("채용공고를 입력해주세요.")
            return
        
        try:
            # 채용 정보 DB 저장
            save_recruitment_info(
                position_id=position_id,
                job_description=job_description,
                additional_info=additional_info
            )
            
            # 입력 정보 세션 저장
            st.session_state.job_description = job_description
            st.session_state.additional_info = additional_info
            
            st.success("채용 정보가 저장되었습니다.")
            
            # 다음 단계로 이동
            st.session_state.current_page = "AI 필터링"
            st.rerun()
            
        except Exception as e:
            st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
            return
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 채용 정보 입력 페이지 사용법
        
        1. **채용공고**: 해당 포지션의 채용공고 전문을 입력합니다.
        2. **기타정보**: 미팅이나 인터뷰에서 얻은 추가 정보를 입력합니다.
        
        ### 주의사항
        - 모든 정보는 다음 단계인 AI 필터링에서 사용됩니다.
        """)
