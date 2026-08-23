"""Modal-dialog fail-closed classification in konsole_driver.

Red control (2026-08-23): with Claude Code's /feedback dialog open, the waker
classified the screen "empty" off a stale transcript prompt line, injected a
tether notice INTO Matt's dialog draft, and marked real messages terminal-
failed. The captured fixture is that real screen (with the injected junk still
in the dialog box). Known-good control is a plain composer viewport.
"""

from __future__ import annotations

from pathlib import Path

from tether.konsole_driver import _screen_is_modal_dialog

FIXTURES = Path("/tmp")
DIALOG = FIXTURES / "fixture_claude_feedback_dialog.txt"
PLAIN = FIXTURES / "fixture_pi_composer.txt"


def test_dialog_fixture_is_modal() -> None:
    screen = DIALOG.read_text()
    assert "Describe the issue below:" in screen  # sanity: fixture is the dialog
    assert _screen_is_modal_dialog(screen) is True


def test_plain_composer_is_not_modal() -> None:
    screen = PLAIN.read_text()
    assert _screen_is_modal_dialog(screen) is False


def test_transcript_mention_of_esc_does_not_trigger() -> None:
    # Transcript text (middle of screen) mentioning "Esc to cancel" must not
    # trip detection — only the bottom of the viewport counts.
    screen = "line one\nEsc to cancel somewhere in history\n" + "filler\n" * 40 + "❯ \n"
    assert _screen_is_modal_dialog(screen) is False


def test_dialog_footer_variants_trigger() -> None:
    for footer in (
        "Enter to continue · Esc to cancel",
        "Esc to close",
        "esc to dismiss",
        "Esc to go back",
    ):
        assert _screen_is_modal_dialog("x\n" + footer) is True, footer
