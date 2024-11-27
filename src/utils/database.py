import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import streamlit as st
from typing import List, Dict, Optional
import json
import pandas as pd
from datetime import datetime

@contextmanager
def get_db_connection():
    """데이터베이스 연결 컨텍스트 매니저"""
    conn = None
    try:
        conn = psycopg2.connect(st.secrets["DATABASE_URL"])
        yield conn
    finally:
        if conn is not None:
            conn.close()

def get_pending_tasks_count():
    """temp_scraping_1 테이블의 남은 작업 수 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as count FROM temp_scraping_1")
            result = cur.fetchone()
            return result['count']

def get_recent_tasks(limit=10):
    """최근 작업 목록 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM temp_scraping_1 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

def get_positions(search_term=None):
    """포지션 목록 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT 
                    id,
                    pool_name,
                    company_name,
                    candidate_count,
                    created_at,
                    demand
                FROM scraping_saramin_position
                WHERE 1=1
            """
            params = []
            
            if search_term:
                query += """ 
                    AND (
                        pool_name ILIKE %s 
                        OR company_name ILIKE %s
                        OR demand ILIKE %s
                    )
                """
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern] * 3)
            
            query += " ORDER BY created_at DESC"
            
            cur.execute(query, params)
            return cur.fetchall()

def get_position_details(position_id):
    """포지션 상세 정보 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, 
                    COUNT(pc.id) as mapped_candidates
                FROM scraping_saramin_position p
                LEFT JOIN scraping_saramin_position_candidate pc 
                    ON p.id = pc.position_id
                WHERE p.id = %s
                GROUP BY p.id
            """, (int(position_id),))
            return cur.fetchone()

def get_latest_prompt(position_id):
    """최신 프롬프트 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM prompt_history
                WHERE position_id = %s AND is_active = true
                ORDER BY created_at DESC
                LIMIT 1
            """, (position_id,))
            return cur.fetchone()

def save_prompt(position_id, prompt_text, created_by):
    """새로운 프롬프트 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO prompt_history 
                (position_id, prompt_text, created_by)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (position_id, prompt_text, created_by))
            conn.commit()
            return cur.fetchone()['id']

def filter_candidates(position_id: int, where_clause: str) -> List[Dict]:
    """후보자 필터링 실행"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1차 필터링: 포지션 기반
                base_query = """
                WITH position_candidates AS (
                    SELECT DISTINCT c.*
                    FROM scraping_saramin_candidates c
                    JOIN scraping_saramin_position_candidate pc 
                    ON c.saramin_key = pc.saramin_key
                    WHERE pc.position_id = %s
                ),
                filtered_candidates AS (
                    SELECT *,
                        CASE 
                            WHEN career_status = '경력' THEN 1
                            ELSE 2
                        END as career_priority
                    FROM position_candidates
                    WHERE {where_clause}
                )
                SELECT *
                FROM filtered_candidates
                ORDER BY 
                    career_priority ASC,
                    last_login DESC
                LIMIT 20
                """
                
                final_query = base_query.format(where_clause=where_clause)
                cur.execute(final_query, (position_id,))
                return cur.fetchall()
                
    except Exception as e:
        st.error(f"필터링 중 오류 발생: {str(e)}")
        return []

def save_filtering_history(position_id: int, job_description: str, step: str, result: dict) -> int:
    """필터링 히스토리 생성 및 초기 단계 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 필터링 히스토리 생성
            cur.execute("""
                INSERT INTO filtering_history 
                (position_id, job_description, status)
                VALUES (%s, %s, 'in_progress')
                RETURNING id
            """, (position_id, job_description))
            
            filtering_id = cur.fetchone()['id']
            
            # 첫 번째 중간 결과 저장
            cur.execute("""
                INSERT INTO filtering_intermediate_results
                (filtering_id, step_number, step_name, result_data)
                VALUES (%s, 1, %s, %s)
            """, (filtering_id, step, json.dumps(result)))
            
            conn.commit()
            return filtering_id

def save_filtering_intermediate(filtering_id: int, step: str, result: dict):
    """중간 결과 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 현재 단계 번호 조회
            cur.execute("""
                SELECT COALESCE(MAX(step_number), 0) + 1 as next_step
                FROM filtering_intermediate_results
                WHERE filtering_id = %s
            """, (filtering_id,))
            next_step = cur.fetchone()['next_step']
            
            # 중간 결과 저장 - JSONB 타입으로 직접 저장
            cur.execute("""
                INSERT INTO filtering_intermediate_results
                (filtering_id, step_number, step_name, result_data)
                VALUES (%s, %s, %s, %s::jsonb)
            """, (filtering_id, next_step, step, json.dumps(result)))
            
            conn.commit()

