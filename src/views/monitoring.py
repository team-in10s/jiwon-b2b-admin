import streamlit as st
from src.utils.auth_helper import require_auth
from src.utils.database import get_pending_tasks_count, get_recent_tasks
import time

@require_auth
def show_monitoring_page():
    st.title("스크래핑 작업 모니터링")
    
    # 자동 새로고침 간격 설정
    if "refresh_interval" not in st.session_state:
        st.session_state.refresh_interval = 5  # 기본값 5초
    
    # 레이아웃 구성
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.session_state.refresh_interval = st.slider(
            "새로고침 간격 (초)", 
            min_value=1, 
            max_value=30, 
            value=st.session_state.refresh_interval
        )
        
        if st.button("수동 새로고침", use_container_width=True):
            st.rerun()
    
    with col1:
        # 남은 작업 수 표시
        pending_count = get_pending_tasks_count()
        st.metric(
            label="남은 작업 수", 
            value=pending_count,
            delta=-1 if pending_count > 0 else None
        )
        
        # 진행률 표시
        if "initial_count" not in st.session_state:
            st.session_state.initial_count = pending_count
        
        if st.session_state.initial_count > 0:
            progress = 1 - (pending_count / st.session_state.initial_count)
            st.progress(progress)
            st.text(f"진행률: {progress*100:.1f}%")
    
    # 최근 작업 목록
    st.subheader("최근 작업 목록")
    recent_tasks = get_recent_tasks()
    if recent_tasks:
        task_df = pd.DataFrame(recent_tasks)
        st.dataframe(
            task_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("현재 진행 중인 작업이 없습니다.")
    
    # 자동 새로고침
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 모니터링 페이지 사용법
        
        1. **남은 작업 수**: temp_scraping_1 테이블에 남아있는 작업의 수를 표시합니다.
        2. **진행률**: 전체 작업 대비 완료된 작업의 비율을 표시합니다.
        3. **최근 작업 목록**: 가장 최근에 추가된 작업들을 보여줍니다.
        
        ### 새로고침 설정
        - 슬라이더를 사용하여 자동 새로고침 간격을 조정할 수 있습니다.
        - '수동 새로고침' 버튼을 클릭하여 즉시 데이터를 갱신할 수 있습니다.
        """)
