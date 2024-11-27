import streamlit as st
import asyncio
import random
from src.utils.auth_helper import require_auth
from src.utils.database import (
    get_db_connection,
    save_scout_history
)
from psycopg2.extras import RealDictCursor
import time

class PlaywrightService:
    def __init__(self):
        self.progress_callback = None
        self.error_callback = None
        self.failed_candidates = []  # 실패한 후보자 목록

    async def send_scout_message(self, candidate: dict, message: dict) -> bool:
        """단일 후보자에게 스카우트 메시지 발송 (가상)"""
        try:
            # 랜덤하게 성공/실패 결정 (80% 성공률)
            success = random.random() > 0.2
            
            if success:
                # 발송 성공 시 상태 업데이트
                with get_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # position_candidate 테이블에서 mapping_id 조회
                        cur.execute("""
                            SELECT id as mapping_id
                            FROM scraping_saramin_position_candidate
                            WHERE position_id = %s AND saramin_key = %s
                        """, (st.session_state.selected_position_id, candidate['saramin_key']))
                        
                        result = cur.fetchone()
                        if not result:
                            raise Exception("Mapping not found")
                        
                        mapping_id = result['mapping_id']
                        
                        # 상태 업데이트
                        cur.execute("""
                            UPDATE scraping_saramin_position_candidate
                            SET scout_status = 'sent',
                                last_checked_at = NOW()
                            WHERE id = %s
                        """, (mapping_id,))
                        
                        # scout_history에 기록 추가
                        cur.execute("""
                            INSERT INTO scout_history 
                            (candidate_filter_id, message_id, status)
                            VALUES (%s, %s, 'sent')
                        """, (mapping_id, message['id']))
                        
                        conn.commit()
                
                await asyncio.sleep(0.5)  # 가상의 딜레이
                return True
            else:
                if self.error_callback:
                    self.error_callback(f"발송 실패 ({candidate.get('name_extraction') or candidate.get('name') or '이름 없음'}): 랜덤 실패")
                self.failed_candidates.append(candidate)
                await asyncio.sleep(0.5)  # 가상의 딜레이
                return False
                
        except Exception as e:
            if self.error_callback:
                self.error_callback(f"발송 실패 ({candidate.get('name_extraction') or candidate.get('name') or '이름 없음'}): {str(e)}")
            self.failed_candidates.append(candidate)
            return False

    async def process_candidates(self, candidates: list, message: dict):
        """모든 후보자에게 순차적으로 메시지 발송"""
        total = len(candidates)
        success_count = 0
        self.failed_candidates = []  # 실패 목록 초기화
        
        for idx, candidate in enumerate(candidates, 1):
            if self.progress_callback:
                self.progress_callback(idx, total)
            
            success = await self.send_scout_message(candidate, message)
            if success:
                success_count += 1
            
            await asyncio.sleep(0.2)  # 서버 부하 방지
        
        return success_count

playwright_service = PlaywrightService()

