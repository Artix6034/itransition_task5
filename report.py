import io
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import matplotlib

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether

from analysis import METHODS
from charts import chart_png

FONT_DIR=Path(matplotlib.get_data_path())/'fonts'/'ttf'
pdfmetrics.registerFont(TTFont('DejaVu',str(FONT_DIR/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DejaVu-Bold',str(FONT_DIR/'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('DejaVu',normal='DejaVu',bold='DejaVu-Bold',italic='DejaVu',boldItalic='DejaVu-Bold')


def make_report(series, results, settings, source):
    out=io.BytesIO()
    styles=getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName='DejaVu-Bold' if 'Heading' in style.name or style.name=='Title' else 'DejaVu'
    styles.add(ParagraphStyle(name='SmallNote',fontName='DejaVu',fontSize=9,leading=13,textColor=colors.HexColor('#536574')))
    styles['Title'].fontSize=24
    styles['Title'].leading=29
    styles['Title'].alignment=0
    styles['Heading1'].textColor=colors.HexColor('#24566b')
    styles['Heading1'].fontSize=17
    styles['BodyText'].fontSize=10
    styles['BodyText'].leading=15
    story=[Paragraph('Mining production report',styles['Title']),
           Paragraph('Weyland-Yutani Corporation',styles['Heading2']),
           Paragraph(escape(source),styles['SmallNote']),Spacer(1,5*mm)]
    first=next(iter(series.values()))[0]
    story.append(Paragraph(f'Period: {first[0]} to {first[-1]}. Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}.',styles['BodyText']))
    story.append(Paragraph('Analysis settings',styles['Heading2']))
    story.append(Paragraph(f"IQR multiplier {settings['iqr']:g}; z-score threshold {settings['z']:g}; moving-average window {settings['window']} previous observations; distance threshold {settings['percent']:g}%; Grubbs alpha {settings['alpha']:g}. Charts: {settings['chart']}, polynomial degree {settings['degree']}, highlight: {escape(settings['method'])}.",styles['BodyText']))
    story.append(Paragraph('Standard deviation uses n-1. IQR uses linearly interpolated quartiles. The moving average excludes the current observation and needs a full window. Spike/drop direction compares output with that preceding mean, or the series median when the window is unavailable. Grubbs is a two-sided single-outlier test, at most one result per series. Its normality assumption can be violated by trends and weekly patterns; flags are candidates for review.',styles['SmallNote']))
    story.append(Paragraph('Production statistics',styles['Heading2']))
    rows=[['Series','Days','Mean','Std. dev.','Median','IQR']]
    for name,result in results.items():
        rows.append([Paragraph(escape(name),styles['SmallNote']),str(result['count']),*[f'{result[key]:,.2f}' for key in ('mean','std','median','iqr')]])
    table=Table(rows,colWidths=[59*mm,16*mm,25*mm,25*mm,25*mm,25*mm],repeatRows=1)
    table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'DejaVu'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef2')),('FONTNAME',(0,0),(-1,0),'DejaVu-Bold'),
       ('FONTSIZE',(0,0),(-1,-1),9),('VALIGN',(0,0),(-1,-1),'TOP'),('ALIGN',(1,1),(-1,-1),'RIGHT'),
       ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dce4e9'))]))
    story.append(table)
    for name,(days,values) in series.items():
        result=results[name]
        story.extend([PageBreak(),Paragraph(escape(name),styles['Heading1']),
                      Image(io.BytesIO(chart_png(name,series,results,settings)),width=175*mm,height=70*mm)])
        counts=', '.join(f'{method}: {int(result["flags"][method].sum())}' for method in METHODS)
        story.append(Paragraph(f'Flag counts - {counts}. Distinct observations: {len(result["anomalies"])}.',styles['BodyText']))
        story.append(Paragraph(f'IQR acceptance interval: {result["low"]:.2f} to {result["high"]:.2f} tons.',styles['SmallNote']))
        if result['grubbs_stat'] is not None:
            story.append(Paragraph(f'Grubbs: G = {result["grubbs_stat"]:.4f}; critical G = {result["grubbs_critical"]:.4f}.',styles['SmallNote']))
        story.append(Paragraph('Anomaly details',styles['Heading2']))
        if not result['anomalies']:
            story.append(Paragraph('No observations were flagged at the selected thresholds.',styles['BodyText']))
        for item in result['anomalies']:
            ma=item['ma_percent']
            distance='not available' if ma!=ma else ('unbounded (zero baseline)' if ma==float('inf') else f'{ma:.1f}%')
            heading=Paragraph(f'{item["date"]}: {item["direction"]} at {item["value"]:.2f} tons',styles['Heading3'])
            body=Paragraph(f'Tests: {escape(", ".join(item["methods"]))}. Reference output: {item["baseline"]:.2f} tons. Absolute z-score: {item["z"]:.2f}. Distance from preceding moving average: {distance}.',styles['SmallNote'])
            story.append(KeepTogether([heading,body,Spacer(1,2*mm)]))
    def footer(canvas,doc):
        canvas.saveState()
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#647686'))
        canvas.drawString(18*mm,12*mm,'Weyland-Yutani - Mining production')
        canvas.drawRightString(193*mm,12*mm,str(doc.page))
        canvas.restoreState()
    SimpleDocTemplate(out,pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=17*mm,
                      topMargin=18*mm,bottomMargin=20*mm,title='Mining production report').build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
