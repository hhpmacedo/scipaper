"""
Tests for the verification checker module.
"""

from unittest.mock import AsyncMock, patch

import pytest

from .conftest import run_async

from scipaper.verify.checker import (
    IssueSeverity,
    IssueType,
    VerificationIssue,
    VerificationReport,
    _fallback_report,
    _heuristic_verification,
    _parse_verification_response,
    attempt_auto_fix,
    verify_piece,
)
from scipaper.generate.writer import Piece
from scipaper.curate.models import Author, Paper


def make_piece(**kwargs):
    defaults = dict(
        paper_id="2403.12345",
        title="Test Piece",
        hook="A test hook.",
        content="The model works well [§1]. Results confirm [§2.1] improvements.",
        word_count=10,
        citations=[{"claim": "works well", "citation": "§1"}],
        generated_at="2025-01-01T00:00:00",
        model_used="test",
    )
    defaults.update(kwargs)
    return Piece(**defaults)


def make_paper(**kwargs):
    defaults = dict(
        arxiv_id="2403.12345",
        title="Test Paper",
        abstract="A test abstract.",
        authors=[Author(name="Alice")],
        categories=["cs.AI"],
        full_text="1 Introduction\nTest text.\n\n2 Methods\nMethod details.\n\n2.1 Data\nData info.\n\n3 Results\nResult details.",
    )
    defaults.update(kwargs)
    return Paper(**defaults)


class TestVerificationReport:
    def test_pass_rate(self):
        report = VerificationReport(
            paper_id="test", status="pass",
            claims_checked=10, claims_verified=8, claims_failed=2,
        )
        assert report.pass_rate == 0.8

    def test_pass_rate_zero_claims(self):
        report = VerificationReport(
            paper_id="test", status="pass",
            claims_checked=0, claims_verified=0, claims_failed=0,
        )
        assert report.pass_rate == 0.0

    def test_should_reject_critical(self):
        report = VerificationReport(
            paper_id="test", status="fail",
            claims_checked=5, claims_verified=4, claims_failed=1,
            issues=[VerificationIssue(
                severity=IssueSeverity.CRITICAL,
                issue_type=IssueType.MISREPRESENTED,
                claim_text="wrong claim",
                cited_passage="actual passage",
                explanation="contradicts source",
            )],
        )
        assert report.should_reject() is True

    def test_should_reject_many_major(self):
        issues = [
            VerificationIssue(
                severity=IssueSeverity.MAJOR,
                issue_type=IssueType.OVERSTATED,
                claim_text=f"claim {i}",
                cited_passage="passage",
                explanation="overstated",
            )
            for i in range(3)
        ]
        report = VerificationReport(
            paper_id="test", status="fail",
            claims_checked=5, claims_verified=2, claims_failed=3,
            issues=issues,
        )
        assert report.should_reject() is True

    def test_should_not_reject_minor(self):
        report = VerificationReport(
            paper_id="test", status="pass",
            claims_checked=5, claims_verified=5, claims_failed=0,
            issues=[VerificationIssue(
                severity=IssueSeverity.MINOR,
                issue_type=IssueType.MISSING_CONTEXT,
                claim_text="claim",
                cited_passage="passage",
                explanation="minor issue",
            )],
        )
        assert report.should_reject() is False


class TestParseVerificationResponse:
    def test_parses_json(self):
        text = '{"claims_checked": 5, "claims_verified": 4, "claims_failed": 1, "issues": []}'
        report = _parse_verification_response(text, "test", "model")
        assert report.claims_checked == 5
        assert report.status == "pass"

    def test_parses_json_in_code_block(self):
        text = '```json\n{"claims_checked": 3, "claims_verified": 3, "claims_failed": 0, "issues": []}\n```'
        report = _parse_verification_response(text, "test", "model")
        assert report.claims_checked == 3
        assert report.status == "pass"

    def test_parses_issues(self):
        text = '''{
            "claims_checked": 2,
            "claims_verified": 1,
            "claims_failed": 1,
            "issues": [{
                "severity": "major",
                "type": "overstated",
                "claim_text": "dramatically improves",
                "cited_passage": "shows modest improvement",
                "explanation": "overstated the result"
            }]
        }'''
        report = _parse_verification_response(text, "test", "model")
        assert len(report.issues) == 1
        assert report.issues[0].severity == IssueSeverity.MAJOR
        assert report.status == "needs_revision"

    def test_fallback_on_invalid_json(self):
        text = "This is not JSON at all"
        report = _parse_verification_response(text, "test", "model")
        assert report.status == "needs_revision"

    def test_reject_on_critical_issue(self):
        text = '''{
            "claims_checked": 1,
            "claims_verified": 0,
            "claims_failed": 1,
            "issues": [{
                "severity": "critical",
                "type": "misrepresented",
                "claim_text": "claim",
                "cited_passage": "passage",
                "explanation": "wrong"
            }]
        }'''
        report = _parse_verification_response(text, "test", "model")
        assert report.status == "fail"


class TestHeuristicVerification:
    def test_valid_citations_pass(self):
        piece = make_piece(
            content="The model performs well [§1]. Data was collected [§2.1]."
        )
        paper = make_paper()
        report = _heuristic_verification(piece, paper)
        assert report.status == "pass"
        assert report.model_used == "heuristic"

    def test_invalid_citations_need_revision(self):
        piece = make_piece(
            content="Claims about section [§99.9] that doesn't exist."
        )
        paper = make_paper()
        report = _heuristic_verification(piece, paper)
        assert report.status == "needs_revision"
        assert report.claims_failed > 0


class TestVerifyPiece:
    def test_requires_full_text(self):
        piece = make_piece()
        paper = make_paper(full_text=None)
        with pytest.raises(ValueError, match="no full text"):
            run_async(verify_piece(piece, paper))

    def test_verify_with_anthropic(self):
        piece = make_piece()
        paper = make_paper()
        json_resp = '{"claims_checked": 2, "claims_verified": 2, "claims_failed": 0, "issues": []}'

        with patch("scipaper.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock:
            mock.return_value = json_resp
            report = run_async(verify_piece(piece, paper))

        assert report.status == "pass"
        assert report.claims_checked == 2

    def test_falls_back_to_heuristic_on_error(self):
        piece = make_piece(
            content="The model performs [§1] well."
        )
        paper = make_paper()

        with patch("scipaper.verify.checker._verify_with_anthropic", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API error")
            report = run_async(verify_piece(piece, paper))

        assert report.model_used == "heuristic"


class TestFallbackReport:
    def test_returns_needs_revision(self):
        report = _fallback_report("test-id", "model")
        assert report.status == "needs_revision"
        assert report.paper_id == "test-id"
        assert len(report.issues) == 1


class TestAttemptAutoFix:
    def test_no_fixable_issues(self):
        piece = make_piece()
        issues = [VerificationIssue(
            severity=IssueSeverity.CRITICAL,
            issue_type=IssueType.MISREPRESENTED,
            claim_text="claim",
            cited_passage="passage",
            explanation="wrong",
        )]
        result = run_async(attempt_auto_fix(piece, issues))
        assert result.content == piece.content  # unchanged

    def test_text_replacement_fallback(self):
        piece = make_piece(content="The model dramatically improves on the baseline [§1].")
        issues = [VerificationIssue(
            severity=IssueSeverity.MAJOR,
            issue_type=IssueType.OVERSTATED,
            claim_text="dramatically improves",
            cited_passage="shows some improvement",
            explanation="overstated",
            suggested_fix="shows improvement",
        )]

        # Force LLM to fail so fallback text replacement is used
        with patch("scipaper.verify.checker.anthropic", create=True) as mock_anthropic:
            mock_anthropic.AsyncAnthropic.side_effect = Exception("no API")
            result = run_async(attempt_auto_fix(piece, issues))

        assert "dramatically improves" not in result.content
        assert "shows improvement" in result.content
