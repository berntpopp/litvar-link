"""The extracted OpenAPI example constants exist and the schema still builds."""

from __future__ import annotations

from litvar_link.api.routes import openapi_examples as ex
from litvar_link.app import create_app


def test_constants_present() -> None:
    assert isinstance(ex.SEARCH_RESPONSES, dict)
    assert 200 in ex.SEARCH_RESPONSES
    assert isinstance(ex.SENSOR_RESPONSES, dict)
    assert isinstance(ex.PUBLICATIONS_RESPONSES, dict)
    assert isinstance(ex.GENE_VARIANTS_RESPONSES, dict)
    assert isinstance(ex.VARIANT_DETAILS_RESPONSES, dict)


def test_openapi_schema_builds_with_examples() -> None:
    schema = create_app().openapi()
    path = schema["paths"]["/api/variants/search"]["get"]
    assert "200" in path["responses"]
