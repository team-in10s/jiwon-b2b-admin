import streamlit as st
import pandas as pd
from src.utils.auth_helper import require_auth
from src.utils.database import (
    save_candidate_selection,
    get_latest_filtering_results
)

@require_auth
def show_candidate_selection_page():
    st.title("후보자 선택")
    
    if "selected_position_id" not in st.session_state:
        st.warning("먼저 포지션을 선택해주세요.")
        return
    
    if 'current_filtering_id' not in st.session_state:
        st.error("필터링 ID를 찾을 수 없습니다. AI 필터링을 먼저 실행해주세요.")
        return
    
    # AI 필터링 결과 확인
    if ('filtering_results' not in st.session_state or 
        st.session_state.get('last_executed_position_id') != st.session_state.selected_position_id):
        # 최신 필터링 결과 로드
        if 'current_filtering_id' in st.session_state:
            results = get_latest_filtering_results(
                st.session_state.selected_position_id, 
                st.session_state.current_filtering_id
            )
        else:
            results = get_latest_filtering_results(st.session_state.selected_position_id)
            
        if results.empty:
            st.warning("필터링 결과가 없습니다. AI 필터링을 먼저 실행해주세요.")
            return
            
        st.session_state.filtering_results = results
        st.session_state.last_executed_position_id = st.session_state.selected_position_id
    
    # 필터링 결과를 리스트로 변환
    candidates = st.session_state.filtering_results.to_dict('records')
    
    # 선택 상태 초기화
    if 'selection_state' not in st.session_state:
        st.session_state.selection_state = {
            str(row['saramin_key']): {'selected': False, 'fixed': False} for row in candidates
        }
    else:
        # 기존 세션 상태가 이전 포맷인 경우 새 포맷으로 변환
        updated_state = {}
        for key, value in st.session_state.selection_state.items():
            if isinstance(value, bool):
                updated_state[key] = {'selected': value, 'fixed': False}
            elif isinstance(value, dict):
                updated_state[key] = {
                    'selected': value.get('selected', False),
                    'fixed': value.get('fixed', False)
                }
            else:
                updated_state[key] = {'selected': False, 'fixed': False}
        st.session_state.selection_state = updated_state
        
        # 새로운 후보자에 대한 상태 추가
        for candidate in candidates:
            key = str(candidate['saramin_key'])
            if key not in st.session_state.selection_state:
                st.session_state.selection_state[key] = {'selected': False, 'fixed': False}
    
    # 후보자 목록 표시
    st.subheader(f"필터링된 후보자 목록 ({len(candidates)}명)")
    
    # 전체 선택/해제 체크박스
    col1, col2 = st.columns([1, 3])
    with col1:
        all_selected = st.checkbox("전체 선택/해제", key="all_select_toggle")
    
    # 전체 선택/해제 로직
    if all_selected:
        for key in st.session_state.selection_state:
            if not st.session_state.selection_state[key].get('fixed', False):
                st.session_state.selection_state[key]['selected'] = True
    else:
        for key in st.session_state.selection_state:
            if not st.session_state.selection_state[key].get('fixed', False):
                st.session_state.selection_state[key]['selected'] = False
    
    # 후보자 목록 표시
    for candidate in candidates:
        col1, col2, col3, col4 = st.columns([0.1, 0.1, 0.6, 0.2])
        
        with col1:
            # 개별 후보자 선택 체크박스
            selected = st.checkbox(
                "선택",
                key=f"select_{candidate['saramin_key']}",
                value=st.session_state.selection_state[str(candidate['saramin_key'])]['selected']
            )
            st.session_state.selection_state[str(candidate['saramin_key'])]['selected'] = selected
        
        with col2:
            # 고정 체크박스
            fixed = st.checkbox(
                "고정",
                key=f"fix_{candidate['saramin_key']}",
                value=st.session_state.selection_state[str(candidate['saramin_key'])]['fixed']
            )
            st.session_state.selection_state[str(candidate['saramin_key'])]['fixed'] = fixed
            
            # 고정 상태가 변경되면 선택 상태도 업데이트
            if fixed:
                st.session_state.selection_state[str(candidate['saramin_key'])]['selected'] = selected
            elif not selected:
                st.session_state.selection_state[str(candidate['saramin_key'])]['selected'] = False
        
        with col3:
            # 후보자 기본 정보
            name = candidate.get('name_extraction') or candidate.get('name') or '이름 없음'
            career_status = candidate.get('career_status', '경력 정보 없음')
            location = candidate.get('location', '정보 없음')
            work_year = candidate.get('regex_work_year', '정보 없음')
            
            st.write(f"**{name}** ({career_status})")
            st.write(f"경력: {work_year} | 지역: {location}")
            with st.expander("상세 정보"):
                # 상세 정보 섹션 추가
                if candidate.get('regex_brief_introduction'):
                    st.write("##### 자기소개")
                    st.write(candidate['regex_brief_introduction'])
                
                if candidate.get('regex_my_skills'):
                    st.write("##### 보유 기술")
                    st.write(candidate['regex_my_skills'])
                
                if candidate.get('regex_work_experience'):
                    st.write("##### 경력사항")
                    st.write(candidate['regex_work_experience'])
                
                if candidate.get('regex_career_technical_details'):
                    st.write("##### 기술 상세")
                    st.write(candidate['regex_career_technical_details'])
                
                if candidate.get('regex_academic_background'):
                    st.write("##### 학력사항")
                    st.write(candidate['regex_academic_background'])
                
                if candidate.get('regex_certificates_awards'):
                    st.write("##### 자격/수상")
                    st.write(candidate['regex_certificates_awards'])
                
                # 추가 정보 표시
                additional_info = []
                if candidate.get('additional_prefer'):
                    additional_info.append(f"선호사항: {candidate['additional_prefer']}")
                if candidate.get('additional_highlight'):
                    additional_info.append(f"주요특징: {candidate['additional_highlight']}")
                if candidate.get('additional_tag'):
                    additional_info.append(f"태그: {candidate['additional_tag']}")
                
                if additional_info:
                    st.write("##### 추가 정보")
                    for info in additional_info:
                        st.write(info)
                
                # 이력서 업데이트 정보
                if candidate.get('regex_resume_update_dt'):
                    st.write(f"이력서 업데이트: {candidate['regex_resume_update_dt']}")
                if candidate.get('regex_login_dt'):
                    st.write(f"최근 로그인: {candidate['regex_login_dt']}")
        
        with col4:
            # 사람인 페이지 링크
            if st.button("사람인 페이지", key=f"url_{candidate['saramin_key']}"):
                js = f"window.open('{candidate.get('page_url', '#')}', '_blank')"
                st.components.v1.html(f"<script>{js}</script>")
    
    # 선택 완료 버튼
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("선택 완료", use_container_width=True):
            # 선택된 후보자 목록 생성
            selected_candidates = [
                candidate for candidate in candidates
                if st.session_state.selection_state[str(candidate['saramin_key'])]['selected']
            ]
            
            if not selected_candidates:
                st.error("최소 1명 이상의 후보자를 선택해주세요.")
                return
            
            if 'current_filtering_id' not in st.session_state:
                st.error("필터링 ID를 찾을 수 없습니다. AI 필터링을 다시 실행해주세요.")
                return
            
            # 선택 결과 저장
            save_candidate_selection(
                st.session_state.current_filtering_id,
                selected_candidates
            )
            
            # 선택된 후보자 세션 저장
            st.session_state.selected_candidates = selected_candidates
            
            st.success(f"{len(selected_candidates)}명의 후보자가 선택되었습니다.")
            
            # 다음 단계로 이동
            st.session_state.current_page = "스카우트 메시지"
            st.rerun()
    
    with col1:
        selected_count = sum(1 for state in st.session_state.selection_state.values() if state['selected'])
        st.info(f"현재 {selected_count}명이 선택되었습니다.")
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 후보자 선택 페이지 사용법
        
        1. **후보자 목록**: AI 필터링을 통과한 후보자들이 표시됩니다.
        2. **선택 방법**: 
           - 개별 선택: 각 후보자 앞의 '선택' 체크박스를 선택
           - 전체 선택/해제: 상단의 '전체 선택/해제' 체크박스 사용
           - 고정: '고정' 체크박스를 선택하면 전체 선택/해제의 영향을 받지 않음
        3. **상세 정보**: 
           - 기본 정보는 바로 확인 가능
           - '상세 정보' 버튼을 클릭하여 추가 정보 확인
           - '사람인 페이지' 버튼으로 원본 이력서 확인
        
        ### 주의사항
        - 최소 1명 이상의 후보자를 선택해야 합니다.
        - 선택 완료 후에는 스카우트 메시지 작성 단계로 이동합니다.
        - 고정된 후보자는 전체 선택/해제의 영향을 받지 않습니다.
        - 고정되지 않은 상태에서 선택을 해제하면, 전체 선택 시에도 선택되지 않습니다.
        """)
