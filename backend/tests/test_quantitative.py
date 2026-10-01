import pytest

from app.agent.quantitative import inventory_facts


@pytest.mark.parametrize(("initial", "arrival_week", "ending"), [
    ("1.600", 2, "840"), ("2.000", 4, "740"), ("900", 1, "140"),
])
def test_inventory_balance_and_delivery_cutoff(initial, arrival_week, ending):
    facts = inventory_facts(
        f"Kho có {initial} sản phẩm; nhu cầu trung bình 420/tuần, ±100; "
        f"lead time 3 tuần; safety stock 250; đơn nhập 500 chiếc đến sau {arrival_week} tuần."
    )
    assert facts["scenarios"][1]["ending_stock"] == ending
    assert facts["reorder_point_base"] == "1510"
    assert "inventory position" in facts["reorder_policy_note"]


def test_incomplete_or_conflicting_scenario_is_not_inferred():
    assert inventory_facts("Kho có 100 sản phẩm, cần phân tích.") is None
    assert inventory_facts("Kho có 100 sản phẩm. Kho có 200 sản phẩm.") is None


def test_adk_uses_verified_quantitative_execution_path():
    from app.agent.adk_orchestrator import AdkOrchestrator
    from app.agent.controls import ChatControls
    from app.agent.routing import Route

    message = "Kho có 1.600 sản phẩm; nhu cầu trung bình 420/tuần, ±100; " \
              "lead time 3 tuần; safety stock 250; đơn nhập 500 chiếc đến sau 2 tuần."
    assert AdkOrchestrator._should_use_compiler(ChatControls(source="general"), Route(), message)
