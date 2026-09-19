from __future__ import annotations

from procedures.models import Procedure, check_environment, recall_procedure


def test_env_mismatch() -> None:
    p = Procedure(
        workspace_id="ws",
        name="deploy-api",
        goal="deploy api",
        environment_constraints={"kubernetes": "1.31", "helm": "3"},
    )
    assert check_environment(p, {"kubernetes": "1.28", "helm": "2"}) == "INCOMPATIBLE"
    assert check_environment(p, {"kubernetes": "1.31", "helm": "3"}) == "VALID"


def test_recall_prefers_successful_version() -> None:
    procs = [
        Procedure(workspace_id="ws", name="restart", goal="restart payments", version=1, success_count=1),
        Procedure(workspace_id="ws", name="restart", goal="restart payments", version=2, success_count=10),
    ]
    out = recall_procedure(procs, goal="restart payments", current_env={})
    assert out is not None
    assert out["procedure"]["version"] == 2
