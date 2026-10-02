"""`api/core/text.py`'s shared text helpers."""

from api.core.text import WORD_SYNONYMS, expand_query_terms, slugify


class TestSlugify:
    def test_ascii_lowercase_hyphenated(self) -> None:
        assert slugify("Apollo Care Hospital") == "apollo-care-hospital"

    def test_devanagari_transliterates_to_nothing(self) -> None:
        assert slugify("अपोलो केयर") == ""


class TestExpandQueryTerms:
    def test_the_original_query_always_comes_first(self) -> None:
        assert expand_query_terms("cashier")[0] == "cashier"

    def test_a_word_with_no_synonym_expands_to_itself_only(self) -> None:
        assert expand_query_terms("cashier") == ["cashier"]

    def test_a_synonym_word_produces_an_expanded_variant(self) -> None:
        variants = expand_query_terms("tech jobs")
        assert "tech jobs" in variants
        assert "technology jobs" in variants

    def test_whole_word_only_a_substring_does_not_trigger_expansion(self) -> None:
        # "it" is a WORD_SYNONYMS key; "credit" must not be treated as
        # containing that word.
        assert expand_query_terms("credit") == ["credit"]

    def test_a_word_with_multiple_synonyms_produces_one_variant_each(self) -> None:
        variants = expand_query_terms("dev")
        assert set(variants) == {"dev", "developer", "development"}

    def test_case_is_normalised(self) -> None:
        assert "technology" in expand_query_terms("TECH")

    def test_every_synonym_key_and_value_is_lower_case(self) -> None:
        for key, values in WORD_SYNONYMS.items():
            assert key == key.lower(), key
            for value in values:
                assert value == value.lower(), value
