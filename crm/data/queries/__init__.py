"""Complex analytical queries for CRM."""

from .insights_queries import (
    analyze_customer_activity,
    get_comprehensive_customer_data,
    get_customer_basic_info
)

from .deal_queries import (
    get_active_deals_for_room_analysis,
    get_deal_communications_comprehensive
)

__all__ = [
    'analyze_customer_activity',
    'get_comprehensive_customer_data',
    'get_customer_basic_info',
    'get_active_deals_for_room_analysis',
    'get_deal_communications_comprehensive',
]

