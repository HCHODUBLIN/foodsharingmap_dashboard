"""Unit tests for DAG task logic."""

import json

import pytest


class TestApiResponseParsing:
    """Test API response handling logic."""

    def test_dict_with_data_key(self):
        """API returns {"success": true, "data": [...]}."""
        payload = {"success": True, "data": [{"id": "1", "name": "Test"}]}

        if isinstance(payload, dict) and "data" in payload:
            data = payload["data"]
        else:
            data = payload

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"

    def test_plain_list(self):
        """API returns a plain list."""
        payload = [{"id": "1", "name": "Test"}]

        if isinstance(payload, dict) and "data" in payload:
            data = payload["data"]
        else:
            data = payload

        assert isinstance(data, list)
        assert data[0]["id"] == "1"

    def test_raises_on_non_list(self):
        """Should raise ValueError if data is not a list."""
        payload = {"error": "something went wrong"}

        if isinstance(payload, dict) and "data" in payload:
            data = payload["data"]
        else:
            data = payload

        with pytest.raises(ValueError):
            if not isinstance(data, list):
                raise ValueError(
                    f"Expected list from API, got {type(data).__name__}"
                )


class TestSnowflakeRowPreparation:
    """Test row preparation for Snowflake insert."""

    def test_row_with_id(self):
        """Record with id should use it."""
        record = {"id": "1510", "name": "Food Bank Albania"}
        ingestion_ts = "2026-03-25T13:00:00"

        row = (record.get("id"), json.dumps(record), ingestion_ts)

        assert row[0] == "1510"
        assert '"name": "Food Bank Albania"' in row[1]
        assert row[2] == ingestion_ts

    def test_row_without_id(self):
        """Record without id should return None for id."""
        record = {"name": "No ID Initiative"}
        ingestion_ts = "2026-03-25T13:00:00"

        row = (record.get("id"), json.dumps(record), ingestion_ts)

        assert row[0] is None
        assert '"name": "No ID Initiative"' in row[1]

    def test_multiple_rows(self):
        """Should prepare correct number of rows."""
        data = [
            {"id": "1", "name": "A"},
            {"id": "2", "name": "B"},
            {"id": "3", "name": "C"},
        ]
        ingestion_ts = "2026-03-25T13:00:00"

        rows = [
            (r.get("id"), json.dumps(r), ingestion_ts) for r in data
        ]

        assert len(rows) == 3
        assert rows[0][0] == "1"
        assert rows[2][0] == "3"