@require_auth
def show_auto_scout_page():
    st.title("스카우트 자동 발송")
    
    # 필요한 세션 데이터 확인
    required_sessions = [
        "selected_candidates",
        "scout_message"
    ]
    
    if not all(key in st.session_state for key in required_sessions):
        st.warning("먼저 스카우트 메시지를 작성해주세요.")
        return
    
    # 발송 대상 필터링 (sent가 아닌 후보자만)
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            candidates_to_send = []
            for candidate in st.session_state.selected_candidates:
                cur.execute("""
                    SELECT c.*, pc.scout_status
                    FROM scraping_saramin_candidates c
                    JOIN scraping_saramin_position_candidate pc 
                        ON c.saramin_key = pc.saramin_key
                    WHERE pc.position_id = %s 
                    AND c.saramin_key = %s
                """, (st.session_state.selected_position_id, candidate['saramin_key']))
                result = cur.fetchone()
                if result and result['scout_status'] != 'sent':
                    candidates_to_send.append(result)  # 전체 정보를 포함한 결과 사용
    
    if not candidates_to_send:
        st.info("모든 후보자에게 이미 발송되었습니다.")
        if st.button("응답 관리로 이동", use_container_width=True):
            st.session_state.current_page = "응답 관리"
            st.rerun()
        return
    
    message = st.session_state.scout_message
    
    # 발송 전 정보 확인
    st.info(f"발송 대상: {len(candidates_to_send)}명의 후보자")
    
    # 메시지 내용 표시
    with st.expander("메시지 내용 확인", expanded=True):
        # 제목 섹션
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(message['title'])
        with col2:
            if st.button("제목 복사", key="copy_title"):
                js = f"navigator.clipboard.writeText(`{message['title']}`)"
                st.components.v1.html(f"<script>{js}</script>")
                st.success("제목이 복사되었습니다!", icon="✂️")
        
        st.write("---")
        
        # 본문 섹션
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(message['content'])
        with col2:
            if st.button("본문 복사", key="copy_content"):
                js = f"navigator.clipboard.writeText(`{message['content']}`)"
                st.components.v1.html(f"<script>{js}</script>")
                st.success("본문이 복사되었습니다!", icon="✂️")
        
        st.caption(f"유효기간: ~ {message['valid_until']}")
    
    # 자동/수동 탭 선택
    tab1, tab2 = st.tabs(["자동 발송", "수동 발송"])
    
    with tab1:
        show_auto_send_ui(candidates_to_send, message)
    
    with tab2:
        show_manual_send_ui(candidates_to_send, message)

def show_auto_send_ui(candidates: list, message: dict):
    """자동 발송 UI"""
    if "sending" not in st.session_state:
        st.session_state.sending = False
        st.session_state.progress = 0
        st.session_state.success_count = 0
        st.session_state.failed_candidates = []
    
    if not st.session_state.sending:
        if st.button("자동 발송 시작", use_container_width=True):
            st.session_state.sending = True
            st.session_state.progress = 0
            st.session_state.success_count = 0
            st.session_state.failed_candidates = []
            st.rerun()
    
    if st.session_state.sending:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 진행 상황 업데이트 콜백
        def update_progress(current, total):
            progress = current / total
            progress_bar.progress(progress)
            status_text.text(f"진행 중... ({current}/{total})")
            st.session_state.progress = progress
        
        # 에러 콜백
        def on_error(error_message):
            st.error(error_message)
        
        playwright_service = PlaywrightService()
        playwright_service.progress_callback = update_progress
        playwright_service.error_callback = on_error
        
        if st.session_state.progress == 0:  # 아직 시작하지 않은 경우
            total = len(candidates)
            success_count = 0
            
            for idx, candidate in enumerate(candidates, 1):
                update_progress(idx, total)
                
                # 가상의 발송 로직
                success = random.random() > 0.2  # 80% 성공률
                
                if success:
                    try:
                        with get_db_connection() as conn:
                            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                                # mapping_id 조회
                                cur.execute("""
                                    SELECT id as mapping_id
                                    FROM scraping_saramin_position_candidate
                                    WHERE position_id = %s AND saramin_key = %s
                                """, (st.session_state.selected_position_id, candidate['saramin_key']))
                                
                                result = cur.fetchone()
                                if not result:
                                    raise Exception("Mapping not found")
                                
                                mapping_id = result['mapping_id']
                                
                                # 상태 업데이트
                                cur.execute("""
                                    UPDATE scraping_saramin_position_candidate
                                    SET scout_status = 'sent',
                                        last_checked_at = NOW()
                                    WHERE id = %s
                                """, (mapping_id,))
                                
                                # scout_history에 기록 추가
                                cur.execute("""
                                    INSERT INTO scout_history 
                                    (candidate_filter_id, message_id, status)
                                    VALUES (%s, %s, 'sent')
                                """, (mapping_id, message['id']))
                                
                                conn.commit()
                        success_count += 1
                    except Exception as e:
                        on_error(f"DB 업데이트 실패: {str(e)}")
                        st.session_state.failed_candidates.append(candidate)
                else:
                    st.session_state.failed_candidates.append(candidate)
                
                time.sleep(0.5)  # 가상의 딜레이
            
            st.session_state.success_count = success_count
            st.session_state.progress = 1.0
            progress_bar.progress(1.0)
            
            # 결과 표시
            st.success(f"발송 완료! {success_count}/{total} 성공")
            
            if st.session_state.failed_candidates:
                st.warning(f"{len(st.session_state.failed_candidates)}명의 후보자에게 발송 실패")
                if st.button("실패한 후보자 재시도", use_container_width=True):
                    st.session_state.progress = 0
                    st.rerun()
            
            if st.button("응답 관리로 이동", use_container_width=True):
                st.session_state.current_page = "응답 관리"
                st.session_state.sending = False
                st.rerun()
            
            if st.button("발송 종료", use_container_width=True):
                st.session_state.sending = False
                st.rerun()

