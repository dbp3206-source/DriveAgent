"""No model/provider: bounded approvals and actual SQL FK ownership."""

from dataclasses import replace

import pytest
from test_retention_policy import NOW, candidate

from app.services.retention_policy import RetentionPolicyError
from app.services.retention_selection import select_batch


def test_fresh_descendant_keeps_parent_and_does_not_hide_independent_old_content():
    parent = candidate(record_id="parent", age=40)
    child = candidate(record_id="child", age=1)
    free = candidate(record_id="independent", age=32)
    assert select_batch([parent, child, free], {parent.key: {child.key}}, now=NOW) == (free,)


def test_oversized_parent_waits_while_children_are_selected_then_can_finish():
    parent = candidate(record_id="parent", age=50)
    children = [candidate(record_id=f"child-{index:03}") for index in range(205)]
    links = {parent.key: {item.key for item in children}}
    first = select_batch([parent, *children], links, now=NOW)
    assert len(first) == 200 and parent not in first
    assert all(item in children for item in first)
    remaining = [item for item in children if item not in first]
    second = select_batch([parent, *remaining], {parent.key: {item.key for item in remaining}},
                          now=NOW)
    assert set(second) == {parent, *remaining}


def test_shared_descendant_counted_once_and_missing_or_cycle_rejected():
    parent, other, child = (candidate(record_id=name) for name in ("parent", "other", "child"))
    selected = select_batch([parent, other, child],
                            {parent.key: {child.key}, other.key: {child.key}}, now=NOW)
    assert set(selected) == {parent, other, child} and len(selected) == 3
    with pytest.raises(RetentionPolicyError, match="not_in_inventory"):
        select_batch([parent], {parent.key: {child.key}}, now=NOW)
    with pytest.raises(RetentionPolicyError, match="dependency_cycle"):
        select_batch([parent, child], {parent.key: {child.key}, child.key: {parent.key}}, now=NOW)
    assert select_batch([parent, replace(child, active=True)], {parent.key: {child.key}},
                        now=NOW) == ()
