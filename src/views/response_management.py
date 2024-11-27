import streamlit as st
import pandas as pd
import asyncio
from src.utils.auth_helper import require_auth
from src.utils.database import (
    get_positions,
    get_position_details,
    update_position_url,
    get_position_candidates,
    update_candidate_status,
    update_candidate_contact,
    get_db_connection
)
from src.services.playwright_service import PlaywrightService
from playwright.async_api import async_playwright
from typing import List, Dict
from psycopg2.extras import RealDictCursor

playwright_service = PlaywrightService()

async def check_candidate_status(url: str, candidate: dict) -> str:
    """후보자의 응답 상태 확인 및 업데이트"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url)
            
            # 상태 확인 로직...
            status = await get_status_from_page(page)
            
            # 상태 매핑
            status_map = {
                "수락": "accepted",
                "거절": "rejected",
                "미응답": "no_response_rejected"
            }
            new_status = status_map.get(status.strip(), "no_response_rejected")
            
            # DB 상태 업데이트
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE scraping_saramin_position_candidate
                        SET scout_status = %s::scout_status,
                            last_checked_at = NOW()
                        WHERE id = %s
                    """, (new_status, candidate['mapping_id']))
                    conn.commit()
            
            return new_status
            
    except Exception as e:
        st.error(f"상태 확인 중 오류 발생: {str(e)}")
        return "no_response_rejected"

