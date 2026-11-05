
"""
AURORA SQL Agent
Database Schema Discovery

Automatically discovers database metadata for PostgreSQL
and MySQL using SQLAlchemy inspection.

Provides:
- Schema discovery
- Table and view discovery
- Column metadata
- Primary keys
- Foreign keys
- Table relationships
- Index information
"""

from typing import Any, Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from database.connection import (
    database_manager,
    DatabaseConnectionError,
)


class SchemaDiscoveryError(Exception):
    """Raised when database schema discovery fails."""


class SchemaDiscovery:
    """Discovers and retrieves database schema information."""

    def __init__(self, engine: Optional[Engine] = None):
        self.engine = engine

    def get_engine(self) -> Engine:
        """Return the configured or active database engine."""

        if self.engine is not None:
            return self.engine

        return database_manager.get_engine()

    def get_inspector(self):
        """Create a SQLAlchemy database inspector."""

        return inspect(self.get_engine())

    def get_default_schema(self) -> Optional[str]:
        """Return the database's default schema."""

        engine = self.get_engine()
        dialect = engine.dialect.name

        if dialect == "postgresql":
            return "public"

        if dialect == "mysql":
            return None

        return None

    def get_schemas(self) -> list[str]:
        """Retrieve available database schemas."""

        try:
            inspector = self.get_inspector()

            if inspector.engine.dialect.name == "mysql":
                return [database_manager.get_database_name()]

            schemas = inspector.get_schema_names()

            excluded_schemas = {
                "information_schema",
                "pg_catalog",
                "pg_toast",
            }

            return [
                schema
                for schema in schemas
                if schema not in excluded_schemas
            ]

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                "Unable to retrieve database schemas."
            ) from exc

    def get_tables(
        self,
        schema: Optional[str] = None
    ) -> list[str]:
        """Retrieve table names."""

        try:
            inspector = self.get_inspector()

            if schema is None:
                schema = self.get_default_schema()

            return inspector.get_table_names(schema=schema)

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                "Unable to retrieve database tables."
            ) from exc

    def get_views(
        self,
        schema: Optional[str] = None
    ) -> list[str]:
        """Retrieve database view names."""

        try:
            inspector = self.get_inspector()

            if schema is None:
                schema = self.get_default_schema()

            return inspector.get_view_names(schema=schema)

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                "Unable to retrieve database views."
            ) from exc

    def get_columns(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Retrieve column metadata for a table."""

        try:
            inspector = self.get_inspector()

            columns = inspector.get_columns(
                table_name,
                schema=schema
            )

            result = []

            for column in columns:
                result.append({
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": column.get("nullable", True),
                    "default": str(column.get("default"))
                    if column.get("default") is not None
                    else None,
                    "primary_key": False,
                    "autoincrement": column.get("autoincrement"),
                    "comment": column.get("comment"),
                })

            primary_key = inspector.get_pk_constraint(
                table_name,
                schema=schema
            )

            primary_key_columns = set(
                primary_key.get("constrained_columns") or []
            )

            for column in result:
                column["primary_key"] = (
                    column["name"] in primary_key_columns
                )

            return result

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                f"Unable to retrieve columns for table '{table_name}'."
            ) from exc

    def get_primary_keys(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> list[str]:
        """Retrieve primary key column names."""

        try:
            inspector = self.get_inspector()

            primary_key = inspector.get_pk_constraint(
                table_name,
                schema=schema
            )

            return primary_key.get("constrained_columns") or []

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                f"Unable to retrieve primary keys for '{table_name}'."
            ) from exc

    def get_foreign_keys(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Retrieve foreign key relationships."""

        try:
            inspector = self.get_inspector()

            foreign_keys = inspector.get_foreign_keys(
                table_name,
                schema=schema
            )

            result = []

            for foreign_key in foreign_keys:
                result.append({
                    "name": foreign_key.get("name"),
                    "constrained_columns": (
                        foreign_key.get("constrained_columns") or []
                    ),
                    "referred_schema": foreign_key.get(
                        "referred_schema"
                    ),
                    "referred_table": foreign_key.get(
                        "referred_table"
                    ),
                    "referred_columns": (
                        foreign_key.get("referred_columns") or []
                    ),
                })

            return result

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                f"Unable to retrieve foreign keys for '{table_name}'."
            ) from exc

    def get_indexes(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Retrieve index information for a table."""

        try:
            inspector = self.get_inspector()

            indexes = inspector.get_indexes(
                table_name,
                schema=schema
            )

            return [
                {
                    "name": index.get("name"),
                    "columns": index.get("column_names") or [],
                    "unique": index.get("unique", False),
                }
                for index in indexes
            ]

        except SQLAlchemyError as exc:
            raise SchemaDiscoveryError(
                f"Unable to retrieve indexes for '{table_name}'."
            ) from exc

    def get_table_schema(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> dict[str, Any]:
        """Retrieve complete metadata for one table."""

        return {
            "table_name": table_name,
            "schema": schema or self.get_default_schema(),
            "columns": self.get_columns(table_name, schema),
            "primary_keys": self.get_primary_keys(
                table_name,
                schema
            ),
            "foreign_keys": self.get_foreign_keys(
                table_name,
                schema
            ),
            "indexes": self.get_indexes(
                table_name,
                schema
            ),
        }

    def discover_schema(
        self,
        schema: Optional[str] = None,
        include_views: bool = True
    ) -> dict[str, Any]:
        """
        Discover the complete database structure.

        Returns schemas, tables, views, columns,
        primary keys, foreign keys and relationships.
        """

        try:
            engine = self.get_engine()
            inspector = self.get_inspector()

            if schema is None:
                schema = self.get_default_schema()

            tables = self.get_tables(schema)
            views = self.get_views(schema) if include_views else []

            table_details = {}
            relationships = []

            for table_name in tables:
                details = self.get_table_schema(
                    table_name,
                    schema
                )

                table_details[table_name] = details

                for foreign_key in details["foreign_keys"]:
                    relationships.append({
                        "source_table": table_name,
                        "source_columns": foreign_key[
                            "constrained_columns"
                        ],
                        "target_table": foreign_key[
                            "referred_table"
                        ],
                        "target_schema": foreign_key[
                            "referred_schema"
                        ],
                        "target_columns": foreign_key[
                            "referred_columns"
                        ],
                    })

            view_details = {}

            for view_name in views:
                view_details[view_name] = {
                    "view_name": view_name,
                    "columns": self.get_columns(
                        view_name,
                        schema
                    ),
                }

            return {
                "database_type": engine.dialect.name,
                "database_name": database_manager.get_database_name()
                if self.engine is None
                else engine.url.database,
                "schema": schema,
                "schemas": self.get_schemas(),
                "tables": tables,
                "views": views,
                "table_details": table_details,
                "view_details": view_details,
                "relationships": relationships,
                "table_count": len(tables),
                "view_count": len(views),
            }

        except (SQLAlchemyError, DatabaseConnectionError) as exc:
            raise SchemaDiscoveryError(
                "Unable to discover the database schema. "
                "Check the database connection and permissions."
            ) from exc

    def get_schema_summary(
        self,
        schema_data: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Convert discovered metadata into a readable schema summary.

        This summary will later be provided to the SQL Generation Agent.
        """

        if schema_data is None:
            schema_data = self.discover_schema()

        lines = [
            f"Database Type: {schema_data['database_type']}",
            f"Database Name: {schema_data['database_name']}",
            f"Schema: {schema_data['schema']}",
            "",
            "DATABASE STRUCTURE",
            "==================",
        ]

        for table_name, details in schema_data[
            "table_details"
        ].items():

            lines.append(f"\nTable: {table_name}")

            for column in details["columns"]:
                attributes = []

                if column["primary_key"]:
                    attributes.append("PRIMARY KEY")

                if not column["nullable"]:
                    attributes.append("NOT NULL")

                attribute_text = (
                    f" ({', '.join(attributes)})"
                    if attributes
                    else ""
                )

                lines.append(
                    f"  - {column['name']}: "
                    f"{column['type']}{attribute_text}"
                )

            for foreign_key in details["foreign_keys"]:
                lines.append(
                    "  FOREIGN KEY: "
                    f"{foreign_key['constrained_columns']} -> "
                    f"{foreign_key['referred_table']}."
                    f"{foreign_key['referred_columns']}"
                )

        if schema_data["view_details"]:
            lines.append("\nDATABASE VIEWS")

            for view_name, details in schema_data[
                "view_details"
            ].items():
                lines.append(f"\nView: {view_name}")

                for column in details["columns"]:
                    lines.append(
                        f"  - {column['name']}: {column['type']}"
                    )

        return "\n".join(lines)


# Shared schema discovery instance
schema_discovery = SchemaDiscovery()
