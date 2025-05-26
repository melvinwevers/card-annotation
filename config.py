import streamlit as st

PAGE_CONFIG = {
    "page_title": "JSON Validator",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

LOCK_DIR = "data/locks"
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.tif']
DEFAULT_SIDEBAR_WIDTH = 500

def apply_custom_css():
    """Apply custom CSS for sidebar width"""
    st.markdown(f"""
        <style>
            section[data-testid=\"stSidebar\"] {{
                width: {DEFAULT_SIDEBAR_WIDTH}px !important;
            }}
            .main .block-container {{
                max-width: calc(100% - {DEFAULT_SIDEBAR_WIDTH + 20}px) !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }}
            section[data-testid=\"stSidebar\"] > div:first-child {{
                width: {DEFAULT_SIDEBAR_WIDTH}px !important;
            }}
        </style>
    """, unsafe_allow_html=True)