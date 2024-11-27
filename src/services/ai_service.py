from openai import OpenAI
from typing import Dict, Optional, List, Tuple
import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from utils.database import get_latest_prompt_template, save_prompt_execution

class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    def extract_job_keywords(self, job_description: str) -> dict:
        """직무 키워드 추출"""
        try:
            # 템플릿 조회
            template = get_latest_prompt_template('keyword_extraction')
            prompt = template['template_content'].replace('{job_description}', job_description)
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful HR recruiter. Answer in Korean."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            keywords = response.choices[0].message.content.strip()
            
            # 실행 이력 저장
            save_prompt_execution(
                filtering_id=st.session_state.get('filtering_id'),
                step_name='keyword_extraction',
                template_id=template['id'],
                used_prompt=prompt,
                result=keywords,
                variables={'job_description': job_description}
            )
            
            return {
                "template_id": template['id'],
                "prompt": prompt,
                "keywords": keywords,
                "raw_response": keywords
            }
            
        except Exception as e:
            st.error(f"키워드 추출 중 오류 발생: {str(e)}")
            return None

    def refine_job_keywords(self, job_type: str) -> dict:
        """직무 키워드 정제 (Step 2)"""
        try:
            prompt = f"""주어진 직무에 대해 레쥬메 서치를 위한 1개 또는 2개의 단어로 구성된 
            핵심 키워드 5개를 산출해주는데 단어간에 띄어쓰기를 하지 말아줘:
            {job_type}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful HR recruiter. Answer in Korean."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            keywords = response.choices[0].message.content.strip()
            return {
                "prompt": prompt,
                "keywords": keywords,
                "raw_response": keywords
            }
            
        except Exception as e:
            st.error(f"키워드 정제 중 오류 발생: {str(e)}")
            return None

    def combine_keywords(self, extracted_keywords: str, refined_keywords: str) -> dict:
        """키워드 통합 (Step 3)"""
        try:
            # 통합 프롬프트 템플릿
            combine_prompt = st.session_state.get('combine_prompt', """
주어진 내용에 중복을 제거하고 중간단계 없이 최종결과만 최대 20개 키워드를 산출해줘:
{extracted_keywords} {refined_keywords}
            """)
            
            # 변수 치환
            prompt = combine_prompt.replace("{extracted_keywords}", extracted_keywords)
            prompt = prompt.replace("{refined_keywords}", refined_keywords)
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful HR recruiter. Answer in Korean."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            keywords = response.choices[0].message.content.strip()
            return {
                "prompt": prompt,
                "keywords": keywords,
                "raw_response": keywords
            }
            
        except Exception as e:
            st.error(f"키워드 통합 중 오류 발생: {str(e)}")
            return None

    def generate_sql(self, keywords: str, job_description: str = "") -> dict:
        """SQL 쿼리 생성 (Step 4)"""
        try:
            # SQL 프롬프트 템플릿
            sql_prompt = st.session_state.get('current_sql_prompt', """
            create table scraping_saramin_candidates as 
            (
                // ... table schema ...
            );

            text 컬럼을 키워드와 비교할때는 LIKE 문장을 이용하고 앞뒤로 %를 붙여서 비교한다.
            {job_description}에 경력 년수에 대한 요건이 있는 경우 해당기간에 대한 값들을 regex_work_yer를 LIKE 문장을 이용하고 앞에는 %, 뒤에는 년%를 붙여서 비교하고 해당 문장들을 ()로 묶어준다.
            지역에 대한 언급이 있는 경우 regex_desired_work_region과 지역을 LIKE 문장을 이용해서 앞뒤로 %를 붙여서 비교하고 해당 문장들을 ()로 묶어준다.
            키워드와 비교할 컬럼들은 regex_my_skills, regex_desired_job, regex_keywords, regex_work_experience 들이야.
            {keywords}를 산출해줘.
            sql 문장을 생성할때는 saramin_key, birth_year, location, regex_desired_annual_salary, regex_desired_job, regex_login_dt가 표시하도록 한다.
            추가로 표시할 내용으로는 키워드가 몇개 일치하는지도 알려줘.
            order는 키워드가 많이 일치하는 순서, 연봉수준이 비슷한것 우선, regex_login_dt가 최근인것 우선으로 표시하고 상위 20명을 표시하도록 해줘.
            """)

            # 변수 치환
            prompt = sql_prompt.replace("{keywords}", keywords)
            prompt = prompt.replace("{job_description}", job_description)

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful SQL expert. Answer with SQL query only, without ```sql or ``` tags."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            query = response.choices[0].message.content.strip()
            return {
                "prompt": prompt,
                "query": query,
                "keywords": keywords
            }
            
        except Exception as e:
            st.error(f"SQL 생성 중 오류 발생: {str(e)}")
            return None
