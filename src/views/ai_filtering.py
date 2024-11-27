import streamlit as st
import pandas as pd
from datetime import datetime
from src.utils.auth_helper import require_auth
from src.utils.database import (
    get_position_details,
    save_filtering_history,
    save_filtering_intermediate,
    get_latest_filtering,
    update_filtering_results,
    get_filtering_history,
    get_latest_prompts,
    save_candidate_filtering_result,
    update_filtering_history,
    execute_query_and_save_results,
    get_latest_step_prompt,
    save_step_prompt,
    save_prompt_template,
    get_latest_prompt_template
)
from src.services.ai_service import AIService
from openai import OpenAI
import json

def load_example_data(example_type: str):
    """예시 데이터 로드"""
    examples = {
        "ui_designer": {
            "job_description": """이런 일을 해요 (UI 디자이너)
            • 사용자 중심의 직관적이고 매력적인 UI 디자인 및 시각적 디자인 작업
            • 사용자 경험(UX) 개선을 위한 디자인 리서치 및 테스트
            • 다양한 플랫폼(웹, 모바일 등)에서의 디자인 작업
            이런 분을 찾고 있어요
            • UI 디자인 경력 4~6년차
            • 시각적 자인 및 상호작용 디자인에 대한 깊은 이해
            • 긍정적인 애티튜드와 문제 해결 능력
            • 다양한 프로젝트 경험 및 포트폴리오 제출 필수
            • 팀워크 및 커뮤니케이션 능력""",
            "job_type": "UI디자인"
        },
        "frontend": {
            "job_description": """Next.js를 주력으로 활용하여 웹 서비스 개발 (전체 업무의 90%)
            - React Native를 활용한 모바일 앱 개발 (전체 업무의 10%)
            - 구직자 통합 이력 관리 대시보드 개발
            - AI 기반 매칭 시스템의 프론트엔드 구현
            - 자체 UI 컴포넌트 라이브러리 제작""",
            "job_type": "프런트엔드"
        },
        "marketer": {
            "job_description": """광고기획, 퍼포머스마케팅, 캠페인, 데이터분석,신규매체발굴, 
            모바일/앱, 매체운영/집행,마케팅최적화,광고최적화,네이버, 구글, 페이스북, 카카오
            서울 역삼동""",
            "job_type": "마케팅"
        }
    }
    
    if example_type in examples:
        example = examples[example_type]
        st.session_state.job_description = example["job_description"]
        st.session_state.job_type = example["job_type"]
        st.rerun()

