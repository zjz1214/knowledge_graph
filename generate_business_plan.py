#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成产品商业计划书 PDF
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

# Register Chinese fonts
pdfmetrics.registerFont(TTFont('SimHei', 'C:/Windows/Fonts/simhei.ttf'))
pdfmetrics.registerFont(TTFont('Microsoft YaHei', 'C:/Windows/Fonts/msyh.ttc'))

# Color palette
COLORS = {
    'primary': HexColor('#1a1a2e'),
    'secondary': HexColor('#16213e'),
    'accent': HexColor('#6c5ce7'),
    'accent_light': HexColor('#a29bfe'),
    'text': HexColor('#2d2d2d'),
    'text_light': HexColor('#666666'),
    'bg_light': HexColor('#f5f5fa'),
    'success': HexColor('#00b894'),
    'warning': HexColor('#fdcb6e'),
    'divider': HexColor('#e0e0e0'),
}

def create_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='Title_CN',
        fontName='SimHei',
        fontSize=28,
        leading=36,
        alignment=TA_CENTER,
        textColor=COLORS['primary'],
        spaceAfter=20
    ))

    styles.add(ParagraphStyle(
        name='Subtitle',
        fontName='SimHei',
        fontSize=14,
        leading=20,
        alignment=TA_CENTER,
        textColor=COLORS['text_light'],
        spaceAfter=30
    ))

    styles.add(ParagraphStyle(
        name='SectionTitle',
        fontName='SimHei',
        fontSize=18,
        leading=24,
        textColor=COLORS['accent'],
        spaceBefore=20,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        name='SubsectionTitle',
        fontName='SimHei',
        fontSize=13,
        leading=18,
        textColor=COLORS['primary'],
        spaceBefore=14,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name='BodyText_CN',
        fontName='SimHei',
        fontSize=10,
        leading=16,
        alignment=TA_JUSTIFY,
        textColor=COLORS['text'],
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name='BulletText',
        fontName='SimHei',
        fontSize=10,
        leading=14,
        leftIndent=20,
        textColor=COLORS['text'],
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name='HighlightBox',
        fontName='SimHei',
        fontSize=11,
        leading=16,
        textColor=white,
        backColor=COLORS['accent'],
        spaceBefore=10,
        spaceAfter=10,
        leftIndent=10,
        rightIndent=10,
        borderPadding=10
    ))

    styles.add(ParagraphStyle(
        name='SmallText',
        fontName='SimHei',
        fontSize=8,
        leading=12,
        textColor=COLORS['text_light']
    ))

    styles.add(ParagraphStyle(
        name='CoverBox',
        fontName='SimHei',
        fontSize=12,
        leading=20,
        alignment=TA_CENTER,
        textColor=white,
        backColor=COLORS['accent'],
        borderPadding=20,
        spaceBefore=30,
        spaceAfter=30
    ))

    styles.add(ParagraphStyle(
        name='MetaInfo',
        fontName='SimHei',
        fontSize=10,
        alignment=TA_CENTER,
        textColor=COLORS['text_light']
    ))

    styles.add(ParagraphStyle(
        name='Closing',
        fontName='SimHei',
        fontSize=11,
        leading=18,
        alignment=TA_CENTER,
        textColor=COLORS['accent'],
        borderPadding=15,
        spaceBefore=20
    ))

    return styles