def get_latest_filtering(position_id: int) -> dict:
    """최근 필터링 결과 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    h.*,
                    r.step_name,
                    r.result_data
                FROM filtering_history h
                LEFT JOIN filtering_intermediate_results r 
                    ON h.id = r.filtering_id
                WHERE h.position_id = %s
                ORDER BY h.created_at DESC, r.step_number DESC
                LIMIT 1
            """, (position_id,))
            return cur.fetchone()

def update_filtering_results(filtering_id: int, status: str, filtered_count: int):
    """필터링 결과 업데이트"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE filtering_history
                SET 
                    status = %s,
                    filtered_count = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (status, filtered_count, filtering_id))
            conn.commit()

def get_filtering_history(position_id: int, limit: int = 5) -> list:
    """필터링 히스토리 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    h.id,
                    h.created_at,
                    h.status,
                    jsonb_agg(
                        jsonb_build_object(
                            'step_name', r.step_name,
                            'result_data', r.result_data
                        ) ORDER BY r.step_number
                    ) as steps
                FROM filtering_history h
                LEFT JOIN filtering_intermediate_results r 
                    ON h.id = r.filtering_id
                WHERE h.position_id = %s
                GROUP BY h.id, h.created_at, h.status
                ORDER BY h.created_at DESC
                LIMIT %s
            """, (position_id, limit))
            return cur.fetchall()

def get_intermediate_result(filtering_id: int, step: str) -> dict:
    """특정 단계의 중간 결과 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT result_data
                FROM filtering_intermediate_results
                WHERE filtering_id = %s AND step_name = %s
                ORDER BY step_number DESC
                LIMIT 1
            """, (filtering_id, step))
            result = cur.fetchone()
            return json.loads(result['result_data']) if result else None

def save_candidate_selection(filtering_id: int, selected_candidates: list):
    """선택된 후보자 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 필터링 ID로 position_id 조회
            cur.execute("""
                SELECT position_id 
                FROM filtering_history 
                WHERE id = %s
            """, (filtering_id,))
            result = cur.fetchone()
            if not result:
                raise Exception("Invalid filtering_id")
            position_id = result['position_id']
            
            # 선택된 후보자들의 상태를 'extracted'로 유지
            for candidate in selected_candidates:
                cur.execute("""
                    INSERT INTO scraping_saramin_position_candidate 
                    (position_id, saramin_key, scout_status)
                    VALUES (%s, %s, 'extracted')
                    ON CONFLICT (position_id, saramin_key) 
                    DO UPDATE SET 
                        scout_status = 'extracted',
                        last_checked_at = NOW()
                """, (position_id, candidate['saramin_key']))
            
            # 선택되지 않은 후보자들은 제거 (선택사항)
            cur.execute("""
                DELETE FROM scraping_saramin_position_candidate
                WHERE position_id = %s
                AND saramin_key NOT IN %s
            """, (position_id, tuple(c['saramin_key'] for c in selected_candidates)))
            
            conn.commit()

def get_candidate_details(saramin_key: str):
    """후보자 상세 정보 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM scraping_saramin_candidates
                WHERE saramin_key = %s
            """, (saramin_key,))
            return cur.fetchone()

def save_scout_message(position_id: int, title: str, content: str, valid_until: str):
    """스카우트 메시지 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO scout_message 
                (position_id, title, content, valid_until)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (position_id, title, content, valid_until))
            conn.commit()
            return cur.fetchone()['id']

def get_latest_scout_message(position_id: int):
    """최근 스카우트 메시지 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM scout_message
                WHERE position_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (position_id,))
            return cur.fetchone()

