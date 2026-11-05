
"""
AURORA SQL Agent
Schema Explorer

Displays database schemas, tables, views, columns,
relationships, primary keys, foreign keys and indexes.
"""

import streamlit as st

from database.metadata import (
    MetadataError,
    metadata_manager,
)


def _initialize_schema_state():
    """Initialize schema explorer session state."""

    defaults = {
        "schema_metadata": {},
        "schema_discovered": False,
        "selected_schema": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_value(data, *keys, default=None):
    """Safely retrieve a value from a dictionary."""

    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data:
            return data[key]

    return default


def _normalize_list(value):
    """Normalize metadata values into a list."""

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, dict):
        return [value]

    return []


def _get_schema_names(metadata):
    """Extract available schema names."""

    schemas = _get_value(
        metadata,
        "schemas",
        "schema_names",
        default=[],
    )

    if isinstance(schemas, dict):
        return list(schemas.keys())

    return [
        item if isinstance(item, str)
        else item.get("name", item.get("schema_name", ""))
        for item in _normalize_list(schemas)
        if isinstance(item, (str, dict))
    ]



def _get_tables(metadata):
    """Extract table names together with their detailed metadata."""

    tables = _get_value(
        metadata,
        "tables",
        "table_metadata",
        default=[],
    )

    table_details = metadata.get("table_details", {})

    if not isinstance(table_details, dict):
        table_details = {}

    if isinstance(tables, dict):
        table_items = [
            dict(value, name=key) if isinstance(value, dict)
            else {"name": key}
            for key, value in tables.items()
        ]
    else:
        table_items = _normalize_list(tables)

    result = []

    for table in table_items:
        if isinstance(table, str):
            table = {"name": table}

        if not isinstance(table, dict):
            continue

        table_name = _get_value(
            table,
            "name",
            "table_name",
            default=None,
        )

        if not table_name:
            continue

        details = table_details.get(table_name, {})

        if not isinstance(details, dict):
            details = {}

        result.append({
            **details,
            **table,
            "name": table_name,
            "columns": details.get(
                "columns",
                table.get("columns", []),
            ),
            "primary_keys": details.get(
                "primary_keys",
                table.get("primary_keys", []),
            ),
            "foreign_keys": details.get(
                "foreign_keys",
                table.get("foreign_keys", []),
            ),
            "indexes": details.get(
                "indexes",
                table.get("indexes", []),
            ),
        })

    return result




def _get_views(metadata):
    """Extract view names together with their detailed metadata."""

    views = _get_value(
        metadata,
        "views",
        "view_metadata",
        default=[],
    )

    view_details = metadata.get("view_details", {})

    if not isinstance(view_details, dict):
        view_details = {}

    if isinstance(views, dict):
        view_items = [
            dict(value, name=key) if isinstance(value, dict)
            else {"name": key}
            for key, value in views.items()
        ]
    else:
        view_items = _normalize_list(views)

    result = []

    for view in view_items:
        if isinstance(view, str):
            view = {"name": view}

        if not isinstance(view, dict):
            continue

        view_name = _get_value(
            view,
            "name",
            "view_name",
            default=None,
        )

        if not view_name:
            continue

        details = view_details.get(view_name, {})

        if not isinstance(details, dict):
            details = {}

        result.append({
            **details,
            **view,
            "name": view_name,
            "columns": details.get(
                "columns",
                view.get("columns", []),
            ),
        })

    return result



def _get_columns(table_metadata):
    """Extract column information from a table."""

    columns = _get_value(
        table_metadata,
        "columns",
        "column_metadata",
        default=[],
    )

    if isinstance(columns, dict):
        return [
            dict(value, name=key) if isinstance(value, dict)
            else {"name": key, "data_type": str(value)}
            for key, value in columns.items()
        ]

    return _normalize_list(columns)