async def collect_contact_info(page_url: str) -> dict:
    """수락한 후보자의 연락처 정보 수집"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(page_url)
            
            # 연락처 정보 추출
            name = await page.locator(".candidate_name").text_content()
            contact = await page.locator(".contact_info").text_content()
            
            await browser.close()
            
            return {
                "name": name.strip(),
                "contact": contact.strip()
            }
            
    except Exception as e:
        st.error(f"연락처 수집 중 오류 발생: {str(e)}")
        return None

async def update_candidate_statuses(position_details: dict, candidates: list):
    """모든 후보자의 상태 업데이트"""
    total = len(candidates)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, candidate in enumerate(candidates, 1):
        progress = idx / total
        progress_bar.progress(progress)
        status_text.text(f"진행 중... ({idx}/{total})")
        
        try:
            # 상태 확인
            status = await check_candidate_status(
                position_details['scout_url'],
                candidate
            )
            
            # 상태 업데이트
            update_candidate_status(
                candidate['mapping_id'],
                status
            )
            
            # 수락한 경우 추가 정보 수집
            if status == 'accepted':
                contact_info = await collect_contact_info(
                    candidate['page_url']
                )
                if contact_info:
                    update_candidate_contact(
                        candidate['saramin_key'],
                        contact_info['name'],
                        contact_info['contact']
                    )
        
        except Exception as e:
            st.error(f"오류 발생 ({candidate['name']}): {str(e)}")
    
    return True

@require_auth
def show_response_page():
    st.title("스카우트 응답 관리")
    
    # 포지션 선택
    positions = get_positions()
    position_options = {
        f"{p['pool_name']} ({p['company_name']})": p['id'] 
        for p in positions
    }
    
    selected_position_name = st.selectbox(
        "포지션 선택",
        options=list(position_options.keys())
    )
    
    if selected_position_name:
        position_id = position_options[selected_position_name]
        position_details = get_position_details(position_id)
        
        # 현재 상태 표시를 여기로 이동
        show_current_status(position_id)
        
        # 자동/수동 탭 선택
        tab1, tab2 = st.tabs(["자동 업데이트", "수동 업데이트"])
        
        with tab1:
            show_auto_update_ui(position_id, position_details)
        
        with tab2:
            show_manual_update_ui(position_id)

def show_auto_update_ui(position_id: int, position_details: dict):
    """자동 업데이트 UI"""
    st.write("### 자동 상태 업데이트")
    
    # URL 입력/수정
    col1, col2 = st.columns([3, 1])
    with col1:
        current_url = position_details.get('scout_url', '')
        new_url = st.text_input(
            "스카우트 응답 확인 URL",
            value=current_url,
            placeholder="URL이 없는 경우 입력해주세요"
        )
    
    with col2:
        if new_url and new_url != current_url:
            if st.button("URL 저장", use_container_width=True):
                update_position_url(position_id, new_url)
                st.success("URL이 저장되었습니다.")
                st.rerun()
    
    # 상태 업데이트 시작
    if st.button("응답 상태 업데이트", use_container_width=True):
        if not position_details.get('scout_url'):
            st.error("먼저 URL을 입력해주세요.")
            return
        
        with st.spinner("응답 상태를 확인하고 있습니다..."):
            # 후보자 목록 조회
            candidates = get_position_candidates(position_id)
            
            # 비동기 업데이트 실행
            asyncio.run(update_candidate_statuses(position_details, candidates))
            
            st.success("상태 업데이트가 완료되었습니다.")

def show_manual_update_ui(position_id: int):
    """수동 업데이트 UI"""
    st.write("### 수동 상태 업데이트")
    
    # sent 상태인 후보자만 조회
    candidates = get_sent_candidates(position_id)
    
    if not candidates:
        st.info("발송된 후보자가 없습니다.")
        return
    
    for candidate in candidates:
        with st.container():
            # 기본 정보 표시
            col1, col2, col3 = st.columns([2.5, 0.5, 1])
            with col1:
                name = candidate.get('name_extraction') or candidate.get('name') or '이름 없음'
                st.write(f"**{name}** ({candidate.get('career_status', '경력 정보 없음')})")
                st.write(f"경력: {candidate.get('regex_work_year', '정보 없음')} | 지역: {candidate.get('location', '정보 없음')}")
                st.write(f"현재 상태: **{candidate['scout_status']}**")
                
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
                new_status = st.selectbox(
                    "상태 변경",
                    options=['sent', 'accepted', 'rejected', 'no_response_rejected'],
                    key=f"status_{candidate['mapping_id']}",
                    index=0
                )
                
                if st.button("상태 업데이트", key=f"update_{candidate['mapping_id']}"):
                    try:
                        update_candidate_status(candidate['mapping_id'], new_status)
                        
                        # 수락한 경우 연락처 정보 수집
                        if new_status == 'accepted':
                            contact_info = {
                                'name': st.text_input("이름", key=f"name_{candidate['mapping_id']}"),
                                'contact': st.text_input("연락처", key=f"contact_{candidate['mapping_id']}")
                            }
                            if contact_info['name'] and contact_info['contact']:
                                update_candidate_contact(
                                    candidate['saramin_key'],
                                    contact_info['name'],
                                    contact_info['contact']
                                )
                        
                        st.success("상태가 업데이트되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"업데이트 실패: {str(e)}")
            
            st.markdown("---")

def get_sent_candidates(position_id: int) -> List[Dict]:
    """발송된 후보자 목록 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    c.*,
                    pc.id as mapping_id,
                    pc.scout_status,
                    pc.last_checked_at
                FROM scraping_saramin_candidates c
                INNER JOIN scraping_saramin_position_candidate pc 
                    ON c.saramin_key = pc.saramin_key
                WHERE pc.position_id = %s
                AND pc.scout_status = 'sent'
                ORDER BY pc.last_checked_at DESC
            """, (position_id,))
            return cur.fetchall()

def show_current_status(position_id):
    """현재 응답 상태 표시"""
    candidates = get_position_candidates(position_id)
    
    if not candidates:
        st.info("매핑된 후보자가 없습니다.")
        return
    
    # 상태별 통계
    df = pd.DataFrame(candidates)
    status_counts = df['scout_status'].value_counts()
    
    # 2행 3열로 통계 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("전체 추출", len(candidates))
    with col2:
        st.metric("발송 완료", status_counts.get('sent', 0))
    with col3:
        st.metric("미발송", len(candidates) - status_counts.get('sent', 0))
    
    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("수락", status_counts.get('accepted', 0))
    with col5:
        st.metric("거절", status_counts.get('rejected', 0))
    with col6:
        st.metric("무응답", status_counts.get('no_response_rejected', 0))
    
    # 후보자 목록 표시
    st.subheader("후보자 목록")
    df = pd.DataFrame(candidates)
    
    # 필요한 컬럼이 없다면 기본값으로 생성
    if 'work_year' not in df.columns:
        df['work_year'] = None
    if 'last_checked_at' not in df.columns:
        df['last_checked_at'] = None
    
    st.dataframe(
        df[[
            'name', 'career_status', 'work_year',
            'location', 'scout_status', 'last_checked_at'
        ]],
        use_container_width=True,
        column_config={
            'name': '이름',
            'career_status': '경력',
            'work_year': '경력 연차',
            'location': '지역',
            'scout_status': '응답 상태',
            'last_checked_at': '마지막 확인'
        }
    )
    
    # DataFrame 정보를 expander 안에 표시
    with st.expander("DataFrame 정보"):
        st.write("Available columns:", df.columns.tolist())
        
        # 존재하는 컬럼만 선택
        available_columns = [col for col in ['work_year', 'last_checked_at'] if col in df.columns]
        if available_columns:
            df[available_columns]
    
    # 도움말
    with st.expander("도움말"):
        st.markdown("""
        ### 응답 관리 페이지 사용법
        
        1. **포지션 선택**: 응답을 확인할 포지션을 선택합니다.
        
        2. **URL 관리**:
           - 처음 실행 시 스카우트 응답 확인 URL 입력
           - URL은 포지션별로 저장됨
        
        3. **상태 업데이트**:
           - '응답 상태 업데이트' 버튼으로 자동 확인
           - 수락한 후보자는 연락처 정보도 자동 수집
        
        4. **상태 확인**:
           - 전체 현황을 한눈에 파악
           - 후보자별 상세 상태 확인 가능
        
        ### 주의사항
        - URL 입력이 필요한 경우 먼저 입력해주세요.
        - 상태 업데이트는 시간이 걸릴 수 있습니다.
        - 수락한 후보자의 연락처는 자동으로 수집됩니다.
        """)