@require_auth
def show_ai_filtering_page():
    st.title("AI 기반 후보자 필터링")
    
    if "selected_position_id" not in st.session_state:
        st.warning("먼저 포지션을 선택해주세요.")
        return
        
    position_id = st.session_state.selected_position_id
    
    # 프롬프트 관리 섹션
    st.header("1. 프롬프트 이력")
    
    # 프롬프트 이력 선택
    history = get_filtering_history(position_id)
    if history:
        history_options = {
            f"#{idx+1} - {entry['created_at'].strftime('%Y-%m-%d %H:%M')}": entry 
            for idx, entry in enumerate(history)
        }
        
        selected_history = st.selectbox(
            "프롬프트 이력 선택",
            options=list(history_options.keys()),
            key="prompt_history_select"
        )
        
        if selected_history:
            selected_entry = history_options[selected_history]
            entry_id = selected_entry.get('id', 'unknown')  # 각 entry의 고유 ID 가져오기
            created_at = selected_entry['created_at'].strftime('%Y%m%d_%H%M%S')  # 타임스탬프
            
            if selected_entry['steps']:
                for step_idx, step in enumerate(selected_entry['steps']):
                    if isinstance(step, dict) and step.get('step_name') == 'prompts':
                        try:
                            prompts = step['result_data'] if isinstance(step['result_data'], dict) else json.loads(step['result_data'])
                            # 선택된 프롬프트를 세션 상태에 저장
                            st.session_state.selected_prompts = prompts
                            
                            # 프롬프트 내용 표시
                            with st.expander("선택된 프롬프트 내용", expanded=False):
                                st.text_area(
                                    "키워드 추출 프롬프트",
                                    value=prompts.get('prompt1', ''),
                                    disabled=True,
                                    height=100,
                                    key=f"history_prompt1_{entry_id}_{created_at}_{step_idx}"
                                )
                                st.text_area(
                                    "직무 키워드 프롬프트",
                                    value=prompts.get('prompt2', ''),
                                    disabled=True,
                                    height=100,
                                    key=f"history_prompt2_{entry_id}_{created_at}_{step_idx}"
                                )
                                st.text_area(
                                    "통합 키워드 프롬프트",
                                    value=prompts.get('prompt3', ''),
                                    disabled=True,
                                    height=100,
                                    key=f"history_prompt3_{entry_id}_{created_at}_{step_idx}"
                                )
                                if 'sql_prompt' in prompts:
                                    st.text_area(
                                        "SQL 프롬프트",
                                        value=prompts.get('sql_prompt', ''),
                                        disabled=True,
                                        height=100,
                                        key=f"history_sql_prompt_{entry_id}_{created_at}_{step_idx}"
                                    )
                                
                                if st.button("이 프롬프트 적용", key=f"apply_prompt_{entry_id}_{created_at}_{step_idx}"):
                                    # 선택된 프롬프트를 각 단계의 프롬프트 설정에 적용
                                    st.session_state.current_prompt2 = prompts.get('prompt2', '')
                                    st.session_state.current_prompt3 = prompts.get('prompt3', '')
                                    st.session_state.current_sql_prompt = prompts.get('sql_prompt', '')
                                    st.success("선택한 프롬프트가 각 단계에 적용되었습니다.")
                                    st.rerun()
                                    
                        except (json.JSONDecodeError, AttributeError) as e:
                            st.error(f"프롬프트 데이터 파싱 오류: {str(e)}")
    else:
        st.info("저장된 프롬프트 이력이 없습니다.")
    
    # 구분선
    st.divider()
    
    # 키워드 추출 섹션
    st.header("2. 키워드 추출")
    
    # 프롬프트 설정
    with st.expander("키워드 추출 프롬프트 설정", expanded=False):
        st.markdown("""
        ### 키워드 추출 프롬프트 가이드라인
        - `{job_description}`: 입력한 채용공고 내용이 자동으로 삽입됩니다
        """)
        
        # 최신 템플릿 가져오기
        latest_template = get_latest_prompt_template('keyword_extraction')
        latest_extract_prompt = latest_template['template_content'] if latest_template else """주어진 Job Description에서 업무경험, 스킬, 도구사용에 대해 1개 또는 2개의 단어로 구성된 
        핵심 키워드 최대 10개를 산출해주는데 단어간에 띄어쓰기를 하지 말아줘: {job_description}"""
        
        template_name = st.text_input(
            "템플릿 이름",
            value=latest_template['template_name'] if latest_template else "키워드 추출 프롬프트",
            key="extract_template_name"
        )
        
        extract_prompt = st.text_area(
            "키워드 추출 프롬프트",
            value=latest_extract_prompt,
            height=150,
            key="extract_prompt_input"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            is_default = st.checkbox("기본 템플릿으로 설정", key="extract_is_default")
        with col2:
            if st.button("추출 프롬프트 저장", key="save_extract_prompt"):
                template_id = save_prompt_template(
                    step_name="keyword_extraction",
                    template_name=template_name,
                    template_content=extract_prompt,
                    is_default=is_default
                )
                st.success("키워드 추출 프롬프트가 저장되었습니다.")
                st.session_state.current_extract_template_id = template_id
    
    # 예시 데이터 버튼들
    st.subheader("예시 데이터")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("UI 디자이너 예시", key="ui_designer_example"):
            load_example_data("ui_designer")
    with col2:
        if st.button("프론트엔드 예시", key="frontend_example"):
            load_example_data("frontend")
    with col3:
        if st.button("마케터 예시", key="marketer_example"):
            load_example_data("marketer")
    
    st.divider()  # 예시 버튼과 입력 필드 사이 구분선
    
    # 입력 필드들
    job_description = st.text_area(
        "채용공고", 
        height=200,
        key="job_description",
        value=st.session_state.get('job_description', '')
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        extract_button = st.button("키워드 추출 실행")
    
    # 추출된 키워드 표시 및 수정
    if 'extracted_keywords' in st.session_state or extract_button:
        if extract_button:
            with st.spinner("키워드 추출 중..."):
                ai_service = AIService()
                result = ai_service.extract_job_keywords(job_description)
                if result:
                    st.session_state.extracted_keywords = result
                    st.success("키워드 추출 완료!")
        
        st.subheader("추출된 키워드")
        edited_keywords = st.text_area(
            "추출된 키워드 (수정 가능)",
            value=st.session_state.extracted_keywords.get('keywords', '') if 'extracted_keywords' in st.session_state else '',
            height=100,
            key="edited_extracted_keywords"
        )
        if edited_keywords != st.session_state.get('extracted_keywords', {}).get('keywords', ''):
            st.session_state.extracted_keywords = {
                "keywords": edited_keywords,
                "raw_response": edited_keywords
            }
    
    # 구분선
    st.divider()
    
    # 키워드 정제 섹션
    st.header("3. 키워드 정제")
    
    with st.expander("정제 프롬프트 설정", expanded=False):
        st.markdown("""
        ### 정제 프롬프트 가이드라인
        - `{job_type}`: 입력한 직무 분류가 자동으로 삽입됩니다
        """)
        
        # 최신 템플릿 가져오기
        latest_refine_template = get_latest_prompt_template('keyword_refinement')
        latest_refine_prompt = latest_refine_template['template_content'] if latest_refine_template else """주어진 직무에 대해 레쥬메 서치를 위한 1개 또는 2개의 단어로 구성된 
        핵심 키워드 5개를 산출해주는데 단어간에 띄어쓰기를 하지 말아줘: {job_type}"""
        
        refine_template_name = st.text_input(
            "템플릿 이름",
            value=latest_refine_template['template_name'] if latest_refine_template else "키워드 정제 프롬프트",
            key="refine_template_name"
        )
        
        refine_prompt = st.text_area(
            "정제 프롬프트",
            value=latest_refine_prompt,
            height=150,
            key="refine_prompt_input"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            refine_is_default = st.checkbox("기본 템플릿으로 설정", key="refine_is_default")
        with col2:
            if st.button("정제 프롬프트 저장", key="save_refine_prompt"):
                template_id = save_prompt_template(
                    step_name="keyword_refinement",
                    template_name=refine_template_name,
                    template_content=refine_prompt,
                    is_default=refine_is_default
                )
                st.success("키워드 정제 프롬프트가 저장되었습니다.")
                st.session_state.current_refine_template_id = template_id
    
    # 직무 분류 입력
    job_type = st.text_input(
        "직무 분류",
        value=st.session_state.get('job_type', ''),
        key="job_type_input"
    )
    
    # 실행 버튼과 결과 표시를 위한 컬럼 배치
    col1, col2 = st.columns([1, 3])
    with col1:
        refine_button = st.button("키워드 정제 실행", key="refine_execute")
    
    # 정제된 키워드 표시 및 수정
    if 'refined_keywords' in st.session_state or (refine_button and job_type):
        if refine_button:
            if not job_type:
                st.error("직무 분류를 입력해주세요.")
            else:
                with st.spinner("키워드 정제 중..."):
                    ai_service = AIService()
                    result = ai_service.refine_job_keywords(job_type)
                    if result:
                        st.session_state.refined_keywords = result
                        st.success("키워드 정제 완료!")
        
        st.subheader("정제된 키워드")
        edited_refined = st.text_area(
            "정제된 키워드 (수정 가능)",
            value=st.session_state.refined_keywords.get('keywords', '') if 'refined_keywords' in st.session_state else '',
            height=100,
            key="edited_refined_keywords"
        )
        if edited_refined != st.session_state.get('refined_keywords', {}).get('keywords', ''):
            st.session_state.refined_keywords = {
                "keywords": edited_refined,
                "raw_response": edited_refined
            }
    elif not job_type:
        st.info("직무 분류를 입력하고 키워드 정제를 실행해주세요.")
    
    # 구분선
    st.divider()
    
    # 키워드 통합 섹션
    st.header("4. 키워드 통합")
    
    if 'extracted_keywords' in st.session_state and 'refined_keywords' in st.session_state:
        with st.expander("통합 프롬프트 설정", expanded=False):
            st.markdown("""
            ### 통합 프롬프트 가이드라인
            - `{extracted_keywords}`: 추출된 키워드가 자동으로 삽입됩니다
            - `{refined_keywords}`: 정제된 키워드가 자동으로 삽입됩니다
            """)
            
            combine_template_name = st.text_input(
                "템플릿 이름",
                value="키워드 통합 프롬프트",
                key="combine_template_name"
            )
            
            combine_prompt = st.text_area(
                "통합 프롬프트",
                value=st.session_state.get('combine_prompt', """
주어진 내용에 중복을 제거하고 중간단계 없이 최종결과만 최대 20개 키워드를 산출해줘:
{extracted_keywords} {refined_keywords}
                """),
                height=150,
                key="combine_prompt_input"
            )
            
            col1, col2 = st.columns([1, 1])
            with col1:
                combine_is_default = st.checkbox("기본 템플릿으로 설정", key="combine_is_default")
            with col2:
                if st.button("통합 프롬프트 저장", key="save_combine_prompt"):
                    template_id = save_prompt_template(
                        step_name="keyword_combination",
                        template_name=combine_template_name,
                        template_content=combine_prompt,
                        is_default=combine_is_default
                    )
                    st.success("키워드 통합 프롬프트가 저장되었습니다.")
                    st.session_state.current_combine_template_id = template_id
                    st.session_state.combine_prompt = combine_prompt
        
        col1, col2 = st.columns([1, 3])
        with col1:
            combine_button = st.button("키워드 통합 실행")
        
        # 통합된 키워드 표시 및 수정
        if 'combined_keywords' in st.session_state or combine_button:
            if combine_button:
                with st.spinner("키워드 통합 중..."):
                    ai_service = AIService()
                    result = ai_service.combine_keywords(
                        st.session_state.extracted_keywords['keywords'],
                        st.session_state.refined_keywords['keywords']
                    )
                    if result:
                        st.session_state.combined_keywords = result
                        st.success("키워드 통합 완료!")
            
            st.subheader("통합된 키워드")
            edited_combined = st.text_area(
                "통합된 키워드 (수정 가능)",
                value=st.session_state.combined_keywords.get('keywords', '') if 'combined_keywords' in st.session_state else '',
                height=100,
                key="edited_combined_keywords"
            )
            if edited_combined != st.session_state.get('combined_keywords', {}).get('keywords', ''):
                st.session_state.combined_keywords = {
                    "keywords": edited_combined,
                    "raw_response": edited_combined
                }
    else:
        st.info("키워드 추출과 정제를 먼저 완료해주세요.")
    
    # 구분선
    st.divider()
    
    # SQL 쿼리 생성 섹션
    st.header("5. SQL 쿼리 생성")
    
    # 프롬프트 설정 UI는 combined_keywords가 있을 때만 표시
    if 'combined_keywords' in st.session_state:
        with st.expander("SQL 쿼리 프롬프트 설정", expanded=False):
            st.markdown("""
            ### SQL 프롬프트 가이드라인
            - `{keywords}`: 통합된 키워드가 자동으로 삽입됩니다
            - `{job_description}`: 입력한 채용공고 내용이 자동으로 삽입됩니다
            """)
            
            sql_template_name = st.text_input(
                "템플릿 이름",
                value="SQL 생성 프롬프트",
                key="sql_template_name"
            )
            
            sql_prompt = st.text_area(
                "SQL 생성 프롬프트",
                value=st.session_state.get('current_sql_prompt', """
create table scraping_saramin_candidates as 
(
    saramin_key text not null,
    name_extraction text,
    name text,
    career_status text,
    birth_year text,
    location text,
    regex_name text,
    regex_career_details text,
    regex_gender_birth_year text,
    regex_address text,
    regex_desired_annual_salary text,
    regex_portfolio_summary text,
    regex_my_skills text,
    regex_academic_background text,
    regex_work_experience text,
    regex_career_technical_details text,
    regex_portfolio text,
    regex_desired_job text,
    regex_desired_industry text,
    regex_keywords text,
    regex_desired_work_region text,
    regex_desired_employment_type text,
    create_dt timestamp with time zone,
    update_dt timestamp with time zone,
    additional_prefer text,
    additional_highlight text,
    additional_tag text,
    regex_work_year text,
    regex_login_dt text
);

text 컬럼을 키워드와 비교할때는 LIKE 문장을 이용하고 앞뒤로 %를 붙여서 비교한다.
{job_description}에 경력 년수에 대한 요건이 있는 경우 해당기간에 대한 값들을 regex_work_yer를 LIKE 문장을 이용하고 앞에는 %, 뒤에는 년%를 붙여서 비교하고 해당 문장들을 ()로 묶어준다.
지역에 대한 언급이 있는 경우 regex_desired_work_region과 지역을 LIKE 문장을 이용해서 앞뒤로 %를 붙여서 비교하고 해당 문장들을 ()로 묶어준다.
키워드와 비교할 컬럼들은 regex_my_skills, regex_desired_job, regex_keywords, regex_work_experience 들이야.
{keywords}를 산출해줘.
sql 문장을 생성할때는 saramin_key, birth_year, location, regex_desired_annual_salary, regex_desired_job, regex_login_dt가 표시하도록 한다.
추가로 표시할 내용으로는 키워드가 몇개 일치하는지도 알려줘.
order는 키워드가 많이 일치하는 순서, 연봉수준이 비슷한것 우선, regex_login_dt가 최근인것 우선으로 표시하고 상위 20명을 표시하도록 해줘."""),
                height=400,
                key="sql_prompt_input"
            )
            
            col1, col2 = st.columns([1, 1])
            with col1:
                sql_is_default = st.checkbox("기본 템플릿으로 설정", key="sql_is_default")
            with col2:
                if st.button("SQL 프롬프트 저장", key="save_sql_prompt"):
                    template_id = save_prompt_template(
                        step_name="sql_generation",
                        template_name=sql_template_name,
                        template_content=sql_prompt,
                        is_default=sql_is_default
                    )
                    st.success("SQL 프롬프트가 저장되었습니다.")
                    st.session_state.current_sql_template_id = template_id
                    st.session_state.current_sql_prompt = sql_prompt
        
        # 쿼리 생성 버튼
        if st.button("SQL 쿼리 생성", key="generate_sql_button"):
            with st.spinner("SQL 쿼리 생성 중..."):
                ai_service = AIService()
                result = ai_service.generate_sql(
                    keywords=st.session_state.combined_keywords['keywords'],
                    job_description=st.session_state.get('job_description', '')
                )
                if result:
                    st.session_state.sql_query = result
                    st.success("SQL 쿼리 생성 완료!")
    
    # 쿼리 편집 및 실행 UI를 항상 표시
    st.subheader("SQL 쿼리 편집")
    edited_query = st.text_area(
        "SQL 쿼리 (직접 입력 또는 수정)",
        value=st.session_state.get('sql_query', {}).get('query', ''),
        height=400,
        key="sql_query_editor"
    )
    
    # 쿼리 실행 섹션
    with st.container():
        st.markdown("---")
        st.subheader("쿼리 실행")
        col1, col2 = st.columns([1, 4])
        with col1:
            execute_button = st.button("쿼리 실행", key="execute_sql_button")
        with col2:
            st.info("쿼리를 직접 입력하거나 수정하여 실행할 수 있습니다.")
        
        if execute_button and edited_query.strip():  # 쿼리가 비어있지 않은 경우에만 실행
            # filtering_id가 없는 경우 새로 생성
            if "filtering_id" not in st.session_state:
                filtering_id = save_filtering_history(
                    position_id=st.session_state.selected_position_id,
                    job_description=st.session_state.get('job_description', ''),
                    step="prompts",
                    result={}
                )
                st.session_state.filtering_id = filtering_id
            
            # 수정된 쿼리로 실행 및 결과 저장
            results = execute_query_and_save_results(
                query=edited_query,
                filtering_id=st.session_state.filtering_id,
                position_id=st.session_state.selected_position_id
            )
            
            # 세션에 필터링 결과와 관련 정보 저장
            st.session_state.filtering_results = results
            st.session_state.executed_query = edited_query
            st.session_state.last_executed_position_id = st.session_state.selected_position_id
            st.session_state.current_filtering_id = st.session_state.filtering_id
            
            # 결과 표시
            st.success(f"쿼리 실행 완료! {len(results)}개의 결과가 있습니다.")
            
            # 결과 데이터프레임 표시
            with st.expander("실행 결과", expanded=True):
                st.dataframe(results)
                
                # 통계 정보 표시
                if 'keyword_match_count' in results.columns:
                    st.subheader("키워드 매칭 통계")
                    st.write(results['keyword_match_count'].describe())
    
    # 다음 단계로 이동하는 버튼을 쿼리 실행 결과와 독립적으로 배치
    st.markdown("---")
    st.subheader("다음 단계")
    if st.button("후보자 선택으로 이동", key="move_to_selection", use_container_width=True):
        # 필요한 상태 정보를 세션에 저장
        st.session_state.previous_page = "AI 필터링"
        st.session_state.current_page = "후보자 선택"
        # 필터링 결과 관련 정보도 유지
        st.session_state.filtering_complete = True
        if "filtering_id" in st.session_state:
            st.session_state.last_filtering_id = st.session_state.filtering_id
        # 즉시 페이지 새로고침
        st.rerun()
    
    # 포지션 변경 감지 및 상태 초기화
    if 'last_position_id' not in st.session_state:
        st.session_state.last_position_id = st.session_state.selected_position_id
    elif st.session_state.last_position_id != st.session_state.selected_position_id:
        # 포지션이 변경된 경우 상태 초기화
        keys_to_clear = [
            'extracted_keywords', 'refined_keywords', 'combined_keywords', 
            'sql_query', 'filtering_results', 'executed_query', 'filtering_id',
            'current_filtering_id', 'last_executed_position_id'
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.last_position_id = st.session_state.selected_position_id
    