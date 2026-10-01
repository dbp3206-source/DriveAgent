"""Exact balances for unambiguous weekly inventory inputs; no probability inference."""

import re
from decimal import Decimal


def inventory_facts(message: str) -> dict | None:
    number = r"(\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?)"
    patterns = {
        "initial": rf"(?:kho có|tồn kho ban đầu)\s+{number}\s+(?:sản phẩm|chiếc|đơn vị)",
        "demand": rf"nhu cầu\s+(?:trung bình\s+)?{number}\s*/\s*tuần",
        "lead": rf"lead time\s+{number}\s+tuần",
        "safety": rf"safety stock\s+{number}",
        "arrival": rf"đơn nhập\s+{number}\s+(?:chiếc|sản phẩm|đơn vị)",
        "arrival_week": rf"đến sau\s+{number}\s+tuần",
        "variation": rf"±\s*{number}",
    }
    values = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, message, re.I)
        if len(matches) != 1:
            return None
        values[key] = Decimal(matches[0].replace(".", "").replace(",", "."))
    if values["variation"] > values["demand"] or values["lead"] <= 0:
        return None
    scenarios = []
    for name, demand in (("low", values["demand"] - values["variation"]),
                         ("base", values["demand"]),
                         ("high", values["demand"] + values["variation"])):
        incoming = values["arrival"] if values["arrival_week"] <= values["lead"] else Decimal(0)
        total = demand * values["lead"]
        ending = values["initial"] + incoming - total
        scenarios.append({
            "scenario": name, "weekly_demand": str(demand), "lead_time_demand": str(total),
            "ending_stock": str(ending), "buffer_above_safety": str(ending - values["safety"]),
            "before_arrival_stock": str(values["initial"] - demand * values["arrival_week"]),
            "ending_without_delivery": str(values["initial"] - total),
            "risk_without_delivery_at_horizon": (
                "unmet_demand" if values["initial"] - total < 0
                else "below_safety_stock" if values["initial"] - total < values["safety"]
                else "at_or_above_safety_stock"
            ),
            "weeks_until_safety_stock_without_receipts": (
                str((values["initial"] - values["safety"]) / demand)
                if demand > 0 else None
            ),
            "weeks_until_stockout_without_receipts": (
                str(values["initial"] / demand) if demand > 0 else None
            ),
        })
    return {
        "method": "Decimal: initial + arrivals - weekly demand * weeks",
        "assumptions": ["Uniform weekly demand", "Delivery at the stated week end",
                        "No other receipts, losses or reservations"],
        "inputs": {key: str(value) for key, value in values.items()},
        "scenarios": scenarios,
        "reorder_point_base": str(values["demand"] * values["lead"] + values["safety"]),
        "current_inventory_position_without_backorders": str(values["initial"] + values["arrival"]),
        "reorder_policy_note": "Compare reorder point with inventory position, including confirmed "
        "incoming orders and subtracting backorders; do not compare only on-hand stock when "
        "a purchase order is already outstanding. Backorders are not provided in this scenario.",
        "feasibility_constraints": [
            "A standard order placed now arrives after the stated lead time. If the no-receipt "
            "safety-stock crossing occurs earlier, that order cannot prevent this earlier breach.",
            "Expediting, auxiliary stock, transfers and alternative suppliers are not provided "
            "resources. Mention them only as conditional options with availability, approval "
            "and arrival time to verify, not as guaranteed executable actions.",
            "Below safety stock is a policy breach, not automatically stockout. Negative balance "
            "means unmet demand under assumptions, not physically negative inventory.",
            "Thresholds derived from uniform demand are scenario calculations, not probabilities "
            "or confirmed supplier service levels.",
        ],
    }
