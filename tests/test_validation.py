"""Tests for utils.validation."""

from utils.validation import (
    ValidationError,
    build_triple_pattern,
    format_supports_named_graphs,
    is_select_query,
    normalize_index,
    recommend_index,
    sanitize_output_stem,
)


class TestNormalizeIndex:
    def test_accepts_valid_index(self):
        assert normalize_index("pso") == "PSO"

    def test_rejects_invalid_index(self):
        try:
            normalize_index("abc")
            assert False, "Expected ValidationError"
        except ValidationError:
            assert True


class TestSanitizeOutputStem:
    def test_replaces_unsafe_chars(self):
        assert sanitize_output_stem("mi archivo?.nt") == "mi_archivo_.nt"

    def test_fallback_when_empty(self):
        assert sanitize_output_stem("***", fallback="graph") == "graph"


class TestBuildTriplePattern:
    def test_builds_with_variables(self):
        assert build_triple_pattern(None, "<p>", None) == "?s <p> ?o"

    def test_builds_quad_pattern(self):
        assert build_triple_pattern("<s>", "<p>", '"x"', None) == '<s> <p> "x" ?g'


class TestSelectValidation:
    def test_accepts_prefix_before_select(self):
        query = "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nSELECT * WHERE { ?s ?p ?o }"
        assert is_select_query(query) is True

    def test_rejects_construct(self):
        assert is_select_query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }") is False


class TestRecommendIndex:
    def test_prefers_predicate_object(self):
        assert recommend_index(None, "<p>", '"x"') == "POS"

    def test_defaults_to_spo(self):
        assert recommend_index(None, None, None) == "SPO"


class TestFormats:
    def test_quad_safe_formats(self):
        assert format_supports_named_graphs("nquads") is True
        assert format_supports_named_graphs("trig") is True
        assert format_supports_named_graphs("turtle") is False