def add_header_footer(canvas, doc):
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(COLORS['accent'])
    canvas.setLineWidth(2)
    canvas.line(2*cm, A4[1] - 1.5*cm, A4[0] - 2*cm, A4[1] - 1.5*cm)

    # Footer
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(COLORS['text_light'])
    canvas.drawString(2*cm, 1.5*cm, "知识图谱个人知识管理系统 | 商业计划书")
    canvas.drawRightString(A4[0] - 2*cm, 1.5*cm, f"{doc.page}")

    canvas.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        "knowledge_graph_business_plan.pdf",
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2*cm,
        title="GraphMind - 个人知识图谱产品商业计划",
        author="GraphMind Team"
    )

    styles = create_styles()
    story = []

    # ==================== Cover Page ====================
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("GraphMind", styles['Title_CN']))
    story.append(Paragraph("基于知识图谱的个人智能知识管理系统", styles['Subtitle']))
    story.append(Spacer(1, 2*cm))

    # Cover highlight
    cover_text = """
    <b>产品定位</b><br/>
    一款面向知识工作者、研究人员和学习者的下一代知识管理工具，<br/>
    将 GraphRAG 检索增强生成与 FSRS 间隔复习完美结合，<br/>
    打造"学以致用、用以促学"的智能知识循环。
    """
    story.append(Paragraph(cover_text, ParagraphStyle(
        name='CoverBox',
        fontName='Helvetica',
        fontSize=12,
        leading=20,
        alignment=TA_CENTER,
        textColor=white,
        backColor=COLORS['accent'],
        borderPadding=20,
        spaceBefore=30,
        spaceAfter=30
    )))

    story.append(Spacer(1, 3*cm))

    # Meta info
    meta_style = ParagraphStyle(
        name='MetaInfo',
        fontName='Helvetica',
        fontSize=10,
        alignment=TA_CENTER,
        textColor=COLORS['text_light']
    )
    story.append(Paragraph(f"版本 1.0 | {datetime.now().strftime('%Y年%m月')}", meta_style))
    story.append(Paragraph("CONFIDENTIAL - 商业计划书", meta_style))

    story.append(PageBreak())

    # ==================== Table of Contents ====================
    story.append(Paragraph("目录", styles['SectionTitle']))
    story.append(Spacer(1, 0.5*cm))

    toc_items = [
        ("1", "执行摘要"),
        ("2", "产品概述"),
        ("3", "市场分析"),
        ("4", "商业模式"),
        ("5", "竞争分析"),
        ("6", "营销策略"),
        ("7", "运营计划"),
        ("8", "财务预测"),
        ("9", "团队介绍"),
        ("10", "风险与机遇"),
    ]

    for num, title in toc_items:
        story.append(Paragraph(f"<b>{num}.</b>  {title}", styles['BodyText_CN']))

    story.append(PageBreak())

    # ==================== 1. Executive Summary ====================
    story.append(Paragraph("1. 执行摘要", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("GraphMind 是什么？", styles['SubsectionTitle']))
    story.append(Paragraph(
        "GraphMind 是一款基于知识图谱的个人知识管理系统，核心特点是：",
        styles['BodyText_CN']
    ))
    summary_points = [
        "• Notion 等笔记工具无缝导入，保持原有工作流",
        "• 自动构建个人知识图谱，挖掘概念间的深层关联",
        "• GraphRAG 智能问答，基于图谱理解提供精准答案",
        "• FSRS 间隔复习算法，遵循遗忘曲线科学安排复习",
        "• 本地部署 + 云端同步，兼顾隐私与便捷"
    ]
    for point in summary_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("为什么现在做？", styles['SubsectionTitle']))
    story.append(Paragraph(
        "后疫情时代，知识工作者面临信息过载、知识碎片化的严峻挑战。传统的笔记工具只做存储，"
        "不做关联；只管输入，不管消化。GraphMind 通过知识图谱和智能复习的结合，让知识真正转化为能力。",
        styles['BodyText_CN']
    ))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("核心亮点", styles['SubsectionTitle']))

    highlight_data = [
        ["指标", "数据"],
        ["目标用户", "知识工作者、研究人员、学习者 (~2亿人)"],
        ["市场规模", "知识管理市场 ~$70B (2025年预期)"],
        ["核心壁垒", "GraphRAG + FSRS 深度整合的算法能力"],
        ["商业模式", "Freemium + Pro 订阅制"],
        ["当前进度", "MVP 已完成，支持 Notion 导入和基础 RAG"],
    ]
    t = Table(highlight_data, colWidths=[4*cm, 10*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'SimHei'),
        ('FONTNAME', (1, 1), (-1, -1), 'SimHei'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), COLORS['bg_light']),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(PageBreak())

    # ==================== 2. Product Overview ====================
    story.append(Paragraph("2. 产品概述", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("2.1 核心功能", styles['SubsectionTitle']))
    story.append(Paragraph(
        "GraphMind 的核心架构围绕「输入 → 理解 → 检索 → 复习」的闭环设计：",
        styles['BodyText_CN']
    ))

    features = [
        ("Notion 导入", "一键同步 Notion 页面，保留标签和层级结构"),
        ("知识图谱构建", "自动抽取实体和关系，Neo4j 图数据库存储"),
        ("GraphRAG 检索", "结合向量相似度和图谱关联的双轨检索"),
        ("智能问答", "基于 MiniMax API 生成准确答案，附带来源"),
        ("FSRS 复习", "科学间隔重复算法，生成个性化复习卡片"),
        ("本地优先", "Docker 部署，数据本地存储，隐私安全"),
    ]

    for name, desc in features:
        story.append(Paragraph(f"<b>{name}</b>：{desc}", styles['BulletText']))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("2.2 技术架构", styles['SubsectionTitle']))

    tech_diagram = """
    <b>数据层</b>：Notion API → Markdown → Neo4j 图数据库

    <b>模型层</b>：Ollama (本地Embedding) + MiniMax API (LLM生成)

    <b>算法层</b>：实体抽取 (LLM) → 关系抽取 → FSRS 调度

    <b>应用层</b>：FastAPI 后端 + Web 可视化界面 + CLI 复习工具
    """
    story.append(Paragraph(tech_diagram, styles['BodyText_CN']))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("2.3 差异化优势", styles['SubsectionTitle']))

    diff_data = [
        ["对比维度", "传统笔记工具", "GraphMind"],
        ["知识组织", "文件夹/标签", "动态知识图谱"],
        ["检索方式", "关键词搜索", "GraphRAG 语义+关联"],
        ["复习机制", "无或简单间隔", "FSRS 科学调度"],
        ["知识关联", "人工建立", "自动挖掘"],
    ]
    t = Table(diff_data, colWidths=[3.5*cm, 5*cm, 5.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), COLORS['bg_light']),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(PageBreak())

    # ==================== 3. Market Analysis ====================
    story.append(Paragraph("3. 市场分析", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("3.1 目标市场", styles['SubsectionTitle']))
    story.append(Paragraph(
        "全球知识管理市场规模在 2025 年预计达到 700 亿美元，年复合增长率 (CAGR) 约为 13%。"
        "这一增长主要由以下因素驱动：数字化办公普及、远程工作常态化、AI 技术渗透率提升。",
        styles['BodyText_CN']
    ))

    market_points = [
        "• <b>知识工作者</b>：全球约 3.5 亿人，中国约 1 亿人",
        "• <b>研究人员</b>：高校、科研机构从业者，学术文档管理需求强烈",
        "• <b>学生群体</b>：考试复习、知识整理，尤其是研究生和终身学习者",
        "• <b>终身学习者</b>：技能提升、职业转型人群中日益增长的需求",
    ]
    for point in market_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("3.2 用户痛点", styles['SubsectionTitle']))

    pain_data = [
        ["痛点", "现有解决方案", "GraphMind 解决方式"],
        ["信息碎片化", "笔记散落在多个工具", "统一导入，图谱关联"],
        ["看过即忘", "无复习机制", "FSRS 间隔复习，科学抗遗忘"],
        ["难以发现关联", "人工整理工作量大", "自动实体抽取，关系发现"],
        ["检索效率低", "关键词匹配，不精准", "GraphRAG 语义理解，精准召回"],
    ]
    t = Table(pain_data, colWidths=[3.5*cm, 5*cm, 5.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), COLORS['bg_light']),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(PageBreak())

    # ==================== 4. Business Model ====================
    story.append(Paragraph("4. 商业模式", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("4.1 订阅模式 (Freemium)", styles['SubsectionTitle']))
    story.append(Paragraph(
        "采用 Freemium 模型，降低用户尝试门槛，通过增值服务实现变现：",
        styles['BodyText_CN']
    ))

    tier_data = [
        ["功能", "Free", "Pro ($9.9/月)", "Team ($19.9/月)"],
        ["笔记导入", "100条", "无限", "无限"],
        ["知识图谱", "基础版", "高级版 (含向量搜索)", "团队共享图谱"],
        ["GraphRAG 问答", "每天5次", "无限", "无限"],
        ["FSRS 复习卡片", "50张", "无限", "无限"],
        ["API 访问", "不支持", "支持", "支持"],
        ["多设备同步", "不支持", "支持", "支持"],
        ["优先支持", "不支持", "支持", "支持"],
    ]
    t = Table(tier_data, colWidths=[4*cm, 3.5*cm, 3.5*cm, 3.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("4.2 收入预测 (五年)", styles['SubsectionTitle']))

    revenue_data = [
        ["年份", "用户数", "付费转化率", "ARPU", "年收入"],
        ["Year 1", "10,000", "3%", "$8", "$24,000"],
        ["Year 2", "50,000", "5%", "$9", "$225,000"],
        ["Year 3", "150,000", "7%", "$10", "$1,050,000"],
        ["Year 4", "400,000", "8%", "$10", "$3,200,000"],
        ["Year 5", "800,000", "10%", "$11", "$8,800,000"],
    ]
    t = Table(revenue_data, colWidths=[2.5*cm, 3*cm, 3*cm, 2.5*cm, 3.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("4.3 其他收入来源", styles['SubsectionTitle']))
    other_revenue = [
        "• <b>企业定制</b>：为特定行业（法律、医疗、金融）提供知识图谱解决方案",
        "• <b>API 变现</b>：开放 GraphRAG API，按调用次数收费",
        "• <b>培训课程</b>：知识管理方法论培训，$99/人",
        "• <b>数据洞察</b>（未来）：聚合匿名化知识图谱数据，提供行业趋势分析",
    ]
    for point in other_revenue:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(PageBreak())

    # ==================== 5. Competition ====================
    story.append(Paragraph("5. 竞争分析", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("5.1 竞争格局", styles['SubsectionTitle']))

    comp_data = [
        ["产品", "优势", "劣势", "与 GraphMind 关系"],
        ["Notion", "生态成熟，用户量大", "无图谱，无 RAG", "我们导入源"],
        ["Obsidian", "本地化，插件生态", "学习曲线陡，无 RAG", "潜在整合或竞争"],
        ["Roam Research", "双向链接先驱", "昂贵，生态封闭", "差异化：RAG+复习"],
        ["Anki", "间隔复习成熟", "无图谱，界面老旧", "我们整合复习算法"],
        ["ChatGPT", "LLM 能力强", "无个人知识图谱", "我们提供差异化检索"],
    ]
    t = Table(comp_data, colWidths=[2.5*cm, 3.5*cm, 3.5*cm, 4*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("5.2 我们的护城河", styles['SubsectionTitle']))
    moat_points = [
        "• <b>GraphRAG + FSRS 深度整合</b>：市场上无直接竞品",
        "• <b>本地部署能力</b>：数据隐私敏感用户（研究员、律师）的首选",
        "• <b>Notion 优先支持</b>：深度集成 Notion API，迁移成本低",
        "• <b>算法壁垒</b>：FSRS 参数优化和 GraphRAG 检索调优需要大量实验数据",
    ]
    for point in moat_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(PageBreak())

    # ==================== 6. Marketing Strategy ====================
    story.append(Paragraph("6. 营销策略", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("6.1 获客渠道", styles['SubsectionTitle']))

    channel_data = [
        ["渠道", "优先级", "预期效果", "成本"],
        ["Product Hunt", "P0", "种子用户 + 曝光", "免费"],
        ["小红书/知乎", "P0", "中文用户种草", "内容成本"],
        ["Notion 社区", "P1", "精准用户导入", "免费"],
        ["学术社群", "P1", "研究人群渗透", "低"],
        ["AI 技术博客", "P2", "技术影响力", "低"],
        ["付费广告", "P2", "规模化获客", "$10k/月 (后期)"],
    ]
    t = Table(channel_data, colWidths=[3*cm, 2*cm, 5*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("6.2 转化策略", styles['SubsectionTitle']))
    conv_points = [
        "• <b>免费额度充分</b>：100 条笔记 + 每天 5 次 RAG 足以让用户体验核心价值",
        "• <b>渐进式引导</b>：新用户引导创建第一张复习卡片，降低认知负担",
        "• <b>数据可迁移</b>：导出功能确保用户无锁定感，降低付费决策风险",
    ]
    for point in conv_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(PageBreak())

    # ==================== 7. Operations ====================
    story.append(Paragraph("7. 运营计划", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("7.1 里程碑", styles['SubsectionTitle']))

    roadmap_data = [
        ["阶段", "时间", "目标"],
        ["MVP", "已完成", "Notion 导入 + 基础 RAG + CLI 复习"],
        ["Beta", "Q3 2026", "邀请 500 用户内测，收集反馈"],
        ["v1.0", "Q4 2026", "正式发布，付费功能上线"],
        ["v2.0", "Q2 2027", "团队协作功能 + 企业版"],
        ["Expansion", "2028+", "多语言支持 + 行业解决方案"],
    ]
    t = Table(roadmap_data, colWidths=[2.5*cm, 2.5*cm, 9*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("7.2 成本结构", styles['SubsectionTitle']))
    cost_points = [
        "• <b>LLM API 成本</b>：MiniMax API，按 token 计费，预计 $500-2000/月",
        "• <b>基础设施</b>：Neo4j Cloud / Docker hosting，~$200/月",
        "• <b>开发人力</b>：创始团队早期 3 人，后期扩招",
        "• <b>营销</b>：早期以内容营销为主，后期 $10k/月付费渠道",
    ]
    for point in cost_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(PageBreak())

    # ==================== 8. Financial Projections ====================
    story.append(Paragraph("8. 财务预测", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("8.1 损益表预测 (单位：美元)", styles['SubsectionTitle']))

    fin_data = [
        ["项目", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
        ["收入", "$24,000", "$225,000", "$1,050,000", "$3,200,000", "$8,800,000"],
        ["LLM 成本", "$6,000", "$30,000", "$80,000", "$150,000", "$300,000"],
        ["基础设施", "$2,400", "$4,800", "$9,600", "$19,200", "$38,400"],
        ["营销", "$5,000", "$30,000", "$100,000", "$300,000", "$600,000"],
        ["人力", "$0", "$50,000", "$150,000", "$400,000", "$800,000"],
        ["其他", "$2,000", "$10,000", "$30,000", "$80,000", "$150,000"],
        ["净利润", "$8,600", "$100,200", "$680,400", "$2,250,800", "$6,911,600"],
        ["净利润率", "36%", "45%", "65%", "70%", "79%"],
    ]
    t = Table(fin_data, colWidths=[3*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("8.2 关键假设", styles['SubsectionTitle']))
    assumption_points = [
        "• 第 3 年起付费转化率达 7%，ARPU 约 $10/月",
        "• LLM 成本随技术进步下降，预计年均降幅 30%",
        "• 团队扩张克制，人力成本控制在收入 20% 以内",
        "• 第五年净利润率 79% 反映规模效应和边际成本趋零",
    ]
    for point in assumption_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(PageBreak())

    # ==================== 9. Team ====================
    story.append(Paragraph("9. 团队介绍", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("创始团队 (3人)", styles['SubsectionTitle']))

    team_data = [
        ["角色", "背景", "负责"],
        ["CEO / Product", "连续创业者，前某科技公司产品负责人", "产品方向 + 融资"],
        ["CTO / Engineer", "前某大厂后端工程师，GraphRAG 研究者", "技术架构 + 算法"],
        ["Designer", "资深 UI/UX设计师，专注知识管理产品", "产品体验 + 品牌"],
    ]
    t = Table(team_data, colWidths=[2.5*cm, 6*cm, 5.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("顾问团", styles['SubsectionTitle']))
    advisor_points = [
        "• <b>知识图谱专家</b>：某高校教授，NLP 领域 20 年经验",
        "• <b>产品增长专家</b>：前某 SaaS 增长负责人，擅长 PLG 策略",
        "• <b>商业化顾问</b>：连续退出创业者，现天使投资人",
    ]
    for point in advisor_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(PageBreak())

    # ==================== 10. Risks & Opportunities ====================
    story.append(Paragraph("10. 风险与机遇", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=COLORS['accent'], spaceAfter=15))

    story.append(Paragraph("10.1 主要风险", styles['SubsectionTitle']))

    risk_data = [
        ["风险", "概率", "影响", "应对措施"],
        ["大厂入局", "中", "高", "快速迭代，积累用户数据壁垒"],
        ["LLM 成本上涨", "中", "中", "优化 prompt，预留预算"],
        ["用户隐私问题", "低", "高", "本地部署优先，合规透明"],
        ["技术替代", "低", "中", "持续跟进 GraphRAG 前沿研究"],
    ]
    t = Table(risk_data, colWidths=[3.5*cm, 1.8*cm, 1.8*cm, 6.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['accent']),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['divider']),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("10.2 市场机遇", styles['SubsectionTitle']))

    opp_points = [
        "• <b>Notion 生态红利</b>：Notion 2 亿用户，天然导入源",
        "• <b>AI Native 趋势</b>：ChatGPT 验证了 AI 改变知识工作的可行性",
        "• <b>个人知识图谱空白</b>：市面上尚无成熟产品做到 GraphRAG + FSRS 整合",
        "• <b>数据主权意识</b>：本地部署需求增长，隐私敏感用户付费意愿强",
    ]
    for point in opp_points:
        story.append(Paragraph(point, styles['BulletText']))

    story.append(Spacer(1, 1*cm))

    # Closing statement
    closing = """
    <b>联系我们</b><br/>
    如对 GraphMind 感兴趣，欢迎交流合作。<br/>
    项目阶段：MVP 已完成，寻求种子轮融资 ($500k)
    """
    story.append(Paragraph(closing, ParagraphStyle(
        name='Closing',
        fontName='Helvetica',
        fontSize=11,
        leading=18,
        alignment=TA_CENTER,
        textColor=COLORS['accent'],
        borderPadding=15,
        spaceBefore=20
    )))

    # Build
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    print("PDF generated: knowledge_graph_business_plan.pdf")


if __name__ == "__main__":
    build_pdf()