"""
PDF EXECUTIVE REPORT GENERATOR
================================
Generates professional PDF reports for:
1. Executive Summary Report
2. Failed Check Action List

Supports:
- Standard filter (DCMA/DOE/NASA/GAO/AACE/Industry/all)
- Severity filter (all/critical/high/medium)
- Fixed font leading for giant score text (no overlap)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from datetime import datetime
import io


# Severity filter helper
SEVERITY_LEVELS = {
    'critical': ['critical'],
    'high': ['critical', 'high'],
    'medium': ['critical', 'high', 'medium'],
    'all': ['critical', 'high', 'medium', 'low', 'info']
}


class PDFReportGenerator:
    """Generates professional PDF reports from health analysis data."""

    def __init__(self, health_data, file_name='', severity_filter='all'):
        self.data = health_data
        self.file_name = file_name
        self.severity_filter = (severity_filter or 'all').lower()
        self.allowed_severities = SEVERITY_LEVELS.get(
            self.severity_filter, SEVERITY_LEVELS['all']
        )
        self.styles = self._create_styles()

    def _create_styles(self):
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=styles['Normal'],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
            spaceAfter=15
        ))

        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor('#1e40af'),
            spaceBefore=12,
            spaceAfter=8,
            fontName='Helvetica-Bold'
        ))

        # FIXED: Added leading=54 to prevent overlap with 48pt font!
        styles.add(ParagraphStyle(
            name='ScoreBig',
            parent=styles['Normal'],
            fontSize=48,
            leading=54,
            textColor=colors.HexColor('#1e40af'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceBefore=6,
            spaceAfter=2
        ))

        styles.add(ParagraphStyle(
            name='ScoreSub',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=12
        ))

        styles.add(ParagraphStyle(
            name='RecommendationText',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#92400e'),
            leading=12,
            spaceBefore=0,
            spaceAfter=0
        ))

        styles.add(ParagraphStyle(
            name='CheckBody',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#334155'),
            leading=13,
            spaceBefore=2,
            spaceAfter=2
        ))

        styles.add(ParagraphStyle(
            name='CheckTitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#0f172a'),
            leading=14,
            spaceBefore=4,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        ))

        return styles

    def _recommendation_box(self, text):
        """Create a clean recommendation box that does not overlap text."""
        if not text:
            return Spacer(1, 0.1 * cm)

        clean = str(text).replace('\n', ' ').strip()
        para = Paragraph(f"💡 {clean}", self.styles['RecommendationText'])

        table = Table([[para]], colWidths=[16 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#F59E0B')),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return table

    def _matches_severity(self, check_or_action):
        """Check if item matches the severity filter."""
        sev = (check_or_action.get('severity') or 'low').lower()
        return sev in self.allowed_severities

    def generate_executive_report(self):
        """Create the executive summary PDF (respects severity filter & no overlaps)."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=1 * cm, bottomMargin=1 * cm,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm
        )

        story = []

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("SCHEDULE HEALTH", self.styles['CustomTitle']))
        story.append(Paragraph("Executive Assessment Report", self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph(
            f"<b>Project File:</b> {self.file_name}",
            self.styles['CheckBody']
        ))
        story.append(Paragraph(
            f"<b>Analysis Date:</b> {self.data.get('analysis_date', datetime.now().strftime('%Y-%m-%d %H:%M'))}",
            self.styles['CheckBody']
        ))
        story.append(Paragraph(
            f"<b>Severity Filter:</b> {self.severity_filter.upper()}",
            self.styles['CheckBody']
        ))

        proj = self.data.get('project_info', {})
        if proj.get('name'):
            story.append(Paragraph(
                f"<b>Project Name:</b> {proj.get('name', 'Unknown')}",
                self.styles['CheckBody']
            ))
        if proj.get('data_date'):
            story.append(Paragraph(
                f"<b>Data Date:</b> {proj.get('data_date', '')}",
                self.styles['CheckBody']
            ))

        story.append(Spacer(1, 0.6 * cm))

        # ─── OVERALL HEALTH SCORE ───
        score = self.data.get('overall_score', 0)
        story.append(Paragraph("OVERALL HEALTH SCORE", self.styles['SectionHeader']))
        story.append(Paragraph(f"{score}", self.styles['ScoreBig']))
        story.append(Paragraph("out of 100", self.styles['ScoreSub']))

        story.append(Spacer(1, 0.4 * cm))

        # Summary Stats
        stats_data = [
            ['Metric', 'Value'],
            ['Total Checks Performed', str(self.data.get('total_checks', 0))],
            ['Checks Passed', f"{self.data.get('passed_checks', 0)} ({round(self.data.get('pass_rate', 0), 1)}%)"],
            ['Checks Failed', str(self.data.get('failed_checks', 0))],
            ['Critical Failures', str(self.data.get('critical_failures', 0))],
            ['High-Severity Failures', str(self.data.get('high_failures', 0))],
            ['Severity Filter Applied', self.severity_filter.upper()],
        ]

        stats_table = Table(stats_data, colWidths=[9 * cm, 7 * cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        story.append(stats_table)

        story.append(PageBreak())

        # ─── Standards Compliance ───
        story.append(Paragraph("STANDARDS COMPLIANCE SUMMARY", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1e40af')))
        story.append(Spacer(1, 0.5 * cm))

        std_data_rows = [['Standard', 'Score', 'Grade', 'Passed', 'Failed', 'Critical']]
        for std_name, std_score in self.data.get('standard_scores', {}).items():
            std_data_rows.append([
                std_name,
                f"{std_score.get('score', 0)}",
                std_score.get('grade', '-'),
                str(std_score.get('passed', 0)),
                str(std_score.get('failed', 0)),
                str(std_score.get('critical_failures', 0)),
            ])

        std_table = Table(std_data_rows, colWidths=[4 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm])
        std_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        story.append(std_table)

        story.append(Spacer(1, 0.8 * cm))

        # ─── Top Priority Actions (filtered) ───
        story.append(Paragraph(
            f"TOP PRIORITY ACTIONS (Severity: {self.severity_filter.upper()})",
            self.styles['SectionHeader']
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#dc2626')))
        story.append(Spacer(1, 0.3 * cm))

        top_actions = self.data.get('top_actions', []) or []
        filtered_actions = [a for a in top_actions if self._matches_severity(a)][:10]

        if not filtered_actions:
            story.append(Paragraph(
                f"<i>No actions found matching severity filter: {self.severity_filter.upper()}</i>",
                self.styles['CheckBody']
            ))
        else:
            for idx, action in enumerate(filtered_actions, 1):
                severity = (action.get('severity') or 'low').upper()
                severity_color = {
                    'CRITICAL': '#7f1d1d',
                    'HIGH': '#dc2626',
                    'MEDIUM': '#f59e0b',
                    'LOW': '#64748b'
                }.get(severity, '#64748b')

                action_text = (
                    f"<b>{idx}. [{action.get('id', '')}] {action.get('name', '')}</b><br/>"
                    f"<font size='9' color='#64748b'>"
                    f"Standard: {action.get('standard', '')} | "
                    f"Severity: <font color='{severity_color}'><b>{severity}</b></font> | "
                    f"Affected: {action.get('count', 0)} activities ({action.get('percentage', 0)}%)"
                    f"</font>"
                )
                story.append(Paragraph(action_text, self.styles['CheckBody']))

                if action.get('recommendation'):
                    story.append(Spacer(1, 0.1 * cm))
                    story.append(self._recommendation_box(action.get('recommendation')))

                failed_items = action.get('failed_items', []) or []
                if failed_items:
                    story.append(Paragraph("<b>Affected Activities:</b>", self.styles['CheckBody']))
                    for item in failed_items[:10]:
                        code = item.get('code', '')
                        name = item.get('name', '')
                        wbs = item.get('wbs', '')
                        line = f"• {code}"
                        if name:
                            line += f" - {name}"
                        if wbs:
                            line += f" ({wbs})"
                        story.append(Paragraph(line, self.styles['CheckBody']))

                story.append(Spacer(1, 0.3 * cm))

        story.append(PageBreak())

        # ─── Detailed Standards Summary (filtered) ───
        story.append(Paragraph("DETAILED STANDARDS SUMMARY", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1e40af')))
        story.append(Spacer(1, 0.5 * cm))

        for std_name, std_data in self.data.get('standards', {}).items():
            story.append(Paragraph(f"<b>{std_name}</b>", self.styles['SectionHeader']))
            story.append(Paragraph(
                f"<i>{std_data.get('description', '')}</i>",
                self.styles['CheckBody']
            ))
            story.append(Spacer(1, 0.2 * cm))

            for category in std_data.get('categories', []):
                total_checks = len(category.get('checks', []))
                passed = sum(1 for c in category.get('checks', []) if c.get('passed'))

                story.append(Paragraph(
                    f"<b>• {category.get('name', '')}:</b> {passed}/{total_checks} passed",
                    self.styles['CheckBody']
                ))

                failed_checks = [
                    c for c in category.get('checks', [])
                    if c.get('status') == 'fail' and self._matches_severity(c)
                ]
                if failed_checks:
                    for check in failed_checks[:5]:
                        story.append(Paragraph(
                            f"&nbsp;&nbsp;&nbsp;&nbsp;❌ <b>{check.get('id')}:</b> {check.get('name')} "
                            f"({check.get('count', 0)} affected)",
                            self.styles['CheckBody']
                        ))
                    story.append(Spacer(1, 0.15 * cm))

        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(
            "<font size='8' color='#64748b'><i>Generated by P6 Schedule Analyzer | Confidential</i></font>",
            self.styles['CheckBody']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_actions_report(self):
        """Create the detailed action list PDF (respects severity filter)."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=1 * cm, bottomMargin=1 * cm,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm
        )

        story = []

        story.append(Paragraph("SCHEDULE HEALTH ACTIONS", self.styles['CustomTitle']))
        story.append(Paragraph("Failed Checks & Corrective Action List", self.styles['CustomSubtitle']))
        story.append(Paragraph(
            f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | File: {self.file_name}</i>",
            self.styles['CheckBody']
        ))
        story.append(Paragraph(
            f"<b>Severity Filter:</b> {self.severity_filter.upper()}",
            self.styles['CheckBody']
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#dc2626')))
        story.append(Spacer(1, 0.5 * cm))

        # ─── Summary Box ───
        summary_data = [
            ['Total Failed Checks', str(self.data.get('failed_checks', 0))],
            ['Critical Failures', str(self.data.get('critical_failures', 0))],
            ['High Severity Failures', str(self.data.get('high_failures', 0))],
            ['Overall Health Score', f"{self.data.get('overall_score', 0)} / 100"],
            ['Severity Filter', self.severity_filter.upper()],
        ]

        summary_table = Table(summary_data, colWidths=[9 * cm, 7 * cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FEF3C7')),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.8 * cm))

        # ═══════════════════════════════════════════════════
        # TOP PRIORITY ACTIONS (with Affected Activities)
        # ═══════════════════════════════════════════════════
        story.append(Paragraph(
            f"TOP PRIORITY ACTIONS (Severity: {self.severity_filter.upper()})",
            self.styles['SectionHeader']
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#dc2626')))
        story.append(Spacer(1, 0.3 * cm))

        top_actions = self.data.get('top_actions', []) or []
        filtered_top = [a for a in top_actions if self._matches_severity(a)][:15]

        if not filtered_top:
            story.append(Paragraph(
                f"<i>No priority actions matched severity filter: {self.severity_filter.upper()}</i>",
                self.styles['CheckBody']
            ))
        else:
            for idx, action in enumerate(filtered_top, 1):
                severity = (action.get('severity') or 'low').upper()
                severity_color = {
                    'CRITICAL': '#7f1d1d',
                    'HIGH': '#dc2626',
                    'MEDIUM': '#f59e0b',
                    'LOW': '#64748b'
                }.get(severity, '#64748b')

                title = (
                    f"<b>{idx}. "
                    f"<font color='{severity_color}'>[{severity}]</font> "
                    f"{action.get('id', '')}: {action.get('name', '')}</b>"
                )
                story.append(Paragraph(title, self.styles['CheckTitle']))

                meta_parts = []
                if action.get('standard'):
                    meta_parts.append(f"Standard: {action.get('standard')}")
                if action.get('category'):
                    meta_parts.append(f"Category: {action.get('category')}")
                if action.get('count') is not None:
                    meta_parts.append(
                        f"Affected: {action.get('count', 0)} "
                        f"({action.get('percentage', 0)}%)"
                    )
                elif action.get('value') is not None:
                    meta_parts.append(f"Value: {action.get('value')}")
                if action.get('threshold'):
                    meta_parts.append(f"Threshold: {action.get('threshold')}")

                if meta_parts:
                    story.append(Paragraph(" | ".join(meta_parts), self.styles['CheckBody']))

                if action.get('description'):
                    story.append(Paragraph(str(action.get('description')), self.styles['CheckBody']))

                if action.get('recommendation'):
                    story.append(Spacer(1, 0.1 * cm))
                    story.append(self._recommendation_box(action.get('recommendation')))

                failed_items = action.get('failed_items', []) or []
                if failed_items:
                    story.append(Spacer(1, 0.15 * cm))
                    story.append(Paragraph("<b>Affected Activities:</b>", self.styles['CheckBody']))
                    for item in failed_items:
                        code = item.get('code', '')
                        name = item.get('name', '')
                        wbs = item.get('wbs', '')
                        line = f"• {code}"
                        if name:
                            line += f" - {name}"
                        if wbs:
                            line += f" ({wbs})"
                        story.append(Paragraph(line, self.styles['CheckBody']))
                else:
                    story.append(Paragraph(
                        "<i>No activity list available for this metric.</i>",
                        self.styles['CheckBody']
                    ))

                story.append(Spacer(1, 0.35 * cm))

        story.append(PageBreak())

        # ═══════════════════════════════════════════════════
        # DETAILED FAILED CHECKS PER STANDARD (filtered)
        # ═══════════════════════════════════════════════════
        story.append(Paragraph(
            f"DETAILED FAILED CHECKS & RECOMMENDATIONS (Severity: {self.severity_filter.upper()})",
            self.styles['SectionHeader']
        ))

        any_failures_found = False

        for std_name, std_data in self.data.get('standards', {}).items():
            failed_in_std = []
            for cat in std_data.get('categories', []):
                for check in cat.get('checks', []):
                    if check.get('status') != 'fail':
                        continue
                    if not self._matches_severity(check):
                        continue
                    failed_in_std.append((cat.get('name', ''), check))

            if not failed_in_std:
                continue

            any_failures_found = True

            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph(
                f"<b>{std_name} Standard</b> ({len(failed_in_std)} failures)",
                self.styles['SectionHeader']
            ))

            for cat_name, check in failed_in_std:
                severity = (check.get('severity') or 'low').upper()
                severity_color = {
                    'CRITICAL': '#7f1d1d',
                    'HIGH': '#dc2626',
                    'MEDIUM': '#f59e0b',
                    'LOW': '#64748b'
                }.get(severity, '#64748b')

                title = (
                    f'<font color="{severity_color}">[{severity}]</font> '
                    f'{check.get("id", "")}: {check.get("name", "")}'
                )
                story.append(Paragraph(title, self.styles['CheckTitle']))

                story.append(Paragraph(f"Category: {cat_name}", self.styles['CheckBody']))

                if check.get('description'):
                    story.append(Paragraph(str(check.get('description')), self.styles['CheckBody']))

                if check.get('count') is not None:
                    metric_line = (
                        f"Affected: <b>{check.get('count')}</b> of {check.get('total')} "
                        f"({check.get('percentage', 0)}%) | "
                        f"Threshold: {check.get('threshold', '')}"
                    )
                    story.append(Paragraph(metric_line, self.styles['CheckBody']))
                elif check.get('value') is not None:
                    metric_line = (
                        f"Value: <b>{check.get('value')}</b> | "
                        f"Threshold: {check.get('threshold', '')}"
                    )
                    story.append(Paragraph(metric_line, self.styles['CheckBody']))

                if check.get('recommendation'):
                    story.append(Spacer(1, 0.12 * cm))
                    story.append(self._recommendation_box(check.get('recommendation')))

                if check.get('failed_items'):
                    story.append(Spacer(1, 0.1 * cm))
                    story.append(Paragraph("<b>Affected Activities:</b>", self.styles['CheckBody']))
                    for item in check.get('failed_items', []):
                        code = item.get('code', '')
                        name = item.get('name', '')
                        wbs = item.get('wbs', '')
                        line = f"• {code}"
                        if name:
                            line += f" - {name}"
                        if wbs:
                            line += f" ({wbs})"
                        story.append(Paragraph(line, self.styles['CheckBody']))

                story.append(Spacer(1, 0.35 * cm))

        if not any_failures_found:
            story.append(Paragraph(
                f"<i>No failures matched severity filter: {self.severity_filter.upper()}</i>",
                self.styles['CheckBody']
            ))

        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(
            "<font size='8' color='#64748b'><i>Generated by P6 Schedule Analyzer | Confidential</i></font>",
            self.styles['CheckBody']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer