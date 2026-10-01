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


def test_safety_policy_breach_is_distinct_from_stockout_and_action_availability():
    from decimal import Decimal

    facts = inventory_facts(
        "Kho có 1.600 sản phẩm; nhu cầu trung bình 420/tuần, ±100; "
        "lead time 3 tuần; safety stock 250; đơn nhập 500 chiếc đến sau 2 tuần."
    )
    high = facts["scenarios"][2]
    assert high["ending_without_delivery"] == "40"
    assert high["risk_without_delivery_at_horizon"] == "below_safety_stock"
    assert Decimal(high["weeks_until_safety_stock_without_receipts"]) < 3
    assert Decimal(high["weeks_until_stockout_without_receipts"]) > 3
    assert "conditional options" in facts["feasibility_constraints"][1]


def test_zero_demand_has_no_invented_deadline():
    facts = inventory_facts(
        "Kho có 100 sản phẩm; nhu cầu trung bình 20/tuần, ±20; "
        "lead time 3 tuần; safety stock 10; đơn nhập 5 chiếc đến sau 2 tuần."
    )
    assert facts["scenarios"][0]["weeks_until_stockout_without_receipts"] is None


def test_adk_uses_verified_quantitative_execution_path():
    from app.agent.adk_orchestrator import AdkOrchestrator
    from app.agent.controls import ChatControls
    from app.agent.routing import Route

    message = "Kho có 1.600 sản phẩm; nhu cầu trung bình 420/tuần, ±100; " \
              "lead time 3 tuần; safety stock 250; đơn nhập 500 chiếc đến sau 2 tuần."
    assert AdkOrchestrator._should_use_compiler(ChatControls(source="general"), Route(), message)
