"""Every audit action has a readable label on screen (History, Audit Log), never the raw code."""
import re
from pathlib import Path

from app.services import client_workflow_service

ROOT = Path(__file__).resolve().parents[2]


def test_every_audit_action_has_a_label():
    code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "backend" / "app").rglob("*.py"))
    actions = set(re.findall(r'log_event\(\s*\w+,\s*"([a-z_]+)"', code)) | set(client_workflow_service._STATUS_ACTIONS)
    labels_js = (ROOT / "frontend" / "src" / "utils" / "auditFormat.js").read_text(encoding="utf-8")
    block = labels_js.split("export const ACTION_LABELS = {", 1)[1].split("};", 1)[0]
    labelled = set(re.findall(r"^\s*([a-z_]+):", block, re.M))
    assert actions, "no audit actions found"
    assert not actions - labelled, f"audit actions without a label: {sorted(actions - labelled)}"
