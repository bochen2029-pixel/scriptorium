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


def test_driver_identity_two_harnesses(monkeypatch):
    """RATIFIED item 8: the driver is claude-code or dsh, honestly reported."""
    for var in ("SCRIPTORIUM_DRIVER_HARNESS", "SCRIPTORIUM_DRIVER_MODEL",
                "CLAUDECODE", "ANTHROPIC_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert a2a._driver_identity() == ("dsh", "dsh")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert a2a._driver_identity() == ("claude-code", "claude")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-fable-5")
    assert a2a._driver_identity() == ("claude-code", "claude-fable-5")
    monkeypatch.setenv("SCRIPTORIUM_DRIVER_HARNESS", "dsh")
    monkeypatch.setenv("SCRIPTORIUM_DRIVER_MODEL", "glm-5.3-flash")
    assert a2a._driver_identity() == ("dsh", "glm-5.3-flash")


def test_join_carries_driver_identity(monkeypatch):
    monkeypatch.setenv("SCRIPTORIUM_DRIVER_HARNESS", "claude-code")
    monkeypatch.setenv("SCRIPTORIUM_DRIVER_MODEL", "claude-fable-5")
    log: list[list[str]] = []
    b = fake_bridge([CP(0, "ab12cd34\n")], log)
    b.join()
    argv = log[0]
    assert argv[argv.index("--harness") + 1] == "claude-code"
    assert argv[argv.index("--model") + 1] == "claude-fable-5"


def test_runner_honors_cli_path(monkeypatch):
    """The INTERCOM_PY override must reach the actual subprocess argv (it was
    once validated in begin() but ignored by the transport)."""
    import subprocess as sp
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return CP(0, "ok", "")

    monkeypatch.setattr(sp, "run", fake_run)
    b = IntercomBridge(project="p", lane="l", cli="X:/custom/intercom.py")
    b.me = "x"
    b.say("hello")
    assert seen["argv"][1] == "X:/custom/intercom.py"


def test_pin_artifact_attestation():
    log: list[list[str]] = []
    b = fake_bridge([CP(0, "pinned", "")], log)
    b.me = "x"
    a2a.pin(b, "C:\\arch\\catalog\\cards\\cards.jsonl", "receipt")
    argv = log[0]
    assert argv[0] == "pin"
    assert argv[argv.index("--file") + 1] == "C:/arch/catalog/cards/cards.jsonl"
    assert argv[-1] == "receipt"

    a2a.pin(None, "x", "no-op")                      # disabled: pure no-op
    b2 = fake_bridge([CP(1, "", "dead")], [])
    b2.me = "x"
    a2a.pin(b2, "y", "soft failure never raises")


def test_try_claim_semantics():
    """True = ours (or bus down/disabled); False = a live co-driver owns it."""
    assert a2a.try_claim(None, "r") is True          # disabled: pure no-op

    log: list[list[str]] = []
    b = fake_bridge([CP(0, "ok", "")], log)
    b.me = "x"
    assert a2a.try_claim(b, "scriptorium:a:p2:d1:0") is True
    assert log[0][0] == "claim"
    assert log[0][log[0].index("--resource") + 1] == "scriptorium:a:p2:d1:0"

    b2 = fake_bridge([CP(3, "", "held by other")], [])
    b2.me = "x"
    assert a2a.try_claim(b2, "r") is False           # refusal: skip, no write

    b3 = fake_bridge([CP(1, "", "bus dead")], [])
    b3.me = "x"
    assert a2a.try_claim(b3, "r") is True            # soft failure: proceed
