import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from openai import OpenAI

from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_comprehensive_analytics_data(conn, user_email: str = None):
    """Get comprehensive analytics data from database

    Args:
        conn: asyncpg connection
        user_email: Authenticated user's email for database routing
    """
    try:
        # Get basic customer data first (without nested aggregates)
        query = """
        SELECT
            ci.client_id,
            ci.name as company,
            p_primary.full_name as primary_contact,
            p_primary.email,
            ci.location,
            ci.status,
            ci.created_at as customer_since,
            COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
            ci.health_score,
            -- Get recent interaction count
            COALESCE((
                SELECT COUNT(*)
                FROM interaction_details i
                WHERE i.customer_id = ci.client_id
                AND i.created_at >= CURRENT_DATE - INTERVAL '30 days'
            ), 0) as interactions_last_30_days
        FROM clients ci
        LEFT JOIN LATERAL (
            SELECT full_name, email FROM personnel
            WHERE client_id = ci.client_id AND is_primary = true
            LIMIT 1
        ) p_primary ON true
        WHERE ci.status IN ('active', 'at-risk')
        ORDER BY
            CASE WHEN ci.status = 'at-risk' THEN 1
                 WHEN ci.health_score < 60 THEN 2
                 ELSE 3 END,
            ci.health_score ASC NULLS LAST
        """

        customers_data = await conn.fetch(query)

        # Get interaction type distribution separately
        interaction_types_query = """
        SELECT
            customer_id,
            json_object_agg(type, type_count) as recent_interaction_types
        FROM (
            SELECT
                customer_id,
                type,
                COUNT(*) as type_count
            FROM interaction_details
            WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY customer_id, type
        ) interaction_summary
        GROUP BY customer_id
        """

        interaction_types_rows = await conn.fetch(interaction_types_query)
        interaction_types_data = {row['customer_id']: row['recent_interaction_types'] for row in interaction_types_rows}

        # Get employee engagement data separately
        employee_engagement_query = """
        SELECT
            customer_id,
            json_object_agg(employee_name, interaction_count) as employee_engagement
        FROM (
            SELECT
                i.customer_id,
                e.name as employee_name,
                COUNT(i.interaction_id) as interaction_count
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.created_at >= CURRENT_DATE - INTERVAL '90 days'
            AND e.name IS NOT NULL
            GROUP BY i.customer_id, e.name
        ) emp_summary
        GROUP BY customer_id
        """

        employee_engagement_rows = await conn.fetch(employee_engagement_query)
        employee_engagement_data = {row['customer_id']: row['employee_engagement'] for row in employee_engagement_rows}

        # Get overall interaction statistics
        interaction_stats_query = """
        SELECT
            COUNT(*) as total_interactions,
            COUNT(DISTINCT customer_id) as customers_with_interactions,
            COALESCE(AVG(EXTRACT(DAY FROM CURRENT_DATE - created_at)), 0) as avg_days_since_interaction,
            COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as interactions_last_7_days,
            COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as interactions_last_30_days
        FROM interaction_details
        WHERE created_at >= CURRENT_DATE - INTERVAL '180 days'
        """

        interaction_stats = await conn.fetchrow(interaction_stats_query)

        # Get interaction type distribution (overall)
        interaction_dist_query = """
        SELECT
            type,
            COUNT(*) as count
        FROM interaction_details
        WHERE created_at >= CURRENT_DATE - INTERVAL '180 days'
        GROUP BY type
        """

        interaction_dist_rows = await conn.fetch(interaction_dist_query)
        interaction_distribution = {row['type']: row['count'] for row in interaction_dist_rows}

        # Get employee productivity stats
        employee_stats_query = """
        SELECT
            e.name,
            e.role,
            e.department,
            COUNT(i.interaction_id) as total_interactions,
            COUNT(DISTINCT i.customer_id) as customers_managed,
            COALESCE(AVG(c.health_score), 0) as avg_customer_health_score,
            COUNT(CASE WHEN c.health_score < 60 THEN 1 END) as high_risk_customers
        FROM employee_info e
        LEFT JOIN interaction_details i ON e.employee_id = i.employee_id
            AND i.created_at >= CURRENT_DATE - INTERVAL '90 days'
        LEFT JOIN clients c ON i.customer_id = c.client_id
        GROUP BY e.employee_id, e.name, e.role, e.department
        HAVING COUNT(i.interaction_id) > 0
        ORDER BY total_interactions DESC
        """

        employee_stats = await conn.fetch(employee_stats_query)

        # Combine the data
        customers_with_extra_data = []
        for customer in customers_data:
            customer_dict = dict(customer)
            customer_id = customer_dict['client_id']

            # Add interaction types data
            customer_dict['recent_interaction_types'] = interaction_types_data.get(customer_id, {})

            # Add employee engagement data
            customer_dict['employee_engagement'] = employee_engagement_data.get(customer_id, {})

            customers_with_extra_data.append(customer_dict)

        # Add interaction distribution to stats
        interaction_stats_dict = dict(interaction_stats) if interaction_stats else {}
        interaction_stats_dict['interaction_type_distribution'] = interaction_distribution

        return {
            'customers': customers_with_extra_data,
            'interaction_stats': interaction_stats_dict,
            'employee_stats': [dict(emp) for emp in employee_stats]
        }

    except Exception as e:
        logger.error(f"Error getting comprehensive analytics data: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching analytics data: {str(e)}")

