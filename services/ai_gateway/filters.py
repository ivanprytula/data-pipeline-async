"""Qdrant filter builder — converts client filter dicts to Qdrant Filter objects."""

from __future__ import annotations

from typing import Any, cast

from qdrant_client.models import FieldCondition, Filter, MatchValue, Range


def dict_to_qdrant_filter(filter_dict: dict[str, Any] | None) -> Filter | None:
    """Convert a dictionary to a Qdrant Filter.

    Supports nested conditions with AND logic.
    Example: {"price": {"gte": 10, "lte": 100}, "category": "electronics"}

    Args:
        filter_dict: Dictionary of field conditions.

    Returns:
        A Qdrant Filter or None if filter_dict is None or empty.
    """
    if not filter_dict:
        return None

    conditions: list[FieldCondition] = []

    for field, condition in filter_dict.items():
        if isinstance(condition, dict):
            cond = _build_field_condition(field, condition)
            if cond:
                conditions.append(cond)
        else:
            cond = _build_field_condition(field, {"eq": condition})
            if cond:
                conditions.append(cond)

    if not conditions:
        return None

    # Cast to broader Qdrant condition union type
    return Filter(must=cast(list, conditions))


def _build_field_condition(
    field: str, condition: dict[str, Any]
) -> FieldCondition | None:
    """Build a FieldCondition from field name and condition dict.

    Args:
        field: Field name in the record.
        condition: Dictionary with operators like 'eq', 'gte', 'lte', 'gt', 'lt'.

    Returns:
        A FieldCondition or None if no valid condition found.
    """
    for operator, value in condition.items():
        if operator == "eq":
            return FieldCondition(key=field, match=MatchValue(value=str(value)))
        elif operator == "gte":
            return FieldCondition(
                key=field,
                range=Range(
                    gte=float(value) if isinstance(value, (int, float)) else None
                ),
            )
        elif operator == "lte":
            return FieldCondition(
                key=field,
                range=Range(
                    lte=float(value) if isinstance(value, (int, float)) else None
                ),
            )
        elif operator == "gt":
            return FieldCondition(
                key=field,
                range=Range(
                    gt=float(value) if isinstance(value, (int, float)) else None
                ),
            )
        elif operator == "lt":
            return FieldCondition(
                key=field,
                range=Range(
                    lt=float(value) if isinstance(value, (int, float)) else None
                ),
            )

    return None
