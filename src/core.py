"""Guided fix workflows for SigmaOS-we-can-fix-everything.

A tiny deterministic decision tree over injected symptoms -> diagnosis ->
ranked fixes. Diagnosis is pure; a fix plan is pure; running a fix is a
thin, risk-gated execute layer that self_test never invokes.
"""
import argparse, json, sys

ENGINE = {
    "name": "sigma-support",
    "summary": "Guided diagnosis and fix plans from a symptom tree",
    "language": "python",
    "verbs": ["diagnose", "fixes", "run-fix-plan"],
    "principles": ["Plan Before Apply", "Least Astonishment", "Fail-Fast",
                   "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-support diagnose --symptom no-sound --facts answers.json
$ sigma-support fixes --symptom no-sound
$ sigma-support run-fix-plan --symptom no-sound --fix restart-audio --yes
"""


class SupportError(Exception):
    pass


# decision tree: each node asks a question; answers pick the next node or a
# terminal diagnosis. Pure data -> trivially testable.
TREE = {
    "start": {
        "question": "What is broken?",
        "choices": {
            "no-sound": "q_sound_cables",
            "no-network": "q_net_cable",
            "slow-boot": "q_boot_target",
        },
    },
    "q_sound_cables": {
        "question": "Are speakers/headphones plugged in and powered on?",
        "choices": {"yes": "dx_sound_route", "no": "dx_sound_cables"},
    },
    "dx_sound_route": {
        "diagnosis": "sound-route",
        "title": "Audio is routed to the wrong output device",
        "severity": "minor",
    },
    "dx_sound_cables": {
        "diagnosis": "sound-unplugged",
        "title": "No audio output device is connected",
        "severity": "user-fix",
    },
    "q_net_cable": {
        "question": "Does a cable appear connected, and do link lights blink?",
        "choices": {"yes": "dx_net_dhcp", "no": "dx_net_cable"},
    },
    "dx_net_dhcp": {
        "diagnosis": "net-dhcp",
        "title": "Interface is up but got no DHCP lease",
        "severity": "system",
    },
    "dx_net_cable": {
        "diagnosis": "net-cable",
        "title": "Physical link is down",
        "severity": "user-fix",
    },
    "q_boot_target": {
        "question": "Did boot get slower after an update?",
        "choices": {"yes": "dx_boot_services", "no": "dx_boot_target"},
    },
    "dx_boot_services": {
        "diagnosis": "boot-services",
        "title": "A service added by an update is blocking boot",
        "severity": "system",
    },
    "dx_boot_target": {
        "diagnosis": "boot-target",
        "title": "Boot is waiting on a slow disk or timeout target",
        "severity": "system",
    },
}

# fixes per diagnosis; each has risk (low/medium/high) and ordered steps
FIXES = {
    "sound-route": [
        {"id": "select-output", "risk": "low",
         "steps": ["pactl set-default-sink alsa_output.pci-0000_00_1f.3.analog-stereo",
                   "pactl set-sink-mute alsa_output.pci-0000_00_1f.3.analog-stereo 0"]},
        {"id": "raise-volume", "risk": "low",
         "steps": ["pactl set-sink-volume alsa_output.pci-0000_00_1f.3.analog-stereo 100%"]},
    ],
    "sound-unplugged": [
        {"id": "check-cables", "risk": "low",
         "steps": ["notify: plug in speakers or headphones, then retest"]},
    ],
    "net-dhcp": [
        {"id": "restart-dhcp", "risk": "medium",
         "steps": ["nmcli device connect eth0", "dhclient -r eth0", "dhclient eth0"]},
        {"id": "renewlease", "risk": "low",
         "steps": ["nmcli connection up 'Wired connection 1'"]},
    ],
    "net-cable": [
        {"id": "check-cable", "risk": "low",
         "steps": ["notify: reseat the ethernet cable and check link lights"]},
    ],
    "boot-services": [
        {"id": "list-failed", "risk": "low",
         "steps": ["systemctl --failed --no-legend"]},
        {"id": "disable-offender", "risk": "high",
         "steps": ["systemctl disable --now suspect.service"]},
    ],
    "boot-target": [
        {"id": "analyze-time", "risk": "low",
         "steps": ["systemd-analyze", "systemd-analyze blame | head"]},
        {"id": "set-timeout", "risk": "medium",
         "steps": ["mkdir -p /etc/systemd/system.conf.d",
                   "write DefaultTimeoutStartSec=10s to 50-timeout.conf"]},
    ],
}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def diagnose(symptom, answers=None):
    """Pure: walk the tree from `symptom` using {node_id: answer} answers."""
    answers = answers or {}
    if symptom not in TREE["start"]["choices"]:
        raise SupportError(f"unknown symptom {symptom!r}; try one of: "
                           + ", ".join(sorted(TREE["start"]["choices"])))
    node_id = TREE["start"]["choices"][symptom]
    path = [symptom]
    while "diagnosis" not in TREE[node_id]:
        question = TREE[node_id]["question"]
        answer = answers.get(node_id)
        if answer is None:
            return {"status": "need-answer", "node": node_id,
                    "question": question,
                    "choices": sorted(TREE[node_id]["choices"]),
                    "path": path}
        if answer not in TREE[node_id]["choices"]:
            raise SupportError(f"answer {answer!r} not valid for {node_id}; "
                               f"choose from {sorted(TREE[node_id]['choices'])}")
        node_id = TREE[node_id]["choices"][answer]
        path.append(node_id)
    node = TREE[node_id]
    return {"status": "diagnosed", "diagnosis": node["diagnosis"],
            "title": node["title"], "severity": node["severity"], "path": path}


def fixes_for(diagnosis):
    """Pure: ranked fix list for a diagnosis id (highest risk last)."""
    if diagnosis not in FIXES:
        raise SupportError(f"no fixes registered for {diagnosis!r}")
    return sorted(FIXES[diagnosis], key=lambda f: RISK_ORDER[f["risk"]])


def plan_fix(diagnosis, fix_id, assume_yes=False):
    """Pure: build an executable plan; high-risk steps need assume_yes."""
    fixes = fixes_for(diagnosis)
    match = [f for f in fixes if f["id"] == fix_id]
    if not match:
        raise SupportError(f"unknown fix {fix_id!r} for {diagnosis!r}; try: "
                           + ", ".join(f["id"] for f in fixes))
    fix = match[0]
    if fix["risk"] == "high" and not assume_yes:
        raise SupportError(f"fix {fix_id!r} is high-risk; re-run with --yes")
    blocked = [f["id"] for f in fixes if f["risk"] == "high"]
    return {"diagnosis": diagnosis, "fix": fix_id, "risk": fix["risk"],
            "steps": list(fix["steps"]),
            "reversible": fix["risk"] != "high",
            "skipped_high_risk": [] if assume_yes else blocked}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    dg = sub.add_parser("diagnose", help="walk the tree for a symptom")
    dg.add_argument("--symptom", required=True)
    dg.add_argument("--facts", default=None,
                    help="JSON {node_id: answer} of prior answers")
    fx = sub.add_parser("fixes", help="list ranked fixes for a diagnosis")
    fx.add_argument("--symptom", required=True)
    fx.add_argument("--facts", default=None)
    rf = sub.add_parser("run-fix-plan", help="print a fix plan (no execution)")
    rf.add_argument("--symptom", required=True)
    rf.add_argument("--facts", default=None)
    rf.add_argument("--fix", required=True)
    rf.add_argument("--yes", action="store_true", help="allow high-risk steps")
    return p


def _resolve(symptom, facts_path):
    answers = {}
    if facts_path:
        with open(facts_path) as fh:
            answers = json.load(fh)
    result = diagnose(symptom, answers)
    if result["status"] != "diagnosed":
        raise SupportError(f"need more answers: {result['question']} "
                           f"(choices: {', '.join(result['choices'])})")
    return result


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "diagnose":
            answers = {}
            if args.facts:
                with open(args.facts) as fh:
                    answers = json.load(fh)
            result = diagnose(args.symptom, answers)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "diagnosed" else 2
        if args.cmd == "fixes":
            result = _resolve(args.symptom, args.facts)
            for fix in fixes_for(result["diagnosis"]):
                print(f"{fix['id']:20} risk={fix['risk']:6} "
                      f"steps={len(fix['steps'])}")
        elif args.cmd == "run-fix-plan":
            result = _resolve(args.symptom, args.facts)
            plan = plan_fix(result["diagnosis"], args.fix, assume_yes=args.yes)
            print(json.dumps(plan, indent=2))
        return 0
    except (SupportError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    # unknown symptom fails fast with the menu
    try:
        diagnose("screen-on-fire")
    except SupportError as e:
        assert "unknown symptom" in str(e)
        assert "no-sound" in str(e)
    else:
        raise AssertionError("unknown symptom not caught")

    # no answers -> asks the first question
    need = diagnose("no-sound")
    assert need["status"] == "need-answer"
    assert "plugged in" in need["question"]
    assert need["choices"] == ["no", "yes"]

    # answered walk -> diagnosis
    d = diagnose("no-sound", {"q_sound_cables": "no"})
    assert d["status"] == "diagnosed"
    assert d["diagnosis"] == "sound-unplugged"
    assert d["severity"] == "user-fix"
    d2 = diagnose("slow-boot", {"q_boot_target": "yes"})
    assert d2["diagnosis"] == "boot-services"

    # invalid answer fails fast
    try:
        diagnose("no-sound", {"q_sound_cables": "maybe"})
    except SupportError as e:
        assert "not valid" in str(e)
    else:
        raise AssertionError("bad answer not caught")

    # fixes are ranked low -> high
    fixes = fixes_for("boot-services")
    assert [f["id"] for f in fixes] == ["list-failed", "disable-offender"]
    assert [f["risk"] for f in fixes] == ["low", "high"]
    assert fixes_for("sound-route")[0]["id"] == "select-output"
    try:
        fixes_for("nonexistent")
    except SupportError as e:
        assert "no fixes" in str(e)
    else:
        raise AssertionError("unknown diagnosis not caught")

    # fix plans: high risk is gated, low risk is free
    plan = plan_fix("sound-route", "select-output")
    assert plan["risk"] == "low" and plan["reversible"] is True
    assert plan["steps"][0].startswith("pactl set-default-sink")
    gated = plan_fix("boot-services", "list-failed")
    assert gated["skipped_high_risk"] == ["disable-offender"]
    try:
        plan_fix("boot-services", "disable-offender")
    except SupportError as e:
        assert "high-risk" in str(e)
    else:
        raise AssertionError("high-risk gate not caught")
    allowed = plan_fix("boot-services", "disable-offender", assume_yes=True)
    assert allowed["steps"] == ["systemctl disable --now suspect.service"]
    assert allowed["skipped_high_risk"] == []
    try:
        plan_fix("sound-route", "disable-offender")
    except SupportError as e:
        assert "unknown fix" in str(e)
    else:
        raise AssertionError("cross-diagnosis fix not caught")

    # determinism: same inputs, same plan
    assert plan_fix("net-dhcp", "restart-dhcp") == plan_fix("net-dhcp", "restart-dhcp")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