def process_analytics_data(raw_data):
    """Process raw data into analytics insights format"""
    customers = raw_data['customers']
    interaction_stats = raw_data['interaction_stats']
    employee_stats = raw_data['employee_stats']

    if not customers:
        return {"error": "No customer data found"}

    # Calculate key metrics
    total_customers = len(customers)
    total_deal_value = sum(float(c.get('total_deal_value', 0) or 0) for c in customers)
    avg_health_score = sum(float(c.get('health_score', 0) or 0) for c in customers) / total_customers if total_customers > 0 else 0

    # Segment customers
    high_value_customers = [c for c in customers if float(c.get('total_deal_value', 0) or 0) > 100000]
    at_risk_customers = [c for c in customers if float(c.get('health_score', 100) or 100) < 60]
    low_engagement = [c for c in customers if int(c.get('interactions_last_30_days', 0) or 0) == 0]

    # Status breakdown
    status_breakdown = {}

    for customer in customers:
        # Status
        status = customer.get('status', 'Unknown')
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

    # Calculate engagement metrics
    highly_engaged = len([c for c in customers if int(c.get('interactions_last_30_days', 0) or 0) >= 3])
    total_interactions_30_days = sum(int(c.get('interactions_last_30_days', 0) or 0) for c in customers)

    return {
        "portfolio_overview": {
            "total_customers": total_customers,
            "total_deal_value": total_deal_value,
            "avg_health_score": avg_health_score,
        },
        "segmentation": {
            "high_value_customers": len(high_value_customers),
            "at_risk_customers": len(at_risk_customers),
            "low_engagement_customers": len(low_engagement),
        },
        "breakdowns": {
            "status": status_breakdown
        },
        "engagement_metrics": {
            "highly_engaged_customers": highly_engaged,
            "total_interactions_30_days": total_interactions_30_days,
            "avg_interactions_per_customer": total_interactions_30_days / total_customers if total_customers > 0 else 0
        },
        "top_performers": {
            "high_value_sample": high_value_customers[:5],
            "at_risk_sample": at_risk_customers[:5]
        },
        "employee_performance": employee_stats[:5],  # Top 5 employees by activity
        "interaction_insights": interaction_stats
    }

