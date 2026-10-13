# -*- coding: utf-8 -*-
"""
pages/approval_mock.py — «Утверждение (макет)»: как будет выглядеть путь
«подготовил → утвердил → отправил» для правок листингов.

МАКЕТ (14.10.2026, «пока нарисуй, подключим потом»). Здесь нет ни одного запроса
к базе и ни одного вызова Amazon: данные — примерные, зашиты ниже; все кнопки
неактивны. Страница видна только администраторам (право `ls.admin`) — пункт меню
добавляет app.py, а на случай прямой ссылки проверка стоит и здесь.

Сегодня роль «Утверждающий» означает только право отправить заголовок в Amazon
из карточки «Синтеза» и править «Методологию»: очереди, статуса «утверждено»,
возврата и отклонения нет. Этот макет — то, к чему роль должна прийти.
"""
from __future__ import annotations

import difflib
import html

import pandas as pd
import streamlit as st

import auth
from components.ui import inject_fonts, eyebrow
from i18n import t

inject_fonts()

if not auth.can("ls.admin"):
    st.error(t("auth.denied"))
    st.stop()

INK, MUTED, BORDER, CARD = "#1A1815", "#57534A", "#E7E4DD", "#FFFFFF"
ADD_BG, ADD_FG = "#DCEEE0", "#2F6B3A"
DEL_BG, DEL_FG = "#F8DEDB", "#9B2C1F"
MONO = "var(--ls-mono)"

st.title(t("approval.title"))
st.warning(t("approval.mock_banner"))

# ── примерные данные: наши ASIN, текущий заголовок с витрины; «стало», оценки и журнал — выдуманы ──
CM, AP = "cm.example@dniprom.com", "approver.example@dniprom.com"
ITEMS = [
    dict(asin="B0DY7VKKBM", mk="DE", what="title", status="pending",
         before="CD-200BC Ultra Akku-Bohrschrauber, 20 V (60 Nm, 2 Geschwindigkeiten, 0-1700 U/min, bürstenlos), "
                "Elektro-Schraubendreher, 1 Akku mit 2 Ah, Ladegerät",
         after="Dnipro-M Akku-Bohrschrauber 20V Brushless CD-200BC Ultra, 60 Nm, 2 Gänge, 0-1700 U/min, "
               "inkl. 2-Ah-Akku und Ladegerät",
         score=(64, 83), prepared=(CM, "13.10 16:42"), log=[]),
    dict(asin="B0GYQ67M83", mk="IT", what="title", status="pending",
         before="Dnipro-M Trapano Avvitatore 20V Brushless 60Nm 2 Velocità 21 Posizioni Kit Completo Batteria 4Ah + "
                "Valigetta | CD-202BC ULTRA",
         after="Dnipro-M Trapano Avvitatore a Batteria 20V Brushless CD-202BC ULTRA, 60 Nm, 2 Velocità, 21+1 Posizioni, "
               "Batteria 4Ah, Caricatore e Valigetta",
         score=(71, 86), prepared=(CM, "13.10 15:10"), log=[]),
    dict(asin="B0DY7TZMTF", mk="IT", what="bullets", status="returned",
         before="Livello laser autolivellante Dnipro-M ML-320G verde, precisione ±0,3 mm/m, portata 20 m",
         after="Livello laser verde autolivellante Dnipro-M ML-320G: precisione ±0,3 mm/m e portata fino a 20 m",
         score=(58, 66), prepared=(CM, "12.10 11:05"),
         log=[(AP, "12.10 17:20", "returned", "approval.example_comment")]),
    dict(asin="B0H26T2BLX", mk="IT", what="title", status="sent",
         before="Dnipro-M Smerigliatrice Angolare 20V Senza Batteria | 8.000 rpm · 115-125mm · BP-220~25min / "
                "BP-240~50min / BP-260~75min · Taglio Metallo Pietra Ceramica | DGA-201M",
         after="Dnipro-M Smerigliatrice Angolare a Batteria 20V DGA-201M, 8000 giri/min, Disco 115-125 mm, "
               "per Metallo, Pietra e Ceramica (Batteria non inclusa)",
         score=(55, 84), prepared=(CM, "11.10 10:30"),
         log=[(AP, "11.10 14:02", "approved", ""), (AP, "11.10 14:03", "sent", "")]),
    dict(asin="B0HF4RY2QC", mk="ES", what="title", status="accepted",
         before="Disco de Lija Autoadherente Dnipro-M P240 125 mm, Pack de 10 Unidades Grano 240 para acabado final "
                "antes de pintar │ 8 orificios de extracción de polvo │ Base de papel reforzada 160 g/m²",
         after="Dnipro-M Discos de Lija Autoadherentes 125 mm Grano P240, Pack de 10, 8 Agujeros de Aspiración, "
               "Base de Papel Reforzado 160 g/m²",
         score=(61, 88), prepared=(CM, "10.10 09:15"),
         log=[(AP, "10.10 12:40", "approved", ""), (AP, "10.10 12:41", "sent", ""),
              ("Amazon", "10.10 12:58", "accepted", "")]),
]
STATUS_ORDER = ["pending", "returned", "ready", "sent", "accepted", "error"]
STATUS_COLOR = {"pending": "#E8590C", "returned": "#B7791F", "ready": "#2B6CB0", "sent": "#2B6CB0",
                "accepted": "#2F6B3A", "error": "#9B2C1F", "rejected": "#57534A"}


def chip(status: str) -> str:
    c = STATUS_COLOR.get(status, MUTED)
    return (f'<span style="border:1px solid {c};color:{c};border-radius:999px;padding:1px 10px;'
            f'font-size:12px;font-weight:600;">{html.escape(t("approval.st." + status))}</span>')


