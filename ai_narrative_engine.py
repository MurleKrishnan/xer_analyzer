"""
AI EXECUTIVE NARRATIVE GENERATOR
=================================
Synthesizes complex schedule health, comparison variance, and EVM performance
into a clear, executive-ready narrative briefing.

Supports:
- Rule-based deterministic text synthesis (Zero-dependency fallback)
- OpenAI API (GPT-4o / GPT-4o-mini)
- Anthropic API (Claude 3.5 Sonnet)
"""

import os
import json
import urllib.request
import logging

logger = logging.getLogger(__name__)


class AINarrativeEngine:
    """Generates executive narrative reports from schedule analysis data."""

    def __init__(self, health_data=None, comparison_data=None, evm_data=None):
        self.health = health_data or {}
        self.comparison = comparison_data or {}
        self.evm = evm_data or {}
        
        self.openai_key = os.environ.get('OPENAI_API_KEY', '')
        self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')

    def generate_narrative(self) -> dict:
        """
        Generate narrative briefing. Uses LLM if API key exists, otherwise smart template.
        """
        prompt_context = self._build_context_summary()
        
        if self.openai_key:
            logger.info("🤖 Generating narrative via OpenAI API...")
            narrative = self._call_openai(prompt_context)
            method = "OpenAI GPT"
        elif self.anthropic_key:
            logger.info("🤖 Generating narrative via Anthropic Claude API...")
            narrative = self._call_anthropic(prompt_context)
            method = "Anthropic Claude"
        else:
            logger.info("💡 Generating narrative via Smart Rule Engine (No API Key)...")
            narrative = self._generate_rule_based_narrative()
            method = "Smart Rule Engine (Built-In)"

        return {
            'narrative': narrative,
            'method': method,
            'context_summary': prompt_context,
        }

    def _build_context_summary(self) -> dict:
        """Extract key KPIs across all engines into a single dict."""
        proj = self.health.get('project_info', {}) or {}
        
        # Health KPIs
        score = self.health.get('overall_score', 'N/A')
        total_checks = self.health.get('total_checks', 0)
        failed_checks = self.health.get('failed_checks', 0)
        critical_fails = self.health.get('critical_failures', 0)
        high_fails = self.health.get('high_failures', 0)
        top_actions = self.health.get('top_actions', [])[:5]
        
        # EVM KPIs
        evm_m = self.evm.get('metrics', {}) or {}
        spi = evm_m.get('spi', 'N/A')
        cpi = evm_m.get('cpi', 'N/A')
        eac = evm_m.get('eac', 'N/A')
        vac = evm_m.get('vac', 'N/A')
        
        # Comparison KPIs
        comp_sum = self.comparison.get('summary', {}) or {}
        slipped = comp_sum.get('slipped_count', 0)
        improved = comp_sum.get('improved_count', 0)
        added = comp_sum.get('added_count', 0)
        deleted = comp_sum.get('deleted_count', 0)
        
        return {
            'project_name': proj.get('name', 'Project'),
            'data_date': proj.get('data_date', 'Unknown'),
            'health_score': score,
            'total_checks': total_checks,
            'failed_checks': failed_checks,
            'critical_failures': critical_fails,
            'high_failures': high_fails,
            'top_action_names': [f"{a.get('id')}: {a.get('name')}" for a in top_actions],
            'spi': spi,
            'cpi': cpi,
            'eac': eac,
            'vac': vac,
            'slipped_activities': slipped,
            'improved_activities': improved,
            'added_activities': added,
            'deleted_activities': deleted,
        }

    # ═══════════════════════════════════════════════════════
    # SMART RULE-BASED SYNTHESIS (Zero API Cost)
    # ═══════════════════════════════════════════════════════

    def _generate_rule_based_narrative(self) -> str:
        ctx = self._build_context_summary()
        
        # Paragraph 1: Executive Overview & Health Grade
        score = ctx['health_score']
        if isinstance(score, (int, float)):
            if score >= 90:
                health_eval = f"demonstrates excellent structural integrity with a Health Score of **{score}/100**"
            elif score >= 80:
                health_eval = f"is in good overall condition with a Health Score of **{score}/100**, though minor logic refinements are advised"
            elif score >= 70:
                health_eval = f"shows moderate schedule risk with a Health Score of **{score}/100**. Moderate logic deficiencies require attention"
            else:
                health_eval = f"exhibits significant structural risk with a critical Health Score of **{score}/100**. Immediate corrective action is recommended"
        else:
            health_eval = "has been analyzed for schedule health and compliance"

        p1 = (
            f"### Executive Overview\n\n"
            f"The schedule **{ctx['project_name']}** (Data Date: {ctx['data_date']}) {health_eval}. "
            f"Across {ctx['total_checks']} automated health checks, **{ctx['failed_checks']} checks failed**, "
            f"including **{ctx['critical_failures']} critical** and **{ctx['high_failures']} high-severity** violations."
        )

        # Paragraph 2: Top Action Items
        if ctx['top_action_names']:
            top_list_str = "\n".join([f"- **{name}**" for name in ctx['top_action_names']])
            p2 = (
                f"### Priority Risk Drivers\n\n"
                f"To restore schedule health and compliance, project controls should prioritize resolving the following top issues:\n\n"
                f"{top_list_str}"
            )
        else:
            p2 = "### Priority Risk Drivers\n\nNo critical risk drivers or high-severity logic failures were detected in this evaluation."

        # Paragraph 3: Variance & EVM Execution (if data present)
        p3_parts = []
        if ctx['slipped_activities'] or ctx['improved_activities']:
            p3_parts.append(
                f"In the current update, **{ctx['slipped_activities']} activities experienced finish date slippage**, "
                f"while {ctx['improved_activities']} activities improved their schedule position. "
                f"A total of {ctx['added_activities']} activities were added and {ctx['deleted_activities']} deleted."
            )
        
        if ctx['spi'] != 'N/A' and ctx['spi'] != 0:
            spi_val = float(ctx['spi'])
            spi_status = "ahead of schedule" if spi_val >= 1.0 else "behind schedule"
            p3_parts.append(
                f"From an Earned Value perspective, the project reflects a Schedule Performance Index (SPI) of **{ctx['spi']}** ({spi_status})."
            )
            
        if ctx['vac'] != 'N/A' and ctx['vac'] != 0:
            vac_val = float(ctx['vac'])
            vac_status = "under budget" if vac_val >= 0 else "over budget"
            p3_parts.append(
                f"The forecasted Variance at Completion (VAC) is **${vac_val:,.0f}** ({vac_status})."
            )

        p3 = "### Performance & Variance Summary\n\n" + " ".join(p3_parts) if p3_parts else ""

        return f"{p1}\n\n{p2}\n\n{p3}"

    # ═══════════════════════════════════════════════════════
    # LIVE LLM CALLS (OpenAI / Anthropic via urllib - No Extra Pip Pkg Needed)
    # ═══════════════════════════════════════════════════════

    def _call_openai(self, ctx: dict) -> str:
        prompt = (
            f"You are a Senior Project Controls Director & Claims Consultant. Write a concise, 3-paragraph "
            f"Executive Summary Report in Markdown based on this schedule analysis JSON:\n\n"
            f"{json.dumps(ctx, indent=2)}\n\n"
            f"Structure:\n"
            f"1. Executive Summary & Overall Health Grade\n"
            f"2. Primary Critical Path & Logic Issues Need Action\n"
            f"3. Variance, Delay Drivers, and EVM Trend Advice"
        )
        
        payload = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You write professional, objective project controls executive reports."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res = json.loads(response.read().decode('utf-8'))
                return res['choices'][0]['message']['content']
        except Exception as e:
            logger.error("OpenAI API call failed: %s. Falling back to rule-based engine.", e)
            return self._generate_rule_based_narrative()

    def _call_anthropic(self, ctx: dict) -> str:
        prompt = (
            f"You are a Senior Project Controls Director & Claims Consultant. Write a concise, 3-paragraph "
            f"Executive Summary Report in Markdown based on this schedule analysis JSON:\n\n"
            f"{json.dumps(ctx, indent=2)}"
        )
        
        payload = json.dumps({
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                res = json.loads(response.read().decode('utf-8'))
                return res['content'][0]['text']
        except Exception as e:
            logger.error("Anthropic API call failed: %s. Falling back to rule-based engine.", e)
            return self._generate_rule_based_narrative()