"""Unit tests for pure functions — no LLM or CRM calls."""
import pytest
from app.services.orchestrator import (
    _is_sensitive,
    _is_bad_reply,
    _is_safe_modification,
    _clean_reply,
)


# =========================
# _is_sensitive
# =========================
class TestIsSensitive:
    def test_detects_fraud(self):
        assert _is_sensitive("This is fraud!") is True

    def test_detects_scam(self):
        assert _is_sensitive("You scammed me") is True

    def test_word_boundary_no_false_positive(self):
        # "legally" should NOT trigger — not a whole word match for "legal"
        # NOTE: update this if regex changes
        assert _is_sensitive("I secretly loved it") is False

    def test_empty_review(self):
        assert _is_sensitive("") is False

    def test_normal_negative_review(self):
        assert _is_sensitive("The service was terrible") is False

    def test_case_insensitive(self):
        assert _is_sensitive("I will go to COURT") is True


# =========================
# _is_bad_reply
# =========================
class TestIsBadReply:
    def test_empty_reply(self):
        assert _is_bad_reply("", 3) is True

    def test_too_short(self):
        assert _is_bad_reply("Sorry about that.", 2) is True

    def test_no_period(self):
        assert _is_bad_reply("We are sorry for your experience and will look into it", 2) is True

    def test_negative_missing_empathy(self):
        assert _is_bad_reply(
            "We have noted your feedback and will act on it accordingly.", 1
        ) is True

    def test_negative_with_empathy(self):
        assert _is_bad_reply(
            "We are truly sorry for your experience. We will look into this immediately.", 1
        ) is False

    def test_duplicate_sentences(self):
        assert _is_bad_reply(
            "Thank you for your feedback. Thank you for your feedback.", 4
        ) is True

    def test_valid_positive_reply(self):
        assert _is_bad_reply(
            "Thank you for the wonderful feedback! We are glad you enjoyed your visit.", 5
        ) is False


# =========================
# _is_safe_modification
# =========================
class TestIsSafeModification:
    def test_empty_inputs(self):
        assert _is_safe_modification("", "something") is False
        assert _is_safe_modification("something", "") is False

    def test_small_change_is_safe(self):
        original = "We are sorry for your experience at our store."
        modified = "We sincerely apologize for your experience at our store."
        assert _is_safe_modification(original, modified) is True

    def test_complete_rewrite_rejected(self):
        original = "Thank you for your kind feedback."
        modified = "We deeply regret the inconvenience caused. Please share your details via the link below."
        assert _is_safe_modification(original, modified) is False


# =========================
# _clean_reply
# =========================
class TestCleanReply:
    def test_removes_duplicate_sentences(self):
        text = "We are sorry. We are sorry. Thank you."
        result = _clean_reply(text)
        assert result.count("We are sorry") == 1

    def test_preserves_unique_sentences(self):
        text = "We are sorry. Thank you for your feedback."
        assert _clean_reply(text) == text
