"""Variant service with caching and business logic."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, NamedTuple, TypeVar

from litvar_link.exceptions import LitVarAPIError, ValidationError
from litvar_link.logging_config import log_error_with_context
from litvar_link.models import (
    GeneVariantsResponse,
    PublicationResponse,
    SensorResponse,
    VariantDetailsResponse,
    VariantSearchResponse,
)
from litvar_link.models.endpoint_specific import VariantDetailsItem
from litvar_link.services.cache_hits import hits_before, was_cache_hit
from litvar_link.utils.caching import create_service_cache_decorator
from litvar_link.validation import (
    MAX_LIMIT,
    validate_gene_name,
    validate_limit,
    validate_query,
    validate_rsid,
)

if TYPE_CHECKING:
    from structlog.typing import FilteringBoundLogger

    from litvar_link.api.client import LitVar2Client
    from litvar_link.config import CacheConfig
    from litvar_link.models.endpoint_specific import AutocompleteVariantItem

_ModelT = TypeVar("_ModelT")

_PATHOGENIC = frozenset({"pathogenic", "likely pathogenic"})
_BENIGN = frozenset({"benign", "likely benign"})


class SignificanceCounts(NamedTuple):
    """Clinical-significance tally that keeps ABSENT distinct from UNCERTAIN.

    ``unclassified`` (LitVar2 said nothing) is NOT ``uncertain`` (LitVar2 said
    "uncertain"). Collapsing the two produces a confidently false clinical
    statement -- see ``_count_clinical_significance``.
    """

    pathogenic: int
    benign: int
    uncertain: int
    unclassified: int

    @property
    def classified(self) -> int:
        """Variants for which LitVar2 supplied ANY clinical significance."""
        return self.pathogenic + self.benign + self.uncertain


def _normalize_significance(value: str) -> str:
    """Fold LitVar2's significance tokens to a canonical form.

    Upstream writes ``likely-pathogenic`` / ``risk-factor`` (HYPHENS); the buckets
    were written with spaces (``"likely pathogenic"``), so a genuinely pathogenic
    variant never matched and fell through to "uncertain". A second, quieter
    instance of the same defect as the absent-field recoding below.
    """
    return value.strip().lower().replace("-", " ").replace("_", " ")

# Canonical LitVar variant ids look like "litvar@rs113993960##". The publications
# endpoint only accepts this form, so non-canonical input (rsID/HGVS/free text)
# must be resolved via autocomplete first.
_CANONICAL_ID_PREFIX = "litvar@"

# Upstream returns 400 with body {"detail": "Variant not found: ..."} for an id
# that does not exist. That is a user-recoverable "not found", not an outage.
_NOT_FOUND_STATUS = (400, 404)


def _is_canonical_variant_id(value: str) -> bool:
    """True for an already-canonical LitVar id like ``litvar@rs113993960##``."""
    return value.startswith(_CANONICAL_ID_PREFIX)


def _is_variant_not_found(exc: LitVarAPIError) -> bool:
    """True when an upstream 4xx clearly means 'this variant id does not exist'."""
    return exc.status_code in _NOT_FOUND_STATUS and "not found" in str(exc).lower()


def _count_clinical_significance(variants: list[Any]) -> SignificanceCounts:
    """Tally clinical significance, keeping ABSENT strictly apart from UNCERTAIN.

    The old version counted a variant with NO ``data_clinical_significance`` as
    ``uncertain``. LitVar2's gene endpoint never carries that field at all, so
    every variant in every gene was bucketed "uncertain" and then COUNTED,
    yielding the confidently false:

        13,264 BRCA1 variants -- 0 pathogenic, 0 benign, 13,264 uncertain

    BRCA1 has thousands of established pathogenic variants. A curator would have
    believed that. In clinical genetics "uncertain" means VUS -- a positive
    assertion that the evidence was weighed and found inconclusive. It is NOT a
    synonym for "nobody told us". A field that is absent upstream must be
    reported as UNKNOWN, never counted as a negative finding.
    """
    pathogenic = benign = uncertain = unclassified = 0
    for variant in variants:
        sigs = getattr(variant, "data_clinical_significance", None)
        if not sigs:
            unclassified += 1
            continue
        normalized = {_normalize_significance(sig) for sig in sigs}
        if normalized & _PATHOGENIC:
            pathogenic += 1
        elif normalized & _BENIGN:
            benign += 1
        else:
            # Present, but neither a pathogenic nor a benign call (e.g. "risk
            # factor", "association", "uncertain significance").
            uncertain += 1
    return SignificanceCounts(pathogenic, benign, uncertain, unclassified)


