import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from io import BytesIO
import streamlit as st
from datetime import datetime, timedelta
import time

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# ============================================================
# إعداد الصفحة
# ============================================================
st.set_page_config(
    page_title="نظام مؤشرات الأداء - المركز القومي لبحوث المياه",
    layout="wide",
    page_icon="📊"
)

current_dir = os.path.dirname(__file__)
logo_path = os.path.join(current_dir, "logo.png")
if os.path.exists(logo_path):
    st.image(logo_path, width=150)

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; }
.stButton > button { width: 100%; }
[data-testid="stMetricValue"] { font-size: 1.5rem; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { direction: rtl !important; }
[data-testid="stDataFrame"] table, [data-testid="stDataEditor"] table { direction: rtl !important; text-align: right !important; }
[data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td,
[data-testid="stDataEditor"] th, [data-testid="stDataEditor"] td { text-align: right !important; direction: rtl !important; }
h1, h2, h3, h4, h5, h6 { direction: rtl; text-align: right; }
.stTabs [data-baseweb="tab-list"] { direction: rtl; }
.stTextInput input, .stNumberInput input, .stTextArea textarea { direction: rtl; text-align: right; }
.stSelectbox div[data-baseweb="select"] { direction: rtl; }
</style>
""", unsafe_allow_html=True)

def get_local_time():
    return (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# Google Sheets
# ============================================================
SPREADSHEET_KEY = "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"

@st.cache_resource(show_spinner=False)
def _get_client():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def _get_spreadsheet_cached(_bust=0):
    return _get_client().open_by_key(SPREADSHEET_KEY)

def get_spreadsheet():
    return _get_spreadsheet_cached(_bust=st.session_state.get("gs_bust", 0))

@st.cache_resource(show_spinner=False)
def _get_ws_cached(sheet_name, _bust=0):
    try:
        return _get_spreadsheet_cached(_bust=_bust).worksheet(sheet_name)
    except Exception:
        return None

def get_worksheet(sheet_name):
    return _get_ws_cached(sheet_name, _bust=st.session_state.get("gs_bust", 0))

def get_or_create_sheet(sheet_name, headers=None):
    ws = get_worksheet(sheet_name)
    if ws is not None:
        return ws
    time.sleep(0.5)
    try:
        return get_spreadsheet().worksheet(sheet_name)
    except Exception:
        pass
    try:
        ws = get_spreadsheet().add_worksheet(title=sheet_name, rows=2000, cols=40)
        if headers:
            ws.append_row(headers)
        st.session_state.gs_bust = st.session_state.get("gs_bust", 0) + 1
        return ws
    except Exception as e:
        if "already exists" in str(e).lower():
            time.sleep(1)
            try:
                return get_spreadsheet().worksheet(sheet_name)
            except Exception:
                return None
        st.error(f"خطأ في الوصول للورقة {sheet_name}: {e}")
        return None

@st.cache_data(ttl=120, show_spinner=False)
def _fetch_cached(sheet_name, _bust=0):
    try:
        ws = get_worksheet(sheet_name)
        if ws is None:
            return []
        for attempt in range(3):
            try:
                return ws.get_all_values()
            except gspread.exceptions.APIError as e:
                if "429" in str(e) or "Quota" in str(e):
                    time.sleep(2 ** attempt)
                    continue
                raise
        return []
    except Exception:
        return []

def fetch_data(sheet_name):
    return _fetch_cached(sheet_name, _bust=st.session_state.get("data_bust", 0))

def invalidate_all():
    st.session_state.gs_bust = st.session_state.get("gs_bust", 0) + 1
    st.session_state.data_bust = st.session_state.get("data_bust", 0) + 1
    _fetch_cached.clear()
    for key in list(st.session_state.keys()):
        if key.startswith("_cd_") or key.startswith("_cb_"):
            del st.session_state[key]

def reset_all():
    invalidate_all()
    for key in list(st.session_state.keys()):
        if key.startswith("_saved_"):
            del st.session_state[key]

def fix_encoding(t):
    if isinstance(t, str):
        try:
            return t.encode('latin1').decode('utf-8')
        except Exception:
            return t
    return t

def rtl_display(df):
    if df.empty:
        return df
    return df[list(reversed(df.columns))]

def load_sheet(sheet_name, columns):
    cache_key = f"_cd_{sheet_name}"
    bust_key = f"_cb_{sheet_name}"
    cur_bust = st.session_state.get("data_bust", 0)
    if st.session_state.get(bust_key, -1) == cur_bust and cache_key in st.session_state:
        return st.session_state[cache_key].copy()
    
    get_or_create_sheet(sheet_name, columns)
    all_values = fetch_data(sheet_name)
    
    if len(all_values) <= 1:
        df = pd.DataFrame(columns=columns)
    else:
        headers = [fix_encoding(h) for h in all_values[0]]
        max_len = len(headers)
        normalized = []
        for row in all_values[1:]:
            row = list(row) + [""] * (max_len - len(row))
            normalized.append(row[:max_len])
        df = pd.DataFrame(normalized, columns=headers)
        for col in df.columns:
            if df[col].dtype == 'object' and col not in columns:
                df[col] = df[col].apply(fix_encoding)
    
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    
    st.session_state[cache_key] = df.copy()
    st.session_state[bust_key] = cur_bust
    return df

def save_list(sheet_name, input_df, base_cols, institute, period_key, period_val):
    try:
        full_cols = base_cols + ["المعهد", period_key]
        ws = get_or_create_sheet(sheet_name, full_cols)
        if ws is None:
            st.error("فشل الاتصال")
            return False
        
        all_values = ws.get_all_values()
        kept = []
        if len(all_values) > 1:
            existing = pd.DataFrame(all_values[1:], columns=all_values[0])
            if "المعهد" in existing.columns and period_key in existing.columns:
                mask = ~((existing["المعهد"] == institute) & (existing[period_key] == period_val))
                kept = existing[mask].values.tolist()
        
        ws.clear()
        ws.append_row(full_cols)
        if kept:
            ws.append_rows([[str(v) for v in r] for r in kept])
        
        new_rows = []
        for _, row in input_df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row.tolist()]
            if all(v.strip() in ["", "nan", "None"] for v in vals):
                continue
            new_rows.append(vals + [institute, period_val])
        if new_rows:
            ws.append_rows(new_rows)
        
        clean_df = input_df.copy().reset_index(drop=True)
        save_key = f"_saved_{sheet_name}_{institute}_{period_val}"
        st.session_state[save_key] = clean_df
        st.session_state["last_save_time"] = get_local_time()
        
        st.session_state.data_bust = st.session_state.get("data_bust", 0) + 1
        _fetch_cached.clear()
        for key in list(st.session_state.keys()):
            if key.startswith("_cd_") or key.startswith("_cb_"):
                del st.session_state[key]
        
        return True
    except Exception as e:
        st.error(f"خطأ في الحفظ: {e}")
        return False

def save_or_update_row(sheet_name, all_cols, data_dict, key_cols):
    try:
        ws = get_or_create_sheet(sheet_name, all_cols)
        if ws is None:
            return None
        
        all_v = ws.get_all_values()
        if len(all_v) == 0:
            new_data = [list(all_cols), [str(data_dict.get(c, "0")) for c in all_cols]]
            result = "added"
        else:
            headers = all_v[0]
            for c in all_cols:
                if c not in headers:
                    headers.append(c)
            new_data = [headers]
            found = False
            expected_len = len(headers)
            for row in all_v[1:]:
                row_list = list(row) + [""] * (expected_len - len(row))
                row_list = row_list[:expected_len]
                is_match = True
                for k in key_cols:
                    if k in headers:
                        idx = headers.index(k)
                        if str(row_list[idx]) != str(data_dict.get(k, "")):
                            is_match = False
                            break
                    else:
                        is_match = False
                        break
                if is_match:
                    new_data.append([str(data_dict.get(h, "0")) for h in headers])
                    found = True
                else:
                    new_data.append(row_list)
            if not found:
                new_data.append([str(data_dict.get(h, "0")) for h in headers])
                result = "added"
            else:
                result = "updated"
        
        ws.clear()
        ws.append_rows(new_data, value_input_option="USER_ENTERED")
        return result
    except Exception as e:
        st.error(f"خطأ في الحفظ: {e}")
        return None

# ============================================================
# دوال RTL لـ Word
# ============================================================
def _rtl_run(run, bold=False, size=11):
    rPr = run._element.get_or_add_rPr()
    rtl = OxmlElement('w:rtl'); rtl.set(qn('w:val'), '1'); rPr.append(rtl)
    run.font.name = 'Arial'
    run.font.size = Pt(size)
    run.font.bold = bold

def _rtl_para(p):
    pPr = p._p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi'); bidi.set(qn('w:val'), '1'); pPr.append(bidi)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

def _rtl_table(table):
    tblPr = table._tbl.tblPr
    tblPr.append(OxmlElement('w:bidiVisual'))

def _add_heading(doc, text, size=16):
    p = doc.add_paragraph()
    _rtl_run(p.add_run(text), bold=True, size=size)
    _rtl_para(p)

def _add_para(doc, text, size=12):
    p = doc.add_paragraph()
    _rtl_run(p.add_run(text), size=size)
    _rtl_para(p)

def _add_table(doc, headers, rows):
    if "م" not in headers:
        headers = ["م"] + list(headers)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _rtl_table(table)
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        _rtl_run(p.add_run(str(h)), bold=True, size=10)
        _rtl_para(p)
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), 'D9D9D9')
        cell._tc.get_or_add_tcPr().append(shd)
    serial_idx = headers.index("م")
    for idx, row_data in enumerate(rows, start=1):
        cells = table.add_row().cells
        cells[serial_idx].text = ""
        p = cells[serial_idx].paragraphs[0]
        _rtl_run(p.add_run(str(idx)), size=10)
        _rtl_para(p)
        col = 0
        for i, h in enumerate(headers):
            if i == serial_idx:
                continue
            val = row_data[col] if col < len(row_data) else ""
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            _rtl_run(p.add_run(str(val) if pd.notna(val) and str(val) != "nan" else ""), size=10)
            _rtl_para(p)
            col += 1

# ============================================================
# ⭐ الثوابت الجديدة وفقاً للملف
# ============================================================
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

# الدراسات الجارية
T_RESEARCH = "خطة بحثية"
T_CONSULT = "استشارية"
T_SELF_FUNDED = "دراسات بتمويل ذاتي"

# التقارير
T_REP_PROGRESS = "تقرير مرحلي"
T_REP_FINAL = "تقرير نهائي"
T_REP_INSPECT = "تقرير معاينة"
T_REP_CALIB = "تقرير معايرة"
T_REP_OTHER = "أخرى"

# المقترحات
T_PROP_CONSULT = "استشارات"
T_PROP_FUNDING = "تمويل أبحاث"

# الأنشطة العلمية
T_ACT_CONF = "مؤتمرات"
T_ACT_WORKSHOP = "ورش عمل"

# الاجتماعات
T_MEET_MINISTRY = "بالوزارة"
T_MEET_CENTER = "بالمركز"
T_MEET_EXTERNAL = "جهات خارجية"
T_MEET_STAFF = "مع العاملين"
T_MEET_OTHER = "جهات أخرى"

# الأوراق البحثية
T_PAPER_PUBLISHED = "المنشورة"
T_PAPER_ONGOING = "الجاري العمل عليها"

# الرسائل العلمية
T_THESIS_FINISHED = "المنتهية"
T_THESIS_ONGOING = "الجاري العمل عليها"

# التدريب
T_TRAIN_IN = "داخل المعهد"
T_TRAIN_OUT = "خارج المعهد"
T_TRAIN_ONLINE = "Online"
T_TR_TYPE_COURSE = "دورة تدريبية"
T_TR_TYPE_WS = "ورشة عمل"
T_TR_TYPE_CONF = "مؤتمر"

# ============================================================
# ⭐ الأعمدة المحدثة
# ============================================================
KPI_COLUMNS = [
    "المعهد", "المستخدم", "الشهر", "السنة",
    # الدراسات
    "خطة بحثية", "استشارية", "دراسات بتمويل ذاتي", "إجمالي الدراسات الجارية",
    # التقارير
    "تقرير مرحلي", "تقرير نهائي", "تقرير معاينة", "تقرير معايرة", "أخرى",
    "إجمالي التقارير",
    # المذكرات
    "عدد المذكرات",
    # المقترحات
    "استشارات", "تمويل أبحاث", "إجمالي المقترحات",
    # المأموريات والمعاينات
    "إجمالي عدد المأموريات", "إجمالي عدد الأيام الفعلية", "إجمالي عدد المعاينات",
    # التدريب
    "متدربين", "مدربين",
    "أيام تدريب داخل المعهد", "أيام تدريب خارج المعهد",
    # الأنشطة العلمية
    "مؤتمرات", "ورش عمل", "إجمالي المشاركين في أنشطة علمية",
    # الاجتماعات
    "اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية",
    "اجتماعات مع العاملين", "اجتماعات جهات أخرى", "إجمالي الاجتماعات",
    # الأوراق البحثية
    "الأوراق المنشورة", "الأوراق الجاري العمل عليها", "إجمالي الأوراق البحثية",
    # الرسائل
    "الرسائل المنتهية", "الرسائل الجاري العمل عليها", "إجمالي الرسائل",
    # العاملون
    "إجمالي عدد العاملين الفعلي",
    "الأساتذة المتفرغين", "الأساتذة", "الأساتذة المساعدون",
    "الباحثون", "الباحث المساعد", "مساعد باحث",
    "الفنيون", "الإداريون", "السائقون",
]

QUARTERLY_COLUMNS = [
    "المعهد", "المستخدم", "الربع", "السنة المالية",
    "عدد الباحثين", "عدد الأساتذة بدون المتفرغين",
    "عدد المهندسين", "إجمالي عدد العاملين",
    "المبلغ المنصرف من الموازنة الاستثمارية",
    "عدد الاجتماعات الدورية", "عدد اجتماعات مجلس الإدارة",
    "عدد اجتماعات وحدة الفكر", "ملاحظات",
]

HALF_COLUMNS = [
    "المعهد", "المستخدم", "النصف", "السنة المالية",
    "إجمالي عدد دراسات الخطة البحثية المنجزة",
    "إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات",
    "إجمالي مبلغ الإيرادات الذاتية",
]

ANNUAL_COLUMNS = ["المعهد", "المستخدم", "السنة المالية", "عدد براءات الاختراع"]

# ============================================================
# ⭐ أعمدة القوائم الشهرية
# ============================================================
LIST_STUDIES = ["م", "عنوان الدراسة", "النوع", "الجهة المستفيدة", "تاريخ البدء", "نسبة التنفيذ %", "ملاحظات"]
LIST_REPORTS = ["م", "عنوان التقرير", "النوع", "تاريخ الإصدار", "الجهة المستفيدة", "ملخص"]
LIST_MEMOS = ["م", "رقم المذكرة", "الموضوع", "التاريخ", "الجهة الموجه إليها"]
LIST_PROPOSALS = ["م", "عنوان المقترح", "النوع", "الجهة التمويل", "موقف المقترح", "ملاحظات"]
LIST_MISSIONS = ["م", "الموقع", "الغرض", "من تاريخ", "إلى تاريخ", "عدد الأيام", "الفريق", "هل معاينة؟"]
LIST_INSPECTIONS = ["م", "الموقع", "الغرض", "التاريخ", "الفريق"]
LIST_TRAINING = ["م", "عنوان البرنامج", "النوع", "المكان", "عدد المتدربين", "عدد المدربين", "عدد الأيام"]
LIST_ACTIVITIES = ["م", "النشاط", "النوع", "عدد المشاركين", "المكان", "التاريخ"]
LIST_MEETINGS = ["م", "التاريخ", "النوع", "الاسم", "الوظيفة", "المكان", "الغرض"]
LIST_PAPERS = ["م", "عنوان البحث", "المجلة", "النوع", "تاريخ النشر", "الباحث الرئيسي"]
LIST_THESES = ["م", "عنوان الرسالة", "النوع", "الباحث", "الجامعة", "تاريخ المناقشة"]

# ⭐ القوائم المحدثة وفقاً للملف
MONTHLY_LISTS = {
    "الدراسات_الجارية": {
        "title": "📚 الدراسات الجارية",
        "cols": LIST_STUDIES,
        "hint": f"النوع: {T_RESEARCH} / {T_CONSULT} / {T_SELF_FUNDED}",
        "dropdowns": {"النوع": [T_RESEARCH, T_CONSULT, T_SELF_FUNDED]},
    },
    "التقارير_الصادرة": {
        "title": "📄 التقارير الصادرة",
        "cols": LIST_REPORTS,
        "hint": f"النوع: {T_REP_PROGRESS} / {T_REP_FINAL} / {T_REP_INSPECT} / {T_REP_CALIB} / {T_REP_OTHER}",
        "dropdowns": {"النوع": [T_REP_PROGRESS, T_REP_FINAL, T_REP_INSPECT, T_REP_CALIB, T_REP_OTHER]},
    },
    "المذكرات_الصادرة": {
        "title": "📝 المذكرات الصادرة", "cols": LIST_MEMOS, "hint": "", "dropdowns": {},
    },
    "المقترحات": {
        "title": "📋 المقترحات الفنية والمالية",
        "cols": LIST_PROPOSALS,
        "hint": f"النوع: {T_PROP_CONSULT} / {T_PROP_FUNDING}",
        "dropdowns": {"النوع": [T_PROP_CONSULT, T_PROP_FUNDING]},
    },
    "المأموريات_الحقلية": {
        "title": "🏃 المأموريات الحقلية والمعاينات", "cols": LIST_MISSIONS,
        "hint": "أدخل عدد الأيام لكل مأمورية. عمود (هل معاينة؟) يشير إلى نوع الزيارة",
        "dropdowns": {"هل معاينة؟": ["مأمورية", "معاينة"]},
    },
    "التدريب": {
        "title": "👥 التدريب",
        "cols": LIST_TRAINING,
        "hint": f"النوع: {T_TR_TYPE_COURSE} / {T_TR_TYPE_WS} / {T_TR_TYPE_CONF} — المكان: {T_TRAIN_IN} / {T_TRAIN_OUT} / {T_TRAIN_ONLINE}",
        "dropdowns": {
            "النوع": [T_TR_TYPE_COURSE, T_TR_TYPE_WS, T_TR_TYPE_CONF],
            "المكان": [T_TRAIN_IN, T_TRAIN_OUT, T_TRAIN_ONLINE],
        },
    },
    "الأنشطة_العلمية": {
        "title": "🔬 الأنشطة العلمية",
        "cols": LIST_ACTIVITIES,
        "hint": f"النوع: {T_ACT_CONF} / {T_ACT_WORKSHOP}",
        "dropdowns": {"النوع": [T_ACT_CONF, T_ACT_WORKSHOP]},
    },
    "الاجتماعات": {
        "title": "🤝 الاجتماعات",
        "cols": LIST_MEETINGS,
        "hint": f"النوع: {T_MEET_MINISTRY} / {T_MEET_CENTER} / {T_MEET_EXTERNAL} / {T_MEET_STAFF} / {T_MEET_OTHER}",
        "dropdowns": {"النوع": [T_MEET_MINISTRY, T_MEET_CENTER, T_MEET_EXTERNAL, T_MEET_STAFF, T_MEET_OTHER]},
    },
    "الأوراق_البحثية": {
        "title": "📝 الأوراق البحثية",
        "cols": LIST_PAPERS,
        "hint": f"النوع: {T_PAPER_PUBLISHED} / {T_PAPER_ONGOING}",
        "dropdowns": {"النوع": [T_PAPER_PUBLISHED, T_PAPER_ONGOING]},
    },
    "الرسائل_العلمية": {
        "title": "🎓 رسائل الماجستير والدكتوراه",
        "cols": LIST_THESES,
        "hint": f"النوع: {T_THESIS_FINISHED} / {T_THESIS_ONGOING}",
        "dropdowns": {"النوع": [T_THESIS_FINISHED, T_THESIS_ONGOING]},
    },
}

# ============================================================
# منطق الفترة المالية
# ============================================================
def get_fiscal_period(month, year):
    result = {
        "fiscal_year": "", "quarter": None, "half": None,
        "months_for_quarter": [], "months_for_half": [],
        "is_quarter_month": month in ["أكتوبر", "يناير", "أبريل", "يوليو"],
        "is_half_month": month in ["يناير", "يوليو"],
        "is_annual_month": month == "يوليو",
    }
    if month == "أكتوبر":
        result["quarter"] = "الربع الأول"
        result["months_for_quarter"] = [("يوليو", year), ("أغسطس", year), ("سبتمبر", year)]
        result["fiscal_year"] = f"{year}/{year + 1}"
    elif month == "يناير":
        result["quarter"] = "الربع الثاني"
        result["months_for_quarter"] = [("أكتوبر", year - 1), ("نوفمبر", year - 1), ("ديسمبر", year - 1)]
        result["fiscal_year"] = f"{year - 1}/{year}"
    elif month == "أبريل":
        result["quarter"] = "الربع الثالث"
        result["months_for_quarter"] = [("يناير", year), ("فبراير", year), ("مارس", year)]
        result["fiscal_year"] = f"{year - 1}/{year}"
    elif month == "يوليو":
        result["quarter"] = "الربع الرابع"
        result["months_for_quarter"] = [("أبريل", year), ("مايو", year), ("يونيو", year)]
        result["fiscal_year"] = f"{year - 1}/{year}"
    else:
        month_idx = MONTHS.index(month) + 1
        result["fiscal_year"] = f"{year}/{year + 1}" if month_idx >= 7 else f"{year - 1}/{year}"
    
    if month == "يناير":
        result["half"] = "النصف الأول"
    elif month == "يوليو":
        result["half"] = "النصف الثاني"
    return result

# ============================================================
# ⭐ حساب KPI - محدث وفقاً للأسماء الجديدة
# ============================================================
def compute_kpi_from_lists(institute, month, year):
    period = f"{month} {year}"
    kpi = {c: 0 for c in KPI_COLUMNS if c not in ["المعهد", "المستخدم", "الشهر", "السنة"]}
    
    def get_list(name):
        save_key = f"_saved_{name}_{institute}_{period}"
        if save_key in st.session_state:
            df = st.session_state[save_key].copy()
            df["المعهد"] = institute
            df["الفترة"] = period
            return df
        cols = MONTHLY_LISTS[name]["cols"] + ["المعهد", "الفترة"]
        df = load_sheet(name, cols)
        if df.empty or "المعهد" not in df.columns or "الفترة" not in df.columns:
            return pd.DataFrame()
        return df[(df["المعهد"] == institute) & (df["الفترة"] == period)]
    
    def to_num(series):
        return pd.to_numeric(series, errors="coerce").fillna(0)
    
    # 1. الدراسات
    s = get_list("الدراسات_الجارية")
    if not s.empty and "النوع" in s.columns:
        kpi["خطة بحثية"] = int((s["النوع"] == T_RESEARCH).sum())
        kpi["استشارية"] = int((s["النوع"] == T_CONSULT).sum())
        kpi["دراسات بتمويل ذاتي"] = int((s["النوع"] == T_SELF_FUNDED).sum())
    kpi["إجمالي الدراسات الجارية"] = kpi["خطة بحثية"] + kpi["استشارية"] + kpi["دراسات بتمويل ذاتي"]
    
    # 2. التقارير
    s = get_list("التقارير_الصادرة")
    if not s.empty and "النوع" in s.columns:
        kpi["تقرير مرحلي"] = int((s["النوع"] == T_REP_PROGRESS).sum())
        kpi["تقرير نهائي"] = int((s["النوع"] == T_REP_FINAL).sum())
        kpi["تقرير معاينة"] = int((s["النوع"] == T_REP_INSPECT).sum())
        kpi["تقرير معايرة"] = int((s["النوع"] == T_REP_CALIB).sum())
        kpi["أخرى"] = int((s["النوع"] == T_REP_OTHER).sum())
    kpi["إجمالي التقارير"] = (kpi["تقرير مرحلي"] + kpi["تقرير نهائي"] + 
                              kpi["تقرير معاينة"] + kpi["تقرير معايرة"] + kpi["أخرى"])
    
    # 3. المذكرات
    s = get_list("المذكرات_الصادرة")
    kpi["عدد المذكرات"] = len(s) if not s.empty else 0
    
    # 4. المقترحات
    s = get_list("المقترحات")
    if not s.empty and "النوع" in s.columns:
        kpi["استشارات"] = int((s["النوع"] == T_PROP_CONSULT).sum())
        kpi["تمويل أبحاث"] = int((s["النوع"] == T_PROP_FUNDING).sum())
    kpi["إجمالي المقترحات"] = kpi["استشارات"] + kpi["تمويل أبحاث"]
    
    # 5. المأموريات والمعاينات
    s = get_list("المأموريات_الحقلية")
    if not s.empty:
        if "عدد الأيام" in s.columns:
            kpi["إجمالي عدد الأيام الفعلية"] = int(to_num(s["عدد الأيام"]).sum())
        if "هل معاينة؟" in s.columns:
            kpi["إجمالي عدد المأموريات"] = int((s["هل معاينة؟"] == "مأمورية").sum())
            kpi["إجمالي عدد المعاينات"] = int((s["هل معاينة؟"] == "معاينة").sum())
        else:
            kpi["إجمالي عدد المأموريات"] = len(s)
    
    # 6. التدريب
    s = get_list("التدريب")
    if not s.empty:
        if "عدد المتدربين" in s.columns:
            kpi["متدربين"] = int(to_num(s["عدد المتدربين"]).sum())
        if "عدد المدربين" in s.columns:
            kpi["مدربين"] = int(to_num(s["عدد المدربين"]).sum())
        if "عدد الأيام" in s.columns and "المكان" in s.columns:
            days = to_num(s["عدد الأيام"])
            kpi["أيام تدريب داخل المعهد"] = int(days[s["المكان"] == T_TRAIN_IN].sum())
            kpi["أيام تدريب خارج المعهد"] = int(days[s["المكان"] == T_TRAIN_OUT].sum())
    
    # 7. الأنشطة العلمية
    s = get_list("الأنشطة_العلمية")
    if not s.empty and "عدد المشاركين" in s.columns and "النوع" in s.columns:
        parts = to_num(s["عدد المشاركين"])
        kpi["مؤتمرات"] = int(parts[s["النوع"] == T_ACT_CONF].sum())
        kpi["ورش عمل"] = int(parts[s["النوع"] == T_ACT_WORKSHOP].sum())
    kpi["إجمالي المشاركين في أنشطة علمية"] = kpi["مؤتمرات"] + kpi["ورش عمل"]
    
    # 8. الاجتماعات
    s = get_list("الاجتماعات")
    if not s.empty and "النوع" in s.columns:
        kpi["اجتماعات بالوزارة"] = int((s["النوع"] == T_MEET_MINISTRY).sum())
        kpi["اجتماعات بالمركز"] = int((s["النوع"] == T_MEET_CENTER).sum())
        kpi["اجتماعات جهات خارجية"] = int((s["النوع"] == T_MEET_EXTERNAL).sum())
        kpi["اجتماعات مع العاملين"] = int((s["النوع"] == T_MEET_STAFF).sum())
        kpi["اجتماعات جهات أخرى"] = int((s["النوع"] == T_MEET_OTHER).sum())
    kpi["إجمالي الاجتماعات"] = (kpi["اجتماعات بالوزارة"] + kpi["اجتماعات بالمركز"] + 
                                 kpi["اجتماعات جهات خارجية"] + kpi["اجتماعات مع العاملين"] + 
                                 kpi["اجتماعات جهات أخرى"])
    
    # 9. الأوراق البحثية
    s = get_list("الأوراق_البحثية")
    if not s.empty and "النوع" in s.columns:
        kpi["الأوراق المنشورة"] = int((s["النوع"] == T_PAPER_PUBLISHED).sum())
        kpi["الأوراق الجاري العمل عليها"] = int((s["النوع"] == T_PAPER_ONGOING).sum())
    kpi["إجمالي الأوراق البحثية"] = kpi["الأوراق المنشورة"] + kpi["الأوراق الجاري العمل عليها"]
    
    # 10. الرسائل
    s = get_list("الرسائل_العلمية")
    if not s.empty and "النوع" in s.columns:
        kpi["الرسائل المنتهية"] = int((s["النوع"] == T_THESIS_FINISHED).sum())
        kpi["الرسائل الجاري العمل عليها"] = int((s["النوع"] == T_THESIS_ONGOING).sum())
    kpi["إجمالي الرسائل"] = kpi["الرسائل المنتهية"] + kpi["الرسائل الجاري العمل عليها"]
    
    return kpi

# ============================================================
# توليد التقارير - محدث
# ============================================================
def generate_monthly_report(institute, month, year):
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21); section.page_height = Cm(29.7)
    section.left_margin = Cm(2); section.right_margin = Cm(2)
    
    doc.add_paragraph(); doc.add_paragraph()
    _add_heading(doc, "تقرير الإنجازات الشهري", size=26)
    _add_heading(doc, f"{institute}", size=20)
    _add_heading(doc, f"({month} {year})", size=18)
    doc.add_page_break()
    
    _add_heading(doc, "المحتويات", size=20)
    for i, c in enumerate(["الدراسات البحثية", "التقارير الفنية", "الاجتماعات",
                            "التدريب والندوات", "اجتماعات تحسين الأداء"], 1):
        _add_para(doc, f"{i}. {c}", size=13)
    doc.add_page_break()
    
    period = f"{month} {year}"
    df_studies = load_sheet("الدراسات_الجارية", LIST_STUDIES + ["المعهد", "الفترة"])
    df_filtered = pd.DataFrame()
    if not df_studies.empty:
        df_filtered = df_studies[(df_studies["المعهد"] == institute) & (df_studies["الفترة"] == period)]
    
    _add_heading(doc, f"الدراسات البحثية - {month} {year}", size=18)
    for label, tval in [("دراسات الخطة البحثية", T_RESEARCH),
                         ("مشروعات بحثية ممولة", T_SELF_FUNDED),
                         ("استشارات بحثية ممولة", T_CONSULT)]:
        _add_heading(doc, label, size=14)
        rows = []
        if not df_filtered.empty and "النوع" in df_filtered.columns:
            r = df_filtered[df_filtered["النوع"] == tval]
            rows = [[row.get("عنوان الدراسة",""), row.get("الجهة المستفيدة",""),
                     row.get("تاريخ البدء",""), row.get("ملاحظات","")] for _, row in r.iterrows()]
        _add_table(doc, ["عنوان الدراسة", "الجهة المستفيدة", "تاريخ الإصدار", "ملخص التقرير"], rows)
    
    doc.add_page_break()
    _add_heading(doc, "التقارير الفنية", size=18)
    df_reports = load_sheet("التقارير_الصادرة", LIST_REPORTS + ["المعهد", "الفترة"])
    rows = []
    if not df_reports.empty:
        r = df_reports[(df_reports["المعهد"] == institute) & (df_reports["الفترة"] == period)]
        rows = [[row.get("عنوان التقرير",""), row.get("تاريخ الإصدار",""),
                 row.get("الجهة المستفيدة",""), "", row.get("ملخص","")] for _, row in r.iterrows()]
    _add_table(doc, ["عنوان التقرير", "تاريخ الإصدار", "الجهة المستفيدة", "الدائرة", "ملخص"], rows)
    
    doc.add_page_break()
    _add_heading(doc, "الاجتماعات", size=18)
    df_meetings = load_sheet("الاجتماعات", LIST_MEETINGS + ["المعهد", "الفترة"])
    df_meet = pd.DataFrame()
    if not df_meetings.empty:
        df_meet = df_meetings[(df_meetings["المعهد"] == institute) & (df_meetings["الفترة"] == period)]
    
    for title, tval in [("أولاً: الاجتماعات بالوزارة", T_MEET_MINISTRY),
                        ("ثانياً: اجتماعات المركز", T_MEET_CENTER),
                        ("ثالثاً: الاجتماعات بمقر المعهد", T_MEET_STAFF),
                        ("رابعاً: اجتماعات بجهات أخرى", T_MEET_EXTERNAL)]:
        _add_heading(doc, title, size=14)
        rows = [[row.get("التاريخ",""), row.get("الاسم",""), row.get("الوظيفة",""),
                 row.get("المكان",""), row.get("الغرض","")] for _, row in df_meet[df_meet["النوع"] == tval].iterrows()] if not df_meet.empty else []
        _add_table(doc, ["التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض"], rows)
    
    doc.add_page_break()
    _add_heading(doc, "الدورات التدريبية / ورش العمل / المؤتمرات", size=18)
    df_training = load_sheet("التدريب", LIST_TRAINING + ["المعهد", "الفترة"])
    rows = []
    if not df_training.empty:
        r = df_training[(df_training["المعهد"] == institute) & (df_training["الفترة"] == period)]
        rows = [[row.get("عنوان البرنامج",""), row.get("المكان",""),
                 row.get("عدد المتدربين",""), row.get("عدد الأيام","")] for _, row in r.iterrows()]
    _add_table(doc, ["عنوان البرنامج", "مكان الانعقاد", "عدد المشاركين", "مدة البرنامج"], rows)
    
    doc.add_page_break()
    _add_heading(doc, "اجتماعات تحسين الأداء", size=18)
    _add_table(doc, ["التاريخ", "عنوان الاجتماع", "الغرض", "الحضور"], [])
    
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output.getvalue()

def generate_quarterly_report(institute, quarter, fiscal_year):
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21); section.page_height = Cm(29.7)
    
    doc.add_paragraph(); doc.add_paragraph()
    _add_heading(doc, "تقرير مؤشرات الأداء", size=26)
    _add_heading(doc, f"{institute}", size=20)
    _add_heading(doc, f"({quarter} — {fiscal_year})", size=16)
    doc.add_page_break()
    
    fy_start = int(fiscal_year.split("/")[0])
    fy_end = int(fiscal_year.split("/")[1])
    if quarter == "الربع الأول":
        q_months = [("يوليو", fy_start), ("أغسطس", fy_start), ("سبتمبر", fy_start)]
    elif quarter == "الربع الثاني":
        q_months = [("أكتوبر", fy_start), ("نوفمبر", fy_start), ("ديسمبر", fy_start)]
    elif quarter == "الربع الثالث":
        q_months = [("يناير", fy_end), ("فبراير", fy_end), ("مارس", fy_end)]
    else:
        q_months = [("أبريل", fy_end), ("مايو", fy_end), ("يونيو", fy_end)]
    
    kpi_df = load_sheet("KPI_Data", KPI_COLUMNS)
    q_df = pd.DataFrame()
    if not kpi_df.empty:
        kpi_f = kpi_df[kpi_df["المعهد"] == institute]
        mask = pd.Series([False]*len(kpi_f), index=kpi_f.index)
        for m, y in q_months:
            mask |= ((kpi_f["الشهر"] == m) & (kpi_f["السنة"] == str(y)))
        q_df = kpi_f[mask].copy()
        for c in q_df.columns:
            if c not in ["المعهد","المستخدم","الشهر","السنة"]:
                q_df[c] = pd.to_numeric(q_df[c], errors="coerce").fillna(0)
    agg = q_df.sum(numeric_only=True) if not q_df.empty else pd.Series()
    
    _add_heading(doc, "1. الأداء التنفيذي للخطة البحثية", size=16)
    _add_heading(doc, "1-1-1 مشروع فردي خاص بالمعهد", size=13)
    df_studies = load_sheet("الدراسات_الجارية", LIST_STUDIES + ["المعهد","الفترة"])
    rows = []
    if not df_studies.empty:
        period_list = [f"{m} {y}" for m, y in q_months]
        r = df_studies[(df_studies["المعهد"] == institute) & (df_studies["الفترة"].isin(period_list)) & (df_studies["النوع"] == T_RESEARCH)]
        rows = [[row.get("عنوان الدراسة",""), row.get("نسبة التنفيذ %",""), "", "", row.get("ملاحظات","")] for _, row in r.iterrows()]
    _add_table(doc, ["عنوان المشروع", "نسبة المنفذ %", "عدد التقارير", "هدف الدراسة", "النتائج"], rows)
    
    _add_heading(doc, "1-1-2 مشروع مشترك مع معاهد أخرى", size=13)
    _add_table(doc, ["عنوان المشروع", "نسبة المنفذ %", "نسبة المشاركة", "عدد التقارير", "الهدف", "النتائج"], [])
    doc.add_page_break()
    
    _add_heading(doc, "2. الاستشارات والدراسات خارج الخطة", size=16)
    consult_count = int(agg.get("استشارية", 0)) if not agg.empty else 0
    self_funded = int(agg.get("دراسات بتمويل ذاتي", 0)) if not agg.empty else 0
    rows = [
        ["عدد المشاريع البحثية الممولة محلياً (STDF)", self_funded],
        ["عدد المشاريع البحثية الممولة دولياً (PRIMA)", 0],
        ["عدد التكليفات من الوزارة", 0],
        ["عدد الاستشارات من الوزارة", consult_count],
        ["عدد الاستشارات من جهات حكومية/خاصة", 0],
        ["الإجمالي", consult_count + self_funded],
    ]
    _add_table(doc, ["البند", "العدد"], rows)
    
    _add_heading(doc, "2-2 المقترحات البحثية (Pipeline)", size=13)
    props_consult = int(agg.get("استشارات", 0)) if not agg.empty else 0
    props_funding = int(agg.get("تمويل أبحاث", 0)) if not agg.empty else 0
    rows = [
        ["عدد المقترحات المقدمة محلياً", props_consult],
        ["عدد المقترحات المقدمة دولياً", 0],
        ["عدد المقترحات المقدمة للوزارة", props_funding],
        ["عدد المقترحات لجهات خارج الوزارة", 0],
        ["الإجمالي", props_consult + props_funding],
    ]
    _add_table(doc, ["البند", "العدد"], rows)
    doc.add_page_break()
    
    _add_heading(doc, "3. التعاون الداخلي والخارجي", size=16)
    _add_heading(doc, "3-1 التعاون الداخلي مع المعاهد", size=13)
    _add_table(doc, ["اسم الدراسة/المشروع", "المعهد", "تاريخ بدء التعاون"], [])
    _add_heading(doc, "3-2 التعاون الداخلي خارج المعاهد", size=13)
    _add_table(doc, ["اسم الدراسة/المشروع", "الجهة", "تاريخ بدء التعاون"], [])
    _add_heading(doc, "3-3 التعاون الخارجي خارج مصر", size=13)
    _add_table(doc, ["اسم الدراسة/المشروع", "الجهة", "تاريخ بدء التعاون"], [])
    doc.add_page_break()
    
    _add_heading(doc, "4. الإنتاج العلمي والنشر", size=16)
    papers_pub = int(agg.get("الأوراق المنشورة", 0)) if not agg.empty else 0
    theses_fin = int(agg.get("الرسائل المنتهية", 0)) if not agg.empty else 0
    rows = [
        ["عدد الأبحاث المنشورة لباحثي المعهد", papers_pub],
        ["عدد الأبحاث في مجالات متميزة Q1/Q2", 0],
        ["عدد الأبحاث بأخذ الموافقة على النشر", 0],
        ["عدد الأبحاث بأخذ مكافأة نشر", 0],
        ["عدد الباحثين بمكافأة نشر", 0],
        ["عدد رسائل الماجستير والدكتوراه المنتهية", theses_fin],
        ["مراجعة وتحكيم بمجلات علمية", 0],
        ["إشراف/تحكيم لباحثي المعهد", 0],
        ["إشراف/تحكيم لباحثين خارجيين", 0],
    ]
    _add_table(doc, ["البند", "العدد"], rows)
    doc.add_page_break()
    
    _add_heading(doc, "5. التدريب والتعليم", size=16)
    df_training = load_sheet("التدريب", LIST_TRAINING + ["المعهد","الفترة"])
    training_data = {}
    if not df_training.empty:
        period_list = [f"{m} {y}" for m, y in q_months]
        r = df_training[(df_training["المعهد"] == institute) & (df_training["الفترة"].isin(period_list))]
        for _, row in r.iterrows():
            key = (row.get("النوع",""), row.get("المكان",""))
            if key not in training_data:
                training_data[key] = {"count": 0, "trainees": 0}
            training_data[key]["count"] += 1
            try:
                training_data[key]["trainees"] += int(float(row.get("عدد المتدربين", 0) or 0))
            except:
                pass
    
    rows = []
    for label, (ntype, place) in [
        ("دورات بالداخل", (T_TR_TYPE_COURSE, T_TRAIN_IN)),
        ("دورات بالخارج", (T_TR_TYPE_COURSE, T_TRAIN_OUT)),
        ("دورات online", (T_TR_TYPE_COURSE, T_TRAIN_ONLINE)),
        ("ورش عمل/ندوات بالداخل", (T_TR_TYPE_WS, T_TRAIN_IN)),
        ("ورش عمل/ندوات بالخارج", (T_TR_TYPE_WS, T_TRAIN_OUT)),
        ("مؤتمرات بالداخل", (T_TR_TYPE_CONF, T_TRAIN_IN)),
        ("مؤتمرات بالخارج", (T_TR_TYPE_CONF, T_TRAIN_OUT)),
    ]:
        d = training_data.get((ntype, place), {"count": 0, "trainees": 0})
        rows.append([label, d["count"], d["trainees"]])
    rows.append(["الإجمالي", sum(r[1] for r in rows), sum(r[2] for r in rows)])
    _add_table(doc, ["الدورة/ورشة العمل", "عدد الدورات", "عدد المتدربين"], rows)
    doc.add_page_break()
    
    _add_heading(doc, "6. التمويل والأداء المالي", size=16)
    df_q = load_sheet("البيانات_الربع_سنوية", QUARTERLY_COLUMNS)
    budget = 0
    if not df_q.empty:
        r = df_q[(df_q["المعهد"] == institute) & (df_q["الربع"] == quarter) & (df_q["السنة المالية"] == fiscal_year)]
        if not r.empty:
            try: budget = float(r.iloc[0].get("المبلغ المنصرف من الموازنة الاستثمارية", 0) or 0)
            except: pass
    
    rows = [
        ["تمويل الخطة البحثية", "0", "0%"],
        ["التمويل الخارجي", "0", "0%"],
        ["المنصرف الفعلي", f"{budget:.2f}", "0%"],
        ["تمويل النشر - دراسات", "0", "-"],
        ["تمويل النشر - أبحاث", "0", "-"],
        ["تمويل النشر - مكافآت", "0", "-"],
    ]
    _add_table(doc, ["البند", "المبلغ (ألف ج)", "النسبة"], rows)
    doc.add_page_break()
    
    _add_heading(doc, "7. الموارد البشرية", size=16)
    per_meet = board_meet = think_meet = 0
    if not df_q.empty and not r.empty:
        try:
            per_meet = int(float(r.iloc[0].get("عدد الاجتماعات الدورية", 0) or 0))
            board_meet = int(float(r.iloc[0].get("عدد اجتماعات مجلس الإدارة", 0) or 0))
            think_meet = int(float(r.iloc[0].get("عدد اجتماعات وحدة الفكر", 0) or 0))
        except: pass
    rows = [
        ["عدد الاجتماعات الدورية", per_meet],
        ["عدد اجتماعات مجلس الإدارة", board_meet],
        ["عدد اجتماعات وحدة الفكر", think_meet],
        ["آليات التسويق", ""],
        ["آليات الثواب والعقاب", ""],
    ]
    _add_table(doc, ["البند", "القيمة"], rows)
    doc.add_page_break()
    
    _add_heading(doc, "8. الاجتماعات الوزارية", size=16)
    df_meetings = load_sheet("الاجتماعات", LIST_MEETINGS + ["المعهد","الفترة"])
    rows = []
    if not df_meetings.empty:
        period_list = [f"{m} {y}" for m, y in q_months]
        r_meet = df_meetings[(df_meetings["المعهد"] == institute) & (df_meetings["الفترة"].isin(period_list)) & (df_meetings["النوع"] == T_MEET_MINISTRY)]
        rows = [[row.get("التاريخ",""), row.get("الاسم",""), row.get("الوظيفة",""), row.get("المكان",""), row.get("الغرض","")] for _, row in r_meet.iterrows()]
    _add_table(doc, ["التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض"], rows)
    
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output.getvalue()

def generate_annual_report_excel(institute, fiscal_year):
    wb = Workbook()
    ws = wb.active
    ws.title = f"تقرير سنوي {fiscal_year}".replace("/", "_")
    ws.sheet_view.rightToLeft = True
    
    header_font = Font(name='Arial', size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    data_font = Font(name='Arial', size=10)
    data_alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
    center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))
    
    fy_start = int(fiscal_year.split("/")[0])
    fy_end = int(fiscal_year.split("/")[1])
    
    kpi_df = load_sheet("KPI_Data", KPI_COLUMNS)
    year_df = pd.DataFrame()
    if not kpi_df.empty:
        kpi_f = kpi_df[kpi_df["المعهد"] == institute]
        fy_months = [
            ("يوليو", fy_start), ("أغسطس", fy_start), ("سبتمبر", fy_start),
            ("أكتوبر", fy_start), ("نوفمبر", fy_start), ("ديسمبر", fy_start),
            ("يناير", fy_end), ("فبراير", fy_end), ("مارس", fy_end),
            ("أبريل", fy_end), ("مايو", fy_end), ("يونيو", fy_end),
        ]
        mask = pd.Series([False]*len(kpi_f), index=kpi_f.index)
        for m, y in fy_months:
            mask |= ((kpi_f["الشهر"] == m) & (kpi_f["السنة"] == str(y)))
        year_df = kpi_f[mask].copy()
        for c in year_df.columns:
            if c not in ["المعهد","المستخدم","الشهر","السنة"]:
                year_df[c] = pd.to_numeric(year_df[c], errors="coerce").fillna(0)
    agg = year_df.sum(numeric_only=True) if not year_df.empty else pd.Series()
    
    ws.merge_cells('A1:B1')
    ws['A1'] = f"تقرير مؤشرات الأداء السنوي - {institute}"
    ws['A1'].font = Font(name='Arial', size=16, bold=True)
    ws['A1'].alignment = center_alignment
    ws.merge_cells('A2:B2')
    ws['A2'] = f"السنة المالية {fiscal_year}"
    ws['A2'].font = Font(name='Arial', size=13, bold=True)
    ws['A2'].alignment = center_alignment
    
    row = 4
    ws.cell(row=row, column=1, value="المؤشر").font = header_font
    ws.cell(row=row, column=1).fill = header_fill
    ws.cell(row=row, column=1).alignment = center_alignment
    ws.cell(row=row, column=1).border = border
    ws.cell(row=row, column=2, value="القيمة").font = header_font
    ws.cell(row=row, column=2).fill = header_fill
    ws.cell(row=row, column=2).alignment = center_alignment
    ws.cell(row=row, column=2).border = border
    row += 1
    
    summary_items = [
        ("إجمالي الدراسات", int(agg.get("إجمالي الدراسات الجارية", 0)) if not agg.empty else 0),
        ("خطة بحثية", int(agg.get("خطة بحثية", 0)) if not agg.empty else 0),
        ("استشارية", int(agg.get("استشارية", 0)) if not agg.empty else 0),
        ("دراسات بتمويل ذاتي", int(agg.get("دراسات بتمويل ذاتي", 0)) if not agg.empty else 0),
        ("إجمالي التقارير", int(agg.get("إجمالي التقارير", 0)) if not agg.empty else 0),
        ("تقرير مرحلي", int(agg.get("تقرير مرحلي", 0)) if not agg.empty else 0),
        ("تقرير نهائي", int(agg.get("تقرير نهائي", 0)) if not agg.empty else 0),
        ("تقرير معاينة", int(agg.get("تقرير معاينة", 0)) if not agg.empty else 0),
        ("تقرير معايرة", int(agg.get("تقرير معايرة", 0)) if not agg.empty else 0),
        ("عدد المذكرات", int(agg.get("عدد المذكرات", 0)) if not agg.empty else 0),
        ("إجمالي المقترحات", int(agg.get("إجمالي المقترحات", 0)) if not agg.empty else 0),
        ("إجمالي المأموريات", int(agg.get("إجمالي عدد المأموريات", 0)) if not agg.empty else 0),
        ("إجمالي أيام المأموريات", int(agg.get("إجمالي عدد الأيام الفعلية", 0)) if not agg.empty else 0),
        ("إجمالي المعاينات", int(agg.get("إجمالي عدد المعاينات", 0)) if not agg.empty else 0),
        ("متدربين", int(agg.get("متدربين", 0)) if not agg.empty else 0),
        ("مدربين", int(agg.get("مدربين", 0)) if not agg.empty else 0),
        ("إجمالي المشاركين في أنشطة", int(agg.get("إجمالي المشاركين في أنشطة علمية", 0)) if not agg.empty else 0),
        ("إجمالي الاجتماعات", int(agg.get("إجمالي الاجتماعات", 0)) if not agg.empty else 0),
        ("إجمالي الأوراق", int(agg.get("إجمالي الأوراق البحثية", 0)) if not agg.empty else 0),
        ("إجمالي الرسائل", int(agg.get("إجمالي الرسائل", 0)) if not agg.empty else 0),
    ]
    
    for label, val in summary_items:
        ws.cell(row=row, column=1, value=label).font = data_font
        ws.cell(row=row, column=1).alignment = data_alignment
        ws.cell(row=row, column=1).border = border
        ws.cell(row=row, column=2, value=val).font = data_font
        ws.cell(row=row, column=2).alignment = center_alignment
        ws.cell(row=row, column=2).border = border
        row += 1
    
    ws.column_dimensions['A'].width = 45
    ws.column_dimensions['B'].width = 20
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

# ============================================================
# المستخدمون
# ============================================================
USERS = {
    "admin": {"password": "admin123", "role": "admin", "institute": "الجميع"},
    "wmri": {"password": "1234", "role": "user", "institute": "معهد بحوث إدارة المياه"},
    "dri": {"password": "1234", "role": "user", "institute": "معهد بحوث الصرف"},
    "wrri": {"password": "1234", "role": "user", "institute": "معهد بحوث الموارد المائية"},
    "nri": {"password": "1234", "role": "user", "institute": "معهد بحوث النيل"},
    "hri": {"password": "1234", "role": "user", "institute": "معهد بحوث الهيدروليكا"},
    "cori": {"password": "1234", "role": "user", "institute": "معهد بحوث الشواطئ"},
    "gwri": {"password": "1234", "role": "user", "institute": "معهد بحوث المياه الجوفية"},
    "chri": {"password": "1234", "role": "user", "institute": "معهد بحوث صيانة القنوات"},
    "eri": {"password": "1234", "role": "user", "institute": "معهد بحوث الإنشاءات"},
    "mri": {"password": "1234", "role": "user", "institute": "معهد بحوث الميكانيكا"},
    "sri": {"password": "1234", "role": "user", "institute": "معهد بحوث المساحة"},
    "ecri": {"password": "1234", "role": "user", "institute": "معهد البيئة وتغير المناخ"},
}

for k, v in [("logged_in", False), ("gs_bust", 0), ("data_bust", 0), ("editor_counter", 0)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# تسجيل الدخول
# ============================================================
if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول - المركز القومي لبحوث المياه")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        if st.button("🚪 دخول", type="primary"):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = USERS[username]["role"]
                st.session_state.institute = USERS[username]["institute"]
                reset_all()
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# ============================================================
# بعد تسجيل الدخول
# ============================================================
c_head = st.columns([5, 1, 1])
with c_head[0]:
    st.success(f"👤 مرحباً **{st.session_state.username}** — 🏢 {st.session_state.institute}")
with c_head[1]:
    if st.button("🔄 تحديث"):
        reset_all()
        st.rerun()
with c_head[2]:
    if st.button("🚪 خروج"):
        st.session_state.clear()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

if st.session_state.role == "admin":
    tab_dash, tab_q_dash, tab_annual, tab_data, tab_debug = st.tabs([
        "📊 Dashboard الشهري", "📈 التقرير الربع سنوي", "📅 التقرير السنوي", "📄 البيانات", "🔧 تشخيص"
    ])
    tab_input = None
else:
    tab_input, tab_dash, tab_q_dash, tab_annual, tab_data = st.tabs([
        "📥 إدخال البيانات", "📊 Dashboard الشهري", "📈 التقرير الربع سنوي", "📅 التقرير السنوي", "📄 البيانات"
    ])
    tab_debug = None

# ============================================================
# 📥 إدخال البيانات
# ============================================================
if tab_input is not None:
    with tab_input:
        st.header("📥 إدخال البيانات")
        
        c1, c2 = st.columns(2)
        with c1:
            month = st.selectbox("الشهر", MONTHS, key="m_month")
        with c2:
            year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="m_year")
        
        fp = get_fiscal_period(month, year)
        period_val = f"{month} {year}"
        
        info_cols = st.columns(4)
        info_cols[0].info(f"🗓️ **{month} {year}**")
        info_cols[1].info(f"💰 السنة المالية: **{fp['fiscal_year']}**")
        info_cols[2].info(f"📅 يُنشئ: **{fp['quarter'] if fp['quarter'] else 'لا يوجد'}**")
        info_cols[3].info(f"📊 يُنشئ: **{fp['half'] if fp['half'] else 'لا يوجد'}**")
        
        if fp["quarter"]:
            months_str = " + ".join([f"{m} {y}" for m, y in fp["months_for_quarter"]])
            st.success(f"🎯 هذا الشهر يُنشئ تقرير **{fp['quarter']}** للفترة: **{months_str}**")
        
        st.divider()
        st.markdown("## 📋 القوائم الشهرية")
        st.caption("يتم احتساب الأرقام تلقائياً. الأعمدة ذات القوائم المنسدلة محددة بـ ▾")
        
        list_tabs = st.tabs([cfg["title"] for cfg in MONTHLY_LISTS.values()])
        
        for idx, (sheet_name, cfg) in enumerate(MONTHLY_LISTS.items()):
            with list_tabs[idx]:
                st.markdown(f"### {cfg['title']}")
                if cfg["hint"]:
                    st.info(f"💡 {cfg['hint']}")
                
                save_key = f"_saved_{sheet_name}_{st.session_state.institute}_{period_val}"
                if save_key in st.session_state:
                    data_clean = st.session_state[save_key].copy()
                    for col in cfg["cols"]:
                        if col not in data_clean.columns:
                            data_clean[col] = ""
                    data_clean = data_clean[cfg["cols"]]
                    st.info(f"💾 {len(data_clean)} صف من الذاكرة المؤقتة")
                else:
                    full_cols = cfg["cols"] + ["المعهد", "الفترة"]
                    data = load_sheet(sheet_name, full_cols)
                    if not data.empty and "المعهد" in data.columns and "الفترة" in data.columns:
                        data = data[(data["المعهد"] == st.session_state.institute) & (data["الفترة"] == period_val)]
                    if data.empty:
                        data_clean = pd.DataFrame(columns=cfg["cols"])
                        st.caption("📝 لا توجد بيانات محفوظة")
                    else:
                        data_clean = data.reindex(columns=cfg["cols"]).fillna("").reset_index(drop=True)
                        st.success(f"✅ تم استرجاع {len(data_clean)} صف")
                
                editor_key = f"{sheet_name}_ed_{period_val}_{st.session_state.editor_counter}"
                
                if not data_clean.empty:
                    display_df = rtl_display(data_clean)
                else:
                    display_df = pd.DataFrame(columns=list(reversed(cfg["cols"])))
                
                column_config = {}
                for col_name, options in cfg.get("dropdowns", {}).items():
                    column_config[col_name] = st.column_config.SelectboxColumn(
                        col_name, options=options, required=False, help=f"اختر من: {' / '.join(options)}"
                    )
                
                input_rtl = st.data_editor(
                    display_df, num_rows="dynamic", use_container_width=True,
                    key=editor_key, hide_index=True, column_config=column_config
                )
                
                if not input_rtl.empty:
                    input_df = input_rtl.reindex(columns=cfg["cols"]).fillna("")
                else:
                    input_df = pd.DataFrame(columns=cfg["cols"])
                
                if st.button(f"💾 حفظ {cfg['title']}", key=f"{sheet_name}_sv"):
                    if save_list(sheet_name, input_df, cfg["cols"], st.session_state.institute, "الفترة", period_val):
                        st.session_state.editor_counter = st.session_state.get("editor_counter", 0) + 1
                        st.success(f"✅ تم الحفظ - المعاينة ستُحدَّث فوراً")
                        st.balloons()
                        time.sleep(0.3)
                        st.rerun()
        
        # المدخلات الربع سنوية
        if fp["is_quarter_month"]:
            st.divider()
            st.markdown(f"## 📊 المدخلات الربع سنوية — {fp['quarter']}")
            df_q = load_sheet("البيانات_الربع_سنوية", QUARTERLY_COLUMNS)
            df_q_filtered = pd.DataFrame()
            if not df_q.empty and "المعهد" in df_q.columns:
                df_q_filtered = df_q[(df_q["المعهد"] == st.session_state.institute) & (df_q["الربع"] == fp["quarter"]) & (df_q["السنة المالية"] == fp["fiscal_year"])]
            existing = df_q_filtered.iloc[0] if not df_q_filtered.empty else None
            
            def qv(col, default=0):
                if existing is None or col not in existing.index: return default
                try: return int(float(existing[col])) if existing[col] and str(existing[col]) not in ["", "nan"] else default
                except: return default
            
            def qvf(col, default=0.0):
                if existing is None or col not in existing.index: return default
                try: return float(existing[col]) if existing[col] and str(existing[col]) not in ["", "nan"] else default
                except: return default
            
            kp = f"{fp['quarter']}_{fp['fiscal_year']}".replace("/", "_").replace(" ", "_")
            
            c1, c2, c3, c4 = st.columns(4)
            q_res = c1.number_input("عدد الباحثين", min_value=0, value=qv("عدد الباحثين"), key=f"q_res_{kp}")
            q_prof = c2.number_input("عدد الأساتذة بدون المتفرغين", min_value=0, value=qv("عدد الأساتذة بدون المتفرغين"), key=f"q_prof_{kp}")
            q_eng = c3.number_input("عدد المهندسين", min_value=0, value=qv("عدد المهندسين"), key=f"q_eng_{kp}")
            q_total = c4.number_input("إجمالي عدد العاملين", min_value=0, value=qv("إجمالي عدد العاملين"), key=f"q_total_{kp}")
            
            c1, c2, c3, c4 = st.columns(4)
            q_budget = c1.number_input("المنصرف من الموازنة الاستثمارية", min_value=0.0, value=qvf("المبلغ المنصرف من الموازنة الاستثمارية"), format="%.2f", key=f"q_bud_{kp}")
            q_periodic = c2.number_input("عدد الاجتماعات الدورية", min_value=0, value=qv("عدد الاجتماعات الدورية"), key=f"q_pm_{kp}")
            q_board = c3.number_input("عدد اجتماعات مجلس الإدارة", min_value=0, value=qv("عدد اجتماعات مجلس الإدارة"), key=f"q_bm_{kp}")
            q_think = c4.number_input("عدد اجتماعات وحدة الفكر", min_value=0, value=qv("عدد اجتماعات وحدة الفكر"), key=f"q_tk_{kp}")
            
            q_notes = st.text_area("ملاحظات", value=str(existing["ملاحظات"]) if existing is not None and "ملاحظات" in existing.index else "", key=f"q_nt_{kp}")
            
            if st.button("💾 حفظ البيانات الربع سنوية", type="primary", key="save_q"):
                q_data = {
                    "المعهد": st.session_state.institute, "المستخدم": st.session_state.username,
                    "الربع": fp["quarter"], "السنة المالية": fp["fiscal_year"],
                    "عدد الباحثين": q_res, "عدد الأساتذة بدون المتفرغين": q_prof,
                    "عدد المهندسين": q_eng, "إجمالي عدد العاملين": q_total,
                    "المبلغ المنصرف من الموازنة الاستثمارية": q_budget,
                    "عدد الاجتماعات الدورية": q_periodic, "عدد اجتماعات مجلس الإدارة": q_board,
                    "عدد اجتماعات وحدة الفكر": q_think, "ملاحظات": q_notes,
                }
                result = save_or_update_row("البيانات_الربع_سنوية", QUARTERLY_COLUMNS, q_data, ["المعهد", "الربع", "السنة المالية"])
                if result:
                    invalidate_all()
                    st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} البيانات")
                    time.sleep(0.5)
                    st.rerun()
        
        # المدخلات النصف سنوية
        if fp["is_half_month"]:
            st.divider()
            st.markdown(f"## 📊 المدخلات النصف سنوية — {fp['half']}")
            df_h = load_sheet("البيانات_النصف_سنوية", HALF_COLUMNS)
            df_h_f = pd.DataFrame()
            if not df_h.empty and "المعهد" in df_h.columns:
                df_h_f = df_h[(df_h["المعهد"] == st.session_state.institute) & (df_h["النصف"] == fp["half"]) & (df_h["السنة المالية"] == fp["fiscal_year"])]
            existing_h = df_h_f.iloc[0] if not df_h_f.empty else None
            
            def hv(col, default=0):
                if existing_h is None or col not in existing_h.index: return default
                try: return int(float(existing_h[col])) if existing_h[col] and str(existing_h[col]) not in ["", "nan"] else default
                except: return default
            
            def hvf(col, default=0.0):
                if existing_h is None or col not in existing_h.index: return default
                try: return float(existing_h[col]) if existing_h[col] and str(existing_h[col]) not in ["", "nan"] else default
                except: return default
            
            kp_h = f"{fp['half']}_{fp['fiscal_year']}".replace("/", "_").replace(" ", "_")
            c1, c2 = st.columns(2)
            h_studies = c1.number_input("إجمالي دراسات الخطة البحثية المنجزة", min_value=0, value=hv("إجمالي عدد دراسات الخطة البحثية المنجزة"), key=f"h_st_{kp_h}")
            h_outputs = c2.number_input("إجمالي المخرجات التطبيقية", min_value=0, value=hv("إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات"), key=f"h_out_{kp_h}")
            h_revenue = st.number_input("إجمالي الإيرادات الذاتية", min_value=0.0, value=hvf("إجمالي مبلغ الإيرادات الذاتية"), format="%.2f", key=f"h_rev_{kp_h}")
            
            if st.button("💾 حفظ البيانات النصف سنوية", type="primary", key="save_h"):
                h_data = {
                    "المعهد": st.session_state.institute, "المستخدم": st.session_state.username,
                    "النصف": fp["half"], "السنة المالية": fp["fiscal_year"],
                    "إجمالي عدد دراسات الخطة البحثية المنجزة": h_studies,
                    "إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات": h_outputs,
                    "إجمالي مبلغ الإيرادات الذاتية": h_revenue,
                }
                result = save_or_update_row("البيانات_النصف_سنوية", HALF_COLUMNS, h_data, ["المعهد", "النصف", "السنة المالية"])
                if result:
                    invalidate_all()
                    st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} البيانات")
                    time.sleep(0.5)
                    st.rerun()
        
        # المدخلات السنوية
        if fp["is_annual_month"]:
            st.divider()
            st.markdown("## 📊 المدخلات السنوية")
            df_a = load_sheet("البيانات_السنوية", ANNUAL_COLUMNS)
            df_a_f = pd.DataFrame()
            if not df_a.empty and "المعهد" in df_a.columns:
                df_a_f = df_a[(df_a["المعهد"] == st.session_state.institute) & (df_a["السنة المالية"] == fp["fiscal_year"])]
            existing_a = df_a_f.iloc[0] if not df_a_f.empty else None
            
            def av(col, default=0):
                if existing_a is None or col not in existing_a.index: return default
                try: return int(float(existing_a[col])) if existing_a[col] and str(existing_a[col]) not in ["", "nan"] else default
                except: return default
            
            a_patents = st.number_input("عدد براءات الاختراع", min_value=0, value=av("عدد براءات الاختراع"), key=f"a_pat_{fp['fiscal_year'].replace('/', '_')}")
            
            if st.button("💾 حفظ البيانات السنوية", type="primary", key="save_a"):
                a_data = {
                    "المعهد": st.session_state.institute, "المستخدم": st.session_state.username,
                    "السنة المالية": fp["fiscal_year"], "عدد براءات الاختراع": a_patents,
                }
                result = save_or_update_row("البيانات_السنوية", ANNUAL_COLUMNS, a_data, ["المعهد", "السنة المالية"])
                if result:
                    invalidate_all()
                    st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} البيانات")
                    time.sleep(0.5)
                    st.rerun()
        
        # المعاينة
        st.divider()
        st.markdown("## 📊 معاينة الأرقام المحسوبة تلقائياً")
        kpi_preview = compute_kpi_from_lists(st.session_state.institute, month, year)
        
        period_check = f"{month} {year}"
        saved_count = sum(1 for k in st.session_state.keys() if k.startswith("_saved_") and period_check in k)
        if saved_count > 0:
            st.success(f"🔵 مصدر البيانات: {saved_count} قائمة محفوظة مؤقتاً — آخر حفظ: {st.session_state.get('last_save_time', '')}")
        else:
            st.info(f"⚪ مصدر البيانات: Google Sheets")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📚 إجمالي الدراسات", kpi_preview["إجمالي الدراسات الجارية"])
        c2.metric("📄 إجمالي التقارير", kpi_preview["إجمالي التقارير"])
        c3.metric("📋 إجمالي المقترحات", kpi_preview["إجمالي المقترحات"])
        c4.metric("🤝 إجمالي الاجتماعات", kpi_preview["إجمالي الاجتماعات"])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏃 أيام المأموريات", kpi_preview["إجمالي عدد الأيام الفعلية"])
        c2.metric("👨‍🎓 المتدربين", kpi_preview["متدربين"])
        c3.metric("📝 الأوراق المنشورة", kpi_preview["الأوراق المنشورة"])
        c4.metric("🎓 الرسائل المنتهية", kpi_preview["الرسائل المنتهية"])
        
        with st.expander("📋 تفاصيل جميع المؤشرات"):
            detail_df = pd.DataFrame([kpi_preview]).T
            detail_df.columns = ["القيمة"]
            detail_df.index.name = "المؤشر"
            st.dataframe(detail_df, use_container_width=True)
        
        if st.button("💾 حفظ/تحديث مؤشرات الأداء الشهرية", type="primary", key="save_kpi"):
            kpi_data = {
                "المعهد": st.session_state.institute, "المستخدم": st.session_state.username,
                "الشهر": month, "السنة": int(year),
            }
            kpi_data.update(kpi_preview)
            result = save_or_update_row("KPI_Data", KPI_COLUMNS, kpi_data, ["المعهد", "الشهر", "السنة"])
            if result:
                invalidate_all()
                st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} مؤشرات الأداء")
                st.balloons()
                time.sleep(0.5)
                st.rerun()
        
        st.divider()
        st.markdown("## 📥 تصدير التقرير الشهري")
        if st.button("📄 توليد التقرير الشهري (Word)", key="gen_monthly_docx"):
            with st.spinner("جاري التوليد..."):
                try:
                    docx_bytes = generate_monthly_report(st.session_state.institute, month, year)
                    st.download_button(
                        label="⬇️ تحميل التقرير الشهري",
                        data=docx_bytes,
                        file_name=f"تقرير_{st.session_state.institute}_{month}_{year}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_monthly"
                    )
                except Exception as e:
                    st.error(f"خطأ: {e}")

# ============================================================
# 📊 Dashboard الشهري
# ============================================================
if 'tab_dash' in dir() and tab_dash is not None:
    with tab_dash:
        st.title("📊 Dashboard الشهري")
        df_m = load_sheet("KPI_Data", KPI_COLUMNS)
        if not df_m.empty and st.session_state.role != "admin" and "المعهد" in df_m.columns:
            df_m = df_m[df_m["المعهد"] == st.session_state.institute]
        
        if df_m.empty:
            st.info("📭 لا توجد بيانات - ابدأ بإدخال البيانات من تبويب (إدخال البيانات)")
        else:
            text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
            for col in df_m.columns:
                if col not in text_cols:
                    df_m[col] = pd.to_numeric(df_m[col], errors="coerce").fillna(0)
            
            st.subheader("🎯 مؤشرات رئيسية")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("📚 الدراسات", int(df_m["إجمالي الدراسات الجارية"].sum()))
            c2.metric("📄 التقارير", int(df_m["إجمالي التقارير"].sum()))
            c3.metric("📋 المقترحات", int(df_m["إجمالي المقترحات"].sum()))
            c4.metric("🤝 الاجتماعات", int(df_m["إجمالي الاجتماعات"].sum()))
            c5.metric("👨‍🎓 المتدربين", int(df_m["متدربين"].sum()))
            
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏃 المأموريات", int(df_m["إجمالي عدد المأموريات"].sum()))
            c2.metric("🔍 المعاينات", int(df_m["إجمالي عدد المعاينات"].sum()))
            c3.metric("📝 الأوراق", int(df_m["إجمالي الأوراق البحثية"].sum()))
            c4.metric("🎓 الرسائل", int(df_m["إجمالي الرسائل"].sum()))
            
            st.divider()
            if "المعهد" in df_m.columns and df_m["المعهد"].nunique() > 0:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 📚 الدراسات")
                    fig = px.bar(df_m, x="المعهد", y=["خطة بحثية", "استشارية", "دراسات بتمويل ذاتي"], barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 📄 التقارير")
                    fig = px.bar(df_m, x="المعهد", y=["تقرير مرحلي", "تقرير نهائي", "تقرير معاينة", "تقرير معايرة"], barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🤝 الاجتماعات")
                    fig = px.bar(df_m, x="المعهد", y=["اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية", "اجتماعات مع العاملين", "اجتماعات جهات أخرى"], barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 👥 التدريب")
                    fig = px.bar(df_m, x="المعهد", y=["متدربين", "مدربين"], barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            st.markdown("### 📄 البيانات التفصيلية")
            st.dataframe(rtl_display(df_m), use_container_width=True, hide_index=True)

# ============================================================
# 📈 التقرير الربع سنوي
# ============================================================
if tab_q_dash is not None:
    with tab_q_dash:
        st.title("📈 التقرير الربع سنوي")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            sel_q = st.selectbox("الربع", ["الربع الأول", "الربع الثاني", "الربع الثالث", "الربع الرابع"], key="report_q")
        with c2:
            sel_fy = st.selectbox("السنة المالية", ["2025/2026", "2026/2027", "2027/2028"], key="report_fy")
        with c3:
            if st.session_state.role == "admin":
                kpi_all = load_sheet("KPI_Data", KPI_COLUMNS)
                institutes = ["الكل"] + (sorted(kpi_all["المعهد"].unique()) if not kpi_all.empty and "المعهد" in kpi_all.columns else [])
                sel_inst = st.selectbox("المعهد", institutes, key="report_inst")
            else:
                sel_inst = st.session_state.institute
        
        fy_start = int(sel_fy.split("/")[0])
        fy_end = int(sel_fy.split("/")[1])
        
        if sel_q == "الربع الأول": q_months = [("يوليو", fy_start), ("أغسطس", fy_start), ("سبتمبر", fy_start)]
        elif sel_q == "الربع الثاني": q_months = [("أكتوبر", fy_start), ("نوفمبر", fy_start), ("ديسمبر", fy_start)]
        elif sel_q == "الربع الثالث": q_months = [("يناير", fy_end), ("فبراير", fy_end), ("مارس", fy_end)]
        else: q_months = [("أبريل", fy_end), ("مايو", fy_end), ("يونيو", fy_end)]
        
        st.info(f"📅 يشمل: {' + '.join([f'{m} {y}' for m, y in q_months])}")
        
        kpi_df = load_sheet("KPI_Data", KPI_COLUMNS)
        if kpi_df.empty:
            st.warning("لا توجد بيانات شهرية")
        else:
            if sel_inst != "الكل":
                kpi_df = kpi_df[kpi_df["المعهد"] == sel_inst]
            elif st.session_state.role != "admin":
                kpi_df = kpi_df[kpi_df["المعهد"] == st.session_state.institute]
            
            mask = pd.Series([False] * len(kpi_df), index=kpi_df.index)
            for m, y in q_months:
                mask |= ((kpi_df["الشهر"] == m) & (kpi_df["السنة"] == str(y)))
            q_df = kpi_df[mask].copy()
            
            if q_df.empty:
                st.warning(f"لا توجد بيانات لهذا الربع")
            else:
                text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
                for col in q_df.columns:
                    if col not in text_cols:
                        q_df[col] = pd.to_numeric(q_df[col], errors="coerce").fillna(0)
                
                st.markdown("## 📊 ملخص الربع")
                agg = q_df.groupby("المعهد").sum(numeric_only=True).reset_index()
                
                st.subheader("🎯 المؤشرات الرئيسية")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("📚 الدراسات", int(agg["إجمالي الدراسات الجارية"].sum()))
                c2.metric("📄 التقارير", int(agg["إجمالي التقارير"].sum()))
                c3.metric("📋 المقترحات", int(agg["إجمالي المقترحات"].sum()))
                c4.metric("🤝 الاجتماعات", int(agg["إجمالي الاجتماعات"].sum()))
                c5.metric("👨‍🎓 المتدربين", int(agg["متدربين"].sum()))
                
                df_q_data = load_sheet("البيانات_الربع_سنوية", QUARTERLY_COLUMNS)
                if not df_q_data.empty and "الربع" in df_q_data.columns:
                    df_q_data = df_q_data[(df_q_data["الربع"] == sel_q) & (df_q_data["السنة المالية"] == sel_fy)]
                    if sel_inst != "الكل": df_q_data = df_q_data[df_q_data["المعهد"] == sel_inst]
                    elif st.session_state.role != "admin": df_q_data = df_q_data[df_q_data["المعهد"] == st.session_state.institute]
                    
                    if not df_q_data.empty:
                        st.markdown("## 👥 إحصائيات الكادر البحثي")
                        for _, row in df_q_data.iterrows():
                            with st.expander(f"🏢 {row['المعهد']}", expanded=True):
                                c1, c2, c3, c4 = st.columns(4)
                                c1.metric("👨‍🔬 الباحثين", row.get("عدد الباحثين", 0))
                                c2.metric("🎓 الأساتذة", row.get("عدد الأساتذة بدون المتفرغين", 0))
                                c3.metric("⚙️ المهندسين", row.get("عدد المهندسين", 0))
                                c4.metric("👥 إجمالي العاملين", row.get("إجمالي عدد العاملين", 0))
                                c1, c2, c3, c4 = st.columns(4)
                                c1.metric("💰 المنصرف من الموازنة", f"{float(row.get('المبلغ المنصرف من الموازنة الاستثمارية', 0) or 0):.2f}")
                                c2.metric("📅 اجتماعات دورية", row.get("عدد الاجتماعات الدورية", 0))
                                c3.metric("🏛️ مجلس الإدارة", row.get("عدد اجتماعات مجلس الإدارة", 0))
                                c4.metric("💡 وحدة الفكر", row.get("عدد اجتماعات وحدة الفكر", 0))
                
                half_to_show = None
                if sel_q == "الربع الثاني": half_to_show = "النصف الأول"
                elif sel_q == "الربع الرابع": half_to_show = "النصف الثاني"
                
                if half_to_show:
                    st.markdown(f"## 📊 البيانات النصف سنوية — {half_to_show}")
                    df_h = load_sheet("البيانات_النصف_سنوية", HALF_COLUMNS)
                    if not df_h.empty and "النصف" in df_h.columns:
                        df_h = df_h[(df_h["السنة المالية"] == sel_fy) & (df_h["النصف"] == half_to_show)]
                        if sel_inst != "الكل": df_h = df_h[df_h["المعهد"] == sel_inst]
                        elif st.session_state.role != "admin": df_h = df_h[df_h["المعهد"] == st.session_state.institute]
                        if not df_h.empty:
                            for _, row in df_h.iterrows():
                                with st.expander(f"🏢 {row['المعهد']}", expanded=False):
                                    c1, c2, c3 = st.columns(3)
                                    c1.metric("📚 الدراسات المنجزة", row.get("إجمالي عدد دراسات الخطة البحثية المنجزة", 0))
                                    c2.metric("🔬 المخرجات التطبيقية", row.get("إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات", 0))
                                    c3.metric("💰 الإيرادات الذاتية", f"{float(row.get('إجمالي مبلغ الإيرادات الذاتية', 0) or 0):.2f}")
                
                if sel_q == "الربع الرابع":
                    st.markdown("## 📊 البيانات السنوية")
                    df_a = load_sheet("البيانات_السنوية", ANNUAL_COLUMNS)
                    if not df_a.empty and "السنة المالية" in df_a.columns:
                        df_a = df_a[df_a["السنة المالية"] == sel_fy]
                        if sel_inst != "الكل": df_a = df_a[df_a["المعهد"] == sel_inst]
                        elif st.session_state.role != "admin": df_a = df_a[df_a["المعهد"] == st.session_state.institute]
                        if not df_a.empty:
                            for _, row in df_a.iterrows():
                                with st.expander(f"🏢 {row['المعهد']}", expanded=False):
                                    st.metric("🔬 براءات الاختراع", row.get("عدد براءات الاختراع", 0))
                
                st.divider()
                st.markdown("## 📄 الجدول الشامل")
                st.dataframe(rtl_display(q_df), use_container_width=True, hide_index=True)
                
                st.divider()
                st.markdown("## 📥 تصدير التقرير الربع سنوي")
                if st.button("📄 توليد التقرير (Word)", key="gen_quarterly_docx"):
                    with st.spinner("جاري التوليد..."):
                        try:
                            inst_to_report = st.session_state.institute if st.session_state.role != "admin" or sel_inst == "الكل" else sel_inst
                            docx_bytes = generate_quarterly_report(inst_to_report, sel_q, sel_fy)
                            st.download_button(
                                label="⬇️ تحميل التقرير الربع سنوي",
                                data=docx_bytes,
                                file_name=f"تقرير_{inst_to_report}_{sel_q}_{sel_fy}.docx".replace("/", "_"),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="dl_quarterly"
                            )
                        except Exception as e:
                            st.error(f"خطأ: {e}")

# ============================================================
# 📅 التقرير السنوي
# ============================================================
if tab_annual is not None:
    with tab_annual:
        st.title("📅 التقرير السنوي")
        
        c1, c2 = st.columns(2)
        with c1:
            annual_fy = st.selectbox("السنة المالية", ["2025/2026", "2026/2027", "2027/2028"], key="annual_fy")
        with c2:
            if st.session_state.role == "admin":
                kpi_check = load_sheet("KPI_Data", KPI_COLUMNS)
                inst_opts = ["الكل"] + (sorted(kpi_check["المعهد"].unique()) if not kpi_check.empty and "المعهد" in kpi_check.columns else [])
                annual_inst = st.selectbox("المعهد", inst_opts, key="annual_inst")
            else:
                annual_inst = st.session_state.institute
        
        st.markdown("## 📊 معاينة البيانات السنوية")
        fy_start = int(annual_fy.split("/")[0])
        fy_end = int(annual_fy.split("/")[1])
        fy_months_all = [
            ("يوليو", fy_start), ("أغسطس", fy_start), ("سبتمبر", fy_start),
            ("أكتوبر", fy_start), ("نوفمبر", fy_start), ("ديسمبر", fy_start),
            ("يناير", fy_end), ("فبراير", fy_end), ("مارس", fy_end),
            ("أبريل", fy_end), ("مايو", fy_end), ("يونيو", fy_end),
        ]
        
        kpi_ann = load_sheet("KPI_Data", KPI_COLUMNS)
        if kpi_ann.empty:
            st.warning("لا توجد بيانات")
        else:
            if annual_inst != "الكل": kpi_ann = kpi_ann[kpi_ann["المعهد"] == annual_inst]
            elif st.session_state.role != "admin": kpi_ann = kpi_ann[kpi_ann["المعهد"] == st.session_state.institute]
            
            mask = pd.Series([False]*len(kpi_ann), index=kpi_ann.index)
            for m, y in fy_months_all:
                mask |= ((kpi_ann["الشهر"] == m) & (kpi_ann["السنة"] == str(y)))
            ann_df = kpi_ann[mask].copy()
            
            if ann_df.empty:
                st.info(f"لا توجد بيانات للسنة المالية {annual_fy}")
            else:
                text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
                for col in ann_df.columns:
                    if col not in text_cols:
                        ann_df[col] = pd.to_numeric(ann_df[col], errors="coerce").fillna(0)
                
                agg_ann = ann_df.groupby("المعهد").sum(numeric_only=True).reset_index()
                st.subheader("🎯 ملخص المؤشرات السنوية")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("📚 الدراسات", int(agg_ann["إجمالي الدراسات الجارية"].sum()))
                c2.metric("📄 التقارير", int(agg_ann["إجمالي التقارير"].sum()))
                c3.metric("📋 المقترحات", int(agg_ann["إجمالي المقترحات"].sum()))
                c4.metric("🤝 الاجتماعات", int(agg_ann["إجمالي الاجتماعات"].sum()))
                c5.metric("👨‍🎓 المتدربين", int(agg_ann["متدربين"].sum()))
                
                st.divider()
                st.markdown("### 📥 تصدير التقرير السنوي (Excel)")
                if st.button("📊 توليد التقرير السنوي", key="gen_annual_xlsx"):
                    with st.spinner("جاري التوليد..."):
                        try:
                            inst_to_export = annual_inst if annual_inst != "الكل" else st.session_state.institute
                            xlsx_bytes = generate_annual_report_excel(inst_to_export, annual_fy)
                            fname = f"تقرير_سنوي_{inst_to_export}_{annual_fy}.xlsx".replace("/", "_")
                            st.download_button(
                                label="⬇️ تحميل التقرير السنوي",
                                data=xlsx_bytes,
                                file_name=fname,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_annual"
                            )
                        except Exception as e:
                            st.error(f"خطأ: {e}")

# ============================================================
# 📄 البيانات
# ============================================================
if tab_data is not None:
    with tab_data:
        st.title("📄 البيانات المجمّعة")
        kpi_df = load_sheet("KPI_Data", KPI_COLUMNS)
        if not kpi_df.empty and st.session_state.role != "admin" and "المعهد" in kpi_df.columns:
            kpi_df = kpi_df[kpi_df["المعهد"] == st.session_state.institute]
        
        if kpi_df.empty:
            st.info("📭 لا توجد بيانات")
        else:
            st.markdown("### 📊 بيانات KPI الشهرية")
            st.dataframe(rtl_display(kpi_df), use_container_width=True, hide_index=True)
            def to_excel(d):
                out = BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as w:
                    d.to_excel(w, index=False, sheet_name="Data")
                return out.getvalue()
            st.download_button("📥 تحميل Excel", data=to_excel(kpi_df),
                              file_name=f"kpi_data_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# 🔧 تشخيص
# ============================================================
if tab_debug is not None:
    with tab_debug:
        st.title("🔧 تشخيص البيانات")
        st.markdown("### 📋 حالة الأوراق")
        sheets_to_check = ["KPI_Data", "البيانات_الربع_سنوية", "البيانات_النصف_سنوية", "البيانات_السنوية"] + list(MONTHLY_LISTS.keys())
        for sname in sheets_to_check:
            try:
                all_v = fetch_data(sname)
                rows_count = max(0, len(all_v) - 1) if all_v else 0
                status = "✅" if rows_count > 0 else "⚠️"
                st.write(f"{status} **{sname}** — {rows_count} صف بيانات")
            except Exception as e:
                st.write(f"❌ **{sname}** — خطأ: {e}")
        
        st.divider()
        st.write(f"**data_bust:** {st.session_state.get('data_bust', 0)}")
        st.write(f"**آخر حفظ:** {st.session_state.get('last_save_time', 'لا يوجد')}")
        st.write(f"**الوقت الحالي (+3):** {get_local_time()}")
