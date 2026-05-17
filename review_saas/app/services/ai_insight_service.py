# =========================================================
# FILE: app/services/ai_insight_service.py
# WORLD-CLASS AI EXECUTIVE INTELLIGENCE ENGINE
# ENTERPRISE • PREDICTIVE • KPI-DRIVEN • BOARDROOM READY
# =========================================================

from datetime import datetime
from typing import Dict, Any, List
from statistics import mean


class AIInsightService:
    """
    ========================================================
    WORLD-CLASS AI EXECUTIVE INTELLIGENCE ENGINE
    ========================================================

    CAPABILITIES:
    - Executive business intelligence
    - Strategic operational analysis
    - Customer behavior intelligence
    - Brand reputation analytics
    - Revenue risk analysis
    - Customer retention forecasting
    - Competitive positioning
    - Predictive operational intelligence
    - AI-driven executive recommendations
    - Business health scoring
    - Crisis detection engine
    - Board-level decision support
    """

    def __init__(self):
        pass

    # =====================================================
    # MAIN AI ENGINE
    # =====================================================

    def generate_ai_insights(
        self,
        company_name: str,
        analytics_data: Dict[str, Any]
    ) -> Dict[str, Any]:

        health_data = self.calculate_business_health(
            analytics_data
        )

        insights = {

            "company_name":
                company_name,

            "generated_at":
                str(datetime.utcnow()),

            "business_health_score":
                health_data["score"],

            "business_status":
                health_data["status"],

            "operational_urgency":
                health_data["urgency"],

            "executive_summary":
                self.executive_summary(
                    analytics_data,
                    health_data
                ),

            "business_strengths":
                self.business_strengths(
                    analytics_data,
                    health_data
                ),

            "critical_issues":
                self.critical_issues(
                    analytics_data,
                    health_data
                ),

            "customer_behavior_analysis":
                self.customer_behavior_analysis(
                    analytics_data,
                    health_data
                ),

            "growth_opportunities":
                self.growth_opportunities(
                    analytics_data,
                    health_data
                ),

            "operational_risks":
                self.operational_risks(
                    analytics_data,
                    health_data
                ),

            "management_recommendations":
                self.management_recommendations(
                    analytics_data,
                    health_data
                ),

            "staff_improvement_plan":
                self.staff_improvement_plan(
                    analytics_data,
                    health_data
                ),

            "customer_retention_strategy":
                self.customer_retention_strategy(
                    analytics_data,
                    health_data
                ),

            "marketing_recommendations":
                self.marketing_recommendations(
                    analytics_data,
                    health_data
                ),

            "revenue_growth_strategy":
                self.revenue_growth_strategy(
                    analytics_data,
                    health_data
                ),

            "competitive_position":
                self.competitive_position(
                    analytics_data,
                    health_data
                ),

            "priority_actions":
                self.priority_actions(
                    analytics_data,
                    health_data
                ),

            "thirty_day_action_plan":
                self.thirty_day_action_plan(
                    analytics_data,
                    health_data
                ),

            "ninety_day_business_strategy":
                self.ninety_day_business_strategy(
                    analytics_data,
                    health_data
                ),

            "executive_decision_support":
                self.executive_decision_support(
                    analytics_data,
                    health_data
                ),

            "financial_risk_analysis":
                self.financial_risk_analysis(
                    analytics_data,
                    health_data
                ),

            "reputation_analysis":
                self.reputation_analysis(
                    analytics_data,
                    health_data
                ),

            "customer_loyalty_analysis":
                self.customer_loyalty_analysis(
                    analytics_data,
                    health_data
                ),

            "operational_efficiency_analysis":
                self.operational_efficiency_analysis(
                    analytics_data,
                    health_data
                )

        }

        return insights

    # =====================================================
    # BUSINESS HEALTH ENGINE
    # =====================================================

    def calculate_business_health(self, data):

        rating = data.get("average_rating", 0)

        positive = data.get(
            "positive_review_percentage",
            0
        )

        negative = data.get(
            "negative_review_percentage",
            0
        )

        reputation = data.get(
            "reputation_score",
            50
        )

        # ================================================
        # WEIGHTED EXECUTIVE SCORING
        # ================================================

        score = (

            (rating / 5) * 35 +

            (positive / 100) * 25 +

            (reputation / 100) * 25 -

            (negative / 100) * 15

        ) * 100

        score = round(
            max(0, min(100, score)),
            2
        )

        # ================================================
        # STATUS CLASSIFICATION
        # ================================================

        if score >= 90:
            status = "Elite"

        elif score >= 75:
            status = "Strong"

        elif score >= 60:
            status = "Stable"

        elif score >= 40:
            status = "Risky"

        else:
            status = "Critical"

        # ================================================
        # URGENCY LEVEL
        # ================================================

        if negative >= 45:
            urgency = "Immediate Executive Attention Required"

        elif negative >= 30:
            urgency = "High Operational Risk"

        elif negative >= 15:
            urgency = "Moderate Operational Monitoring"

        else:
            urgency = "Operationally Stable"

        return {

            "score": score,

            "status": status,

            "urgency": urgency

        }

    # =====================================================
    # EXECUTIVE SUMMARY
    # =====================================================

    def executive_summary(
        self,
        data,
        health
    ):

        rating = data.get("average_rating", 0)

        positive = data.get(
            "positive_review_percentage",
            0
        )

        negative = data.get(
            "negative_review_percentage",
            0
        )

        score = health["score"]

        status = health["status"]

        urgency = health["urgency"]

        # ================================================
        # CONTRADICTION PREVENTION
        # ================================================

        if negative > positive:

            summary = f"""
            Executive intelligence analysis indicates elevated customer dissatisfaction trends impacting overall brand perception and operational stability.

            The organization currently maintains a business health score of {score}% with an average customer rating of {rating}/5.

            Negative customer sentiment ({negative}%) currently exceeds positive sentiment ({positive}%), indicating measurable operational and reputation management challenges.

            Current business classification is '{status}' with operational urgency level categorized as '{urgency}'.

            Strategic intervention is recommended to stabilize customer satisfaction, reduce operational friction, and strengthen long-term customer retention performance.
            """

        else:

            summary = f"""
            Executive intelligence analysis indicates generally stable business performance supported by moderate customer satisfaction and operational consistency.

            The organization currently maintains a business health score of {score}% with an average customer rating of {rating}/5.

            Positive customer sentiment remains higher than negative sentiment, supporting relatively stable market perception and customer engagement indicators.

            Current business classification is '{status}' with operational urgency level categorized as '{urgency}'.

            Continued operational optimization and customer experience enhancement initiatives are recommended to strengthen long-term scalability and brand competitiveness.
            """

        return summary.strip()

    # =====================================================
    # BUSINESS STRENGTHS
    # =====================================================

    def business_strengths(
        self,
        data,
        health
    ):

        strengths = []

        rating = data.get(
            "average_rating",
            0
        )

        positive = data.get(
            "positive_review_percentage",
            0
        )

        if rating >= 4.5:

            strengths.append(
                "Customer satisfaction performance significantly exceeds industry standards."
            )

        if positive >= 70:

            strengths.append(
                "Strong positive customer sentiment indicates resilient customer trust."
            )

        if health["score"] >= 80:

            strengths.append(
                "Operational and reputation indicators support long-term market competitiveness."
            )

        top_points = data.get(
            "top_positive_points",
            []
        )

        for point in top_points[:5]:

            strengths.append(
                f"Customers consistently recognize strength in: {point[0]}"
            )

        if not strengths:

            strengths.append(
                "Current operational performance indicates limited strategic strengths requiring management optimization focus."
            )

        return strengths

    # =====================================================
    # CRITICAL ISSUES
    # =====================================================

    def critical_issues(
        self,
        data,
        health
    ):

        issues = []

        negative = data.get(
            "negative_review_percentage",
            0
        )

        rating = data.get(
            "average_rating",
            0
        )

        if negative >= 40:

            issues.append(
                "Elevated negative customer sentiment indicates systemic operational dissatisfaction."
            )

        if rating < 3:

            issues.append(
                "Customer satisfaction levels are significantly below competitive market expectations."
            )

        if health["status"] in [
            "Critical",
            "Risky"
        ]:

            issues.append(
                "Current business health indicators require executive-level operational intervention."
            )

        customer_issues = data.get(
            "top_customer_issues",
            []
        )

        for issue in customer_issues[:5]:

            issues.append(
                f"Recurring customer complaint detected around: {issue[0]}"
            )

        if not issues:

            issues.append(
                "No major systemic operational threats currently detected."
            )

        return issues

    # =====================================================
    # CUSTOMER BEHAVIOR ANALYSIS
    # =====================================================

    def customer_behavior_analysis(
        self,
        data,
        health
    ):

        positive = data.get(
            "positive_review_percentage",
            0
        )

        negative = data.get(
            "negative_review_percentage",
            0
        )

        insights = []

        if positive >= 70:

            insights.append(
                "Customers demonstrate strong trust, loyalty, and positive brand engagement behavior."
            )

        if negative >= 25:

            insights.append(
                "Customer frustration indicators are increasing and may negatively impact retention rates."
            )

        if negative > positive:

            insights.append(
                "Negative customer experiences currently outweigh positive engagement indicators."
            )

        insights.append(
            "Customer purchasing and loyalty behavior is highly influenced by operational consistency and response efficiency."
        )

        insights.append(
            "Online review sentiment is directly impacting brand trust, acquisition efficiency, and market perception."
        )

        return insights

    # =====================================================
    # GROWTH OPPORTUNITIES
    # =====================================================

    def growth_opportunities(
        self,
        data,
        health
    ):

        opportunities = []

        rating = data.get(
            "average_rating",
            0
        )

        if rating >= 4:

            opportunities.append(
                "Strong customer satisfaction metrics support premium market positioning opportunities."
            )

        opportunities.append(
            "Operational optimization initiatives can significantly improve customer retention performance."
        )

        opportunities.append(
            "Positive customer feedback can be leveraged in high-conversion digital marketing campaigns."
        )

        opportunities.append(
            "AI-driven customer intelligence systems can improve operational forecasting and proactive issue detection."
        )

        opportunities.append(
            "Customer loyalty programs can strengthen retention and lifetime customer value growth."
        )

        return opportunities

    # =====================================================
    # OPERATIONAL RISKS
    # =====================================================

    def operational_risks(
        self,
        data,
        health
    ):

        risks = []

        negative = data.get(
            "negative_review_percentage",
            0
        )

        if negative >= 35:

            risks.append(
                "High negative sentiment concentration may accelerate customer churn and reputation deterioration."
            )

        risks.append(
            "Operational inconsistency may continue reducing customer trust and engagement quality."
        )

        risks.append(
            "Delayed customer response handling may weaken retention and loyalty performance."
        )

        risks.append(
            "Competitors with stronger customer experience performance may capture market share."
        )

        return risks

    # =====================================================
    # MANAGEMENT RECOMMENDATIONS
    # =====================================================

    def management_recommendations(
        self,
        data,
        health
    ):

        return [

            "Implement executive-level customer experience monitoring systems.",

            "Establish a centralized customer complaint escalation framework.",

            "Deploy operational KPI dashboards for real-time performance tracking.",

            "Conduct weekly executive sentiment review sessions.",

            "Strengthen cross-functional operational accountability systems."

        ]

    # =====================================================
    # STAFF IMPROVEMENT PLAN
    # =====================================================

    def staff_improvement_plan(
        self,
        data,
        health
    ):

        return [

            "Conduct advanced customer experience training programs.",

            "Implement response-time performance accountability metrics.",

            "Strengthen employee communication and escalation handling procedures.",

            "Introduce customer interaction quality assurance monitoring.",

            "Deploy structured operational SOP compliance systems."

        ]

    # =====================================================
    # CUSTOMER RETENTION STRATEGY
    # =====================================================

    def customer_retention_strategy(
        self,
        data,
        health
    ):

        return [

            "Respond professionally to all negative customer experiences.",

            "Implement loyalty and repeat-customer engagement programs.",

            "Increase personalized customer interaction initiatives.",

            "Launch proactive customer satisfaction recovery campaigns.",

            "Develop AI-driven customer retention monitoring systems."

        ]

    # =====================================================
    # MARKETING RECOMMENDATIONS
    # =====================================================

    def marketing_recommendations(
        self,
        data,
        health
    ):

        return [

            "Leverage positive customer experiences in brand positioning campaigns.",

            "Strengthen local SEO and reputation management strategies.",

            "Deploy customer testimonial-driven advertising initiatives.",

            "Increase digital reputation visibility through review optimization.",

            "Use sentiment analytics to guide campaign messaging strategies."

        ]

    # =====================================================
    # REVENUE GROWTH STRATEGY
    # =====================================================

    def revenue_growth_strategy(
        self,
        data,
        health
    ):

        return [

            "Improve operational efficiency to strengthen profit margins.",

            "Increase customer lifetime value through loyalty optimization.",

            "Leverage reputation-driven marketing to improve acquisition conversion.",

            "Expand premium service offerings for high-value customer segments.",

            "Reduce customer churn through proactive sentiment management."

        ]

    # =====================================================
    # COMPETITIVE POSITION
    # =====================================================

    def competitive_position(
        self,
        data,
        health
    ):

        score = health["score"]

        if score >= 90:
            return "Market Leader"

        if score >= 75:
            return "Strong Competitive Position"

        if score >= 60:
            return "Moderately Competitive"

        if score >= 40:
            return "Operationally Vulnerable"

        return "Weak Competitive Position"

    # =====================================================
    # PRIORITY ACTIONS
    # =====================================================

    def priority_actions(
        self,
        data,
        health
    ):

        actions = []

        negative = data.get(
            "negative_review_percentage",
            0
        )

        if negative >= 20:

            actions.append(
                "Immediately investigate recurring customer dissatisfaction drivers."
            )

        actions.append(
            "Improve operational response handling efficiency."
        )

        actions.append(
            "Strengthen customer experience quality assurance systems."
        )

        actions.append(
            "Deploy executive-level reputation monitoring."
        )

        actions.append(
            "Track operational KPIs and sentiment metrics weekly."
        )

        return actions

    # =====================================================
    # 30 DAY ACTION PLAN
    # =====================================================

    def thirty_day_action_plan(
        self,
        data,
        health
    ):

        return {

            "Week 1": [

                "Audit operational complaints and customer dissatisfaction patterns.",

                "Identify highest-risk operational bottlenecks.",

                "Analyze recurring negative review themes."

            ],

            "Week 2": [

                "Implement operational escalation and response SOPs.",

                "Conduct advanced staff training initiatives.",

                "Improve customer communication workflows."

            ],

            "Week 3": [

                "Launch customer satisfaction recovery campaigns.",

                "Strengthen reputation management processes.",

                "Monitor KPI stabilization metrics."

            ],

            "Week 4": [

                "Evaluate operational performance improvements.",

                "Prepare executive operational intelligence report.",

                "Adjust business strategy based on updated analytics."

            ]

        }

    # =====================================================
    # 90 DAY STRATEGY
    # =====================================================

    def ninety_day_business_strategy(
        self,
        data,
        health
    ):

        return {

            "Month 1":
                "Operational stabilization and complaint reduction.",

            "Month 2":
                "Customer experience enhancement and retention optimization.",

            "Month 3":
                "Brand strengthening, scalability improvement, and revenue optimization."

        }

    # =====================================================
    # EXECUTIVE DECISION SUPPORT
    # =====================================================

    def executive_decision_support(
        self,
        data,
        health
    ):

        score = health["score"]

        if score >= 85:

            return (
                "Business performance indicators support strategic scaling, premium market expansion, and leadership positioning initiatives."
            )

        if score >= 70:

            return (
                "Business performance remains operationally stable but requires continued customer experience optimization to strengthen long-term competitiveness."
            )

        if score >= 40:

            return (
                "Operational risk indicators suggest immediate management attention is required to stabilize customer satisfaction and brand trust performance."
            )

        return (
            "Critical operational intervention is recommended to reduce customer dissatisfaction, protect brand reputation, and prevent retention deterioration."
        )

    # =====================================================
    # FINANCIAL RISK ANALYSIS
    # =====================================================

    def financial_risk_analysis(
        self,
        data,
        health
    ):

        negative = data.get(
            "negative_review_percentage",
            0
        )

        if negative >= 40:

            return (
                "Current negative sentiment concentration presents elevated revenue retention risk and potential customer acquisition inefficiencies."
            )

        return (
            "Financial risk indicators remain operationally manageable under current customer sentiment conditions."
        )

    # =====================================================
    # REPUTATION ANALYSIS
    # =====================================================

    def reputation_analysis(
        self,
        data,
        health
    ):

        reputation = data.get(
            "reputation_score",
            50
        )

        if reputation >= 80:

            return (
                "Brand reputation performance remains commercially strong with healthy customer trust indicators."
            )

        if reputation >= 60:

            return (
                "Brand reputation remains moderately stable but requires continuous sentiment monitoring."
            )

        return (
            "Brand reputation performance is currently under pressure due to elevated customer dissatisfaction trends."
        )

    # =====================================================
    # CUSTOMER LOYALTY ANALYSIS
    # =====================================================

    def customer_loyalty_analysis(
        self,
        data,
        health
    ):

        positive = data.get(
            "positive_review_percentage",
            0
        )

        if positive >= 70:

            return (
                "Customer loyalty indicators remain strong with healthy trust and engagement behavior."
            )

        return (
            "Customer loyalty performance may weaken without operational consistency improvements."
        )

    # =====================================================
    # OPERATIONAL EFFICIENCY ANALYSIS
    # =====================================================

    def operational_efficiency_analysis(
        self,
        data,
        health
    ):

        negative = data.get(
            "negative_review_percentage",
            0
        )

        if negative >= 35:

            return (
                "Operational efficiency indicators suggest recurring workflow instability and customer experience inconsistency."
            )

        return (
            "Operational performance indicators remain relatively stable with manageable efficiency risk levels."
        )


# =========================================================
# GLOBAL INSTANCE
# =========================================================

ai_insight_service = AIInsightService()
