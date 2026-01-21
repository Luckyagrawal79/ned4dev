import streamlit as st

def record_feedback(mid, value):
    st.session_state.feedback_data.append({"id":mid,"value":value})
