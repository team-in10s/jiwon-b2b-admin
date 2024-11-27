import streamlit as st
from src.config import ADMIN_PASSWORD

def check_password():
    """비밀번호를 확인하고 인증 상태를 세션에 저장"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        return True

    password = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    
    if password:
        if password == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.success("인증되었습니다!")
            st.rerun()
        else:
            st.error("잘못된 비밀번호입니다.")
            return False
    
    return False

def show_auth_page():
    """인증 페이지 표시"""
    st.title("B2B Admin System")
    st.subheader("관리자 인증")
    
    return check_password()
