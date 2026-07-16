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


from scipaper.text_utils import strip_leading_hook


def test_strip_leading_hook_removes_duplicated_hook():
    hook = "You can now identify which AI wrote a snippet with 87% accuracy."
    content = (
        "You can now identify which AI wrote a snippet with 87% accuracy.\n\n"
        "## The Problem\nAttribution is hard [§1]."
    )
    result = strip_leading_hook(content, hook)
    assert result.startswith("## The Problem")
    assert "87% accuracy" not in result.split("## The Problem")[0]


def test_strip_leading_hook_leaves_clean_content_untouched():
    hook = "You can now identify which AI wrote a snippet."
    content = "## The Problem\nAttribution is hard [§1]."
    assert strip_leading_hook(content, hook) == content


def test_strip_leading_hook_matches_despite_whitespace_and_case():
    hook = "A single misleading document can override five accurate ones."
    content = (
        "A single   misleading document can override five accurate ones.\n\n"
        "## The Problem\nRAG is messy."
    )
    assert strip_leading_hook(content, hook).startswith("## The Problem")


def test_strip_leading_hook_does_not_strip_long_paragraph():
    # A real Problem paragraph that merely shares opening words must survive.
    hook = "Models fail on noisy inputs."
    content = (
        "Models fail on noisy inputs in ways that matter enormously for anyone "
        "shipping to production, and this section explains exactly why that "
        "happens across a dozen distinct failure modes that compound.\n\n"
        "## The Problem\nMore detail."
    )
    assert strip_leading_hook(content, hook) == content


def test_strip_leading_hook_handles_empty():
    assert strip_leading_hook("", "hook") == ""
    assert strip_leading_hook("content", "") == "content"