def show_manual_send_ui(candidates: list, message: dict):
    """수동 발송 UI"""
    st.write("### 수동 발송")
    st.write("각 후보자별로 발송 여부를 직접 선택할 수 있습니다.")
    
    for candidate in candidates:
        with st.container():
            # 기본 정보 표시
            col1, col2, col3 = st.columns([2.5, 0.5, 1])
            with col1:
                name = candidate.get('name_extraction') or candidate.get('name') or '이름 없음'
                st.write(f"**{name}** ({candidate.get('career_status', '경력 정보 없음')})")
                st.write(f"경력: {candidate.get('regex_work_year', '정보 없음')} | 지역: {candidate.get('location', '정보 없음')}")
                
                # 상세 정보 expander
                with st.expander("상세 정보"):
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
            
            with col2:
                # 사람인 페이지 링크
                if st.button("사람인 페이지", key=f"url_{candidate['saramin_key']}"):
                    js = f"window.open('{candidate.get('page_url', '#')}', '_blank')"
                    st.components.v1.html(f"<script>{js}</script>")
            
            with col3:
                if st.button("발송 완료", key=f"manual_send_{candidate['saramin_key']}"):
                    try:
                        with get_db_connection() as conn:
                            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                                # mapping_id 조회
                                cur.execute("""
                                    SELECT id as mapping_id
                                    FROM scraping_saramin_position_candidate
                                    WHERE position_id = %s AND saramin_key = %s
                                """, (st.session_state.selected_position_id, candidate['saramin_key']))
                                
                                result = cur.fetchone()
                                if not result:
                                    raise Exception("Mapping not found")
                                
                                mapping_id = result['mapping_id']
                                
                                # 상태 업데이트
                                cur.execute("""
                                    UPDATE scraping_saramin_position_candidate
                                    SET scout_status = 'sent',
                                        last_checked_at = NOW()
                                    WHERE id = %s
                                """, (mapping_id,))
                                
                                # scout_history에 기록 추가
                                cur.execute("""
                                    INSERT INTO scout_history 
                                    (candidate_filter_id, message_id, status)
                                    VALUES (%s, %s, 'sent')
                                """, (mapping_id, message['id']))
                                
                                conn.commit()
                                
                        st.success(f"{name}님에게 발송 완료")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"발송 실패: {str(e)}")
            
            st.markdown("---")
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 자동 발송 프로세스
        
        1. **발송 준비**:
           - 선택된 후보자와 메시지 내용을 확인
           - '발송 시작' 버튼을 클릭하여 프로세스 시작
        
        2. **자동화 발송**:
           - 각 후보자에게 자동으로 메시지 발송
           - 실시간 진행 상황 모니터링
           - 실패한 경우 재시도 가능
        
        3. **결과 확인**:
           - 전체 발송 결과 요약
           - 실패한 경우 오류 메시지 확인
        
        ### 주의사항
        - 발송이 시작되면 중료될 때까지 기다려주세요.
        - 실패한 후보자가 있는 경우 재시도할 수 있습니다.
        - 모든 발송이 완료되면 응답 관리 페이지로 이동할 수 있습니다.
        """)