def _render_column_table(columns):
    """Display table columns and their properties."""

    if not columns:
        st.caption("No column information available.")
        return

    rows = []

    for column in columns:
        if isinstance(column, str):
            rows.append({
                "Column": column,
                "Data Type": "Unknown",
                "Nullable": "Unknown",
                "Default": "-",
                "Primary Key": "No",
            })
            continue

        name = _get_value(
            column,
            "name",
            "column_name",
            default="Unknown",
        )

        data_type = _get_value(
            column,
            "type",
            "data_type",
            default="Unknown",
        )

        nullable = _get_value(
            column,
            "nullable",
            "is_nullable",
            default=None,
        )

        default = _get_value(
            column,
            "default",
            "column_default",
            default="-",
        )

        primary_key = _get_value(
            column,
            "primary_key",
            "is_primary_key",
            default=False,
        )

        rows.append({
            "Column": str(name),
            "Data Type": str(data_type),
            "Nullable": (
                "Yes" if nullable is True
                else "No" if nullable is False
                else "Unknown"
            ),
            "Default": str(default) if default is not None else "-",
            "Primary Key": "Yes" if primary_key else "No",
        })

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )


def _render_primary_keys(table_metadata):
    """Display primary key information."""

    primary_keys = _get_value(
        table_metadata,
        "primary_keys",
        "primary_key",
        default=[],
    )

    if isinstance(primary_keys, str):
        primary_keys = [primary_keys]

    elif isinstance(primary_keys, dict):
        primary_keys = _get_value(
            primary_keys,
            "constrained_columns",
            "columns",
            default=[],
        )

    primary_keys = _normalize_list(primary_keys)

    if primary_keys:
        st.write(", ".join(str(key) for key in primary_keys))
    else:
        st.caption("No primary key information available.")


def _render_foreign_keys(table_metadata):
    """Display foreign key relationships."""

    foreign_keys = _get_value(
        table_metadata,
        "foreign_keys",
        "relationships",
        default=[],
    )

    foreign_keys = _normalize_list(foreign_keys)

    if not foreign_keys:
        st.caption("No foreign key relationships found.")
        return

    rows = []

    for foreign_key in foreign_keys:
        if isinstance(foreign_key, str):
            rows.append({
                "Column": foreign_key,
                "Referenced Table": "Unknown",
                "Referenced Column": "Unknown",
            })
            continue

        local_columns = _get_value(
            foreign_key,
            "constrained_columns",
            "columns",
            "column",
            default=[],
        )

        if isinstance(local_columns, str):
            local_columns = [local_columns]

        referred_columns = _get_value(
            foreign_key,
            "referred_columns",
            "referenced_columns",
            default=[],
        )

        if isinstance(referred_columns, str):
            referred_columns = [referred_columns]

        referred_table = _get_value(
            foreign_key,
            "referred_table",
            "referenced_table",
            "target_table",
            default="Unknown",
        )

        rows.append({
            "Column": ", ".join(map(str, local_columns)),
            "Referenced Table": str(referred_table),
            "Referenced Column": ", ".join(
                map(str, referred_columns)
            ),
        })

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )


def _render_indexes(table_metadata):
    """Display table indexes."""

    indexes = _get_value(
        table_metadata,
        "indexes",
        "index_metadata",
        default=[],
    )

    indexes = _normalize_list(indexes)

    if not indexes:
        st.caption("No index information available.")
        return

    rows = []

    for index in indexes:
        if isinstance(index, str):
            rows.append({
                "Index Name": index,
                "Columns": "Unknown",
                "Unique": "Unknown",
            })
            continue

        columns = _get_value(
            index,
            "column_names",
            "columns",
            default=[],
        )

        if isinstance(columns, str):
            columns = [columns]

        unique = _get_value(
            index,
            "unique",
            "is_unique",
            default=None,
        )

        rows.append({
            "Index Name": _get_value(
                index,
                "name",
                "index_name",
                default="Unknown",
            ),
            "Columns": ", ".join(map(str, columns)),
            "Unique": (
                "Yes" if unique is True
                else "No" if unique is False
                else "Unknown"
            ),
        })

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )


def _render_table_details(table_metadata):
    """Render detailed information for an individual table."""

    columns = _get_columns(table_metadata)

    tab_columns, tab_primary, tab_foreign, tab_indexes = st.tabs(
        [
            "Columns",
            "Primary Keys",
            "Foreign Keys",
            "Indexes",
        ]
    )

    with tab_columns:
        _render_column_table(columns)

    with tab_primary:
        _render_primary_keys(table_metadata)

    with tab_foreign:
        _render_foreign_keys(table_metadata)

    with tab_indexes:
        _render_indexes(table_metadata)


