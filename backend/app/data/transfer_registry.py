"""
Transfer Registry — Simulated server-side transfer metadata.

In a real Razorpay integration, transfer metadata (ordered quantity, total amount,
vendor details) would be fetched from Razorpay's Route API or an internal order
management system. For this prototype, we maintain a deterministic server-side
registry so that ordered_quantity is NEVER a user-supplied financial input.

This is a security boundary: the document is validated against what the system
already knows was ordered, not what the user claims was ordered.
"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class TransferRecord(BaseModel):
    transfer_id: str
    total_amount: Decimal
    ordered_quantity: int
    vendor_name: str
    item_description: str


# ── Simulated transfer records ─────────────────────────────────────────────────
# Each record represents a Razorpay Route transfer that has been placed on hold
# pending fulfillment verification.  The ordered_quantity comes from the purchase
# order that created the transfer — it is authoritative server-side data.

SIMULATED_TRANSFERS: dict[str, TransferRecord] = {

    # SAFE demo: all goods accounted for, Route action executes automatically.
    # Corresponds to synthetic document dataset/images/challan_043.png
    "TRF_DEMO_SAFE": TransferRecord(
        transfer_id="TRF_DEMO_SAFE",
        total_amount=Decimal("105000.00"),
        ordered_quantity=105,
        vendor_name="Sharma Logistics Pvt Ltd",
        item_description="Industrial pressure valves — Batch B-2026",
    ),

    # UNACCOUNTED demo: arithmetic mismatch (unaccounted qty = 5), Safety Engine
    # escalates to Human Review.
    # Corresponds to synthetic document dataset/images/challan_053.png
    "TRF_DEMO_REVIEW": TransferRecord(
        transfer_id="TRF_DEMO_REVIEW",
        total_amount=Decimal("145000.00"),
        ordered_quantity=145,
        vendor_name="Patel Electronic Distributors",
        item_description="Electronic control modules — Order EL-9912",
    ),

    # CONFLICT demo: used to demonstrate the two-pass disagreement flow.
    # The mock provider returns conflicting Pass 1 / Pass 2 values for this transfer.
    # Clearly labelled as SIMULATED MODEL CONFLICT — not a real Gemini disagreement.
    "TRF_DEMO_CONFLICT": TransferRecord(
        transfer_id="TRF_DEMO_CONFLICT",
        total_amount=Decimal("80000.00"),
        ordered_quantity=80,
        vendor_name="Mehta Auto Supplies",
        item_description="Automotive brake components — PO-4471",
    ),
}


def get_transfer(transfer_id: str) -> Optional[TransferRecord]:
    """Look up a transfer by ID.  Returns None if not found."""
    return SIMULATED_TRANSFERS.get(transfer_id)


def list_transfers() -> list[TransferRecord]:
    """Return all registered transfers (for the demo dropdown)."""
    return list(SIMULATED_TRANSFERS.values())
