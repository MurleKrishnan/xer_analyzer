"""
PDF EXECUTIVE REPORT GENERATOR
================================
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from datetime import datetime
from xml.sax.saxutils import escape
import io
import logging

logger = logging.getLogger(__name__)

try:
    from config import (
        COMPANY_NAME,
        APP_TITLE,
        MAX_ITEMS_PER_CHECK_PDF,
        MAX_TOP_ACTIONS_PDF,
        get_theme,
    )
except ImportError:
    COMPANY_NAME = "P6 Schedule Analyzer"
    APP_TITLE = "P6 Schedule Analyzer"
    MAX_ITEMS_PER_CHECK_PDF = 50
    MAX_TOP_ACTIONS_PDF = 15

    def get_theme():
        return {
            'primary': '#1e40af',
            'success': '#10b981',
            'warning': '#f59e0b',
            'danger': '#dc2626',
            'muted': '#64748b',
        }


SEVERITY_LEVELS = {
    'critical': ['critical'],
    'high': ['critical', 'high'],
    'medium': ['critical', 'high', 'medium'],
    'all': ['critical', 'high', 'medium', 'low', 'info'],
}

SEVERITY_WEIGHT = {
    'critical': 100,
    'high': 50,
    'medium': 20,
    'low': 5,
    'info': 0,
}


class PDFReportGenerator:
    def __init__(self, health_data, file_name='', severity_filter='all'):
        self.data = health_data or {}
        self.file_name = file_name or ''
        self.severity_filter = (severity_filter or 'all').lower()
        self.allowed_severities = SEVERITY_LEVELS.get(
            self.severity_filter, SEVERITY_LEVELS['all']
        )
        self.theme = get_theme()
        self.primary = colors.HexColor(self.theme.get('primary', '#1e40af'))
        self.danger = colors.HexColor(self.theme.get('danger', '#dc2626'))
        self.muted = colors.HexColor(self.theme.get('muted', '#64748b'))
        self.styles = self._create_styles()
        self.max_items = int(MAX_ITEMS_PER_CHECK_PDF or 50)
        self.max_top = int(MAX_TOP_ACTIONS_PDF or 15)

    def _safe(self, text):
        if text is None:
            return ''
        return escape(str(text))

    def _p(self, text, style_name='CheckBody'):
        style = self.styles[style_name]
        return Paragraph(self._safe(text), style)

    def _p_markup(self, markup, style_name='CheckBody'):
        return Paragraph(str(markup), self.styles[style_name])

    def _matches_severity(self, check_or_action):
        sev = (check_or_action.get('severity') or 'low').lower()
        return sev in self.allowed_severities

    def _activity_line(self, item):
        code = self._safe(item.get('code', ''))
        name = self._safe(item.get('name', ''))
        wbs = self._safe(item.get('wbs', ''))
        line = f"• {code}"
        if name:
            line += f" - {name}"
        if wbs:
            line += f" ({wbs})"
        return line

    def _iter_failed_checks(self):
        for std_name, std_data in (self.data.get('standards') or {}).items():
            for cat in std_data.get('categories') or []:
                cat_name = cat.get('name', '')
                for check in cat.get('checks') or []:
                    if check.get('status') != 'fail':
                        continue
                    if not self._matches_severity(check):
                        continue
                    yield std_name, cat_name, check

    def _build_priority_actions(self, limit=None):
        actions = []
        for std_name, cat_name, check in self._iter_failed_checks():
            count = check.get('count', 0) or 0
            sev = (check.get('severity') or 'low').lower()
            priority = SEVERITY_WEIGHT.get(sev, 5) + min(count, 100)
            actions.append({
                'standard': std_name,
                'category': cat_name,
                'id': check.get('id'),
                'name': check.get('name'),
                'severity': sev,
                'count': count,
                'total': check.get('total', 0),
                'percentage': check.get('percentage', 0),
                'value': check.get('value'),
                'threshold': check.get('threshold', ''),
                'description': check.get('description', ''),
                'recommendation': check.get('recommendation', ''),
                'failed_items': check.get('failed_items') or [],
                'priority': priority,
            })

        if not actions:
            for a in (self.data.get('top_actions') or []):
                if self._matches_severity(a):
                    actions.append(a)

        actions.sort(key=lambda x: x.get('priority', 0), reverse=True)
        if limit is not None:
            return actions[:limit]
        return actions

    def _score_color(self, score):
        try:
            s = float(score)
        except (TypeError, ValueError):
            s = 0
        if s >= 90:
            return colors.HexColor('#059669')
        if s >= 80:
            return colors.HexColor('#2563eb')
        if s >= 70:
            return colors.HexColor('#d97706')
        return colors.HexColor('#dc2626')

    def _severity_color_hex(self, severity):
        return {
            'CRITICAL': '#7f1d1d',
            'HIGH': '#dc2626',
            'MEDIUM': '#f59e0b',
            'LOW': '#64748b',
            'INFO': '#64748b',
        }.get((severity or 'LOW').upper(), '#64748b')

    def _create_styles(self):
        styles = getSampleStyleSheet()
        primary_hex = self.theme.get('primary', '#1e40af')

        styles.add(ParagraphStyle(
            name='CustomTitle', parent=styles['Heading1'], fontSize=22, leading=26,
            textColor=colors.HexColor(primary_hex), spaceAfter=8, alignment=TA_CENTER, fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='CustomSubtitle', parent=styles['Normal'], fontSize=12, leading=15,
            textColor=colors.HexColor('#64748b'), alignment=TA_CENTER, spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='SectionHeader', parent=styles['Heading2'], fontSize=14, leading=18,
            textColor=colors.HexColor(primary_hex), spaceBefore=12, spaceAfter=8, fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='ScoreBig', parent=styles['Normal'], fontSize=48, leading=54,
            textColor=colors.HexColor(primary_hex), alignment=TA_CENTER, fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=2
        ))
        styles.add(ParagraphStyle(
            name='ScoreSub', parent=styles['Normal'], fontSize=11, leading=14,
            textColor=colors.HexColor('#64748b'), alignment=TA_CENTER, spaceBefore=0, spaceAfter=12
        ))
        styles.add(ParagraphStyle(
            name='RecommendationText', parent=styles['Normal'], fontSize=9,
            textColor=colors.HexColor('#92400e'), leading=12, spaceBefore=0, spaceAfter=0
        ))
        styles.add(ParagraphStyle(
            name='CheckBody', parent=styles['Normal'], fontSize=9,
            textColor=colors.HexColor('#334155'), leading=13, spaceBefore=2, spaceAfter=2, alignment=TA_LEFT
        ))
        styles.add(ParagraphStyle(
            name='CheckTitle', parent=styles['Normal'], fontSize=10,
            textColor=colors.HexColor('#0f172a'), leading=14, spaceBefore=4, spaceAfter=2, fontName='Helvetica-Bold'
        ))
        return styles

    def _recommendation_box(self, text):
        if not text:
            return Spacer(1, 0.05 * cm)

        clean = self._safe(str(text).replace('\n', ' ').strip())
        if len(clean) > 800:
            clean = clean[:800] + '…'

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

    def _add_page_decor(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        page_w, _ = A4
        fname = (self.file_name or APP_TITLE)[:50]
        canvas.drawString(1.5 * cm, 0.6 * cm, fname)
        canvas.drawRightString(page_w - 1.5 * cm, 0.6 * cm, f"Page {doc.page}")
        canvas.drawCentredString(page_w / 2, 0.6 * cm, f"{COMPANY_NAME} | Confidential")
        canvas.restoreState()

    def _build_doc(self, buffer):
        return SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=1.2 * cm, bottomMargin=1.4 * cm,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
            title=f"{APP_TITLE} Health Report", author=COMPANY_NAME
        )

    def generate_executive_report(self):
        buffer = io.BytesIO()
        doc = self._build_doc(buffer)
        story = []

        selected_std = self.data.get('selected_standard', 'all')
        score = self.data.get('overall_score', 0)

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("SCHEDULE HEALTH", self.styles['CustomTitle']))
        story.append(Paragraph("Executive Assessment Report", self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.2 * cm))

        meta_lines = [
            f"<b>Project File:</b> {self._safe(self.file_name)}",
            f"<b>Analysis Date:</b> {self._safe(self.data.get('analysis_date', datetime.now().strftime('%Y-%m-%d %H:%M')))}",
            f"<b>Standard Scope:</b> {self._safe(str(selected_std).upper())}",
            f"<b>Severity Filter (action lists):</b> {self._safe(self.severity_filter.upper())}",
        ]
        proj = self.data.get('project_info') or {}
        if proj.get('name'):
            meta_lines.append(f"<b>Project Name:</b> {self._safe(proj.get('name'))}")
        if proj.get('data_date'):
            meta_lines.append(f"<b>Data Date:</b> {self._safe(proj.get('data_date'))}")

        for line in meta_lines:
            story.append(self._p_markup(line, 'CheckBody'))

        story.append(Spacer(1, 0.35 * cm))
        story.append(Paragraph("OVERALL HEALTH SCORE", self.styles['SectionHeader']))
        score_style = ParagraphStyle(
            'ScoreBigDynamic', parent=self.styles['ScoreBig'], textColor=self._score_color(score)
        )
        story.append(Paragraph(self._safe(str(score)), score_style))
        story.append(Paragraph("out of 100 (weighted)", self.styles['ScoreSub']))

        stats_data = [
            [Paragraph('<b>Metric</b>', self.styles['CheckBody']), Paragraph('<b>Value</b>', self.styles['CheckBody'])],
            ['Total Checks Performed (full run)', str(self.data.get('total_checks', 0))],
            ['Checks Passed', f"{self.data.get('passed_checks', 0)} ({self.data.get('pass_rate', 0)}%)"],
            ['Checks Failed', str(self.data.get('failed_checks', 0))],
            ['Critical Failures (full run)', str(self.data.get('critical_failures', 0))],
            ['High-Severity Failures (full run)', str(self.data.get('high_failures', 0))],
            ['Action list severity filter', self.severity_filter.upper()],
        ]
        stats_table_data = []
        for i, row in enumerate(stats_data):
            if i == 0:
                stats_table_data.append(row)
            else:
                stats_table_data.append([
                    Paragraph(self._safe(row[0]), self.styles['CheckBody']),
                    Paragraph(self._safe(str(row[1])), self.styles['CheckBody']),
                ])

        stats_table = Table(stats_table_data, colWidths=[10 * cm, 6 * cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        story.append(stats_table)

        story.append(PageBreak())

        story.append(Paragraph("STANDARDS COMPLIANCE SUMMARY", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=2, color=self.primary))
        story.append(Spacer(1, 0.35 * cm))

        std_header = ['Standard', 'Score', 'Grade', 'Passed', 'Failed', 'Critical']
        std_rows = [std_header]
        for std_name, std_score in (self.data.get('standard_scores') or {}).items():
            std_rows.append([
                str(std_name), str(std_score.get('score', 0)), str(std_score.get('grade', '-')),
                str(std_score.get('passed', 0)), str(std_score.get('failed', 0)), str(std_score.get('critical_failures', 0)),
            ])

        if len(std_rows) == 1:
            std_rows.append(['—', '—', '—', '—', '—', '—'])

        std_table_data = []
        for i, row in enumerate(std_rows):
            std_table_data.append([
                Paragraph(f"<b>{self._safe(c)}</b>" if i == 0 else self._safe(c), self.styles['CheckBody'])
                for c in row
            ])

        std_table = Table(std_table_data, colWidths=[3.5 * cm, 2.2 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
        std_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.primary),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
        ]))
        story.append(std_table)
        story.append(Spacer(1, 0.6 * cm))

        story.append(Paragraph(f"TOP PRIORITY ACTIONS (Severity: {self.severity_filter.upper()})", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=2, color=self.danger))
        story.append(Spacer(1, 0.25 * cm))

        filtered_actions = self._build_priority_actions(limit=min(10, self.max_top))

        if not filtered_actions:
            story.append(self._p_markup(f"<i>No actions found matching severity filter: {self._safe(self.severity_filter.upper())}</i>", 'CheckBody'))
        else:
            for idx, action in enumerate(filtered_actions, 1):
                block = []
                severity = (action.get('severity') or 'low').upper()
                sev_hex = self._severity_color_hex(severity)

                title = (
                    f"<b>{idx}. [{self._safe(action.get('id', ''))}] {self._safe(action.get('name', ''))}</b><br/>"
                    f"<font size='9' color='#64748b'>Standard: {self._safe(action.get('standard', ''))} | Severity: <font color='{sev_hex}'><b>{self._safe(severity)}</b></font> | Affected: {self._safe(action.get('count', 0))} ({self._safe(action.get('percentage', 0))}%)</font>"
                )
                block.append(self._p_markup(title, 'CheckBody'))

                if action.get('recommendation'):
                    block.append(Spacer(1, 0.08 * cm))
                    block.append(self._recommendation_box(action.get('recommendation')))

                items = action.get('failed_items') or []
                if items:
                    block.append(self._p_markup("<b>Affected Activities:</b>", 'CheckBody'))
                    for item in items[:10]:
                        block.append(self._p_markup(self._activity_line(item), 'CheckBody'))
                    if len(items) > 10:
                        block.append(self._p_markup(f"<i>… and {len(items) - 10} more</i>", 'CheckBody'))

                block.append(Spacer(1, 0.25 * cm))
                story.append(KeepTogether(block))

        doc.build(story, onFirstPage=self._add_page_decor, onLaterPages=self._add_page_decor)
        buffer.seek(0)
        return buffer

    def generate_actions_report(self):
        buffer = io.BytesIO()
        doc = self._build_doc(buffer)
        story = []

        selected_std = self.data.get('selected_standard', 'all')

        story.append(Paragraph("SCHEDULE HEALTH ACTIONS", self.styles['CustomTitle']))
        story.append(Paragraph("Failed Checks & Corrective Action List", self.styles['CustomSubtitle']))
        story.append(self._p_markup(f"<i>Generated: {self._safe(datetime.now().strftime('%Y-%m-%d %H:%M'))} | File: {self._safe(self.file_name)}</i>", 'CheckBody'))
        story.append(self._p_markup(f"<b>Standard Scope:</b> {self._safe(str(selected_std).upper())} | <b>Severity Filter:</b> {self._safe(self.severity_filter.upper())}", 'CheckBody'))
        story.append(HRFlowable(width="100%", thickness=2, color=self.danger))
        story.append(Spacer(1, 0.4 * cm))

        summary_data = [
            ['Total Failed Checks (full run)', str(self.data.get('failed_checks', 0))],
            ['Critical Failures (full run)', str(self.data.get('critical_failures', 0))],
            ['High Severity Failures (full run)', str(self.data.get('high_failures', 0))],
            ['Overall Health Score', f"{self.data.get('overall_score', 0)} / 100"],
            ['This report severity filter', self.severity_filter.upper()],
        ]
        summary_table_data = [
            [Paragraph(self._safe(a), self.styles['CheckBody']), Paragraph(self._safe(b), self.styles['CheckBody'])]
            for a, b in summary_data
        ]
        summary_table = Table(summary_table_data, colWidths=[10 * cm, 6 * cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FEF3C7')),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.55 * cm))

        story.append(Paragraph(f"TOP PRIORITY ACTIONS (Severity: {self.severity_filter.upper()})", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=2, color=self.danger))
        story.append(Spacer(1, 0.25 * cm))

        filtered_top = self._build_priority_actions(limit=self.max_top)

        if not filtered_top:
            story.append(self._p_markup(f"<i>No priority actions matched severity filter: {self._safe(self.severity_filter.upper())}</i>", 'CheckBody'))
        else:
            for idx, action in enumerate(filtered_top, 1):
                block = self._render_action_block(idx, action)
                story.append(KeepTogether(block))

        story.append(PageBreak())

        story.append(Paragraph(f"DETAILED FAILED CHECKS (Severity: {self.severity_filter.upper()})", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2 * cm))

        any_failures = False
        by_std = {}
        for std_name, cat_name, check in self._iter_failed_checks():
            by_std.setdefault(std_name, []).append((cat_name, check))

        for std_name, items in by_std.items():
            any_failures = True
            story.append(Spacer(1, 0.3 * cm))
            story.append(self._p_markup(f"<b>{self._safe(std_name)} Standard</b> ({len(items)} filtered failures)", 'SectionHeader'))

            for cat_name, check in items:
                block = []
                severity = (check.get('severity') or 'low').upper()
                sev_hex = self._severity_color_hex(severity)

                title = f'<font color="{sev_hex}">[{self._safe(severity)}]</font> {self._safe(check.get("id", ""))}: {self._safe(check.get("name", ""))}'
                block.append(self._p_markup(title, 'CheckTitle'))
                block.append(self._p_markup(f"Category: {self._safe(cat_name)}", 'CheckBody'))

                if check.get('description'):
                    block.append(self._p_markup(self._safe(check.get('description')), 'CheckBody'))

                if check.get('count') is not None:
                    metric_line = f"Affected: <b>{self._safe(check.get('count'))}</b> of {self._safe(check.get('total'))} ({self._safe(check.get('percentage', 0))}%) | Threshold: {self._safe(check.get('threshold', ''))}"
                    block.append(self._p_markup(metric_line, 'CheckBody'))
                elif check.get('value') is not None:
                    metric_line = f"Value: <b>{self._safe(check.get('value'))}</b> | Threshold: {self._safe(check.get('threshold', ''))}"
                    block.append(self._p_markup(metric_line, 'CheckBody'))

                if check.get('recommendation'):
                    block.append(Spacer(1, 0.1 * cm))
                    block.append(self._recommendation_box(check.get('recommendation')))

                failed_items = check.get('failed_items') or []
                if failed_items:
                    block.append(Spacer(1, 0.08 * cm))
                    block.append(self._p_markup("<b>Affected Activities:</b>", 'CheckBody'))
                    shown = failed_items[: self.max_items]
                    for item in shown:
                        block.append(self._p_markup(self._activity_line(item), 'CheckBody'))
                    leftover = len(failed_items) - len(shown)
                    if leftover > 0:
                        block.append(self._p_markup(f"<i>… and {leftover} more (see Excel export)</i>", 'CheckBody'))
                else:
                    block.append(self._p_markup("<i>No activity list available for this metric.</i>", 'CheckBody'))

                block.append(Spacer(1, 0.3 * cm))
                story.append(KeepTogether(block))

        if not any_failures:
            story.append(self._p_markup(f"<i>No failures matched severity filter: {self._safe(self.severity_filter.upper())}</i>", 'CheckBody'))

        doc.build(story, onFirstPage=self._add_page_decor, onLaterPages=self._add_page_decor)
        buffer.seek(0)
        return buffer

    def _render_action_block(self, idx, action):
        block = []
        severity = (action.get('severity') or 'low').upper()
        sev_hex = self._severity_color_hex(severity)

        title = f"<b>{idx}. <font color='{sev_hex}'>[{self._safe(severity)}]</font> {self._safe(action.get('id', ''))}: {self._safe(action.get('name', ''))}</b>"
        block.append(self._p_markup(title, 'CheckTitle'))

        meta_parts = []
        if action.get('standard'):
            meta_parts.append(f"Standard: {self._safe(action.get('standard'))}")
        if action.get('category'):
            meta_parts.append(f"Category: {self._safe(action.get('category'))}")
        if action.get('count') is not None:
            meta_parts.append(f"Affected: {self._safe(action.get('count', 0))} ({self._safe(action.get('percentage', 0))}%)")
        elif action.get('value') is not None:
            meta_parts.append(f"Value: {self._safe(action.get('value'))}")
        if action.get('threshold'):
            meta_parts.append(f"Threshold: {self._safe(action.get('threshold'))}")

        if meta_parts:
            block.append(self._p_markup(" | ".join(meta_parts), 'CheckBody'))

        if action.get('description'):
            block.append(self._p_markup(self._safe(action.get('description')), 'CheckBody'))

        if action.get('recommendation'):
            block.append(Spacer(1, 0.08 * cm))
            block.append(self._recommendation_box(action.get('recommendation')))

        failed_items = action.get('failed_items') or []
        if failed_items:
            block.append(Spacer(1, 0.1 * cm))
            block.append(self._p_markup("<b>Affected Activities:</b>", 'CheckBody'))
            shown = failed_items[: self.max_items]
            for item in shown:
                block.append(self._p_markup(self._activity_line(item), 'CheckBody'))
            leftover = len(failed_items) - len(shown)
            if leftover > 0:
                block.append(self._p_markup(f"<i>… and {leftover} more (see Excel export)</i>", 'CheckBody'))
        else:
            block.append(self._p_markup("<i>No activity list available for this metric.</i>", 'CheckBody'))

        block.append(Spacer(1, 0.3 * cm))
        return block
