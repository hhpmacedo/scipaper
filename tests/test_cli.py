"""
Tests for the top-level CLI entrypoint (python -m scipaper).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import run_async

from scipaper.curate.models import AnchorDocument
from scipaper.pipeline import PipelineConfig, PipelineResult
from scipaper.publish.email import ButtondownConfig
from scipaper.publish.web import WebConfig


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sample_anchor():
    return AnchorDocument(
        week="2025-W10",
        updated_by="test",
        updated_at=datetime(2025, 3, 5, tzinfo=timezone.utc),
        hot_topics=["LLM reasoning"],
        declining_topics=[],
        boost_keywords=["transformer"],
        institutions_of_interest=["MIT"],
    )


@pytest.fixture
def successful_pipeline_result():
    """A PipelineResult with pieces that passed verification."""
    result = PipelineResult(
        papers_ingested=20,
        papers_scored=20,
        papers_selected=5,
        pieces_generated=5,
        pieces_verified=5,
        pieces_passed=3,
        errors=[],
    )
    return result


@pytest.fixture
def empty_pipeline_result():
    """A PipelineResult with zero pieces passing verification."""
    return PipelineResult(
        papers_ingested=10,
        papers_scored=10,
        papers_selected=3,
        pieces_generated=3,
        pieces_verified=3,
        pieces_passed=0,
        errors=["All pieces rejected"],
    )


# ── Import tests ──────────────────────────────────────────────────────


def test_main_is_importable():
    """The top-level CLI module imports cleanly."""
    import scipaper.__main__ as cli_module
    assert hasattr(cli_module, "main")


def test_main_is_callable():
    """main() is a callable function."""
    from scipaper.__main__ import main
    assert callable(main)


def test_cmd_run_pipeline_is_callable():
    """cmd_run_pipeline is a callable coroutine function."""
    import inspect
    from scipaper.__main__ import cmd_run_pipeline
    assert callable(cmd_run_pipeline)
    assert inspect.iscoroutinefunction(cmd_run_pipeline)


# ── cmd_run_pipeline tests ────────────────────────────────────────────


def test_cmd_run_pipeline_calls_run_pipeline_with_correct_config(
    sample_anchor, successful_pipeline_result
):
    """cmd_run_pipeline calls run_pipeline with a PipelineConfig."""
    import os
    from scipaper.__main__ import cmd_run_pipeline

    mock_args = MagicMock()
    mock_args.week = None
    mock_args.log_level = "INFO"

    with patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result) as mock_run, \
         patch.dict(os.environ, {}, clear=False):
        run_async(cmd_run_pipeline(mock_args))

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    # First positional arg is the anchor
    assert call_args[0][0] is sample_anchor
    # Second positional arg is a PipelineConfig
    config = call_args[0][1]
    assert isinstance(config, PipelineConfig)


def test_cmd_run_pipeline_passes_week_to_load_anchor(
    sample_anchor, successful_pipeline_result
):
    """When --week is given, load_anchor receives it."""
    from scipaper.__main__ import cmd_run_pipeline

    mock_args = MagicMock()
    mock_args.week = "2025-W10"
    mock_args.log_level = "INFO"

    with patch("scipaper.__main__.load_anchor", return_value=sample_anchor) as mock_load, \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result):
        run_async(cmd_run_pipeline(mock_args))

    mock_load.assert_called_once_with("2025-W10")


def test_cmd_run_pipeline_sets_buttondown_config_from_env(
    sample_anchor, successful_pipeline_result
):
    """ButtondownConfig api_key is populated from BUTTONDOWN_API_KEY env var."""
    import os
    from scipaper.__main__ import cmd_run_pipeline

    mock_args = MagicMock()
    mock_args.week = None
    mock_args.log_level = "INFO"

    with patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result) as mock_run, \
         patch.dict(os.environ, {"BUTTONDOWN_API_KEY": "test-key-123"}):
        run_async(cmd_run_pipeline(mock_args))

    config = mock_run.call_args[0][1]
    assert isinstance(config.email, ButtondownConfig)
    assert config.email.api_key == "test-key-123"


def test_cmd_run_pipeline_sets_web_config(
    sample_anchor, successful_pipeline_result
):
    """PipelineConfig.web is a WebConfig instance."""
    from scipaper.__main__ import cmd_run_pipeline

    mock_args = MagicMock()
    mock_args.week = None
    mock_args.log_level = "INFO"

    with patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result) as mock_run:
        run_async(cmd_run_pipeline(mock_args))

    config = mock_run.call_args[0][1]
    assert isinstance(config.web, WebConfig)


def test_cmd_run_pipeline_sets_web_base_url_from_env(
    sample_anchor, successful_pipeline_result
):
    """web_base_url is populated from SIGNAL_WEB_URL env var."""
    import os
    from scipaper.__main__ import cmd_run_pipeline

    mock_args = MagicMock()
    mock_args.week = None
    mock_args.log_level = "INFO"

    with patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result) as mock_run, \
         patch.dict(os.environ, {"SIGNAL_WEB_URL": "https://my.signal.site"}):
        run_async(cmd_run_pipeline(mock_args))

    config = mock_run.call_args[0][1]
    assert config.web_base_url == "https://my.signal.site"


def test_cmd_run_pipeline_default_web_base_url(
    sample_anchor, successful_pipeline_result
):
    """web_base_url defaults to signal.example.com when env var absent."""
    import os
    from scipaper.__main__ import cmd_run_pipeline

    mock_args = MagicMock()
    mock_args.week = None
    mock_args.log_level = "INFO"

    env_without_url = {k: v for k, v in os.environ.items() if k != "SIGNAL_WEB_URL"}

    with patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result) as mock_run, \
         patch.dict(os.environ, env_without_url, clear=True):
        run_async(cmd_run_pipeline(mock_args))

    config = mock_run.call_args[0][1]
    assert config.web_base_url == "https://signal.hugohmacedo.com"


# ── main() argument parsing tests ─────────────────────────────────────


def test_main_without_run_prints_help(capsys):
    """Calling main() with no --run argument prints help text."""
    from scipaper.__main__ import main

    with patch("sys.argv", ["scipaper"]):
        main()

    captured = capsys.readouterr()
    assert "usage" in captured.out.lower() or "--run" in captured.out


def test_main_exits_with_code_1_when_no_pieces_passed(
    sample_anchor, empty_pipeline_result
):
    """main() exits with code 1 when pieces_passed == 0."""
    from scipaper.__main__ import main

    with patch("sys.argv", ["scipaper", "--run"]), \
         patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=empty_pipeline_result), \
         patch("scipaper.__main__.setup_logging"):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1


def test_main_exits_with_code_0_when_pieces_passed(
    sample_anchor, successful_pipeline_result
):
    """main() exits with code 0 (or no SystemExit) when pieces passed."""
    from scipaper.__main__ import main

    with patch("sys.argv", ["scipaper", "--run"]), \
         patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result), \
         patch("scipaper.__main__.setup_logging"):
        # Should NOT raise SystemExit
        main()


def test_main_run_with_week_flag(sample_anchor, successful_pipeline_result):
    """main() passes --week value through to load_anchor."""
    from scipaper.__main__ import main

    with patch("sys.argv", ["scipaper", "--run", "--week", "2025-W10"]), \
         patch("scipaper.__main__.load_anchor", return_value=sample_anchor) as mock_load, \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result), \
         patch("scipaper.__main__.setup_logging"):
        main()

    mock_load.assert_called_once_with("2025-W10")


def test_main_log_level_passed_to_setup_logging(
    sample_anchor, successful_pipeline_result
):
    """main() passes --log-level to setup_logging."""
    from scipaper.__main__ import main

    with patch("sys.argv", ["scipaper", "--run", "--log-level", "DEBUG"]), \
         patch("scipaper.__main__.load_anchor", return_value=sample_anchor), \
         patch("scipaper.__main__.run_pipeline", new_callable=AsyncMock, return_value=successful_pipeline_result), \
         patch("scipaper.__main__.setup_logging") as mock_setup:
        main()

    mock_setup.assert_called_once_with("DEBUG", json_logs=False)


def test_default_web_url_is_production():
    """Default web URL should be the production URL."""
    from scipaper.pipeline import PipelineConfig
    config = PipelineConfig()
    assert config.web_base_url == "https://signal.hugohmacedo.com"
