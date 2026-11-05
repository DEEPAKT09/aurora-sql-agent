
"""
AURORA SQL Agent
Database Metadata Manager

Responsibilities:
- Retrieve database schema metadata.
- Cache discovered schema information.
- Avoid repeated database inspection.
- Refresh metadata when requested.
- Provide table and column information.
- Search relevant tables and columns.
- Generate schema context for AI agents.
"""

import copy
import threading
import time

from typing import Any, Optional

from database.schema_discovery import (
    SchemaDiscovery,
    SchemaDiscoveryError,
    schema_discovery,
)


class MetadataError(Exception):
    """Raised when metadata operations fail."""


class SchemaMetadataManager:
    """Manages and caches database schema metadata."""

    def __init__(
        self,
        discovery: Optional[SchemaDiscovery] = None,
        cache_ttl: int = 300,
    ):
        self.discovery = discovery or schema_discovery
        self.cache_ttl = cache_ttl

        self._cache: dict[str, Any] = {}
        self._cache_timestamp: dict[str, float] = {}
        self._lock = threading.RLock()

    def _get_cache_key(
        self,
        schema: Optional[str],
        include_views: bool,
    ) -> str:
        """Generate a unique cache key for the active database."""

        engine = self.discovery.get_engine()

        return (
            f"{id(engine)}:"
            f"{engine.url.database}:"
            f"{schema or 'default'}:"
            f"{include_views}"
        )

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check whether cached metadata is still valid."""

        if cache_key not in self._cache:
            return False

        timestamp = self._cache_timestamp.get(cache_key, 0)

        return (time.monotonic() - timestamp) < self.cache_ttl

    def get_schema_metadata(
        self,
        schema: Optional[str] = None,
        include_views: bool = True,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieve complete schema metadata.

        Returns cached metadata when available.
        Set refresh=True to force a fresh database inspection.
        """

        try:
            cache_key = self._get_cache_key(
                schema,
                include_views,
            )

            with self._lock:

                if (
                    not refresh
                    and self._is_cache_valid(cache_key)
                ):
                    return copy.deepcopy(self._cache[cache_key])

                metadata = self.discovery.discover_schema(
                    schema=schema,
                    include_views=include_views,
                )

                self._cache[cache_key] = copy.deepcopy(metadata)

                self._cache_timestamp[cache_key] = (
                    time.monotonic()
                )

                return copy.deepcopy(metadata)

        except SchemaDiscoveryError as exc:
            raise MetadataError(
                "Unable to retrieve database metadata."
            ) from exc

        except Exception as exc:
            raise MetadataError(
                "An unexpected error occurred while retrieving metadata."
            ) from exc

    def get_tables(
        self,
        schema: Optional[str] = None,
        refresh: bool = False,
    ) -> list[str]:
        """Return all available table names."""

        metadata = self.get_schema_metadata(
            schema=schema,
            refresh=refresh,
        )

        return metadata["tables"]

    def get_views(
        self,
        schema: Optional[str] = None,
        refresh: bool = False,
    ) -> list[str]:
        """Return all available view names."""

        metadata = self.get_schema_metadata(
            schema=schema,
            include_views=True,
            refresh=refresh,
        )

        return metadata["views"]

    def get_table_metadata(
        self,
        table_name: str,
        schema: Optional[str] = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Retrieve metadata for a specific table."""

        metadata = self.get_schema_metadata(
            schema=schema,
            refresh=refresh,
        )

        table_details = metadata["table_details"]

        if table_name not in table_details:
            raise MetadataError(
                f"Table '{table_name}' was not found."
            )

        return table_details[table_name]

    def get_table_columns(
        self,
        table_name: str,
        schema: Optional[str] = None,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve columns belonging to a table."""

        table_metadata = self.get_table_metadata(
            table_name,
            schema,
            refresh,
        )

        return table_metadata["columns"]

    def get_all_relationships(
        self,
        schema: Optional[str] = None,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve all foreign key relationships."""

        metadata = self.get_schema_metadata(
            schema=schema,
            refresh=refresh,
        )

        return metadata["relationships"]

    def search_tables(
        self,
        search_term: str,
        schema: Optional[str] = None,
    ) -> list[str]:
        """Search table names using case-insensitive matching."""

        metadata = self.get_schema_metadata(schema=schema)

        search_term = search_term.strip().lower()

        if not search_term:
            return metadata["tables"]

        return [
            table
            for table in metadata["tables"]
            if search_term in table.lower()
        ]

    def search_columns(
        self,
        search_term: str,
        schema: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """Search column names across all discovered tables."""

        metadata = self.get_schema_metadata(schema=schema)

        search_term = search_term.strip().lower()

        results = []

        for table_name, details in metadata[
            "table_details"
        ].items():

            for column in details["columns"]:

                if (
                    not search_term
                    or search_term in column["name"].lower()
                ):
                    results.append({
                        "table": table_name,
                        "column": column["name"],
                        "type": column["type"],
                    })

        return results

    def get_schema_context(
        self,
        schema: Optional[str] = None,
        refresh: bool = False,
    ) -> str:
        """
        Generate a readable schema context for LLM prompts.

        This context helps the SQL Generation Agent identify
        actual tables, columns and relationships.
        """

        metadata = self.get_schema_metadata(
            schema=schema,
            refresh=refresh,
        )

        return self.discovery.get_schema_summary(metadata)

    def get_metadata_summary(
        self,
        schema: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return a compact database overview."""

        metadata = self.get_schema_metadata(schema=schema)

        total_columns = sum(
            len(details["columns"])
            for details in metadata["table_details"].values()
        )

        return {
            "database_type": metadata["database_type"],
            "database_name": metadata["database_name"],
            "schema": metadata["schema"],
            "table_count": metadata["table_count"],
            "view_count": metadata["view_count"],
            "column_count": total_columns,
            "relationship_count": len(
                metadata["relationships"]
            ),
            "tables": metadata["tables"],
            "views": metadata["views"],
        }

    def invalidate_cache(
        self,
        schema: Optional[str] = None,
    ) -> None:
        """
        Invalidate cached metadata.

        If schema is provided, invalidate entries for that schema.
        Otherwise, clear all cached metadata.
        """

        with self._lock:

            if schema is None:
                self._cache.clear()
                self._cache_timestamp.clear()
                return

            matching_keys = [
                key
                for key in self._cache
                if key.endswith(f":{schema}:True")
                or key.endswith(f":{schema}:False")
            ]

            for key in matching_keys:
                self._cache.pop(key, None)
                self._cache_timestamp.pop(key, None)

    def clear_cache(self) -> None:
        """Clear all cached metadata."""

        self.invalidate_cache()

    def get_cache_status(self) -> dict[str, Any]:
        """Return cache information for debugging."""

        with self._lock:

            current_time = time.monotonic()

            entries = []

            for key, timestamp in self._cache_timestamp.items():

                age = current_time - timestamp

                entries.append({
                    "key": key,
                    "age_seconds": round(age, 2),
                    "valid": age < self.cache_ttl,
                })

            return {
                "cache_entries": len(entries),
                "cache_ttl_seconds": self.cache_ttl,
                "entries": entries,
            }


# Shared metadata manager instance
metadata_manager = SchemaMetadataManager()
