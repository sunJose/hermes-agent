"""Tests for soft-archiving sessions."""

from hermes_state import SessionDB


def test_set_session_archived_hides_from_default_list(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    db.create_session("keep", source="cli")
    db.append_message("keep", role="user", content="keep me visible")
    db.create_session("hide", source="cli")
    db.append_message("hide", role="user", content="archive me")

    assert db.set_session_archived("hide", True) is True

    default_ids = {s["id"] for s in db.list_sessions_rich(include_children=True)}
    assert "keep" in default_ids
    assert "hide" not in default_ids

    archived_ids = {
        s["id"]
        for s in db.list_sessions_rich(include_children=True, archived_only=True)
    }
    assert archived_ids == {"hide"}

    include_ids = {
        s["id"]
        for s in db.list_sessions_rich(include_children=True, include_archived=True)
    }
    assert {"keep", "hide"}.issubset(include_ids)


def test_set_session_archived_can_unarchive(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    db.create_session("s", source="cli")
    db.append_message("s", role="user", content="hello")

    assert db.set_session_archived("s", True) is True
    assert db.set_session_archived("s", False) is True

    default_ids = {s["id"] for s in db.list_sessions_rich(include_children=True)}
    assert "s" in default_ids
    archived_ids = {
        s["id"]
        for s in db.list_sessions_rich(include_children=True, archived_only=True)
    }
    assert "s" not in archived_ids


def test_set_session_archived_returns_false_for_missing_session(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    assert db.set_session_archived("missing", True) is False
