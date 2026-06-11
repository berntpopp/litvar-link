"""Unit tests for NDJSON parsing and response normalization (DRY cluster #4)."""

from __future__ import annotations

from litvar_link.api.parsing import (
    extract_list,
    parse_ndjson,
)


class TestParseNdjson:
    def test_double_quoted_json_lines(self) -> None:
        text = '{"a": 1}\n{"b": 2}'
        assert parse_ndjson(text) == [{"a": 1}, {"b": 2}]

    def test_single_quote_python_dict_hack(self) -> None:
        # LitVar2 sometimes returns Python-style single-quoted dicts.
        text = "{'a': 1}\n{'b': 2}"
        assert parse_ndjson(text) == [{"a": 1}, {"b": 2}]

    def test_skips_unparseable_line(self) -> None:
        text = '{"a": 1}\nnot json at all'
        assert parse_ndjson(text) == [{"a": 1}]

    def test_blank_lines_ignored(self) -> None:
        assert parse_ndjson("\n\n") == []


class TestExtractList:
    def test_list_passthrough(self) -> None:
        assert extract_list([1, 2], key="results") == [1, 2]

    def test_dict_with_key(self) -> None:
        assert extract_list({"results": [1]}, key="results") == [1]

    def test_dict_without_key_returns_empty(self) -> None:
        assert extract_list({"other": 1}, key="results") == []

    def test_none_returns_empty(self) -> None:
        assert extract_list(None, key="results") == []
