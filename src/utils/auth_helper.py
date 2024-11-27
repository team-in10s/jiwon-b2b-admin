import streamlit as st
from functools import wraps

def require_auth(func):
    """인증이 필요한 페이지에 적용할 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("authenticated", False):
            st.warning("인증이 필요합니다. 메인 페이지에서 인증을 진행해주세요.")
            st.stop()
        return func(*args, **kwargs)
    return wrapper
