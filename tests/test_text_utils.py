"""Tests for text truncation utility."""


def test_strips_references_section():
    text = "Abstract\n\nSome content.\n\n1 Introduction\n\nIntro text.\n\nReferences\n\n[1] Doe et al."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "[1] Doe et al." not in result
    assert "Some content." in result


def test_strips_acknowledgments():
    text = "Content here.\n\nAcknowledgments\n\nThanks to everyone.\n\n2 Methods\n\nMore content."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text)
    assert "Thanks to everyone" not in result
    assert "Content here." in result


def test_truncates_at_sentence_boundary():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=40)
    assert result.endswith(".")
    assert len(result) <= 40


def test_preserves_abstract_and_sections():
    text = "Abstract\n\nThis is the abstract.\n\n1 Introduction\n\nIntro.\n\n2 Methods\n\nMethods text."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "This is the abstract." in result
    assert "Methods text." in result


def test_handles_empty_text():
    from scipaper.text_utils import prepare_text_for_llm
    assert prepare_text_for_llm("") == ""


def test_handles_text_shorter_than_max():
    from scipaper.text_utils import prepare_text_for_llm
    short = "Short text."
    assert prepare_text_for_llm(short, max_chars=5000) == short


def test_strips_bibliography_variant():
    text = "Content.\n\nBibliography\n\n[1] Smith 2024."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "[1] Smith 2024." not in result


def test_strips_appendix():
    text = "Content.\n\nAppendix A\n\nSupplementary material."
    from scipaper.text_utils import prepare_text_for_llm
    result = prepare_text_for_llm(text, max_chars=5000)
    assert "Supplementary material" not in result