class VariantService:
    """Service for variant operations with caching and business logic."""

    def __init__(
        self,
        client: LitVar2Client,
        cache_config: CacheConfig,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize variant service.

        Args:
            client: LitVar2 API client
            cache_config: Cache configuration
            logger: Optional logger instance
        """
        self.client = client
        self.cache_config = cache_config
        self.logger = logger

        # Initialize centralized cache manager
        self.cache = create_service_cache_decorator(logger)

        # Apply caching decorators to methods
        self._setup_cached_methods()

    def _generate_cache_key(self, operation: str, **kwargs: Any) -> str:
        """Generate cache key for operation.

        Args:
            operation: Operation name
            **kwargs: Parameters for cache key

        Returns:
            Cache key string
        """
        parts = [operation]
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        return self.cache.cache_stats

    def _setup_cached_methods(self) -> None:
        """Set up cached methods using the cache manager."""
        # Use config values or defaults for search variants
        search_maxsize = self.cache_config.size if hasattr(self.cache_config, "size") else 256
        search_ttl = self.cache_config.ttl if hasattr(self.cache_config, "ttl") else 3600

        self._cached_search_variants = self.cache.cached(
            maxsize=search_maxsize,
            ttl=search_ttl,
            key_pattern="search_variants",
        )(self._search_variants_impl)

        self._cached_get_variant_details = self.cache.cached(
            maxsize=500,
            ttl=7200,
            key_pattern="variant_details",
        )(self._get_variant_details_impl)

        self._cached_get_variant_publications = self.cache.cached(
            maxsize=500,
            ttl=3600,
            key_pattern="variant_publications",
        )(self._get_variant_publications_impl)

        self._cached_sensor_lookup = self.cache.cached(
            maxsize=1000,
            ttl=86400,
            key_pattern="sensor_lookup",
        )(self._sensor_lookup_impl)

        self._cached_get_variants_by_gene = self.cache.cached(
            maxsize=200,
            ttl=3600,
            key_pattern="gene_variants",
        )(self._get_variants_by_gene_impl)

    async def _search_variants_impl(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search variants implementation."""
        return await self.client.search_variants(query, limit=limit)

    async def _get_variant_details_impl(self, variant_id: str) -> dict[str, Any]:
        """Get variant details implementation."""
        return await self.client.get_variant_details(variant_id)

    async def _get_variant_publications_impl(self, variant_id: str) -> list[str]:
        """Get variant publications implementation."""
        return await self.client.get_variant_publications(variant_id)

    async def _sensor_lookup_impl(self, rsid: str) -> dict[str, Any] | None:
        """RSID sensor lookup implementation."""
        return await self.client.sensor_lookup(rsid)

    async def _get_variants_by_gene_impl(
        self,
        gene_name: str,
    ) -> list[dict[str, Any]]:
        """Get variants by gene implementation."""
        return await self.client.get_variants_by_gene(gene_name)

    def _parse_items(
        self,
        data_list: list[dict[str, Any]],
        model_cls: type[_ModelT],
    ) -> list[_ModelT]:
        """Parse raw rows into ``model_cls`` instances, skipping bad rows.

        Rows that fail validation are logged (with context) and dropped rather
        than aborting the whole response. Shared by the autocomplete-search and
        gene-search parse paths.
        """
        parsed: list[_ModelT] = []
        for data in data_list:
            try:
                parsed.append(model_cls(**data))
            except Exception as e:  # per-row resilience: skip bad rows
                if self.logger:
                    log_error_with_context(
                        self.logger,
                        e,
                        "variant_parsing",
                        {"variant_data": data},
                    )
        return parsed

    async def search_variants(
        self,
        query: str,
        limit: int = 10,
    ) -> VariantSearchResponse:
        """Search variants with caching and validation.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Variant search response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        query = validate_query(query)
        limit = validate_limit(limit)

        try:
            start_time = time.time()

            # OVER-FETCH one row past the page so `has_more` is a FACT, not a
            # guess. The old code inferred `has_more = len(variants) == limit`,
            # which is exactly the "total == page size" lie: it cannot tell "the
            # page is full and that is all there is" from "the page is full and
            # thousands more exist" (issue #66 D2). LitVar2 rejects limit > 100,
            # so at the ceiling a full page is treated as "more may exist" --
            # conservative by design: over-claiming completeness is the harm.
            fetch_limit = min(limit + 1, MAX_LIMIT)

            initial_hits = hits_before(self._cached_search_variants)
            variant_data = await self._cached_search_variants(query, fetch_limit)
            cached = was_cache_hit(self._cached_search_variants, before=initial_hits)

            # Parse variants using the endpoint-specific model
            from litvar_link.models.endpoint_specific import AutocompleteVariantItem

            fetched = self._parse_items(variant_data, AutocompleteVariantItem)
            has_more = len(fetched) > limit if limit < MAX_LIMIT else len(fetched) >= MAX_LIMIT
            variants = fetched[:limit]

            search_time = (time.time() - start_time) * 1000

            return VariantSearchResponse(
                variants=variants,
                total_count=len(variants),
                query=query,
                limit=limit,
                has_more=has_more,
                search_time_ms=search_time,
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "search_variants",
                    {"query": query, "limit": limit},
                )
            raise

    async def get_variant_summary(self, variant_id: str) -> VariantDetailsResponse:
        """Get detailed variant information for a LitVar id, rsID, or HGVS/free text.

        ``variant_id`` may be a canonical LitVar id, an rsID, or HGVS/free text;
        non-canonical input is resolved via autocomplete first (the variant/get
        endpoint only accepts ``litvar@...##`` and 400s on anything else). The
        resolved id is returned so the caller can see WHICH record answered.

        Raises:
            ValidationError: For invalid/unresolvable input
            LitVarAPIError: For genuine upstream errors (rate limit, outage)
        """
        if not variant_id or not variant_id.strip():
            msg = "Variant ID cannot be empty"
            raise ValidationError(msg, field="variant_id")

        variant_id = variant_id.strip()
        try:
            resolved_id = await self._resolve_to_variant_id(variant_id)

            initial_hits = hits_before(self._cached_get_variant_details)
            variant_data = await self._cached_get_variant_details(resolved_id)
            cached = was_cache_hit(self._cached_get_variant_details, before=initial_hits)

            # Build the model the response actually DECLARES. This used to build a
            # `VariantDetails` and launder it past mypy with `cast("Any", ...)`;
            # pydantic rejected it at runtime on EVERY call, so the tool answered
            # `internal` for its own canonical ids and was dead for ~every input.
            # The cast is gone: mypy now proves the two types agree, forever.
            return VariantDetailsResponse(
                variant=VariantDetailsItem(**variant_data),
                resolved_variant_id=resolved_id,
                cached=cached,
            )

        except ValidationError:
            raise  # already a clean, user-recoverable message
        except LitVarAPIError as e:
            if _is_variant_not_found(e):
                msg = (
                    f"LitVar2 has no variant record for {variant_id!r} (variant not found). "
                    "Use search_genetic_variants to find a valid variant id."
                )
                raise ValidationError(msg, field="variant_id") from e
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "get_variant_summary",
                    {"variant_id": variant_id},
                )
            raise
        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "get_variant_summary",
                    {"variant_id": variant_id},
                )
            raise

    async def _resolve_to_variant_id(self, raw: str) -> str:
        """Resolve free-text / rsID / HGVS to a canonical LitVar id.

        Already-canonical ids (``litvar@...``) pass through untouched; otherwise
        the autocomplete endpoint resolves the top hit. Raises ``ValidationError``
        (a user-recoverable error the tool surfaces verbatim) when nothing
        matches, so an unresolvable variant reads as a clear "not found" rather
        than a masked retry-later internal error.
        """
        if _is_canonical_variant_id(raw):
            return raw
        search = await self.search_variants(raw, limit=1)
        if not search.variants:
            msg = (
                f"No LitVar2 variant found for {raw!r}. "
                "Use search_genetic_variants to find the variant id."
            )
            raise ValidationError(msg, field="variant_id")
        return search.variants[0].id

    async def _fetch_publication_response(self, resolved_id: str) -> PublicationResponse:
        """Fetch + shape publications for an already-canonical LitVar id."""
        initial_hits = hits_before(self._cached_get_variant_publications)
        pmids = await self._cached_get_variant_publications(resolved_id)
        cached = was_cache_hit(self._cached_get_variant_publications, before=initial_hits)

        from litvar_link.models.variants import Publication

        publications: list[Publication] = []
        for pmid in pmids:
            if not pmid:
                continue
            try:
                publications.append(Publication(pmid=pmid))
            except Exception as e:  # per-row resilience: skip malformed rows
                if self.logger:
                    log_error_with_context(
                        self.logger,
                        e,
                        "publication_parsing",
                        {"pmid": pmid},
                    )
        return PublicationResponse(
            variant_id=resolved_id,
            publications=publications,
            total_count=len(publications),
            pmid_count=len(publications),
            pmc_count=0,  # Not available from this endpoint
            format="json",
            cached=cached,
        )

    def _log_literature_error(self, exc: Exception, variant_id: str) -> None:
        """Log an unexpected literature-path error with context (no-op if no logger)."""
        if self.logger:
            log_error_with_context(
                self.logger,
                exc,
                "get_variant_literature",
                {"variant_id": variant_id},
            )

    async def get_variant_literature(self, variant_id: str) -> PublicationResponse:
        """Get publications associated with a variant.

        ``variant_id`` may be a canonical LitVar id, an rsID, or HGVS/free text;
        non-canonical input is resolved to the canonical id via autocomplete
        before the publications call (the endpoint only accepts ``litvar@...##``).
        An unresolvable/unknown variant raises ``ValidationError`` (a recoverable
        "not found"), never a masked retry-later internal error.

        Raises:
            ValidationError: For invalid/unresolvable/unknown variants
            LitVarAPIError: For genuine upstream errors (rate limit, outage)
        """
        if not variant_id or not variant_id.strip():
            msg = "Variant ID cannot be empty"
            raise ValidationError(msg, field="variant_id")

        variant_id = variant_id.strip()
        try:
            resolved_id = await self._resolve_to_variant_id(variant_id)
            return await self._fetch_publication_response(resolved_id)
        except ValidationError:
            raise  # already a clean, user-recoverable message
        except LitVarAPIError as e:
            if _is_variant_not_found(e):
                msg = (
                    f"LitVar2 has no literature record for {variant_id!r} "
                    "(variant not found). Use search_genetic_variants to find a "
                    "valid variant id."
                )
                raise ValidationError(msg, field="variant_id") from e
            self._log_literature_error(e, variant_id)
            raise
        except Exception as e:
            self._log_literature_error(e, variant_id)
            raise

    async def _resolve_rsid_record(
        self,
        rsid: str,
    ) -> AutocompleteVariantItem | None:
        """Enrich an rsID with its canonical autocomplete record (issue #20).

        The LitVar2 sensor endpoint returns only ``{pmids_count, rsid, link,
        logo}`` -- it carries neither the canonical ``variant_id`` (``_id``) nor
        ``gene``/``name``. resolve_rsid must surface those three so the result
        chains into get_variant_summary / get_variant_literature, so we read them
        from autocomplete. Best-effort: a transient autocomplete failure degrades
        to ``None`` (availability is already known from the sensor call).

        Misattribution guard: autocomplete is a free-text search, not an exact
        rsID index, so its top (or only) hit can be for a *different* variant
        than the one queried. A result is only treated as a confident match
        when either (a) some candidate's ``rsid`` equals the queried rsID, or
        (b) there is exactly one candidate and it carries no ``rsid`` at all
        (autocomplete gave nothing to compare against, so its sole answer is
        accepted). Any other shape -- notably a sole/top candidate whose
        ``rsid`` actively disagrees with the query -- is treated as "no
        match" (``None``) rather than silently attributing the wrong
        gene/variant_id/variant_name to the query. A misattributed
        variant_id would otherwise drive get_variant_literature to return
        literature for an unrelated variant.
        """
        try:
            search = await self.search_variants(rsid, limit=5)
        except Exception as exc:  # enrichment is best-effort; never break resolve
            if self.logger:
                log_error_with_context(self.logger, exc, "resolve_rsid_enrich", {"rsid": rsid})
            return None
        for item in search.variants:
            if getattr(item, "rsid", None) == rsid:
                return item
        if len(search.variants) == 1 and search.variants[0].rsid is None:
            return search.variants[0]
        return None

    @staticmethod
    def _unavailable_sensor(rsid: str, *, cached: bool) -> SensorResponse:
        """Build the 'rsID not in LitVar2' response (all metadata None)."""
        return SensorResponse(
            rsid=rsid,
            available=False,
            variant_id=None,
            litvar_url=None,
            pmids_count=None,
            gene=None,
            variant_name=None,
            cached=cached,
        )

    async def lookup_rsid(self, rsid: str) -> SensorResponse:
        """Check if RSID is available in LitVar2.

        Enriches the result with variant_id / gene / variant_name from the
        autocomplete endpoint (issue #20): the sensor payload only carries
        ``{pmids_count, rsid, link, logo}`` so those three id fields must come
        from autocomplete. Maps a sensor 400 "Variant not found" to
        ``available=False`` (recoverable) rather than propagating the error.

        Raises:
            ValidationError: For invalid RSID format
            LitVarAPIError: For genuine upstream errors (rate limit, outage)
        """
        rsid = validate_rsid(rsid)
        cached = False
        try:
            initial_hits = hits_before(self._cached_sensor_lookup)
            sensor_data = await self._cached_sensor_lookup(rsid)
            cached = was_cache_hit(self._cached_sensor_lookup, before=initial_hits)

            if sensor_data is None:
                return self._unavailable_sensor(rsid, cached=cached)

            record = await self._resolve_rsid_record(rsid)
            return SensorResponse(
                rsid=rsid,
                available=True,
                # variant_id / gene / variant_name come from autocomplete; the
                # sensor payload exposes only pmids_count + link (issue #20).
                variant_id=record.id if record else None,
                litvar_url=sensor_data.get("link"),
                pmids_count=sensor_data.get("pmids_count"),
                gene=record.gene if record else None,
                variant_name=(record.name or None) if record else None,
                cached=cached,
            )
        except LitVarAPIError as e:
            if _is_variant_not_found(e):
                return self._unavailable_sensor(rsid, cached=False)
            if self.logger:
                log_error_with_context(self.logger, e, "lookup_rsid", {"rsid": rsid})
            raise
        except Exception as e:
            if self.logger:
                log_error_with_context(self.logger, e, "lookup_rsid", {"rsid": rsid})
            raise

    async def search_gene_variants(self, gene_name: str) -> GeneVariantsResponse:
        """Get all variants for a specific gene.

        Args:
            gene_name: Gene symbol

        Returns:
            Gene variants response

        Raises:
            ValidationError: For invalid input parameters
            LitVarAPIError: For API-related errors
        """
        gene_name = validate_gene_name(gene_name)
        try:
            initial_hits = hits_before(self._cached_get_variants_by_gene)
            variant_data = await self._cached_get_variants_by_gene(gene_name)
            cached = was_cache_hit(
                self._cached_get_variants_by_gene,
                before=initial_hits,
            )

            # Parse variants using the endpoint-specific model
            from litvar_link.models.endpoint_specific import GeneVariantItem

            variants = self._parse_items(variant_data, GeneVariantItem)

            counts = _count_clinical_significance(variants)

            # Calculate total publications (sum of pmids_count)
            total_publications = sum(
                getattr(variant, "pmids_count", 0) or 0 for variant in variants
            )

            return GeneVariantsResponse(
                gene=gene_name,
                variants=variants,
                total_count=len(variants),
                pathogenic_count=counts.pathogenic,
                benign_count=counts.benign,
                uncertain_count=counts.uncertain,
                unclassified_count=counts.unclassified,
                classified_count=counts.classified,
                total_publications=total_publications,
                cached=cached,
            )

        except Exception as e:
            if self.logger:
                log_error_with_context(
                    self.logger,
                    e,
                    "search_gene_variants",
                    {"gene_name": gene_name},
                )
            raise

    async def clear_cache(self, pattern: str | None = None) -> dict[str, int]:
        """Clear service cache using centralized cache manager.

        Args:
            pattern: Optional pattern to match cache keys

        Returns:
            Dictionary with cleared cache statistics
        """
        return self.cache.clear_all_caches(pattern)

    def get_cache_info(self) -> dict[str, Any]:
        """Get detailed cache information for all cached methods.

        Returns:
            Dictionary with cache information for each cached method
        """
        return self.cache.get_cache_info()
