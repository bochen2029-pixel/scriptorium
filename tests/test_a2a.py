"""A2A layer under test: opt-in gating, lease refusal stops the pass, soft bus
failures degrade to no-ops, body cap, end never raises. The real Intercom CLI
is never executed here (fake runner / monkeypatched subprocess runner)."""

import pytest

import a2a
from a2a import A2ARefused, IntercomBridge


class CP:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_bridge(script: list[CP], log: list[list[str]]) -> IntercomBridge:
    def run(argv: list[str]) -> CP:
        log.append(list(argv))
        return script.pop(0) if script else CP(0, "ok", "")
    return IntercomBridge(project="scriptorium-test",
                          lane="orchestrator-test", runner=run)


def test_join_mints_id_and_later_verbs_carry_it():
    log: list[list[str]] = []
    b = fake_bridge([CP(0, "boot log line\nab12cd34\n")], log)
    assert b.join() == "ab12cd34"
    b.say("hello")
    b.claim("scriptorium:arch:p2-read")
    b.release("scriptorium:arch:p2-read")
    b.leave()
    assert log[0][0] == "join"
    assert log[1][:3] == ["say", "--me", "ab12cd34"]
    assert log[1][-3] == "--type" and log[1][-2] == "finding"
    assert log[2][0] == "claim" and log[2][-2:] == ["--ttl", "900"]
    assert log[3][0] == "release" and log[4][0] == "leave"


def test_exit3_is_refused_and_other_failures_are_soft():
    log: list[list[str]] = []
    b = fake_bridge([CP(3, "", "refused: held by z9")], log)
    b.me = "x"                    # joined before claiming (the real flow)
    with pytest.raises(A2ARefused, match="held by z9"):
        b.claim("x")
    b2 = fake_bridge([CP(1, "", "boom")], [])
    b2.me = "x"
    with pytest.raises(a2a._Soft):
        b2.claim("x")


def test_say_body_capped_at_4k():
    log: list[list[str]] = []
    b = fake_bridge([], log)
    b.me = "x"
    b.say("A" * 10000)
    assert len(log[0][-1]) == a2a.BODY_CAP


def test_note_and_end_never_raise():
    log: list[list[str]] = []
    b = fake_bridge([CP(1, "", "dead")] * 10, log)
    b.me = "x"
    b.resource = "r"
    a2a.note(b, "msg")            # say fails -> noted, no raise
    a2a.end(b, "summary")         # say/release/leave all fail -> no raise
    a2a.note(None, "x")           # None bridge: pure no-op
    a2a.end(None, "y")


def test_end_happy_path_order():
    log: list[list[str]] = []
    b = fake_bridge([], log)
    b.me = "x"
    b.resource = "scriptorium:a:p2-read"
    a2a.end(b, "cards 3 quar 1 $0.001")
    assert log[0][0] == "say" and log[0][-1].startswith("run_end: cards 3")
    assert log[1][:2] == ["release", "--me"]
    assert log[2][0] == "leave"


def test_begin_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SCRIPTORIUM_A2A", raising=False)
    called = []

    def spy(argv):
        called.append(argv)
        return CP(0, "x", "")

    monkeypatch.setattr(a2a.IntercomBridge, "_subprocess_runner",
                        staticmethod(spy))
    assert a2a.begin("P2-read", "arch") is None
    assert called == []           # zero subprocess traffic when disabled


def test_begin_bus_down_returns_none(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_A2A", "1")
    # the real runner contract: OSError is caught and degraded to exit-1 CP
    monkeypatch.setattr(
        a2a.IntercomBridge, "_subprocess_runner",
        staticmethod(lambda argv: CP(1, "", "OSError: no interpreter")))
    assert a2a.begin("P2-read", "arch") is None


def test_begin_refused_stops_the_pass(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_A2A", "1")

    def runner(argv):
        return CP(0, "id1\n") if argv[0] == "join" else CP(3, "", "held")

    monkeypatch.setattr(a2a.IntercomBridge, "_subprocess_runner",
                        staticmethod(runner))
    with pytest.raises(SystemExit, match="held by another live driver"):
        a2a.begin("P2-read", "arch")


def test_begin_happy_path_identity_and_lease(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_A2A", "1")

    def runner(argv):
        return CP(0, "ab12cd34\n") if argv[0] == "join" else CP(0, "ok", "")

    monkeypatch.setattr(a2a.IntercomBridge, "_subprocess_runner",
                        staticmethod(runner))
    b = a2a.begin("P2-read", "myarch")
    assert b is not None
    assert b.me == "ab12cd34"
    assert b.resource == "scriptorium:myarch:p2-read"
    assert b.project == "scriptorium-myarch"
    assert b.lane == "orchestrator-p2-read"


def test_begin_cli_missing_disables(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_A2A", "1")
    monkeypatch.setenv("INTERCOM_PY", "C:/definitely/missing/intercom.py")
    assert a2a.begin("P", "a") is None
