"""Unit tests for the shared validation module (DRY cluster #1)."""

from __future__ import annotations

import pytest

from litvar_link.exceptions import ValidationError
from litvar_link.validation import (
    validate_gene_name,
    validate_limit,
    validate_query,
    validate_rsid,
)


class TestValidateQuery:
    def test_strips_and_returns(self) -> None:
        assert validate_query("  CFH  ") == "CFH"

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_empty_rejected(self, bad: str | None) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_query(bad)  # type: ignore[arg-type]
        assert exc.value.field == "query"

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_query("x" * 101)
        assert exc.value.field == "query"


class TestValidateLimit:
    @pytest.mark.parametrize("good", [1, 10, 100])
    def test_in_range_ok(self, good: int) -> None:
        assert validate_limit(good) == good

    @pytest.mark.parametrize("bad", [0, -1, 101, 1000])
    def test_out_of_range_rejected(self, bad: int) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_limit(bad)
        assert exc.value.field == "limit"


class TestValidateRsid:
    def test_lowercases_and_returns(self) -> None:
        assert validate_rsid("RS1061170") == "rs1061170"

    @pytest.mark.parametrize("bad", ["", "rs", "rsABC", "1061170", "x1061170"])
    def test_invalid_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_rsid(bad)
        assert exc.value.field == "rsid"


class TestValidateGeneName:
    def test_strips_uppercases(self) -> None:
        assert validate_gene_name("  cfh ") == "CFH"

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_empty_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_gene_name(bad)
        assert exc.value.field == "gene_name"

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_gene_name("G" * 51)
        assert exc.value.field == "gene_name"
