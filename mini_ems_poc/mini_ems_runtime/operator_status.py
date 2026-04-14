from typing import Optional


def build_operator_message(
    current_price_ct_kwh: float,
    current_slot_label: str,
    today_date_iso: str,
    tomorrow_prices_available: bool,
    safe_mode_active: bool,
    safe_mode_reason: Optional[str],
    degraded_reason: Optional[str] = None,
) -> str:
    if safe_mode_active:
        return "Current spot price for {0} on {1} is {2:.4f} ct/kWh. Write status failed. Reason: {3}.".format(
            current_slot_label,
            today_date_iso,
            current_price_ct_kwh,
            safe_mode_reason or "unknown",
        )

    if degraded_reason:
        return (
            "Current spot price for {0} on {1}: {2:.4f} ct/kWh. "
            "Runtime is degraded. Reason: {3}. Tomorrow cache is {4}."
        ).format(
            current_slot_label,
            today_date_iso,
            current_price_ct_kwh,
            degraded_reason,
            "available" if tomorrow_prices_available else "not available yet",
        )

    parts = [
        "Current spot price for {0} on {1}: {2:.4f} ct/kWh.".format(
            current_slot_label,
            today_date_iso,
            current_price_ct_kwh,
        ),
        "Tomorrow cache is {0}.".format(
            "available" if tomorrow_prices_available else "not available yet"
        ),
    ]
    return " ".join(parts)