def _render_tables(metadata, heading="Tables"):
    """Render all tables in expandable sections."""

    tables = _get_tables(metadata)

    st.markdown(f"### {heading}")

    if not tables:
        st.info("No tables found in this schema.")
        return

    st.caption(f"{len(tables)} table(s) found.")

    for table in tables:

        if isinstance(table, str):
            table = {"name": table}

        table_name = _get_value(
            table,
            "name",
            "table_name",
            default="Unknown Table",
        )

        columns = _get_columns(table)

        with st.expander(
            f"📋 {table_name}  ·  {len(columns)} columns"
        ):
            _render_table_details(table)


def _render_views(metadata):
    """Render database views."""

    views = _get_views(metadata)

    st.markdown("### Views")

    if not views:
        st.caption("No views found.")
        return

    for view in views:

        if isinstance(view, str):
            view = {"name": view}

        view_name = _get_value(
            view,
            "name",
            "view_name",
            default="Unknown View",
        )

        with st.expander(f"👁️ {view_name}"):
            columns = _get_columns(view)
            _render_column_table(columns)


def _discover_metadata(schema=None, force_refresh=False):
    """Discover or retrieve database schema metadata."""

    try:
        if force_refresh:
            metadata_manager.invalidate_cache()

        metadata = metadata_manager.get_schema_metadata(
            schema=schema,
            include_views=True,
        )

        if not isinstance(metadata, dict):
            raise MetadataError(
                "The schema discovery service returned an invalid response."
            )

        st.session_state.schema_metadata = metadata
        st.session_state.schema_discovered = True
        st.session_state.selected_schema = schema

        return metadata

    except Exception as exc:
        st.session_state.schema_discovered = False
        st.error(f"Schema discovery failed: {exc}")
        return None


def render_schema_explorer():
    """
    Render the database schema explorer.

    Returns:
        dict: Discovered schema metadata, or an empty dictionary.
    """

    _initialize_schema_state()

    st.title("Schema Explorer")

    st.caption(
        "Explore database schemas, tables, columns, "
        "relationships and indexes."
    )

    if not st.session_state.get("database_connected", False):
        st.warning(
            "Connect to a database before exploring its schema."
        )
        st.info(
            "Open the Database Connection page from the sidebar "
            "to establish a connection."
        )
        return {}

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### Database Structure")

    with col2:
        refresh_clicked = st.button(
            "↻ Refresh Schema",
            width="stretch",
        )

    # Retrieve cached metadata or discover the schema.
    metadata = st.session_state.get("schema_metadata", {})

    if refresh_clicked or not st.session_state.schema_discovered:
        metadata = _discover_metadata(
            schema=st.session_state.get("database_schema"),
            force_refresh=refresh_clicked,
        )

    if not metadata:
        st.info("No schema metadata is currently available.")
        return {}

    # Database overview.
    tables = _get_tables(metadata)
    views = _get_views(metadata)

    total_columns = sum(
        len(_get_columns(table))
        for table in tables
        if isinstance(table, dict)
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Tables", len(tables))
    col2.metric("Views", len(views))
    col3.metric("Columns", total_columns)

    st.divider()

    # Schema selection.
    schemas = _get_schema_names(metadata)

    selected_schema = st.session_state.get(
        "selected_schema"
    )

    if schemas:
        schema_options = ["All Schemas"] + schemas

        current_index = (
            schema_options.index(selected_schema)
            if selected_schema in schema_options
            else 0
        )

        selected_schema = st.selectbox(
            "Select Schema",
            options=schema_options,
            index=current_index,
            key="schema_selector",
        )

        if selected_schema == "All Schemas":
            selected_schema = None

        if selected_schema != st.session_state.get(
            "selected_schema"
        ):
            metadata = _discover_metadata(
                schema=selected_schema,
                force_refresh=False,
            )

            if not metadata:
                return {}

    st.divider()

    # Render database objects.
    _render_tables(metadata)
    st.divider()
    _render_views(metadata)

    return metadata
