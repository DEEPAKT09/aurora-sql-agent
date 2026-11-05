
"""
AURORA SQL Agent
Main Streamlit Application
"""

import streamlit as st

from config import settings

from ui.sidebar import render_sidebar, get_active_page
from ui.chat_interface import render_chat_interface
from ui.database_panel import render_database_panel
from ui.schema_explorer import render_schema_explorer
from ui.sql_editor import render_sql_editor


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AURORA SQL Agent",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# GLOBAL LIGHT THEME
# ============================================================

def apply_global_styles():
    """Apply consistent light theme and high-contrast styling."""

    st.markdown(
        """
        <style>

        /* ----------------------------------------------------
           GLOBAL THEME
        ---------------------------------------------------- */

        :root {
            color-scheme: light !important;

            --aurora-bg: #F7F8FC;
            --aurora-white: #FFFFFF;
            --aurora-text: #25213A;
            --aurora-secondary: #514B65;
            --aurora-muted: #625B73;
            --aurora-border: #C8C3D5;
            --aurora-purple: #6841B8;
            --aurora-purple-dark: #50318F;
            --aurora-purple-light: #F0EAFE;
        }

        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            color-scheme: light !important;
            background: var(--aurora-bg) !important;
            color: var(--aurora-text) !important;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1500px;
            padding-top: 2rem !important;
            padding-bottom: 3rem !important;
        }

        header[data-testid="stHeader"] {
            background: var(--aurora-bg) !important;
            border-bottom: 1px solid #E2DFEA !important;
        }

        [data-testid="stToolbar"] {
            background: transparent !important;
        }

        /* ----------------------------------------------------
           TYPOGRAPHY
        ---------------------------------------------------- */

        h1, h2, h3, h4, h5, h6 {
            color: #25213A !important;
            font-weight: 700 !important;
        }

        [data-testid="stMain"] p,
        [data-testid="stMain"] li,
        [data-testid="stMain"] label,
        [data-testid="stMarkdownContainer"] {
            color: #39334D !important;
        }

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            color: #625B73 !important;
        }

        /* ----------------------------------------------------
           INPUTS AND TEXT AREAS
        ---------------------------------------------------- */

        [data-testid="stMain"] input,
        [data-testid="stMain"] textarea {
            color-scheme: light !important;
            background-color: #FFFFFF !important;
            color: #25213A !important;
            border: 1px solid #BDB7CE !important;
            border-radius: 9px !important;
        }

        [data-testid="stMain"] input::placeholder,
        [data-testid="stMain"] textarea::placeholder {
            color: #777187 !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] input:focus,
        [data-testid="stMain"] textarea:focus {
            border-color: #6841B8 !important;
            box-shadow: 0 0 0 2px rgba(104, 65, 184, 0.15) !important;
        }

        /* ----------------------------------------------------
           SELECTBOXES - STRONG BORDER FIX
           
           Explicitly target Streamlit's selectbox wrapper,
           BaseWeb select component and combobox element.
        ---------------------------------------------------- */

        [data-testid="stSelectbox"] {
            color-scheme: light !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] {
            background: #FFFFFF !important;
            color-scheme: light !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stSelectbox"] [data-baseweb="select"] div[role="combobox"],
        [data-testid="stSelectbox"] div[role="combobox"] {
            background-color: #FFFFFF !important;
            color: #25213A !important;
            border: 1.5px solid #AFA8C2 !important;
            border-radius: 9px !important;
            box-shadow: none !important;
            min-height: 42px !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div:hover,
        [data-testid="stSelectbox"] div[role="combobox"]:hover {
            border-color: #6841B8 !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
        [data-testid="stSelectbox"] div[role="combobox"]:focus-within {
            border: 2px solid #6841B8 !important;
            box-shadow: 0 0 0 2px rgba(104, 65, 184, 0.13) !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] span,
        [data-testid="stSelectbox"] [data-baseweb="select"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"] div {
            color: #25213A !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] svg {
            fill: #403653 !important;
            color: #403653 !important;
        }

        /* Dropdown menu */

        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"] {
            background-color: #FFFFFF !important;
            color: #25213A !important;
            border: 1px solid #C8C3D5 !important;
        }

        [role="option"] {
            background-color: #FFFFFF !important;
            color: #25213A !important;
        }

        [role="option"]:hover {
            background-color: #F0EAFE !important;
        }

        /* ----------------------------------------------------
           BUTTONS
        ---------------------------------------------------- */

        [data-testid="stMain"] .stButton > button,
        [data-testid="stMain"] .stFormSubmitButton > button,
        [data-testid="stMain"] .stDownloadButton > button {
            min-height: 42px !important;
            border-radius: 9px !important;
            font-weight: 600 !important;
            background: #FFFFFF !important;
            color: #33264F !important;
            border: 1px solid #AFA5C5 !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] .stButton > button:hover,
        [data-testid="stMain"] .stFormSubmitButton > button:hover,
        [data-testid="stMain"] .stDownloadButton > button:hover {
            background: #F0EAFE !important;
            color: #50318F !important;
            border-color: #6841B8 !important;
        }

        [data-testid="stMain"] button[kind="primary"] {
            background: #6841B8 !important;
            color: #FFFFFF !important;
            border: 1px solid #6841B8 !important;
        }

        [data-testid="stMain"] button[kind="primary"]:hover {
            background: #50318F !important;
            color: #FFFFFF !important;
            border-color: #50318F !important;
        }

        [data-testid="stMain"] button:disabled {
            background: #EAE7F0 !important;
            color: #625B73 !important;
            border-color: #D5D0DF !important;
            opacity: 1 !important;
        }

        /* ----------------------------------------------------
           FORMS AND CARDS
        ---------------------------------------------------- */

        [data-testid="stForm"] {
            background: #FFFFFF !important;
            border: 1px solid #D7D3E1 !important;
            border-radius: 13px !important;
            padding: 20px !important;
        }

        [data-testid="stMetric"] {
            background: #FFFFFF !important;
            border: 1px solid #D7D3E1 !important;
            border-radius: 12px !important;
            padding: 18px !important;
        }

        [data-testid="stMetricLabel"] {
            color: #625B73 !important;
        }

        [data-testid="stMetricValue"] {
            color: #25213A !important;
        }

        /* ----------------------------------------------------
           EXPANDERS
        ---------------------------------------------------- */

        [data-testid="stExpander"] {
            background: #FFFFFF !important;
            border: 1px solid #D7D3E1 !important;
            border-radius: 10px !important;
        }

        [data-testid="stExpander"] summary {
            background: #FFFFFF !important;
            color: #25213A !important;
        }

        /* ----------------------------------------------------
           TABLES
        ---------------------------------------------------- */

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background: #FFFFFF !important;
            border: 1px solid #D7D3E1 !important;
            border-radius: 10px !important;
            overflow: hidden;
        }

        /* ----------------------------------------------------
           CHAT
        ---------------------------------------------------- */

        [data-testid="stChatMessage"] {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #25213A !important;
        }

        [data-testid="stChatMessage"] p {
            color: #39334D !important;
        }

        [data-testid="stChatInput"] {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }

        [data-testid="stChatInput"] > div {
            background: #FFFFFF !important;
            border: 1px solid #BDB7CE !important;
            border-radius: 12px !important;
            box-shadow: 0 2px 8px rgba(35, 24, 57, 0.05) !important;
        }

        [data-testid="stChatInput"] textarea {
            background: #FFFFFF !important;
            color: #25213A !important;
            border: none !important;
        }

        [data-testid="stChatInput"] button {
            background: #6841B8 !important;
            color: #FFFFFF !important;
        }

        /* ----------------------------------------------------
           TABS
        ---------------------------------------------------- */

        button[data-baseweb="tab"] {
            color: #514963 !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: #6841B8 !important;
        }

        /* ----------------------------------------------------
           ALERTS AND CODE
        ---------------------------------------------------- */

        [data-testid="stAlert"] {
            border-radius: 10px !important;
        }

        [data-testid="stAlert"] p {
            color: #302944 !important;
        }

        [data-testid="stCode"],
        pre {
            background: #F0EFF6 !important;
            border: 1px solid #D7D3E1 !important;
            border-radius: 9px !important;
        }

        code {
            color: #50318F !important;
        }

        /* ----------------------------------------------------
           DARK PURPLE SIDEBAR
        ---------------------------------------------------- */

        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div {
            background: #241638 !important;
            color-scheme: dark !important;
        }

        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] div {
            color: #F3EFFB !important;
        }

        [data-testid="stSidebar"] button {
            color: #FFFFFF !important;
        }

        /* ----------------------------------------------------
           DIVIDERS AND BOTTOM AREA
        ---------------------------------------------------- */

        hr {
            border-color: #E2DFEA !important;
        }

        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"] {
            background: #F7F8FC !important;
        }

        /* ----------------------------------------------------
           RESPONSIVE
        ---------------------------------------------------- */

        @media (max-width: 768px) {
            [data-testid="stMainBlockContainer"] {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION STATE
# ============================================================

def initialize_app_state():
    """Initialize application-wide session state."""

    defaults = {
        "database_connected": False,
        "database_type": None,
        "database_name": None,
        "database_schema": None,
        "database_config": None,
        "chat_messages": [],
        "conversation_history": [],
        "generated_sql": "",
        "edited_sql": "",
        "sql_validation_result": None,
        "sql_execution_result": None,
        "result_analysis": None,
        "visualization_figure": None,
        "schema_metadata": {},
        "schema_discovered": False,
        "active_page": "New Chat",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================================================
# SETTINGS PAGE
# ============================================================

def render_settings_page():
    """Render application settings."""

    st.title("Settings")

    st.caption(
        "View the application configuration and execution settings."
    )

    st.divider()

    st.markdown("### Application Information")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Application Name**")
        st.write(settings.app_name)

        st.markdown("**Application Version**")
        st.write(settings.app_version)

        st.markdown("**Environment**")
        st.write(settings.environment)

    with col2:
        st.markdown("**LLM Provider**")
        st.write("Google Gemini")

        st.markdown("**Gemini Model**")
        st.write(settings.gemini_model)

        st.markdown("**Workflow Framework**")
        st.write("LangGraph")

    st.divider()

    st.markdown("### Query Execution Settings")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Maximum Rows", settings.max_rows)
        st.metric(
            "Query Timeout",
            f"{settings.query_timeout} seconds",
        )

    with col2:
        st.metric("Maximum Retries", settings.max_retries)
        st.metric(
            "Read-Only Mode",
            "Enabled" if settings.read_only_mode else "Disabled",
        )

    st.divider()

    st.markdown("### Database Connection")

    if st.session_state.database_connected:
        st.success("Database connected.")

        st.write(
            f"**Database:** {st.session_state.database_name}"
        )

        st.write(
            f"**Type:** {st.session_state.database_type}"
        )
    else:
        st.warning("No database is currently connected.")

    st.divider()

    st.markdown("### Observability")

    if settings.langsmith_tracing:
        st.success("LangSmith tracing is enabled.")
        st.write(
            f"**Project:** {settings.langsmith_project}"
        )
    else:
        st.info("LangSmith tracing is disabled.")

    st.caption(
        "To change environment variables, update your .env file "
        "and restart the application."
    )


# ============================================================
# QUERY HISTORY
# ============================================================

def render_query_history_page():
    """Display previous conversations."""

    st.title("Query History")

    st.caption(
        "Review questions and responses from the current session."
    )

    messages = st.session_state.get("chat_messages", [])

    user_queries = [
        message
        for message in messages
        if message.get("role") == "user"
    ]

    if not user_queries:
        st.info("No query history is available yet.")
        return

    st.markdown(f"### {len(user_queries)} Question(s)")

    for index, message in enumerate(user_queries, start=1):

        question = message.get("content", "")

        with st.expander(
            f"Query {index}: {question[:90]}"
        ):
            st.write(question)

    st.divider()

    st.caption(
        "Query history currently uses session state. "
        "It will not persist after the session is cleared."
    )


# ============================================================
# PAGE ROUTER
# ============================================================

def render_selected_page():
    """Render the selected dashboard page."""

    active_page = get_active_page()

    if active_page == "New Chat":
        render_chat_interface()

    elif active_page == "Database Connection":
        render_database_panel()

    elif active_page == "Schema Explorer":
        render_schema_explorer()

    elif active_page == "SQL Workspace":
        render_sql_editor()

    elif active_page == "Query History":
        render_query_history_page()

    elif active_page == "Settings":
        render_settings_page()

    else:
        render_chat_interface()


# ============================================================
# MAIN APPLICATION
# ============================================================

def main():
    """Start the AURORA SQL Agent application."""

    initialize_app_state()

    apply_global_styles()

    render_sidebar(
        database_connected=st.session_state.database_connected
    )

    render_selected_page()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