# ── очередь ──
st.markdown(eyebrow(t("approval.queue")), unsafe_allow_html=True)
вид = st.segmented_control(t("approval.filter"), ["all"] + STATUS_ORDER, default="all",
                           format_func=lambda s: t("approval.st." + s) if s != "all" else t("approval.all"),
                           key="appr_filter") or "all"
очередь = [i for i in ITEMS if вид == "all" or i["status"] == вид]
таблица = pd.DataFrame([{
    t("approval.col.asin"): i["asin"],
    t("approval.col.mk"): i["mk"],
    t("approval.col.what"): t("approval.what." + i["what"]),
    t("approval.col.prepared_by"): i["prepared"][0],
    t("approval.col.when"): i["prepared"][1],
    t("approval.col.status"): t("approval.st." + i["status"]),
} for i in очередь])
if таблица.empty:
    st.caption(t("approval.empty"))
    st.stop()
st.dataframe(таблица, hide_index=True, width="stretch")

выбор = st.selectbox(t("approval.pick"), range(len(очередь)),
                     format_func=lambda k: f'{очередь[k]["asin"]} · {очередь[k]["mk"]} · '
                                           f'{t("approval.st." + очередь[k]["status"])}',
                     key="appr_pick")
item = очередь[выбор]

# ── карточка «было → стало» ──
st.markdown(eyebrow(t("approval.card")), unsafe_allow_html=True)


def diff_html(a: str, b: str) -> tuple[str, str]:
    """Разница по словам: убранное — красным зачёркнутым в «было», добавленное — зелёным в «стало»."""
    wa, wb = a.split(), b.split()
    left, right = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=wa, b=wb, autojunk=False).get_opcodes():
        ea, eb = html.escape(" ".join(wa[i1:i2])), html.escape(" ".join(wb[j1:j2]))
        if op == "equal":
            left.append(ea); right.append(eb)
        if op in ("delete", "replace") and ea:
            left.append(f'<span style="background:{DEL_BG};color:{DEL_FG};text-decoration:line-through;">{ea}</span>')
        if op in ("insert", "replace") and eb:
            right.append(f'<span style="background:{ADD_BG};color:{ADD_FG};font-weight:600;">{eb}</span>')
    return " ".join(left), " ".join(right)


было, стало = diff_html(item["before"], item["after"])
s0, s1 = item["score"]
шапка = (f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
         f'<div style="font-family:{MONO};font-size:13px;color:{MUTED};">{item["asin"]} · {item["mk"]} · '
         f'{html.escape(t("approval.what." + item["what"]))}</div>{chip(item["status"])}</div>')


def блок(подпись: str, тело: str, n: int) -> str:
    return (f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;'
            f'margin-bottom:8px;"><div style="font-size:11px;font-weight:700;color:{MUTED};letter-spacing:.06em;'
            f'text-transform:uppercase;margin-bottom:4px;">{html.escape(подпись)} · '
            f'<span style="font-family:{MONO};">{n}/200</span></div>'
            f'<div style="font-size:14px;color:{INK};line-height:1.55;">{тело}</div></div>')


st.markdown(шапка + блок(t("approval.before"), было, len(item["before"]))
            + блок(t("approval.after"), стало, len(item["after"])), unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric(t("approval.audit_before"), f"{s0}/100")
c2.metric(t("approval.audit_after"), f"{s1}/100", delta=f"{s1 - s0:+d}")
c3.metric(t("approval.prepared"), item["prepared"][1], help=item["prepared"][0])
st.caption(t("approval.audit_hint"))

# ── решение: кнопки неактивны ──
st.markdown(eyebrow(t("approval.decision")), unsafe_allow_html=True)
st.text_area(t("approval.comment"), placeholder=t("approval.comment_ph"), disabled=True, key="appr_comment")
b1, b2, b3, _ = st.columns([1.1, 1.4, 1, 2])
b1.button(t("approval.btn.approve"), type="primary", disabled=True, key="appr_ok")
b2.button(t("approval.btn.return"), disabled=True, key="appr_back")
b3.button(t("approval.btn.reject"), disabled=True, key="appr_no")
st.caption(t("approval.buttons_off"))

# ── путь после решения ──
st.markdown(eyebrow(t("approval.flow")), unsafe_allow_html=True)
шаги = ["pending", "approved", "ready", "sent", "accepted"]
дошёл = {"pending": 0, "returned": 0, "approved": 1, "ready": 2, "sent": 3, "accepted": 4, "error": 4}[item["status"]]
части = []
for k, шаг in enumerate(шаги):
    подпись = t("approval.st." + шаг) if шаг != "accepted" else t("approval.st.accepted_or_error")
    цвет = INK if k <= дошёл else "#B5B0A6"
    вес = 700 if k == дошёл else 400
    части.append(f'<span style="color:{цвет};font-weight:{вес};">{html.escape(подпись)}</span>')
st.markdown('<div style="font-size:14px;">' + ' <span style="color:#B5B0A6;">→</span> '.join(части) + "</div>",
            unsafe_allow_html=True)
st.caption(t("approval.flow_hint"))

# ── журнал ──
st.markdown(eyebrow(t("approval.log")), unsafe_allow_html=True)
журнал = [(item["prepared"][0], item["prepared"][1], "prepared", "")] + item["log"]
st.dataframe(pd.DataFrame([{
    t("approval.col.when"): когда,
    t("approval.col.who"): кто,
    t("approval.col.event"): t("approval.ev." + что),
    t("approval.col.comment"): t(комм) if комм else "",
} for кто, когда, что, комм in журнал]), hide_index=True, width="stretch")
