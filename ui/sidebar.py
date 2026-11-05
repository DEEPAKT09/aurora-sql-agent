
"""
AURORA SQL Agent
Sidebar UI

Responsibilities:
- Render the application sidebar.
- Display application branding.
- Provide dashboard navigation.
- Display database connection status.
- Provide a New Chat action.
- Display application information.
"""

import streamlit as st


# --------------------------------------------------
# Sidebar configuration
# --------------------------------------------------

NAVIGATION_ITEMS = [
    "New Chat",
    "Database Connection",
    "Schema Explorer",
    "SQL Workspace",
    "Query History",
    "Settings",
]


# --------------------------------------------------
# Sidebar styling
# --------------------------------------------------

def _apply_sidebar_styles():
    """Apply custom styling to the sidebar."""

    st.markdown(
        """
        <style>
        /* Sidebar background */
        section[data-testid="stSidebar"] {
            background-color: #211638;
            border-right: 1px solid #35264f;
        }

        section[data-testid="stSidebar"] > div {
            background-color: #211638;
        }

        /* Sidebar text */
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: #e8e2f3;
        }

        /* Branding */
        .aurora-sidebar-brand {
            padding: 12px 8px 22px 8px;
        }

        .aurora-sidebar-title {
            color: #ffffff;
            font-size: 23px;
            font-weight: 750;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        }

        .aurora-sidebar-subtitle {
            color: #b8a9d2;
            font-size: 12px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }

        .aurora-sidebar-divider {
            border: none;
            border-top: 1px solid #403253;
            margin: 12px 0 18px 0;
        }

        .aurora-sidebar-section {
            color: #a995c8;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin: 18px 0 8px 8px;
        }

        .aurora-sidebar-status {
            display: flex;
            align-items: center;
            gap: 9px;
            background-color: #302344;
            border: 1px solid #46365d;
            border-radius: 9px;
            padding: 11px 12px;
            margin-top: 8px;
            margin-bottom: 10px;
            font-size: 12px;
            color: #e8e2f3;
        }

        .aurora-status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
        }

        .aurora-status-connected {
            background-color: #32d296;
            box-shadow: 0 0 7px #32d296;
        }

        .aurora-status-disconnected {
            background-color: #f0a34a;
        }

        .aurora-sidebar-footer {
            color: #9584af;
            font-size: 11px;
            text-align: center;
            padding: 18px 5px 8px 5px;
        }

        /* Navigation radio buttons */
        section[data-testid="stSidebar"] div[role="radiogroup"] {
            gap: 5px;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            background-color: transparent;
            border-radius: 8px;
            padding: 9px 10px;
            transition: background-color 0.2s ease;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            background-color: #35264f;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {
            background-color: #55378a;
            border: 1px solid #7653b5;
        }

        /* Sidebar buttons */
        section[data-testid="stSidebar"] button {
            border-radius: 8px;
            font-weight: 600;
        }

        section[data-testid="stSidebar"] button[kind="primary"] {
            background-color: #7950c7;
            border: 1px solid #8963d4;
            color: white;
        }

        section[data-testid="stSidebar"] button[kind="primary"]:hover {
            background-color: #8b62d9;
            border-color: #9d79e4;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------
# Session state initialization
# --------------------------------------------------

def _initialize_sidebar_state():
    """Initialize sidebar-related session state."""

    defaults = {
        "active_page": "New Chat",
        "conversation_history": [],
        "query_history": [],
        "current_question": "",
        "generated_sql": "",
        "validated_sql": "",
        "execution_result": None,
        "result_analysis": None,
        "visualization": None,
        "chat_messages": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# --------------------------------------------------
# New Chat action
# --------------------------------------------------

def _start_new_chat():
    """Reset conversation-related state without disconnecting the database."""

    reset_keys = [
        "conversation_history",
        "current_question",
        "generated_sql",
        "validated_sql",
        "execution_result",
        "result_analysis",
        "visualization",
        "chat_messages",
        "sql_valid",
        "validation_result",
        "validation_error",
        "execution_success",
        "execution_error",
        "analysis_success",
        "analysis_error",
        "visualization_success",
        "visualization_skipped",
        "workflow_status",
        "current_agent",
        "last_workflow_state",
        "clarification_needed",
        "clarification_question",
    ]

    for key in reset_keys:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state["active_page"] = "New Chat"


# --------------------------------------------------
# Sidebar rendering
# --------------------------------------------------

def render_sidebar(
    database_connected: bool = False,
) -> str:
    """
    Render the complete application sidebar.

    Args:
        database_connected:
            Current database connection status.

    Returns:
        Selected navigation page.
    """

    _initialize_sidebar_state()
    _apply_sidebar_styles()

    with st.sidebar:

        # Application branding
        st.markdown(
            """
            <div class="aurora-sidebar-brand">
                <div class="aurora-sidebar-title">
                    ✦ AURORA
                </div>
                <div class="aurora-sidebar-subtitle">
                    SQL Agent
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<hr class="aurora-sidebar-divider">',
            unsafe_allow_html=True,
        )

        # # New Chat button
        # if st.button(
        #     "＋  New Chat",
        #     key="sidebar_new_chat",
        #     type="primary",
        #     width="stretch",
        # ):
        #     _start_new_chat()
        #     st.rerun()

        # Navigation
        st.markdown(
            '<div class="aurora-sidebar-section">Workspace</div>',
            unsafe_allow_html=True,
        )

        current_page = st.session_state.get(
            "active_page",
            "New Chat",
        )

        selected_page = st.radio(
            "Navigation",
            options=NAVIGATION_ITEMS,
            index=NAVIGATION_ITEMS.index(current_page)
            if current_page in NAVIGATION_ITEMS
            else 0,
            key="sidebar_navigation",
            label_visibility="collapsed",
            format_func=lambda item: {
                "New Chat": "💬  Chat",
                "Database Connection": "🔌  Database Connection",
                "Schema Explorer": "🗂️  Schema Explorer",
                "SQL Workspace": "⌨️  SQL Workspace",
                "Query History": "🕘  Query History",
                "Settings": "⚙️  Settings",
            }.get(item, item),
        )

        st.session_state["active_page"] = selected_page
        # Show New Chat only on the Chat page.
        if selected_page == "New Chat":
            if st.button(
                "＋  New Chat",
                key="sidebar_new_chat",
                type="primary",
                width="stretch",
            ):
                _start_new_chat()
                st.rerun()

        st.markdown(
            '<hr class="aurora-sidebar-divider">',
            unsafe_allow_html=True,
        )

        # Database status
        st.markdown(
            '<div class="aurora-sidebar-section">Database Status</div>',
            unsafe_allow_html=True,
        )

        if database_connected:
            status_html = """
            <div class="aurora-sidebar-status">
                <span class="aurora-status-dot aurora-status-connected"></span>
                <span>Database Connected</span>
            </div>
            """
        else:
            status_html = """
            <div class="aurora-sidebar-status">
                <span class="aurora-status-dot aurora-status-disconnected"></span>
                <span>Database Disconnected</span>
            </div>
            """

        st.markdown(
            status_html,
            unsafe_allow_html=True,
        )

        # Application information
        st.markdown(
            '<hr class="aurora-sidebar-divider">',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="aurora-sidebar-footer">
                <div><b>AURORA SQL Agent</b></div>
                <div>Version 1.0.0</div>
                <div style="margin-top: 7px;">
                    Intelligent Natural Language to SQL
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return selected_page


# --------------------------------------------------
# Public helper
# --------------------------------------------------

def get_active_page() -> str:
    """Return the currently selected navigation page."""

    return st.session_state.get(
        "active_page",
        "New Chat",
    )
