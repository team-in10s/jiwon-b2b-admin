import streamlit as st
import pandas as pd
from datetime import datetime
from src.utils.auth_helper import require_auth
from src.utils.database import (
    get_positions, 
    get_position_details,
    get_latest_recruitment_info
)

@require_auth
def show_position_page():
    st.title("포지션 선택")
    
    # 세션 상태 초기화
    if "selected_position_id" not in st.session_state:
        st.session_state.selected_position_id = None
    
    # 포지션 목록 조회
    positions = get_positions()
    
    if not positions:
        st.info("등록된 포지션이 없습니다.")
        return
    
    # 데이터프레임 생성
    df = pd.DataFrame(positions)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    
    # 포지션 목록 표시
    st.subheader("포지션 목록")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("포지션 ID", width="small"),
            "pool_name": "포지션명",
            "company_name": "회사명",
            "candidate_count": st.column_config.NumberColumn("후보자 수", width="small"),
            "created_at": "생성일",
            "demand": st.column_config.TextColumn(
                "차수",  # 요구사항 -> 차수로 변경
                width="small",
                help="채용 차수"  # 도움말도 수정
            )
        },
        hide_index=True
    )
    
    # 포지션 선택
    st.subheader("포지션 선택")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 선택 옵션 생성
        position_options = {
            f"{p['pool_name']} ({p['company_name']}) - {p['demand']}":  # 차수 표시 추가
            str(p['id'])
            for p in positions
        }
        
        selected_position_name = st.selectbox(
            "작업할 포지션을 선택하세요",
            options=list(position_options.keys()),
            help="포지션 목록에서 작업할 포지션을 선택해주세요."
        )
    
    if selected_position_name:
        position_id = int(position_options[selected_position_name])
        st.session_state.selected_position_id = position_id
        
        # 선택된 포지션 상세 정보 표시
        position_details = get_position_details(position_id)
        latest_info = get_latest_recruitment_info(position_id)  # 최근 채용 정보 로드
        
        if position_details:
            st.divider()
            st.subheader("선택된 포지션 정보")
            
            # 기본 정보 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("포지션명", position_details["pool_name"])
            with col2:
                st.metric("회사명", position_details["company_name"])
            with col3:
                st.metric("매핑된 후보자 수", position_details.get("mapped_candidates", 0))
            
            # 차수 표시
            st.metric("채용 차수", f"{position_details.get('demand', '1')}")
            
            # 채용 정보 표시
            if latest_info:
                st.text_area(
                    "채용공고",
                    value=latest_info['job_description'],
                    disabled=True,
                    height=200
                )
                
                st.text_area(
                    "기타정보(녹음내용)",
                    value=latest_info['additional_info'],
                    disabled=True,
                    height=150
                )
            
            # 다음 단계 버튼
            st.divider()
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("채용 정보 입력으로 이동", use_container_width=True):
                    st.session_state.current_page = "채용 정보 입력"
                    st.rerun()
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 포지션 선택 페이지 사용법
        
        1. **포지션 목록 확인**
           - 상단의 테이블에서 모든 포지션 정보를 확인할 수 있습니다.
           - 각 열을 클릭하여 정렬이 가능합니다.
           - 차수는 해당 포지션의 채용 차수를 나타냅니다.
        
        2. **포지션 선택 방법**
           - 드롭다운 메뉴에서 작업할 포지션을 선택합니다.
           - 포지션명, 회사명, 차수가 함께 표시되어 쉽게 구분할 수 있습니다.
        
        3. **선택된 포지션 정보**
           - 선택 시 해당 포지션의 상세 정보가 표시됩니다.
           - 매핑된 후보자 수를 통해 현재 상태를 확인할 수 있습니다.
           - 이전에 입력된 채용공고와 기타정보를 확인할 수 있습니다.
        
        4. **다음 단계**
           - 포지션 선택 후 '채용 정보 입력으로 이동' 버튼을 클릭하여 진행���니다.
           - 선택된 포지션 정보는 다음 단계에서 계속 사용됩니다.
        
        ### 주의사항
        - 한 번에 하나의 포지션만 선택할 수 있습니다.
        - 선택된 포지션은 전체 프로세스에서 사용되므로 신중히 선택해주세요.
        - 작업 중간에 포지션을 변경하면 이전 작업 내용이 초기화될 수 있습니다.
        """)