@router.post("/generate-analytics-insights")
async def generate_analytics_insights(tenant: tuple = Depends(get_tenant_connection)) -> Dict:
    """Generate AI-powered analytics insights using real database data and Gemini AI."""

    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info("Generating AI analytics insights from database...")

        # Get comprehensive data from database
        raw_data = await get_comprehensive_analytics_data(conn, user_email)

        # Process into analytics format
        analytics_data = process_analytics_data(raw_data)

        if "error" in analytics_data:
            return {
                "status": "error",
                "insights": {"content": "No customer data available for analysis."}
            }

        # Get API key and model
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="API key not configured. Please set OPENAI_API_KEY environment variable."
            )

        model_name = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4.1-mini")

        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Create comprehensive analytics prompt
        prompt = f"""You are a Senior Customer Success Analyst providing executive-level insights. Analyze this customer portfolio data and provide strategic recommendations.

PORTFOLIO OVERVIEW:
📊 Total Customers: {analytics_data['portfolio_overview']['total_customers']}
💰 Total Deal Value: ${analytics_data['portfolio_overview']['total_deal_value']:,.2f}
📈 Average Health Score: {analytics_data['portfolio_overview']['avg_health_score']:.1f}/100

CRITICAL SEGMENTS:
🔥 At-Risk Customers: {analytics_data['segmentation']['at_risk_customers']} ({(analytics_data['segmentation']['at_risk_customers']/analytics_data['portfolio_overview']['total_customers']*100):.1f}% of portfolio)
💎 High-Value Customers: {analytics_data['segmentation']['high_value_customers']} (${sum(float(c.get('total_deal_value', 0) or 0) for c in analytics_data['top_performers']['high_value_sample']):,.0f} deal value sample)
📉 Low Engagement: {analytics_data['segmentation']['low_engagement_customers']} customers (no interactions in 30 days)

ENGAGEMENT INSIGHTS:
📞 Total Interactions (30 days): {analytics_data['engagement_metrics']['total_interactions_30_days']}
🎯 Highly Engaged: {analytics_data['engagement_metrics']['highly_engaged_customers']} customers (3+ interactions/month)
📊 Interaction Average: {analytics_data['engagement_metrics']['avg_interactions_per_customer']:.1f} per customer/month

STATUS DISTRIBUTION:
{analytics_data['breakdowns']['status']}

TOP EMPLOYEE PERFORMANCE:
{analytics_data['employee_performance']}

HIGH-VALUE CUSTOMER SAMPLE:
{analytics_data['top_performers']['high_value_sample']}

AT-RISK CUSTOMER SAMPLE:
{analytics_data['top_performers']['at_risk_sample']}

Generate a comprehensive executive analysis with these specific sections:

**AI-Generated Customer Insights**

**Revenue Optimization Opportunity**
[Identify specific revenue growth potential with concrete numbers and customer segments]

**Churn Risk Alert**
[Highlight immediate risks with specific customer counts and recommended actions]

**Success Pattern Identified**
[Identify what's working well with specific metrics and percentages]

**Segmentation Recommendation**
[Provide customer portfolio segmentation with percentages and strategic approach for each segment]

**Employee Performance Insights**
[Analyze team performance and identify optimization opportunities]

**Immediate Action Items**
[3-4 specific, actionable recommendations with customer counts and deadlines]

**Strategic Recommendations**
[2-3 longer-term strategic initiatives based on the data patterns]

Make insights specific, actionable, and data-driven. Include percentages, dollar amounts, and customer counts where relevant. Focus on immediate opportunities and risks that require attention."""

        # Make API call to OpenAI
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a Senior Customer Success Analyst providing executive-level insights."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        # Validate response
        if not response.choices or not response.choices[0].message.content:
            raise Exception("Failed to generate analytics insights")

        insights_content = response.choices[0].message.content.strip()

        logger.info(f"Successfully generated analytics insights for {analytics_data['portfolio_overview']['total_customers']} customers")

        return {
            "status": "success",
            "insights": {
                "content": insights_content,
                "generated_by": f"openai-{model_name}",
                "data_summary": {
                    "total_customers": analytics_data['portfolio_overview']['total_customers'],
                    "total_deal_value": analytics_data['portfolio_overview']['total_deal_value'],
                    "avg_health_score": round(analytics_data['portfolio_overview']['avg_health_score'], 1),
                    "at_risk_count": analytics_data['segmentation']['at_risk_customers'],
                    "low_engagement": analytics_data['segmentation']['low_engagement_customers'],
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "analyst": user.get('name', 'Customer Success Manager')
            }
        }

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="OpenAI library not installed. Please install with: pip install openai"
        )
    except Exception as e:
        logger.error(f"Error generating analytics insights: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analytics insights: {str(e)}"
        )

@router.get("/portfolio-metrics")
async def get_portfolio_metrics(tenant: tuple = Depends(get_tenant_connection)) -> Dict:
    """Get quick portfolio metrics without AI analysis"""

    try:
        conn, user = tenant
        user_email = user.get('email', '')
        raw_data = await get_comprehensive_analytics_data(conn, user_email)
        analytics_data = process_analytics_data(raw_data)

        if "error" in analytics_data:
            return {"error": "No customer data available"}

        return {
            "status": "success",
            "metrics": analytics_data
        }

    except Exception as e:
        logger.error(f"Error getting portfolio metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
