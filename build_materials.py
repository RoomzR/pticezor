# -*- coding: utf-8 -*-
"""Заявка и презентация хакатона «Код Будущего», проект «Птицезор»."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor, Emu
from pptx import Presentation
from pptx.dml.color import RGBColor as PColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn as pqn
from pptx.util import Emu as PEmu
from pptx.util import Inches, Pt as PPt

ROOT = Path("/Users/roomz/Documents/хакатон")
IMG = ROOT / "fig"
IMG.mkdir(exist_ok=True)

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
TNR = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
TNR_B = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"

INK = "1C2421"
GREEN = "1E3A34"
RUST = "8E3B2F"
PAPER = "F3F0E8"
CARD = "FFFCF7"
LINE = "D4CBBC"
MUTED = "5E675F"


def font(path, size):
    return ImageFont.truetype(path, size)


def rounded(draw, box, r, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def dashed_rect(draw, box, color="#2F5D4E", width=3, dash=16, gap=10):
    x1, y1, x2, y2 = box
    x = x1
    while x < x2:
        draw.line((x, y1, min(x + dash, x2), y1), fill=color, width=width)
        draw.line((x, y2, min(x + dash, x2), y2), fill=color, width=width)
        x += dash + gap
    y = y1
    while y < y2:
        draw.line((x1, y, x1, min(y + dash, y2)), fill=color, width=width)
        draw.line((x2, y, x2, min(y + dash, y2)), fill=color, width=width)
        y += dash + gap


def draw_scheme():
    W, H = 1800, 900
    im = Image.new("RGB", (W, H), "#F7F4EE")
    d = ImageDraw.Draw(im)
    f_s = font(ARIAL, 22)
    f_b = font(ARIAL_B, 26)
    f_xs = font(ARIAL, 18)

    d.rounded_rectangle((24, 24, 1776, 876), radius=16, fill="#FFFCF7", outline="#1E3A34", width=3)
    d.text((48, 42), "План секции. В каждой зоне пара: обычная камера и тепловизор.", font=f_b, fill="#1E3A34")

    # vestibule
    d.rounded_rectangle((48, 110, 280, 700), radius=10, fill="#E7EFEA", outline="#1E3A34", width=2)
    d.text((112, 140), "тамбур", font=f_b, fill="#1E3A34")
    d.rounded_rectangle((88, 200, 240, 300), radius=8, fill="#1E3A34")
    d.text((112, 232), "компьютер", font=f_s, fill="#F3F0E8")
    for i, line in enumerate(("расчёт в корпусе", "видео наружу", "не уходит")):
        d.text((78, 330 + i * 28), line, font=f_xs, fill="#1C2421")

    # hall
    d.rectangle((310, 110, 1752, 700), outline="#1E3A34", width=3)

    # two camera zones
    dashed_rect(d, (340, 155, 1000, 660))
    dashed_rect(d, (1040, 155, 1712, 660))
    def pair_badge(x, y):
        d.rounded_rectangle((x, y, x + 118, y + 34), radius=6, fill="#1E3A34")
        d.text((x + 16, y + 4), "камера", font=f_xs, fill="#F3F0E8")
        d.rounded_rectangle((x + 128, y, x + 268, y + 34), radius=6, fill="#8E3B2F")
        d.text((x + 150, y + 4), "тепло", font=f_xs, fill="#F3F0E8")

    d.text((360, 172), "зона 1", font=f_b, fill="#1E3A34")
    pair_badge(500, 168)
    d.text((1060, 172), "зона 2", font=f_b, fill="#1E3A34")
    pair_badge(1200, 168)

    # feeders and drinkers, kept inside the hall and clear of the titles
    for y in (280, 450, 610):
        d.rounded_rectangle((360, y, 980, y + 14), radius=6, fill="#C4B49A")
        d.rounded_rectangle((1060, y, 1690, y + 14), radius=6, fill="#C4B49A")
    for y in (360, 530):
        d.line((370, y, 970, y), fill="#7E98A8", width=4)
        d.line((1070, y, 1680, y), fill="#7E98A8", width=4)

    birds = []
    for zone_x in (390, 1090):
        for col in range(6):
            for row, y0 in enumerate((230, 320, 400, 490, 575)):
                if (col + row) % 2 == 0:
                    continue
                birds.append((zone_x + col * 90, y0))
    for x, y in birds:
        d.ellipse((x, y, x + 14, y + 11), fill="#8A8478")

    # alerts sit in open gaps, not on the lines
    alerts = [(760, 390, "1   −5 °C"), (1420, 500, "2   −4 °C")]
    for x, y, n in alerts:
        d.ellipse((x - 22, y - 22, x + 22, y + 22), outline="#C46A2F", width=6)
        d.ellipse((x - 16, y - 16, x + 16, y + 16), outline="#8E3B2F", width=3)
        d.line((x - 8, y - 8, x + 8, y + 8), fill="#8E3B2F", width=3)
        d.line((x + 8, y - 8, x - 8, y + 8), fill="#8E3B2F", width=3)
        d.text((x + 28, y - 14), n, font=f_b, fill="#8E3B2F")

    # legend under the plan, one row, nothing overlaps the hall
    legend_y = 740
    d.rounded_rectangle((48, legend_y, 78, legend_y + 16), radius=4, fill="#C4B49A")
    d.text((90, legend_y - 4), "кормушка", font=f_xs, fill="#1C2421")
    d.line((250, legend_y + 8, 310, legend_y + 8), fill="#7E98A8", width=4)
    d.text((322, legend_y - 4), "поилка", font=f_xs, fill="#1C2421")
    d.ellipse((470, legend_y, 486, legend_y + 14), fill="#8A8478")
    d.text((498, legend_y - 4), "живая птица", font=f_xs, fill="#1C2421")
    d.ellipse((690, legend_y - 2, 712, legend_y + 20), outline="#C46A2F", width=4)
    d.text((724, legend_y - 4), "точка падежа, холоднее соседей", font=f_xs, fill="#1C2421")
    d.rounded_rectangle((1188, legend_y, 1210, legend_y + 16), radius=3, fill="#1E3A34")
    d.text((1218, legend_y - 4), "камера", font=f_xs, fill="#1C2421")
    d.rounded_rectangle((1340, legend_y, 1362, legend_y + 16), radius=3, fill="#8E3B2F")
    d.text((1370, legend_y - 4), "тепловизор", font=f_xs, fill="#1C2421")

    path = IMG / "scheme.png"
    im.save(path, quality=95)
    return path


def draw_screen():
    W, H = 1920, 1080
    im = Image.new("RGB", (W, H), "#E6E1D6")
    d = ImageDraw.Draw(im)
    f_title = font(ARIAL_B, 32)
    f_h = font(ARIAL_B, 26)
    f = font(ARIAL, 22)
    f_b = font(ARIAL_B, 22)
    f_big = font(ARIAL_B, 54)
    f_sm = font(ARIAL, 18)
    f_sm_b = font(ARIAL_B, 18)

    d.rectangle((0, 0, W, 72), fill="#1E3A34")
    d.text((28, 18), "Птицезор", font=f_title, fill="#F3F0E8")
    d.text((230, 24), "секция 2    ·    сутки тура 27    ·    06:10", font=f, fill="#D5E0DA")
    d.text((1540, 24), "мастер корпуса", font=f, fill="#D5E0DA")

    d.rounded_rectangle((24, 84, 1896, 168), radius=12, fill="#FFFCF7", outline="#D4CBBC", width=2)
    counts = [
        (48, "Посажено по журналу", "25 000"),
        (680, "Видно в зонах камер", "23 840"),
        (1310, "Расхождение, не инвентаризация", "1 160"),
    ]
    for x, label, value in counts:
        d.text((x, 94), label, font=f_sm, fill="#5E675F")
        d.text((x, 114), value, font=font(ARIAL_B, 36), fill="#1C2421")

    # plan
    d.rounded_rectangle((24, 180, 1180, 748), radius=12, fill="#FFFCF7", outline="#D4CBBC", width=2)
    d.text((48, 192), "Зона 1. Обычная камера и тепловизор", font=f_h, fill="#1E3A34")
    d.rectangle((48, 232, 1148, 710), outline="#1E3A34", width=2, fill="#F6F1E6")

    for y in (300, 450, 600):
        d.rectangle((80, y, 1110, y + 10), fill="#C4B49A")
    for y in (370, 530):
        d.line((90, y, 1100, y), fill="#8AA0AE", width=3)

    birds = []
    for col in range(12):
        for row in range(7):
            if (col + row) % 3 == 0:
                continue
            x = 110 + col * 80 + (row % 2) * 18
            y = 255 + row * 58
            birds.append((x, y))
    for x, y in birds:
        d.ellipse((x, y, x + 18, y + 14), fill="#8A8478")

    marks = [((430, 500), "В3", "−5 °C"), ((900, 340), "Г1", "−6 °C"), ((280, 640), "А2", "−4 °C")]
    for (x, y), cell, tm in marks:
        d.ellipse((x - 18, y - 18, x + 18, y + 18), outline="#8E3B2F", width=4)
        d.text((x + 24, y - 16), f"{cell}  {tm}", font=f_sm_b, fill="#8E3B2F")

    d.text((48, 716), "Красным – холоднее соседей. Г1 ещё без подтверждения мастера.", font=f_sm, fill="#5E675F")

    # cards
    cards = [
        (1204, 180, 1888, 352, "Падёж за сутки", "3 точки", "2 подтверждены, 1 ждёт мастера"),
        (1204, 368, 1888, 552, "Живой вес, медиана", "1 842 г", "норма кросса на 27-е сутки  1 910 г"),
        (1204, 568, 1888, 748, "Активность к 06:00", "ниже обычной", "сравнение с этим же часом вчера"),
    ]
    for x1, y1, x2, y2, title, big, sub in cards:
        d.rounded_rectangle((x1, y1, x2, y2), radius=12, fill="#FFFCF7", outline="#D4CBBC", width=2)
        d.text((x1 + 24, y1 + 16), title, font=f, fill="#5E675F")
        d.text((x1 + 24, y1 + 58), big, font=f_big, fill="#1C2421")
        d.text((x1 + 24, y1 + y2 - y1 - 48), sub, font=f_sm, fill="#1E3A34")

    # deviation chip
    d.rounded_rectangle((1688, 430, 1856, 478), radius=8, fill="#F4E4DC")
    d.text((1704, 440), "−3,6 %", font=f_b, fill="#8E3B2F")

    # table
    d.rounded_rectangle((24, 764, 1888, 1064), radius=12, fill="#FFFCF7", outline="#D4CBBC", width=2)
    d.text((48, 776), "Точки за ночь", font=f_h, fill="#1E3A34")
    headers = [(48, "Время"), (260, "Клетка плана"), (520, "Пара и тепло"), (860, "Статус"), (1280, "Кто отметил")]
    for x, t in headers:
        d.text((x, 822), t, font=f_sm_b, fill="#5E675F")
    d.line((48, 854, 1850, 854), fill="#D4CBBC", width=2)
    rows = [
        ("02:14", "В3", "зона 1, −5 °C", "подтверждено, падаль", "мастер, 06:02"),
        ("04:41", "Г1", "зона 1, −6 °C", "ждёт проверки", "–"),
        ("05:06", "А2", "зона 2, −4 °C", "подтверждено, падаль", "мастер, 06:04"),
    ]
    for i, row in enumerate(rows):
        y = 868 + i * 40
        xs = (48, 260, 520, 860, 1280)
        color = "#8E3B2F" if "ждёт" in row[3] else "#1C2421"
        for x, val in zip(xs, row):
            d.text((x, y), val, font=f, fill=color)

    path = IMG / "screen.png"
    im.save(path, quality=95)
    return path


def set_run_font(run, name="Times New Roman", size=14, bold=False, italic=False, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._element.get_or_add_rPr()
    lang = rPr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rPr.append(lang)
    lang.set(qn("w:val"), "ru-RU")
    lang.set(qn("w:eastAsia"), "ru-RU")


def shade_cell(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")


def set_cell_borders(cell, color="1E3A34", sz="4"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge in ("top", "left", "bottom", "right"):
        el = tcBorders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            tcBorders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), sz)
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)


def set_cell_margins(cell, top=40, bottom=40, left=80, right=80):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.find(qn("w:tcMar"))
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)
    for m, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = tcMar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tcMar.append(node)
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")


def prevent_row_split(row):
    tr = row._tr
    trPr = tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    trPr.append(cant)


def para(doc, text, *, size=14, bold=False, italic=False, center=False, justify=True,
         indent=True, before=0, after=0, space=1.5, color=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = space
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.first_line_indent = Cm(0)
    elif justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.first_line_indent = Cm(1.25) if indent else Cm(0)
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.first_line_indent = Cm(1.25) if indent else Cm(0)
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic, color=color)
    return p


def heading(doc, text):
    return para(doc, text, bold=True, justify=False, indent=False, before=14, after=4, space=1.15)


def caption(doc, text):
    return para(doc, text, size=12, italic=True, center=True, indent=False, before=2, after=8, space=1.0)


def add_page_field(paragraph):
    run = paragraph.add_run()
    set_run_font(run, size=11)
    r = run._r
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    r.append(fld1)
    r.append(instr)
    r.append(fld2)


def fill_cell(cell, text, *, bold=False, size=11, center=True, color=None, fill=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    if fill:
        shade_cell(cell, fill)
    set_cell_borders(cell)
    set_cell_margins(cell)
    # vertical align
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    vAlign = tcPr.find(qn("w:vAlign"))
    if vAlign is None:
        vAlign = OxmlElement("w:vAlign")
        tcPr.append(vAlign)
    vAlign.set(qn("w:val"), "center")


def build_docx(scheme, screen):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Mm(210)
    sec.page_height = Mm(297)
    sec.left_margin = Mm(30)
    sec.right_margin = Mm(15)
    sec.top_margin = Mm(18)
    sec.bottom_margin = Mm(16)
    sec.header_distance = Mm(6)
    sec.footer_distance = Mm(6)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    header = sec.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hr = hp.add_run("Хакатон «Код Будущего»  ·  заявка  ·  проект «Птицезор»")
    set_run_font(hr, size=10, color="5E675F")
    hp.paragraph_format.space_after = Pt(2)

    # header line
    pBdr = hp._p.get_or_add_pPr()
    pBdr_el = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1E3A34")
    pBdr_el.append(bottom)
    pBdr.append(pBdr_el)

    footer = sec.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("Сельское хозяйство  ·  стр. ")
    set_run_font(fr, size=11, color="5E675F")
    add_page_field(fp)

    core = doc.core_properties
    core.title = "Заявка. Проект «Птицезор»"
    core.subject = "Хакатон «Код Будущего», номинация «Сельское хозяйство»"
    core.author = ""
    core.comments = ""
    core.category = ""

    para(doc, "ХАКАТОН «КОД БУДУЩЕГО»", size=12, bold=True, center=True, before=0, after=0, space=1.0, color="1E3A34")
    para(doc, "ЗАЯВКА", size=16, bold=True, center=True, before=2, after=0, space=1.0)
    para(
        doc,
        "на участие со стартап-проектом (программный продукт)",
        size=13,
        center=True,
        before=0,
        after=2,
        space=1.0,
    )
    para(doc, "Проект «Птицезор»", size=14, bold=True, center=True, before=2, after=0, space=1.0)
    para(
        doc,
        "Номинация: сельское хозяйство",
        size=13,
        center=True,
        before=0,
        after=6,
        space=1.0,
    )

    heading(doc, "1. Общие сведения")
    para(
        doc,
        "«Птицезор» – программа для птичника с напольным содержанием бройлера. Обычная камера и тепловизор закреплены сверху и смотрят на один участок пола. По видео программа отмечает место павшей птицы, оценивает средний живой вес тех голов, которых в кадр было нормально видно, и считает, сколько голов видно в зонах камер. Тушку от спящей отличает тепло: павшая холоднее соседей. Мастер корпуса утром открывает экран: точки за ночь, две цифры по головам (сколько посадили по журналу и сколько видно в зонах), вес за сутки и строка, не села ли секция раньше обычного.",
    )
    para(
        doc,
        "Заявка подаётся в номинации «Сельское хозяйство». По требованиям к материалам стартап-проект здесь понимается как программный продукт. На дату подачи окно программы уже открывается на компьютере: показ правила, утро мастера, схема зала и лист обхода сотрудника. Содержательная часть и инструкция пользователя лежат в открытом доступе: https://github.com/RoomzR/pticezor. Это разработанное приложение: окно открывается на компьютере защиты. Установки в хозяйстве и готового кейса нет. Алгоритм реализации дан в этой заявке и в презентации (файл PPTX, соотношение сторон 16:9). Видеоролик не прикладывается.",
    )
    para(
        doc,
        "Команда – не больше 4 человек, возраст от 18 до 31 года, граждане Республики Беларусь. Графы таблицы заполняются до отправки. Без фамилий организатор не сможет включить команду в список на финал.",
        before=2,
    )

    table = doc.add_table(rows=5, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = [Cm(3.6), Cm(2.6), Cm(4.0), Cm(2.8), Cm(3.5)]
    headers = ["ФИО", "Дата рождения", "Место учёбы или работы", "Роль в команде", "Телефон и почта"]
    for i, h in enumerate(headers):
        fill_cell(table.rows[0].cells[i], h, bold=True, size=10, fill="1E3A34", color="FFFFFF")
    for r in range(1, 5):
        for c in range(5):
            fill_cell(table.rows[r].cells[c], " ", size=10)
        prevent_row_split(table.rows[r])
        tr = table.rows[r]._tr
        trPr = tr.get_or_add_trPr()
        trHeight = OxmlElement("w:trHeight")
        trHeight.set(qn("w:val"), "420")
        trHeight.set(qn("w:hRule"), "atLeast")
        trPr.append(trHeight)
    fill_cell(table.rows[1].cells[4], "rudenbelstad@gmail.com", size=9, center=False)
    tr1 = table.rows[1]._tr
    tr1Pr = tr1.get_or_add_trPr()
    tr1h = OxmlElement("w:trHeight")
    tr1h.set(qn("w:val"), "700")
    tr1h.set(qn("w:hRule"), "atLeast")
    tr1Pr.append(tr1h)
    prevent_row_split(table.rows[0])
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            cell.width = widths[i]
    # set tbl width
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), "9350")
    tblW.set(qn("w:type"), "dxa")

    para(
        doc,
        "Контакт для писем организаторов (один на команду): телефон ____________________, почта rudenbelstad@gmail.com.",
        indent=False,
        justify=False,
        before=6,
        after=0,
        space=1.15,
        size=12,
    )

    heading(doc, "2. Описание бизнес-идеи")
    para(
        doc,
        "На площадке сидит 20–100 тысяч голов. Две цифры, от которых зависит тур, до сих пор получают ногами и руками.",
    )
    para(
        doc,
        "Первая цифра – падёж. Тушку собирают обходом. Зал длинный, к концу тура птица крупная, подстилка тёмная, павшую голову легко пройти мимо. Её находят через несколько часов или уже следующим проходом. Пока тушка лежит, для соседних голов это грязное место. В журнале обычно остаётся число вынесенных голов. Где они лежали, чаще всего не пишут, хотя именно место показывает, падёж размазан по залу или он собрался у стены, у поилки, у двери.",
    )
    para(
        doc,
        "Вторая цифра – живой вес. Раз или два в неделю ловят несколько десятков голов, ставят на весы и отпускают. По выборке решают, идёт ли партия по кривой кросса, трогать ли корм и на какой день ставить сдачу. Между взвешиваниями график пустой. В руки при этом чаще попадается птица, которая хуже уворачивается, и средний вес выборки уезжает от среднего веса зала.",
    )
    para(
        doc,
        "Камеры на корпусах иногда уже висят. По ним смотрят, что происходит в зале, но ни падёж, ни вес с картинки не считают. Масштаб потери виден и без нашей площадки: на совещании 3 октября 2025 г. назван падёж на выращивании и откорме птицы – 22,5 млн голов за 2024 год и 15 млн за январь–август 2025 г. Эти миллионы в нашу выручку не переносятся. Они показывают, что учёт тушки ногами остаётся отраслевой дырой, а не частным случаем одного зала.",
    )
    para(
        doc,
        "«Птицезор» закрывает обе цифры камерами сверху. Каждая прикручена и по залу не ездит. Птицу ради веса не ловят. Ради падежа мастер идёт не вдоль всего прохода, а по точкам на плане. Расчёт стоит в тамбуре корпуса: связь на площадке рвётся, видео за территорию не отправляется.",
    )
    para(
        doc,
        "Из тех же следов, без второй системы, видно ещё одно. Если к утру стадо сбилось в одну сторону или почти перестало ходить в тот час, когда вчера ходило, на утреннем экране появляется короткая строка. Наружу она не уходит. Это не диагноз и не замена ветеринарного врача. Это повод проверить вентиляцию, температуру и воду раньше, чем суточный падёж уже вырос.",
    )
    para(
        doc,
        "Дальше программа в работу специалиста не входит. Она не назначает корм, не ставит день убоя и не считает тушку в убойном цехе. Решение остаётся за хозяйством. Меняется только исходная цифра: она есть каждое утро, а не два раза за неделю.",
    )

    heading(doc, "3. Конкретные задачи, на которые нацелена разработка")
    para(
        doc,
        "Задача 1. Утренний список падежа по секции: число и место. Место нужно клеткой плана, чтобы человек дошёл до тушки, а не искал её по залу. Новая точка висит в статусе «ждёт проверки», пока мастер не отметит «падаль» или «живая». Без этой отметки спящую птицу рано или поздно запишут в падёж, и журнал разойдётся с фактом.",
        indent=True,
    )
    para(
        doc,
        "Задача 2. Оценка среднего живого веса за каждые сутки без отлова. На экран выходит медиана по тем головам, которых за день было нормально видно, и норма кросса на этот день жизни. Ориентир по точности – опубликованный опыт с обычной камерой над бройлером: средняя относительная ошибка около 7 % на возрасте примерно от 5 до 35 суток. Точность до грамма на одну голову не заявляется. Моложе пяти суток цифру не показываем: на мелком цыплёнке разброс выше. На последней неделе тура оценка с камеры сверяется контрольным взвешиванием, потому что сдача партии идёт по весам.",
    )
    para(
        doc,
        "Задача 3. Сигнал, что секция ведёт себя не так, как вчера в этот же час. Считается доля птицы, которая почти не двигалась, и доля птицы по частям кадра. Сравнение только с этим залом и этим туром, не с чужой нормой из справочника. Строка на экране короткая, без медицинских слов: «активность ниже обычной для этого часа» или «птица собралась у стены». Порог ставят по первой неделе наблюдения. Если включить строку с первого дня, мастер привыкнет её закрывать.",
    )
    para(
        doc,
        "Задача 4. Счёт на площадке, без отправки видео в интернет. Видео остаётся на компьютере в тамбуре. Сообщение смене лежит на этом же экране. Звонка, письма и сообщения на телефон программа не делает.",
    )

    heading(doc, "4. Алгоритмы")
    para(doc, "4.1. Кадр и масштаб", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "Камера прикручена к конструкции. В работе она не ездит и не поворачивается. Высота примерно 2,5–3,5 м, ось близка к вертикали. Дальше в тексте слово «сдвиг» означает сдвиг птицы внутри кадра, не сдвиг камеры. Если крепление случайно толкнули, рамка плана съезжает и масштаб снимают заново: это поломка юстировки, не способ осмотреть зал. Масштаб берут один раз по мерной планке или по кормушке известной длины. Пиксель переводится в сантиметр и не пересчитывается, пока камера стоит на том же месте. Без этой проверки вес «поплывёт», а точка падежа встанет не в ту клетку плана.",
    )
    para(doc, "4.2. Обнаружение птицы и сопровождение", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "Детектор семейства YOLO дообучается на кадрах того зала, где его повесят: свет, подстилка и плотность там свои. На каждом кадре он ставит рамку на видимую птицу. Сопровождение ByteTrack даёт рамке номер и тянет этот номер за птицей из кадра в кадр. Камера в этот момент стоит. Номер нужен, пока птицу видно. Когда её закрыли соседи, номер пропадает: это не вывод «птица пала», это дырка в следе. Карточку на каждую голову на весь тур не ведём. Рамки теряются и путаются, для среднего веса и для падежа поштучный паспорт не нужен.",
    )
    para(doc, "4.3. Решение о падеже", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "Падёж не ставят за то, что голова долго не ходит. В тёмную паузу так лежит весь зал. Рядом с обычной камерой прикручен тепловизор. Оба смотрят в один прямоугольник пола и совмещены по тем же меткам на полу. Точку и днём, и ночью открывают только если пятно этой головы холоднее медианы соседей в кадре минимум на 4 °C и так держится 10 минут. Спящая остаётся в общем диапазоне стада, тушка остывает. Если холодных сразу много и пол тоже холодный, это сбой тепловизора, точек нет. Если замер весь кадр по движению, это сигнал активности из п. 4.5, не список тушек.",
    )
    para(
        doc,
        "Позу считаем по рамке сверху, отдельную сеть на позу не ставим. Длинная сторона больше короткой в 2 раза и более – «на боку». Отношение меньше 1,8 – птица сидит, точки нет. Между 1,8 и 2 не решаем. Ночью ход не проверяют: зал лежит весь. Ночью хватает позы на боку и холода на 4 °C в течение 10 минут. Днём к этому добавляются ход соседей, смещение центра меньше 5 см за 15 минут и изменение рамки меньше 10 %. Шаг бройлера длиннее 5 см, дыхание короче. Спящая днём поднимает голову, рамка меняется, у тушки нет. Тёплая голова сообщение не получает ни днём, ни ночью.",
    )
    para(
        doc,
        "У кормушки, у поилки и в углу живые закрывают тушку. Слипшиеся рамки в падёж не пишем. Пропавший номер в толпе тоже не падёж: следы рвутся при каждом кормлении. Линию запускают со щита, у поддона никто не дежурит. Если между птицами видно холодное пятно на 4 °C ниже соседей, точку ставят сразу. Если тушку закрыли целиком и пятна нет, клетку смотрят через 15 минут после остановки линии. Под поддоном кормушки пола не видно ни обычной камере, ни тепловизору. Эта маска на плане закрашена и в детектор не входит.",
    )
    para(
        doc,
        "Дальше точка падает на план и остаётся на экране. Мастер нажимает «падаль» или «живая». Оба ответа сохраняются. Если в том же месте за несколько часов запись уже открыта, вторая не создаётся: лежащую тушку нельзя посчитать дважды. В суточный падёж входят только подтверждённые точки. Непроверенные видны отдельно и в журнал до отметки мастера не попадают.",
    )
    para(doc, "4.4. Оценка живой массы", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "В формулу не берётся рамка с края кадра и рамка, которая слиплась с соседней. У остальных берутся ширина, высота и площадь в сантиметрах по п. 4.1 и возраст партии в сутках. Это вход регрессии. На прототипе достаточно линейной модели или полинома небольшой степени. Учить её нужно на весах того кросса, который стоит в этом зале. В разные дни тура взвешивают несколько десятков голов и в тот же день оставляют кадр. Чужой кросс в ту же формулу не подмешивается: в одном возрасте Ross и Cobb по корпусу не совпадают, и чужая кривая даст красивый график мимо факта.",
    )
    para(
        doc,
        "За сутки на экран выводится медиана оценок, не среднее. Среднее тянут в сторону случайные срывы рамки, медиана к этому спокойнее. Рядом показывается нормативная кривая кросса на данный день жизни. Моложе пяти суток оценку веса с камеры не выводим.",
    )
    para(
        doc,
        "Ориентир, от которого считаем цель пилота, опубликован: по видео сверху средняя относительная ошибка оценки массы бройлера около 7 % (опыт с обычной камерой, возраст примерно 5–35 суток; Campbell и соавторы, Smart Agricultural Technology, 2025). Системы с объёмной камерой на последней неделе тура заявляют порядка 50–100 г на голову. После калибровки на своём кроссе медиана секции должна лечь около этих 7 %. Если контрольные весы покажут хуже, в отчёте пилота так и останется. Подтягивать график к желаемой кривой нельзя: мастер тогда смотрит на картинку, а не на стадо.",
    )
    para(doc, "4.5. Активность и размещение по залу", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "За час считается доля голов, у которых центр рамки сместился меньше 5 см, и доля птицы по сетке кадра 3×3. Мельче сетка уже шумит: головы перекрывают друг друга. Строка на экране появляется, если доля замерших выросла больше чем на 15 процентных пунктов против того же часа вчера в этой партии. Первые сутки тура строку копят и как сигнал не поднимают: сравнивать не с чем. На телефон это не уходит.",
    )
    para(doc, "4.6. Сколько голов видно в зонах камер", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "Одна камера видит свой прямоугольник пола, не весь птичник. На секцию ставят несколько камер и стыкуют зоны так, чтобы один и тот же кусок пола не вошёл в две зоны целиком. В каждой зоне считают головы, которых в этот час нормально видно, и складывают зоны. На экран выходят две цифры. Первая – сколько посадили: её берут из журнала при заселении, видео её не придумывает. Вторая – сколько голов видно в зонах камер. Разница между ними – сигнал: слепая зона, перекрытие и падёж, который мастер ещё не подтвердил. Вторую цифру не подписывают «поголовье корпуса» и в акт инвентаризации не ставят. Ошибка счёта по кадрам на плотной посадке около 5 %. На секции 25 000 голов это около 1 000–1 500 голов, поэтому в акт эту цифру не ставят. На учебном ролике посажено 32 и видно 23: так на экране помещается правило, это не секция из расчёта эффекта. Журнал посадки и документы на сдачу партии камера не заменяет.",
    )
    para(doc, "4.7. Что в алгоритм не входит", bold=True, indent=False, justify=False, before=6, after=2, space=1.15)
    para(
        doc,
        "Нет постановки диагноза, нет прогноза цены мяса и нет команды на кормовую линию. Видео не заводит карточки на каждую голову на весь тур и не подменяет инвентаризацию. Весовую платформу, на которую птица заходит сама, не ставим: она меряет только тех, кто на неё встал. Вес в проекте – медиана по рамкам обычной камеры.",
    )

    heading(doc, "5. Применяемые и планируемые технологии")
    para(
        doc,
        "Окно программы уже собрано и открывается на ноутбуке. На показе рамки учебного ролика считаются по контрасту, если файла модели нет, и на экране это написано. Правило падежа от этого не меняется: его проверяют на учебном теплоканале. Железо промышленного исполнения нужно на площадке. Для защиты достаточно этого окна и того же алгоритма.",
        after=4,
    )

    tech = doc.add_table(rows=8, cols=2)
    tech.alignment = WD_TABLE_ALIGNMENT.CENTER
    tech_rows = [
        ("Часть", "Что применяется"),
        ("Съёмка", "Обычная камера и тепловизор 160×120 или выше, оба сверху, высота 2,5–3,5 м, один прямоугольник пола. Для ролика на финал хватает пары, жёстко закреплённой рядом."),
        ("Масштаб", "Мерная планка или кормушка известной длины. Пиксель переводится в сантиметр один раз и держится, пока камера стоит на месте."),
        ("Обнаружение", "YOLO на PyTorch, дообучение на кадрах зала. Открытые ролики бройлерных помещений – только для чернового прототипа."),
        ("Сопровождение", "ByteTrack. Номер следа живёт, пока птица в кадре."),
        ("Падёж и вес", "Падёж: поза на боку и пятно холоднее медианы соседей на 4 °C не меньше 10 минут. В толпе без холодного пятна точку не ставят. Вес: регрессия (scikit-learn) по размеру рамки и возрасту, обучение на весах своего кросса."),
        ("Экран", "Окно на компьютере: Python, OpenCV, FastAPI. Сообщение смене остаётся на этом экране."),
        ("Где считается", "На защите – ноутбук. На площадке – компьютер в тамбуре. Видео за территорию не отправляется."),
    ]
    for r, (a, b) in enumerate(tech_rows):
        fill_cell(
            tech.rows[r].cells[0],
            a,
            bold=True,
            size=11,
            center=False,
            fill="1E3A34" if r == 0 else "F4F1EA",
            color="FFFFFF" if r == 0 else "1C2421",
        )
        fill_cell(
            tech.rows[r].cells[1],
            b,
            bold=(r == 0),
            size=11,
            center=False,
            fill="1E3A34" if r == 0 else None,
            color="FFFFFF" if r == 0 else "1C2421",
        )
        prevent_row_split(tech.rows[r])
    for row in tech.rows:
        row.cells[0].width = Cm(3.6)
        row.cells[1].width = Cm(12.9)

    para(
        doc,
        "Рисунок 1 показывает, как это садится в секцию. Рисунок 2 – утренний экран уже собранного окна. Цифры на снимке учебные, к конкретному хозяйству не относятся.",
        before=8,
    )

    doc.add_picture(str(scheme), width=Cm(16.0))
    last = doc.paragraphs[-1]
    last.alignment = WD_ALIGN_PARAGRAPH.CENTER
    last.paragraph_format.space_before = Pt(4)
    last.paragraph_format.space_after = Pt(0)
    caption(doc, "Рисунок 1 – Две зоны на секцию. В каждой обычная камера и тепловизор на один пол. Красным – точка падежа, она холоднее соседей.")

    doc.add_picture(str(screen), width=Cm(16.0))
    last = doc.paragraphs[-1]
    last.alignment = WD_ALIGN_PARAGRAPH.CENTER
    last.paragraph_format.space_before = Pt(2)
    last.paragraph_format.space_after = Pt(0)
    caption(doc, "Рисунок 2 – Утренний экран программы. Цифры учебного ролика, к конкретному хозяйству не относятся.")

    heading(doc, "6. Как с этим работает мастер корпуса")
    para(
        doc,
        "Утром мастер открывает окно программы. Сообщение смене остаётся на этом экране и наружу не уходит. Он видит точки за ночь, две цифры по головам (посажено по журналу и видно в зонах камер), медиану веса против нормы кросса и строку по активности. Если расхождение по головам выросло, он смотрит сначала точки падежа, а не пересчитывает зал. Непроверенную точку проходит по клетке плана. Если это падаль – отмечает в программе и выносит тушку по обычному порядку хозяйства. Если птица живая – жмёт «живая», и эта точка в суточный падёж не входит. Схему зала разбирает мастер. Камеру включает сотрудник, не мастер.",
    )
    para(
        doc,
        "Раз в неделю на время пилота остаётся обычное контрольное взвешивание. Средний вес выборки мастер вносит в программу рядом с медианой камеры. Так копится расхождение, без которого про точность говорить рано. Отлов ради ежедневного графика не нужен. Отлов ради проверки графика – нужен.",
    )
    para(
        doc,
        "На площадке счёт ставят на компьютер в тамбуре и на две пары камер на одну секцию. Тур ради монтажа не останавливают: камеру крепят в тот санитарный порядок, который на корпусе уже действует. Журнал посадки и весы сдачи партии остаются на хозяйстве. Интернет для счёта не нужен. Площадка на 100 тысяч голов – это несколько секций, и пары камер ставят по секциям, а не одной камерой на весь двор. Мастер разбирает схему и отмечает точки. Сотрудник включает камеру и линию кормления. Мастер камеру не пускает.",
    )

    heading(doc, "7. Экономический эффект и как его проверить")
    para(
        doc,
        "На дату заявки экономия не получена: пилота не было, хозяйство не названо. Ниже счёт, который можно пересчитать. На учебном ролике посажено 32: так видно правило, это не площадка из таблицы. В отчёт строка попадает только против соседней секции того же тура, где учёт не меняли. Соседней секции нет – строка в отчёте ноль.",
    )
    para(
        doc,
        "Почему прежний пример на 820 руб. за тур мал для 20–100 тысяч голов. Там была одна секция, один тур и цена 3 руб. за кг живого веса. Живая тушка в эту цену не помещается. Дальше считаем недополученную выручку с головы, которая до убоя дошла бы, и складываем год. Найденная падаль в выручку не возвращается: в строке только те головы, которых не потеряли дополнительно.",
    )
    para(
        doc,
        "Цена одной сохранённой головы. Живая масса к убою в примере 2,3 кг, выход потрошёной тушки 70 %: 2,3 × 0,7 = 1,61 кг. Цена тушки в примере 7 руб./кг. Это порядок открытой розницы: на дату подготовки заявки тушка цыплёнка-бройлера «Петруха» на витрине стоила 7,09 руб./кг. Хозяйство продаёт дешевле розницы, поэтому 7 руб. – не его касса. В лист пилота ставят свою отпускную цену, и вся таблица пересчитывается одним умножением. 1,61 × 7 = 11,27 руб. с головы.",
    )
    para(
        doc,
        "Срез, на который претендует программа. Если против соседней секции падёж за тур ниже на 0,3–0,5 процентного пункта, середина вилки 0,4. Головы = поголовье × 0,004. Деньги за тур = головы × 11,27 руб. Год = тур × 6, если санитарный разрыв пускает шесть туров. Чужой календарь за свой не выдаём: шесть – условие примера, его заменяют графиком площадки.",
    )

    money = doc.add_table(rows=4, cols=5)
    money.alignment = WD_TABLE_ALIGNMENT.CENTER
    money_rows = [
        ("Поголовье", "−0,4 п.п., голов", "За тур, руб.", "За год, 6 туров", "Вилка 0,3–0,5 п.п. за год"),
        ("20 000", "80", "901,60", "5 409,60", "4 057,20–6 762"),
        ("50 000", "200", "2 254", "13 524", "10 143–16 905"),
        ("100 000", "400", "4 508", "27 048", "20 286–33 810"),
    ]
    for r, row in enumerate(money_rows):
        for c, value in enumerate(row):
            fill_cell(
                money.rows[r].cells[c],
                value,
                bold=(r == 0),
                size=10,
                fill="1E3A34" if r == 0 else "F4F1EA",
                color="FFFFFF" if r == 0 else "1C2421",
            )
        prevent_row_split(money.rows[r])
    for row in money.rows:
        for cell, width in zip(row.cells, (Cm(3.0), Cm(3.4), Cm(2.8), Cm(3.2), Cm(4.6))):
            cell.width = width
    para(
        doc,
        "Таблица. Недополученная выручка, если падёж ниже на 0,4 процентного пункта. Проверка строки 100 000: 100 000 × 0,004 = 400 голов; 400 × 11,27 = 4 508 руб. за тур; 4 508 × 6 = 27 048 руб. за год. Края вилки: 300 × 11,27 × 6 = 20 286 руб. и 500 × 11,27 × 6 = 33 810 руб.",
        before=4,
        after=4,
    )
    para(
        doc,
        "Масштаб самой проблемы шире среза. Если падёж тура около 4 % (это масштаб для счёта, не замер названного хозяйства), на 100 000 голов это 4 000 голов за тур: 4 000 × 11,27 = 45 080 руб., за шесть туров 270 480 руб. недополученной выручки. Срез 0,4 процентного пункта – ровно десятая часть этих 4 %. Программа не забирает весь падёж площадки. Она претендует на эту десятую и только там, где соседняя секция это подтвердила.",
    )
    para(
        doc,
        "На 20 000 голов тот же падёж 4 % – это 800 голов за тур и 54 096 руб. за год. Середина среза на этом поголовье – 5 409,60 руб. в год, не 820 руб. за один тур.",
    )
    para(
        doc,
        "Обход порядка не меняет. Если проход по точкам короче обхода зала на 20 минут в сутки, за 40 суток это 800 минут, 13,3 часа. При ставке 10 руб. в час выходит около 130 руб. за тур с секции. Минуты пишут в лист одни и те же люди, несколько дней по-старому и несколько дней по плану. На четырёх секциях площадки в 100 000 голов это около 3 тыс. руб. в год. Рядом с 27 тыс. руб. от падежа строка обхода остаётся добавкой, и в таблицу она не подмешана: минуты ещё не замерены.",
    )
    para(
        doc,
        "Вес в рубли не переводим. Медиана есть каждое утро, ошибка отдельного дня около 7 % годится как ориентир серии дней. День сдачи партии этой ошибкой не сдвигают. Документы сдачи остаются на весах.",
    )
    para(
        doc,
        "Окупаемость. Срок = цена комплекта на секцию / эффект года одной секции. На 25 000 голов середина среза близка к строке 20 000, то есть около 5,4 тыс. руб. в год с секции. Цену двух пар камер и компьютера в тамбуре в заявке не подставляем: её даёт поставка, не алгоритм. Пока цены нет, срок в месяцах не называем.",
    )
    para(
        doc,
        "Порядок проверки: одна секция против соседней, две пары камер, две недели рядом со старым обходом, контрольное взвешивание не реже раза в неделю. В конце три числа, и только они заменяют таблицу. Первое – доля сигналов, которые мастер подтвердил как падаль. Второе – среднее расхождение медианы с контрольными весами. Третье – минуты обхода с планом и без плана. Цену тушки в лист ставит хозяйство.",
    )

    heading(doc, "8. Что будет готово к финалу")
    para(
        doc,
        "Финал очный, 13 ноября 2026 г., г. Речица, ДКиТ «Нефтяник». Заявка и презентация направляются на marafon@beloil.by до 30 сентября 2026 г.",
    )
    para(
        doc,
        "На защиту выносится разработанное приложение, не установка в хозяйстве. Окно уже собрано: роли мастера и сотрудника, утренний экран с графиками этого разбора, схема зала по чертежу, демо-ролик с правилом падежа, локальные камеры без отправки видео наружу. На показе 13 ноября открывается это окно. Что проверяется только на площадке, сказано отдельно: подтверждение мастером на живой птице, расхождение с контрольными весами, время обхода.",
    )
    para(
        doc,
        "Готового кейса хозяйства нет: пилот не проводился, полученной экономии нет. Расчёт примера – в разделе 7: на 100 000 голов середина среза даёт 27 048 руб. за год, вилка 20 286–33 810 руб. Ссылка на ресурс с содержательной частью проекта и инструкцией пользователя: https://github.com/RoomzR/pticezor. Тот же адрес записан отдельным документом на ноутбуке.",
        before=2,
    )

    heading(doc, "9. Ответы до вопроса эксперта")
    para(
        doc,
        "Почему в акте нет полученной экономии. Пилота не было. Пример на 100 000 голов и шесть туров: 400 × 11,27 × 6 = 27 048 руб. в середине вилки. В отчёт строка попадает только против соседней секции того же тура.",
    )
    para(
        doc,
        "Почему это не 820 руб. Прежний пример брал одну секцию, один тур и 3 руб. за кг живого веса. На 20–100 тысяч голов и шести турах середина среза – 5 409,60–27 048 руб. в год. 820 руб. этот масштаб не описывают.",
    )
    para(
        doc,
        "Откуда 0,4 процентного пункта. Это середина вилки 0,3–0,5. На 100 000 голов края – 300 и 500 голов за тур, за год 20 286 и 33 810 руб. Если падёж тура около 4 %, этот срез – десятая часть потери, не весь падёж.",
    )
    para(
        doc,
        "Откуда 7 %. Это опубликованный ориентир опыта с обычной камерой, не замер этого хозяйства. Свой замер – второе число проверки, расхождение с контрольными весами.",
    )
    para(
        doc,
        "Почему в окне 32 и 23, а в таблице 20–100 тысяч. 32 и 23 – учебный ролик для проверки правила. 20–100 тысяч – поголовье площадки в счёте эффекта. Одно другим не подменяется.",
    )
    para(
        doc,
        "Почему камера не называет поголовье корпуса. Она видит свою зону. Разница «посажено − видно» – сигнал смотреть зоны. Ошибка счёта на плотной посадке порядка 5 %, на 25 000 голов это 1 000–1 500 голов. В инвентаризацию цифра не ставится.",
    )
    para(
        doc,
        "Почему ночью не все лежащие – падёж. Ночью зал лежит. Точку открывают поза на боку и холод на 4 °C ниже соседей в течение 10 минут. Тёплая голова в падёж не идёт. Много холодных пятен и холодный пол – сбой тепловизора, не список тушек.",
    )
    para(
        doc,
        "Куда уходит видео и кто пускает камеру. Видео остаётся на компьютере. Строка смене на экране. Телефон, почта и облако не вызываются. Камеру включает сотрудник и только после отметки, что это камера этого компьютера. Мастер камеру не пускает: он отмечает точки и разбирает схему. Схему сотрудник не разбирает.",
    )
    para(
        doc,
        "Как внедрять, не останавливая тур. Две пары камер на секцию и компьютер в тамбуре, в тот санитарный порядок, который на корпусе уже есть. Журнал посадки и весы сдачи партии не меняются. Интернет для счёта не нужен. Диагноз, корм и день убоя в программу не входят.",
    )

    out = ROOT / "Заявка_Птицезор.docx"
    doc.save(out)
    return out


# ---------- presentation ----------

def rgb(hex_color):
    return PColor.from_string(hex_color)


def set_run(run, text, size, bold=False, color=INK, font_name="Arial", italic=False):
    run.text = text
    run.font.size = PPt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = rgb(color)
    run.font.name = font_name


def add_box(slide, l, t, w, h, text, size=18, bold=False, color=INK, align="left",
            anchor=MSO_ANCHOR.TOP, italic=False):
    shape = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    try:
        tf._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}[anchor])
    except Exception:
        pass
    p = tf.paragraphs[0]
    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
    p.space_before = PPt(0)
    p.space_after = PPt(0)
    run = p.add_run()
    set_run(run, text, size, bold, color, italic=italic)
    return shape


def add_lines(slide, l, t, w, h, lines, size=18, color=INK, align="left", spacing=8, bold=False):
    """lines: list of strings or (text, bold, size, color)."""
    shape = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
    tf.margin_top = Inches(0.0)
    tf.margin_bottom = Inches(0.0)
    for i, item in enumerate(lines):
        if isinstance(item, str):
            text, b, sz, col = item, bold, size, color
        else:
            text = item[0]
            b = item[1] if len(item) > 1 else bold
            sz = item[2] if len(item) > 2 else size
            col = item[3] if len(item) > 3 else color
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER}[align]
        p.space_before = PPt(0)
        p.space_after = PPt(spacing)
        run = p.add_run()
        set_run(run, text, sz, b, col)
    return shape


def rect(slide, l, t, w, h, fill, line=None, radius=None):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(shape_type, Inches(l), Inches(t), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = rgb(line)
        sh.line.width = PPt(1)
    if radius:
        # smaller corner
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
    sh.shadow.inherit = False
    return sh


def bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(color)


def content_chrome(slide, title, num):
    bg(slide, PAPER)
    rect(slide, 0, 0, 13.333, 0.12, GREEN)
    add_box(slide, 0.48, 0.28, 11.2, 0.62, title, size=30, bold=True, color=INK)
    rect(slide, 0.50, 0.98, 1.35, 0.055, RUST)
    rect(slide, 0.48, 7.18, 12.38, 0.01, LINE)
    add_box(slide, 0.48, 7.20, 8.5, 0.28, "Птицезор  ·  сельское хозяйство  ·  «Код Будущего»", size=11, color=MUTED)
    add_box(slide, 11.3, 7.20, 1.5, 0.28, f"{num}  /  10", size=11, color=MUTED, align="right")


def build_pptx(scheme, screen):
    prs = Presentation()
    prs.slide_width = Inches(13.333333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = "Птицезор. Презентация"
    prs.core_properties.author = ""
    prs.core_properties.subject = "Хакатон «Код Будущего»"
    blank = prs.slide_layouts[6]

    # TITLE
    s = prs.slides.add_slide(blank)
    bg(s, GREEN)
    rect(s, 0, 0, 0.18, 7.5, RUST)
    add_box(s, 0.7, 0.85, 11.5, 0.4, "ХАКАТОН «КОД БУДУЩЕГО»", size=16, bold=True, color="D5E0DA")
    add_box(s, 0.68, 1.7, 12, 1.3, "Птицезор", size=72, bold=True, color="F3F0E8")
    add_box(s, 0.7, 3.15, 11, 0.9, "Видеоучёт падежа и среднего привеса\nв птичнике с бройлером", size=26, color="F3F0E8")
    rect(s, 0.72, 4.35, 2.1, 0.045, RUST)
    add_lines(
        s, 0.7, 4.6, 10, 1.8,
        [
            "Номинация: сельское хозяйство",
            "Стартап-проект, программный продукт",
            "Финал: 13 ноября 2026 г., Речица, ДКиТ «Нефтяник»",
        ],
        size=18,
        color="D5E0DA",
        spacing=6,
    )

    # 1
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Две цифры, которые до сих пор берут руками", 1)
    rect(s, 0.48, 1.35, 6.05, 4.35, CARD, LINE, 0.08)
    rect(s, 6.75, 1.35, 6.1, 4.35, CARD, LINE, 0.08)
    add_box(s, 0.72, 1.52, 5.5, 0.45, "Падёж", size=24, bold=True, color=GREEN)
    add_lines(
        s, 0.72, 2.15, 5.5, 3.2,
        [
            "Тушку ищут обходом зала.",
            "В журнале остаётся число.",
            "Место на плане чаще всего не пишут.",
            "Часть голов находят только следующим проходом.",
        ],
        size=18,
        spacing=10,
    )
    add_box(s, 7.0, 1.52, 5.5, 0.45, "Живой вес", size=24, bold=True, color=GREEN)
    add_lines(
        s, 7.0, 2.15, 5.5, 3.2,
        [
            "Ловят несколько десятков голов.",
            "Так делают раз или два в неделю.",
            "Между взвешиваниями график пустой.",
            "В руки чаще попадает птица, которую проще поймать.",
        ],
        size=18,
        spacing=10,
    )
    add_box(s, 0.5, 5.85, 12.3, 1.15, "На площадке 20–100 тыс. голов падёж тура в единицы процентов – это тысячи голов. Камера ставит место тушки на план и даёт сигнал раньше. Весь падёж страны она на себя не берёт.", size=16, color=INK)

    # 2
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Что мастер видит утром", 2)
    items = [
        ("01", "Точки падежа", "Сколько их за ночь и в какой клетке плана. Пока мастер не нажмёт «падаль» или «живая», точка в журнал не пишется."),
        ("02", "Две цифры по головам", "Посажено по журналу и сколько видно в зонах камер. Разница – сигнал. Подписью «поголовье корпуса» видео не называем и в инвентаризацию не ставим."),
        ("03", "Средний вес", "Медиана по головам, которых было нормально видно, и отклонение от кривой кросса на этот день жизни."),
        ("04", "Активность", "Секция села или сбилась к стене относительно вчерашнего того же часа. Повод проверить воздух и воду, не диагноз."),
    ]
    for i, (n, title, body) in enumerate(items):
        y = 1.22 + i * 1.38
        rect(s, 0.48, y, 12.35, 1.28, CARD, LINE, 0.06)
        add_box(s, 0.7, y + 0.28, 1.0, 0.55, n, size=24, bold=True, color=RUST)
        add_box(s, 1.85, y + 0.16, 10.6, 0.4, title, size=20, bold=True, color=GREEN)
        add_box(s, 1.85, y + 0.58, 10.6, 0.6, body, size=15, color=INK)
    add_box(s, 0.5, 6.78, 12.3, 0.35, "Одна камера видит свой прямоугольник пола. Зал закрывают несколько зон. Счёт идёт в тамбуре, видео наружу не уходит.", size=14, color=MUTED)

    # 3
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Задачи, на которые нацелена разработка", 3)
    tasks = [
        ("1", "Суточный падёж", "Число и место на плане. Каждую точку мастер подтверждает."),
        ("2", "Вес без отлова", "Медиана за сутки. Цель пилота – ошибка около 7 %. До грамма не обещаем."),
        ("3", "Сигнал по залу", "Доля замерших голов выросла больше чем на 15 п.п. к тому же часу вчера."),
        ("4", "Счёт на месте", "Видео остаётся на компьютере. Сообщение смене – на том же экране."),
    ]
    for i, (n, title, body) in enumerate(tasks):
        col = i % 2
        row = i // 2
        x = 0.48 + col * 6.4
        y = 1.4 + row * 2.55
        rect(s, x, y, 6.15, 2.35, CARD, LINE, 0.08)
        add_box(s, x + 0.25, y + 0.25, 1.0, 0.6, n, size=32, bold=True, color=RUST)
        add_box(s, x + 1.2, y + 0.32, 4.6, 0.5, title, size=22, bold=True, color=GREEN)
        add_box(s, x + 0.28, y + 1.1, 5.6, 1.0, body, size=16, color=INK)

    # 4
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Алгоритм падежа", 4)
    steps = [
        ("1", "Камера стоит", "Прикручена и смотрит вниз. По залу не ездит. Сдвиг в алгоритме – это птица."),
        ("2", "След птицы", "YOLO ставит рамку. Номер идёт за птицей. Камера при этом не движется."),
        ("3", "Когда это падёж", "Поза на боку и пятно холоднее соседей на 4 °C десять минут. Спящая тёплая."),
        ("4", "Толпа", "Холодное пятно видно – точку ставят. Закрыли целиком – смотрят через 15 минут."),
    ]
    for i, (n, title, body) in enumerate(steps):
        x = 0.4 + i * 3.22
        rect(s, x, 1.45, 3.05, 3.35, CARD, LINE, 0.08)
        add_box(s, x + 0.18, 1.62, 2.6, 0.55, n, size=28, bold=True, color=RUST)
        add_box(s, x + 0.18, 2.3, 2.7, 0.8, title, size=20, bold=True, color=GREEN)
        add_box(s, x + 0.18, 3.2, 2.7, 1.3, body, size=15, color=INK)
    rect(s, 0.48, 5.1, 12.35, 1.75, "F4E4DC", None, 0.06)
    add_box(s, 0.75, 5.28, 11.9, 0.38, "Тепловизор", size=18, bold=True, color=RUST)
    add_box(s, 0.75, 5.72, 11.9, 0.95, "Ночью зал лежит, но спит тёплым. Точку ставит холод на 4 °C ниже соседей, и так не меньше 10 минут. Тёплая голова в падёж не идёт ни днём, ни ночью.", size=16, color=INK)

    # 5
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Алгоритм оценки веса", 5)
    left_steps = [
        "В расчёт не берём край кадра и рамки, слипшиеся с соседом.",
        "Ширина, высота и площадь переводятся в сантиметры по мерке на полу.",
        "К размеру добавляется возраст партии в сутках.",
        "Регрессия учится на контрольных весах этого кросса, не чужого.",
        "На экран выходит медиана секции за сутки.",
    ]
    rect(s, 0.48, 1.35, 7.55, 5.45, CARD, LINE, 0.08)
    add_box(s, 0.72, 1.52, 7.0, 0.4, "Как получается цифра", size=20, bold=True, color=GREEN)
    add_lines(s, 0.72, 2.15, 7.0, 4.3, [f"{i}.  {t}" for i, t in enumerate(left_steps, 1)], size=16, spacing=12)

    rect(s, 8.25, 1.35, 4.6, 5.45, GREEN, None, 0.08)
    add_lines(
        s, 8.5, 1.6, 4.15, 4.9,
        [
            ("Ориентир пилота", True, 18, "F3F0E8"),
            ("около 7 %", True, 32, "F3F0E8"),
            ("средней относительной ошибки. Так выходило в опыте с обычной камерой, возраст 5–35 суток.", False, 15, "D5E0DA"),
            ("Моложе 5 суток цифру не показываем.", False, 15, "F3F0E8"),
            ("На последней неделе сверяем обычными весами. Сдача партии идёт по ним.", False, 15, "F3F0E8"),
        ],
        spacing=10,
    )

    # 6
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Из чего состоит комплекс", 6)
    rect(s, 0.48, 1.32, 6.35, 5.5, CARD, LINE, 0.06)
    rows = [
        ("Камеры", "Обычная и тепловизор, сверху, 2,5–3,5 м"),
        ("Масштаб", "Планка или кормушка известной длины"),
        ("Детектор", "YOLO, дообучение на этом зале"),
        ("След", "ByteTrack"),
        ("Вес", "Регрессия: размер рамки и сутки"),
        ("Экран", "Python, OpenCV, FastAPI"),
        ("Где считается", "Компьютер в тамбуре"),
    ]
    for i, (k, v) in enumerate(rows):
        y = 1.48 + i * 0.72
        add_box(s, 0.7, y, 2.15, 0.45, k, size=15, bold=True, color=GREEN)
        add_box(s, 2.85, y, 3.7, 0.55, v, size=15, color=INK)
    with Image.open(scheme) as scheme_im:
        scheme_aspect = scheme_im.width / scheme_im.height
    scheme_w = 5.85
    scheme_h = scheme_w / scheme_aspect
    if scheme_h > 3.55:
        scheme_h = 3.55
        scheme_w = scheme_h * scheme_aspect
    s.shapes.add_picture(str(scheme), Inches(7.05), Inches(1.32), Inches(scheme_w), Inches(scheme_h))
    add_box(
        s, 7.05, 1.42 + scheme_h, 5.85, 1.5,
        "Две зоны. В каждой обычная камера и тепловизор. Красным отмечена точка холоднее соседей. Рисунок условный, это не снимок корпуса.",
        size=14, color=MUTED,
    )

    # 7
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Утренний экран программы", 7)
    with Image.open(screen) as screen_im:
        screen_aspect = screen_im.width / screen_im.height
    img_h = 5.05
    img_w = img_h * screen_aspect
    if img_w > 12.4:
        img_w = 12.4
        img_h = img_w / screen_aspect
    img_l = (13.333 - img_w) / 2
    s.shapes.add_picture(str(screen), Inches(img_l), Inches(1.22), Inches(img_w), Inches(img_h))
    add_box(s, 0.48, 6.5, 12.35, 0.55, "Снимок окна. Цифры учебного ролика. «Видно в зонах камер» – не инвентаризация корпуса.", size=14, color=MUTED)

    # 8
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Экономический эффект", 8)
    add_box(s, 0.5, 1.16, 12.3, 0.48, "Середина среза −0,4 п.п., шесть туров. На ролике посажено 32 – это другое.", size=18, bold=True, color=GREEN)
    money = [
        ("5,4 тыс.", "20 000 голов", "80 голов за тур × 11,27 руб. × 6 = 5 409,60 руб. в год."),
        ("13,5 тыс.", "50 000 голов", "200 × 11,27 × 6 = 13 524 руб. в год."),
        ("27 тыс.", "100 000 голов", "400 × 11,27 × 6 = 27 048 руб. Вилка 20–34 тыс."),
    ]
    for i, (n, t, b) in enumerate(money):
        x = 0.48 + i * 4.2
        rect(s, x, 1.78, 4.0, 2.85, CARD, LINE, 0.08)
        add_box(s, x + 0.2, 1.92, 3.6, 0.55, n, size=28, bold=True, color=RUST)
        add_box(s, x + 0.2, 2.52, 3.6, 0.4, t, size=18, bold=True, color=GREEN)
        add_box(s, x + 0.2, 3.05, 3.6, 1.3, b, size=15, color=INK)
    add_box(
        s, 0.5, 4.8, 12.3, 1.95,
        "Голова в примере: 2,3 кг × 70 % × 7 руб./кг тушки = 11,27 руб. 7 руб. – порядок розницы (тушка «Петруха» 7,09 руб./кг), не отпускная цена хозяйства. На 100 тыс. голов падёж 4 % за тур – это уже около 270 тыс. руб. в год. Срез 0,4 п.п. – десятая часть, 27 тыс. Найденная тушка в выручку не возвращается. Без соседней секции строка ноль. Вес в рубли не входит. На дату заявки сумма не получена.",
        size=15,
    )

    # 9
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Что показываем 13 ноября", 9)
    rect(s, 0.48, 1.35, 6.15, 5.4, CARD, LINE, 0.08)
    rect(s, 6.85, 1.35, 6.0, 5.4, "F4E4DC", None, 0.08)
    add_box(s, 0.72, 1.55, 5.6, 0.45, "Будет на защите", size=22, bold=True, color=GREEN)
    add_lines(
        s, 0.75, 2.25, 5.6, 4.0,
        [
            "Окно уже открывается: утро, схема, демо, обход.",
            "Ролик: рамки на птице и точки, которые ждут мастера.",
            "Графики этого разбора и лист сводки на компьютере.",
            "Ссылка на описание и инструкцию – в заявке и на ноутбуке.",
        ],
        size=16,
        spacing=12,
    )
    add_box(s, 7.1, 1.55, 5.5, 0.45, "На дату заявки этого нет", size=22, bold=True, color=RUST)
    add_lines(
        s, 7.1, 2.25, 5.5, 4.0,
        [
            "Установки в хозяйстве.",
            "Полученной суммы. 27 тыс. руб. в год на 100 тыс. голов – пример, не касса.",
            "Обещания диагностировать болезнь или управлять кормом.",
            "Отправки видео с корпуса в сеть.",
        ],
        size=16,
        spacing=12,
    )

    # 10
    s = prs.slides.add_slide(blank)
    content_chrome(s, "Сроки", 10)
    timeline = [
        ("30 сентября\n2026", "Заявка, презентация и ссылка на программу"),
        ("Уже есть", "Окно: демо, утро, схема зала, роли"),
        ("До 13 ноября", "Прогон показа и лист: что только на площадке"),
        ("13 ноября\n2026", "Очная защита, Речица, ДКиТ «Нефтяник»"),
    ]
    for i, (when, what) in enumerate(timeline):
        x = 0.45 + i * 3.22
        rect(s, x, 2.0, 3.05, 3.5, CARD, LINE, 0.08)
        rect(s, x, 2.0, 3.05, 0.12, RUST if i in (0, 3) else GREEN)
        add_box(s, x + 0.18, 2.3, 2.7, 1.15, when, size=20, bold=True, color=GREEN)
        add_box(s, x + 0.18, 3.55, 2.7, 1.6, what, size=15, color=INK)
    add_box(s, 0.5, 5.8, 12.3, 1.1, "Приложение уже открывается на защите. На площадку – две пары камер и компьютер в тамбуре, тур не останавливая. Видео наружу не уходит.", size=16)

    # CLOSING
    s = prs.slides.add_slide(blank)
    bg(s, GREEN)
    rect(s, 0, 0, 0.18, 7.5, RUST)
    add_box(s, 0.7, 0.7, 11, 0.8, "Птицезор", size=48, bold=True, color="F3F0E8")
    add_box(s, 0.7, 1.6, 11, 0.5, "Спасибо за внимание", size=24, color="D5E0DA")
    rect(s, 0.72, 2.3, 2.1, 0.045, RUST)
    add_box(s, 0.7, 2.55, 11, 0.4, "Состав команды заполняется перед отправкой", size=16, color="D5E0DA")
    for i in range(4):
        add_box(s, 0.7, 3.15 + i * 0.55, 8, 0.45, f"{i + 1}.   _______________________________________", size=18, color="F3F0E8")
    add_box(s, 0.7, 5.5, 11, 0.8, "Контакт команды: телефон ____________________    почта rudenbelstad@gmail.com", size=16, color="D5E0DA")
    add_box(s, 0.7, 6.5, 11, 0.4, "Номинация «Сельское хозяйство»  ·  финал 13 ноября 2026 г., Речица", size=14, color="A8BDB4")

    out = ROOT / "Презентация_Птицезор.pptx"
    prs.save(out)
    return out


def build_link_docx():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    core = doc.core_properties
    core.title = "Ссылка на ресурс. Проект «Птицезор»"
    core.author = ""
    para(doc, "ХАКАТОН «КОД БУДУЩЕГО»", size=12, bold=True, center=True, before=0, after=0, space=1.0, color="1E3A34")
    para(doc, "ССЫЛКА НА РЕСУРС", size=16, bold=True, center=True, before=2, after=6, space=1.0)
    para(
        doc,
        "Проект «Птицезор». Номинация: сельское хозяйство.",
        size=13,
        center=True,
        before=0,
        after=8,
    )
    para(
        doc,
        "Ресурс в глобальной сети, где лежат содержательная часть проекта и инструкция пользователя:",
    )
    para(doc, "https://github.com/RoomzR/pticezor", bold=True, before=2, after=6)
    para(
        doc,
        "На странице: что делает программа, роли мастера и сотрудника, правило падежа, схема зала, графики этого разбора, снимки всех экранов и пошаговая инструкция. Видео с компьютера на этот ресурс не отправляется.",
    )
    para(
        doc,
        "Расчёт эффекта приведён в заявке и на странице проекта. На 100 000 голов середина среза в примере даёт 27 048 руб. за год, вилка 20 286–33 810 руб. Это арифметика, не полученная сумма: пилот не проводился. Адрес страницы – https://github.com/RoomzR/pticezor.",
        before=2,
    )
    out = ROOT / "Ссылка_на_ресурс_Птицезор.docx"
    doc.save(out)
    return out


def main():
    scheme = draw_scheme()
    live = IMG / "screen-live.png"
    screen = live if live.exists() else draw_screen()
    docx = build_docx(scheme, screen)
    pptx = build_pptx(scheme, screen)
    link = build_link_docx()
    print(docx)
    print(pptx)
    print(link)
    print("slides", 12)


if __name__ == "__main__":
    main()
