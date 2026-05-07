"""
Event-driven stage auto-progression.

Called inline (fire-and-forget) after email/deal events.
Forward-only: never regresses stage. Manual overrides are respected.

Stage flow: new → contacted → replied → engaged → quoting

Rules:
  1. At least 1 outbound email sent           → new → contacted
  2. At least 1 inbound email received         → contacted → replied
  3. 3+ total emails OR at least 1 deal exists → replied → engaged
  4. Quote requested (email intent or deal room)→ engaged → quoting
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

STAGE_ORDER = {
    "new": 0,
    "contacted": 1,
    "replied": 2,
    "engaged": 3,
    "quoting": 4,
}


async def evaluate_stage_progression(conn, customer_id: int) -> Optional[str]:
    """
    Evaluate whether a customer's stage should advance.
    Returns new stage string if progression is warranted, else None.
    Single SQL query, ~30ms.
    """
    row = await conn.fetchrow("""
        SELECT
            c.stage AS current_stage,
            COALESCE((SELECT COUNT(*) FROM crm_emails
                      WHERE customer_id = $1 AND direction = 'sent'), 0) AS sent_count,
            COALESCE((SELECT COUNT(*) FROM crm_emails
                      WHERE customer_id = $1 AND direction = 'received'), 0) AS received_count,
            COALESCE((SELECT COUNT(*) FROM crm_emails
                      WHERE customer_id = $1), 0) AS total_emails,
            COALESCE((SELECT COUNT(*) FROM deals
                      WHERE client_id = $1), 0) AS deal_count,
            COALESCE((SELECT COUNT(*) FROM crm_emails
                      WHERE customer_id = $1 AND direction = 'received'
                      AND intent IN ('question', 'interested')), 0) AS quote_email_count,
            COALESCE((SELECT COUNT(*) FROM deals
                      WHERE client_id = $1
                      AND room_status = 'quote_requested'), 0) AS quote_deal_count
        FROM clients c
        WHERE c.client_id = $1
    """, customer_id)

    if not row or not row['current_stage']:
        return None

    current = row['current_stage']
    current_order = STAGE_ORDER.get(current, -1)
    if current_order < 0 or current_order >= STAGE_ORDER["quoting"]:
        return None

    new_stage = current

    # Rule 1: new → contacted (sent at least one email)
    if current_order < STAGE_ORDER["contacted"] and row['sent_count'] > 0:
        new_stage = "contacted"

    # Rule 2: contacted → replied (received at least one email)
    if STAGE_ORDER[new_stage] < STAGE_ORDER["replied"] and row['received_count'] > 0:
        new_stage = "replied"

    # Rule 3: replied → engaged (3+ total exchanges OR has deals)
    if STAGE_ORDER[new_stage] < STAGE_ORDER["engaged"]:
        if row['total_emails'] >= 3 or row['deal_count'] > 0:
            new_stage = "engaged"

    # Rule 4: engaged → quoting (quote requested via email intent OR deal room)
    if STAGE_ORDER[new_stage] < STAGE_ORDER["quoting"]:
        if row['quote_email_count'] > 0 or row['quote_deal_count'] > 0:
            new_stage = "quoting"

    if new_stage != current:
        return new_stage
    return None


async def apply_stage_progression(conn, customer_id: int) -> Optional[str]:
    """
    Evaluate and apply stage progression. Returns new stage if changed, else None.
    Fire-and-forget safe — catches all exceptions internally.
    """
    try:
        new_stage = await evaluate_stage_progression(conn, customer_id)
        if new_stage:
            await conn.execute(
                "UPDATE clients SET stage = $1, updated_at = NOW() "
                "WHERE client_id = $2",
                new_stage, customer_id,
            )
            logger.info(
                f"Stage auto-progressed: customer {customer_id} → {new_stage}"
            )
            return new_stage
    except Exception as e:
        logger.warning(f"Stage progression failed for customer {customer_id}: {e}")
    return None
