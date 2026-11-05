
"""
AURORA SQL Agent
Database Connection Panel

Provides a Streamlit interface for connecting to PostgreSQL
and MySQL databases.
"""

import streamlit as st

from database.connection import (
    DatabaseConnectionConfig,
    DatabaseConnectionError,
    database_manager,
)


DATABASE_DEFAULTS = {
    "postgresql": {
        "port": 5432,
        "label": "PostgreSQL",
    },
    "mysql": {
        "port": 3306,
        "label": "MySQL",
    },
}


def _initialize_database_state():
    """Initialize database-related session state."""

    defaults = {
        "database_connected": False,
        "database_type": None,
        "database_name": None,
        "database_schema": None,
        "database_config": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _build_connection_config(
    database_type,
    host,
    port,
    database,
    username,
    password,
    schema,
    ssl_mode,
):
    """Build the database connection configuration."""

    return DatabaseConnectionConfig(
        database_type=database_type,
        host=host.strip(),
        port=int(port),
        database=database.strip(),
        username=username.strip(),
        password=password,
        schema=schema.strip() or None,
        ssl_mode=ssl_mode or None,
    )


def _show_connection_details():
    """Display the current database connection details."""

    st.markdown("### Active Database Connection")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Database Type**")
        st.write(
            DATABASE_DEFAULTS.get(
                st.session_state.database_type,
                {},
            ).get("label", "Unknown")
        )

        st.markdown("**Database Name**")
        st.write(st.session_state.database_name or "Not available")

    with col2:
        st.markdown("**Schema**")
        st.write(st.session_state.database_schema or "Default")

        st.markdown("**Connection Status**")
        st.success("Connected")

    st.divider()

    if st.button(
        "Disconnect Database",
        type="secondary",
        width="stretch",
        key="disconnect_database",
    ):
        try:
            database_manager.close()

            st.session_state.database_connected = False
            st.session_state.database_type = None
            st.session_state.database_name = None
            st.session_state.database_schema = None
            st.session_state.database_config = None

            st.success("Database disconnected successfully.")
            st.rerun()

        except Exception as exc:
            st.error(f"Unable to disconnect database: {exc}")


def _test_connection(config):
    """Test the supplied database configuration."""

    try:
        result = database_manager.test_connection(config)

        # Support boolean, tuple and dictionary responses.
        if isinstance(result, tuple):
            success = bool(result[0])
            message = (
                result[1]
                if len(result) > 1
                else "Connection test completed."
            )

        elif isinstance(result, dict):
            success = bool(
                result.get("success", result.get("connected", False))
            )
            message = result.get(
                "message",
                "Connection test completed.",
            )

        elif isinstance(result, bool):
            success = result
            message = "Connection test completed."

        else:
            success = result is not None
            message = "Connection test completed."

        if success:
            st.success(f"Connection test successful. {message}")
        else:
            st.error(f"Connection test failed. {message}")

    except (DatabaseConnectionError, Exception) as exc:
        st.error(f"Connection test failed: {exc}")


def _connect_database(config):
    """Establish and save the database connection."""

    try:
        result = database_manager.connect(config)

        if result is False:
            st.error("Database connection could not be established.")
            return

        st.session_state.database_connected = True
        st.session_state.database_type = config.database_type
        st.session_state.database_name = config.database
        st.session_state.database_schema = config.schema
        st.session_state.database_config = config

        # Invalidate previously cached schema information.
        st.session_state["schema_metadata"] = {}
        st.session_state["schema_discovered"] = False

        st.success(
            f"Successfully connected to {config.database}."
        )

        st.rerun()

    except (DatabaseConnectionError, Exception) as exc:
        st.session_state.database_connected = False
        st.error(f"Database connection failed: {exc}")


def render_database_panel():
    """
    Render the database connection panel.

    Returns:
        bool: True if a database is currently connected.
    """

    _initialize_database_state()

    st.title("Database Connection")

    st.caption(
        "Connect your PostgreSQL or MySQL database "
        "to start querying your data using natural language."
    )

    st.divider()

    # Display existing connection.
    if st.session_state.database_connected:
        _show_connection_details()
        return True

    st.markdown("### Configure Database")

    with st.form("database_connection_form"):

        col1, col2 = st.columns(2)

        with col1:
            database_type = st.selectbox(
                "Database Type",
                options=["postgresql", "mysql"],
                format_func=lambda value: DATABASE_DEFAULTS[value]["label"],
                key="db_type_input",
            )

            host = st.text_input(
                "Host",
                value="localhost",
                placeholder="localhost or database server address",
            )

            port = st.number_input(
                "Port",
                min_value=1,
                max_value=65535,
                value=DATABASE_DEFAULTS[database_type]["port"],
                step=1,
            )

            database = st.text_input(
                "Database Name",
                placeholder="Enter database name",
            )

        with col2:
            username = st.text_input(
                "Username",
                placeholder="Enter database username",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter database password",
            )

            schema = st.text_input(
                "Schema (Optional)",
                placeholder="public",
                help=(
                    "PostgreSQL schema or database-specific "
                    "schema setting. Leave blank for the default."
                ),
            )

            ssl_mode = st.selectbox(
                "SSL Mode",
                options=["Default", "require", "prefer", "disable"],
                help="Choose the SSL connection preference.",
            )

        st.divider()

        test_col, connect_col = st.columns(2)

        with test_col:
            test_submitted = st.form_submit_button(
                "Test Connection",
                width="stretch",
            )

        with connect_col:
            connect_submitted = st.form_submit_button(
                "Connect to Database",
                type="primary",
                width="stretch",
            )

    if test_submitted or connect_submitted:

        # Basic input validation.
        if not host.strip():
            st.error("Please enter the database host.")

        elif not database.strip():
            st.error("Please enter the database name.")

        elif not username.strip():
            st.error("Please enter the database username.")

        elif not password:
            st.error("Please enter the database password.")

        else:
            try:
                config = _build_connection_config(
                    database_type=database_type,
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password=password,
                    schema=schema,
                    ssl_mode=(
                        None if ssl_mode == "Default" else ssl_mode
                    ),
                )

                if test_submitted:
                    _test_connection(config)

                elif connect_submitted:
                    _connect_database(config)

            except (ValueError, TypeError) as exc:
                st.error(f"Invalid database configuration: {exc}")

    st.divider()

    st.info(
        "Security note: Use a dedicated database account with "
        "read-only permissions. AURORA SQL Agent is designed "
        "for read-only query execution."
    )

    return st.session_state.database_connected