def save_scout_history(candidate_filter_id: int, message_id: int, status: str = 'sent'):
    """스카우트 발송 이력 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO scout_history 
                (candidate_filter_id, message_id, status)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (candidate_filter_id, message_id, status))
            conn.commit()
            return cur.fetchone()['id']

def update_position_url(position_id: int, url: str):
    """포지션 URL 업데이트"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE scraping_saramin_position
                SET scout_url = %s
                WHERE id = %s
            """, (url, position_id))
            conn.commit()

def get_position_candidates(position_id: int):
    """포지션에 매핑된 후보자 목록 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    c.*,
                    pc.id as mapping_id,
                    pc.scout_status
                FROM scraping_saramin_candidates c
                INNER JOIN scraping_saramin_position_candidate pc 
                    ON c.saramin_key = pc.saramin_key
                WHERE pc.position_id = %s
            """, (position_id,))
            return cur.fetchall()

def update_candidate_status(mapping_id: int, status: str):
    """후보자 상태 업데이트"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE scraping_saramin_position_candidate
                SET scout_status = %s,
                    last_checked_at = NOW()
                WHERE id = %s
            """, (status, mapping_id))
            conn.commit()

def update_candidate_contact(saramin_key: str, name: str, contact: str):
    """수락한 후보자의 연락처 정보 업데이트"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE scraping_saramin_candidates
                SET name = %s,
                    contact_info = %s,
                    update_dt = NOW()
                WHERE saramin_key = %s
            """, (name, contact, saramin_key))
            conn.commit()

def get_latest_recruitment_info(position_id):
    """최근 채용 정보 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    job_description,
                    additional_info
                FROM filtering_history
                WHERE position_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (position_id,))
            result = cur.fetchone()
            return {
                'job_description': result['job_description'] if result else "",
                'additional_info': result['additional_info'] if result else ""
            }

def save_recruitment_info(position_id: int, job_description: str, additional_info: str):
    """채용 정보 저장"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO filtering_history 
                (position_id, job_description, additional_info)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (position_id, job_description, additional_info))
            conn.commit()
            return cur.fetchone()['id']

def execute_query(query: str) -> pd.DataFrame:
    """SQL 쿼리 실행"""
    with get_db_connection() as conn:
        return pd.read_sql(query, conn)

def get_latest_prompts(position_id: int) -> dict:
    """최신 프롬프트 세트 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                WITH latest_filtering AS (
                    SELECT id
                    FROM filtering_history
                    WHERE position_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                SELECT result_data
                FROM filtering_intermediate_results r
                JOIN latest_filtering f ON r.filtering_id = f.id
                WHERE r.step_name = 'prompts'
                ORDER BY r.step_number DESC
                LIMIT 1
            """, (position_id,))
            result = cur.fetchone()
            
            if result and result['result_data']:
                try:
                    # result_data가 이미 dict인 경우 그대로 반환
                    if isinstance(result['result_data'], dict):
                        return result['result_data']
                    # 문자열인 경우 JSON 파싱
                    elif isinstance(result['result_data'], str):
                        return json.loads(result['result_data'])
                    # JSONB 타입인 경우 그대로 반환
                    else:
                        return result['result_data']
                except (json.JSONDecodeError, TypeError) as e:
                    st.error(f"프롬트 데이터 파싱 오류: {str(e)}")
                    return {}
            return {}

def save_candidate_filtering_result(filtering_id: int, saramin_key: str, keyword_match_count: int):
    """후보자 필터링 결과 저장"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO candidate_filtering_result 
                (filtering_id, saramin_key, keyword_match_count, status)
                VALUES (%s, %s, %s, 'filtered')
                ON CONFLICT (filtering_id, saramin_key) 
                DO UPDATE SET 
                    keyword_match_count = EXCLUDED.keyword_match_count,
                    status = 'filtered'
            """, (filtering_id, saramin_key, keyword_match_count))
            conn.commit()

def update_filtering_history(filtering_id: int, status: str, filtered_count: int):
    """필터링 이력 상태 업데이트"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE filtering_history 
                SET 
                    status = %s,
                    filtered_count = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (status, filtered_count, filtering_id))
            conn.commit()

def get_latest_filtering_results(position_id: int, filtering_id: Optional[int] = None) -> pd.DataFrame:
    """최신 필터링 결과 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    c.*,  -- 모든 후보자 정보 (page_url 포함)
                    pc.id as mapping_id,
                    pc.scout_status,
                    pc.last_checked_at
                FROM scraping_saramin_candidates c
                INNER JOIN scraping_saramin_position_candidate pc 
                    ON c.saramin_key = pc.saramin_key
                WHERE pc.position_id = %s
                AND pc.scout_status = 'extracted'
                ORDER BY pc.last_checked_at DESC
            """, (position_id,))
            
            results = cur.fetchall()
            return pd.DataFrame(results) if results else pd.DataFrame()

def execute_query_and_save_results(query: str, filtering_id: int, position_id: int) -> pd.DataFrame:
    """SQL 쿼리 실행 및 결과 저장"""
    with get_db_connection() as conn:
        try:
            # 쿼리 실행
            df = pd.read_sql(query, conn)
            
            # 결과가 있는 경우에만 저장 진행
            if not df.empty:
                with conn.cursor() as cur:
                    # 각 후보자를 position_candidate 테이블에 'extracted' 상태로 저장
                    for _, row in df.iterrows():
                        cur.execute("""
                            INSERT INTO scraping_saramin_position_candidate 
                            (position_id, saramin_key, scout_status)
                            VALUES (%s, %s, 'extracted')
                            ON CONFLICT (position_id, saramin_key) 
                            DO UPDATE SET 
                                scout_status = 
                                    CASE 
                                        WHEN scraping_saramin_position_candidate.scout_status = 'extracted' 
                                        THEN 'extracted'
                                        ELSE scraping_saramin_position_candidate.scout_status
                                    END,
                                last_checked_at = NOW()
                        """, (position_id, row['saramin_key']))
                    
                    # 필터링 이력 업데이트
                    cur.execute("""
                        UPDATE filtering_history 
                        SET status = 'completed',
                            filtered_count = %s,
                            completed_at = NOW()
                        WHERE id = %s
                    """, (len(df), filtering_id))
                    
                    conn.commit()
            
            return df
            
        except Exception as e:
            conn.rollback()
            raise e

def get_filtering_results(filtering_id: int) -> pd.DataFrame:
    """특정 필터링 ID의 결과 조회"""
    with get_db_connection() as conn:
        query = """
            SELECT 
                c.saramin_key,
                c.birth_year,
                c.location,
                c.regex_desired_annual_salary,
                c.regex_desired_job,
                c.regex_login_dt,
                r.keyword_match_count,
                r.status as filtering_status
            FROM candidate_filtering_result r
            JOIN scraping_saramin_candidates c ON c.saramin_key = r.saramin_key
            WHERE r.filtering_id = %s
            ORDER BY r.keyword_match_count DESC, c.regex_login_dt DESC
        """
        return pd.read_sql(query, conn, params=(filtering_id,))

def get_latest_step_prompt(filtering_id: int, step_name: str) -> str:
    """특정 단계의 최신 프롬프트 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT result_data->>'prompt' as prompt
                FROM filtering_intermediate_results
                WHERE filtering_id = %s 
                AND step_name = %s
                ORDER BY step_number DESC
                LIMIT 1
            """, (filtering_id, step_name))
            result = cur.fetchone()
            return result['prompt'] if result else None

def save_step_prompt(filtering_id: int, step_name: str, prompt: str):
    """단계별 프롬프트 저장"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 현재 단계 번호 조회
            cur.execute("""
                SELECT COALESCE(MAX(step_number), 0) + 1 as next_step
                FROM filtering_intermediate_results
                WHERE filtering_id = %s
            """, (filtering_id,))
            next_step = cur.fetchone()[0]
            
            # 프롬프트 저장
            cur.execute("""
                INSERT INTO filtering_intermediate_results
                (filtering_id, step_name, step_number, result_data)
                VALUES (%s, %s, %s, %s::jsonb)
            """, (
                filtering_id,
                step_name,
                next_step,
                json.dumps({"prompt": prompt})
            ))
            conn.commit()

def get_latest_prompt_template(step_name: str) -> dict:
    """단계별 최신 프롬프트 템플릿 조회"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, template_name, template_content
                FROM prompt_templates
                WHERE step_name = %s
                ORDER BY CASE WHEN is_default THEN 1 ELSE 2 END,
                         created_at DESC
                LIMIT 1
            """, (step_name,))
            return cur.fetchone()

def save_prompt_execution(filtering_id: int, step_name: str, template_id: int, 
                        used_prompt: str, result: str, variables: dict) -> int:
    """프롬프트 실행 이력 장"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prompt_execution_history
                (filtering_id, step_name, template_id, used_prompt, result, variables)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
            """, (filtering_id, step_name, template_id, used_prompt, result, 
                 json.dumps(variables)))
            conn.commit()
            return cur.fetchone()[0]

def save_prompt_template(step_name: str, template_name: str, 
                       template_content: str, is_default: bool = False) -> int:
    """새로운 프롬프트 템플릿 저장"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 기본 템플릿으로 설정하는 경우 기존 기본값 해제
            if is_default:
                cur.execute("""
                    UPDATE prompt_templates 
                    SET is_default = false
                    WHERE step_name = %s AND is_default = true
                """, (step_name,))
            
            cur.execute("""
                INSERT INTO prompt_templates
                (step_name, template_name, template_content, is_default)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (step_name, template_name, template_content, is_default))
            conn.commit()
            return cur.fetchone()[0]
