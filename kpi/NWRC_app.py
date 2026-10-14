import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from io import BytesIO
import streamlit as st
from datetime import datetime
import time

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

# ============================================================
# دوال Google Sheets
# ============================================================
SPREADSHEET_KEY = "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"

def col_letter(n):
    """تحويل رقم العمود (1-based) إلى حرف (A, B, ..., Z, AA, AB, ...)"""
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result

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

# ============================================================
# load_sheet
# ============================================================
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
        invalidate_all()
        return True
    except Exception as e:
        st.error(f"خطأ في الحفظ: {e}")
        return False

# ============================================================
# ⭐ دالة حفظ/تحديث KPI - النسخة المُصححة
# ============================================================
def save_or_update_row(sheet_name, all_cols, data_dict, key_cols):
    """حفظ أو تحديث صف بطريقة آمنة"""
    try:
        ws = get_or_create_sheet(sheet_name, all_cols)
        if ws is None:
            st.error(f"فشل الوصول للورقة {sheet_name}")
            return None
        
        all_v = ws.get_all_values()
        
        # إذا كانت الورقة فارغة
        if len(all_v) == 0:
            ws.append_row(all_cols)
            all_v = [all_cols]
        
        headers = all_v[0]
        
        # إذا كان فقط صف العناوين
        if len(all_v) == 1:
            new_row = [str(data_dict.get(c, "0")) for c in headers]
            ws.append_row(new_row)
            return "added"
        
        # البحث عن صف مطابق
        found_idx = None
        for i, r in enumerate(all_v[1:]):
            match = True
            for k in key_cols:
                if k not in headers:
                    match = False
                    break
                col_idx = headers.index(k)
                row_val = str(r[col_idx]) if col_idx < len(r) else ""
                if row_val != str(data_dict.get(k, "")):
                    match = False
                    break
            if match:
                found_idx = i
                break
        
        new_row = [str(data_dict.get(c, "0")) for c in headers]
        n_cols = len(headers)
        end_col = col_letter(n_cols)
        
        if found_idx is not None:
            # تحديث صف موجود
            row_num = found_idx + 2
            range_str = f"A{row_num}:{end_col}{row_num}"
            try:
                ws.update(range_name=range_str, values=[new_row])
                return "updated"
            except Exception as e1:
                # بديل: حذف الصف وإعادة الإضافة
                try:
                    ws.delete_rows(row_num)
                    ws.append_row(new_row)
                    return "updated"
                except Exception as e2:
                    st.error(f"فشل التحديث: {e1} | {e2}")
                    return None
        else:
            # إضافة صف جديد
            ws.append_row(new_row)
            return "added"
    except Exception as e:
        st.error(f"خطأ في الحفظ: {e}")
        return None

# ============================================================
# ثوابت
# ============================================================
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
          "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

T_RESEARCH = "خطة بحثية"
T_CONSULT = "استشارية"
T_PROJECTS = "مشروعات بحثية"
T_REP_PROGRESS = "تقرير مرحلي"
T_REP_FINAL = "تقرير نهائي"
T_PROP_CONSULT = "مقترحات دراسات استشارية"
T_PROP_PROJECTS = "مقترحات مشروعات بحثية"
T_TRAIN_IN = "داخل المعهد"
T_TRAIN_OUT = "خارج المعهد"
T_TRAIN_ONLINE = "Online"
T_ACT_CONF = "مؤتمر"
T_ACT_WORKSHOP = "ورشة عمل"
T_MEET_MINISTRY = "بالوزارة"
T_MEET_CENTER = "بالمركز"
T_MEET_EXTERNAL = "جهات خارجية"
T_PAPER_LOCAL = "محلية"
T_PAPER_INTL = "دولية"
T_THESIS_MASTER = "ماجستير"
T_THESIS_PHD = "دكتوراه"
T_TR_TYPE_COURSE = "دورة تدريبية"
T_TR_TYPE_WS = "ورشة عمل"
T_TR_TYPE_CONF = "مؤتمر"

# ============================================================
# الأعمدة
# ============================================================
KPI_COLUMNS = [
    "المعهد", "المستخدم", "الشهر", "السنة",
    "دراسات خطة بحثية جارية", "دراسات استشارية جارية", "مشروعات بحثية جارية",
    "إجمالي الدراسات الجارية",
    "تقرير مرحلي", "تقرير نهائي", "إجمالي التقارير",
    "المذكرات",
    "مقترحات دراسات استشارية", "مقترحات مشروعات بحثية", "إجمالي المقترحات",
    "إجمالي أيام المأموريات",
    "المتدربين", "المدربين",
    "أيام تدريب داخل المعهد", "أيام تدريب خارج المعهد",
    "مشتركين مؤتمرات", "مشتركين ورش عمل", "إجمالي المشاركين في أنشطة علمية",
    "اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية", "إجمالي الاجتماعات",
    "أوراق بحثية منشورة", "أوراق بحثية دولية منشورة",
    "رسائل ماجستير ودكتوراه منتهية",
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

ANNUAL_COLUMNS = [
    "المعهد", "المستخدم", "السنة المالية",
    "عدد براءات الاختراع",
]

LIST_STUDIES = ["م", "عنوان الدراسة", "النوع", "الجهة المستفيدة", "تاريخ البدء", "نسبة التنفيذ %", "ملاحظات"]
LIST_REPORTS = ["م", "عنوان التقرير", "النوع", "تاريخ الإصدار", "الجهة المستفيدة", "ملخص"]
LIST_MEMOS = ["م", "رقم المذكرة", "الموضوع", "التاريخ", "الجهة الموجه إليها"]
LIST_PROPOSALS = ["م", "عنوان المقترح", "النوع", "الجهة التمويل", "موقف المقترح", "ملاحظات"]
LIST_MISSIONS = ["م", "الموقع", "الغرض", "من تاريخ", "إلى تاريخ", "عدد الأيام", "الفريق"]
LIST_TRAINING = ["م", "عنوان البرنامج", "النوع", "المكان", "عدد المتدربين", "عدد المدربين", "عدد الأيام"]
LIST_ACTIVITIES = ["م", "النشاط", "النوع", "عدد المشاركين", "المكان", "التاريخ"]
LIST_MEETINGS = ["م", "التاريخ", "النوع", "الاسم", "الوظيفة", "المكان", "الغرض"]
LIST_PAPERS = ["م", "عنوان البحث", "المجلة", "النوع", "تاريخ النشر", "الباحث الرئيسي"]
LIST_THESES = ["م", "عنوان الرسالة", "النوع", "الباحث", "الجامعة", "تاريخ المناقشة"]

MONTHLY_LISTS = {
    "الدراسات_الجارية": {"title": "📚 الدراسات الجارية", "cols": LIST_STUDIES,
                         "hint": f"النوع: {T_RESEARCH} / {T_CONSULT} / {T_PROJECTS}"},
    "التقارير_الصادرة": {"title": "📄 التقارير الصادرة", "cols": LIST_REPORTS,
                         "hint": f"النوع: {T_REP_PROGRESS} / {T_REP_FINAL}"},
    "المذكرات_الصادرة": {"title": "📝 المذكرات الصادرة", "cols": LIST_MEMOS, "hint": ""},
    "المقترحات": {"title": "📋 المقترحات الفنية والمالية", "cols": LIST_PROPOSALS,
                  "hint": f"النوع: {T_PROP_CONSULT} / {T_PROP_PROJECTS}"},
    "المأموريات_الحقلية": {"title": "🏃 المأموريات الحقلية", "cols": LIST_MISSIONS,
                            "hint": "أدخل عدد الأيام لكل مأمورية"},
    "التدريب": {"title": "👥 التدريب", "cols": LIST_TRAINING,
                "hint": f"النوع: {T_TR_TYPE_COURSE} / {T_TR_TYPE_WS} / {T_TR_TYPE_CONF} — المكان: {T_TRAIN_IN} / {T_TRAIN_OUT} / {T_TRAIN_ONLINE}"},
    "الأنشطة_العلمية": {"title": "🔬 الأنشطة العلمية", "cols": LIST_ACTIVITIES,
                        "hint": f"النوع: {T_ACT_CONF} / {T_ACT_WORKSHOP}"},
    "الاجتماعات": {"title": "🤝 الاجتماعات", "cols": LIST_MEETINGS,
                   "hint": f"النوع: {T_MEET_MINISTRY} / {T_MEET_CENTER} / {T_MEET_EXTERNAL}"},
    "الأوراق_البحثية": {"title": "📝 الأوراق البحثية", "cols": LIST_PAPERS,
                        "hint": f"النوع: {T_PAPER_LOCAL} / {T_PAPER_INTL}"},
    "الرسائل_العلمية": {"title": "🎓 رسائل الماجستير والدكتوراه", "cols": LIST_THESES,
                        "hint": f"النوع: {T_THESIS_MASTER} / {T_THESIS_PHD}"},
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
        if month_idx >= 7:
            result["fiscal_year"] = f"{year}/{year + 1}"
        else:
            result["fiscal_year"] = f"{year - 1}/{year}"
    
    if month == "يناير":
        result["half"] = "النصف الأول"
        result["months_for_half"] = [
            ("يوليو", year - 1), ("أغسطس", year - 1), ("سبتمبر", year - 1),
            ("أكتوبر", year - 1), ("نوفمبر", year - 1), ("ديسمبر", year - 1)
        ]
    elif month == "يوليو":
        result["half"] = "النصف الثاني"
        result["months_for_half"] = [
            ("يناير", year), ("فبراير", year), ("مارس", year),
            ("أبريل", year), ("مايو", year), ("يونيو", year)
        ]
    
    return result

# ============================================================
# حساب KPI
# ============================================================
def compute_kpi_from_lists(institute, month, year):
    period = f"{month} {year}"
    kpi = {c: 0 for c in KPI_COLUMNS if c not in ["المعهد", "المستخدم", "الشهر", "السنة"]}
    
    def get_list(name):
        cols = MONTHLY_LISTS[name]["cols"] + ["المعهد", "الفترة"]
        df = load_sheet(name, cols)
        if df.empty or "المعهد" not in df.columns or "الفترة" not in df.columns:
            return pd.DataFrame()
        return df[(df["المعهد"] == institute) & (df["الفترة"] == period)]
    
    def to_num(series):
        return pd.to_numeric(series, errors="coerce").fillna(0)
    
    s = get_list("الدراسات_الجارية")
    if not s.empty and "النوع" in s.columns:
        kpi["دراسات خطة بحثية جارية"] = int((s["النوع"] == T_RESEARCH).sum())
        kpi["دراسات استشارية جارية"] = int((s["النوع"] == T_CONSULT).sum())
        kpi["مشروعات بحثية جارية"] = int((s["النوع"] == T_PROJECTS).sum())
    kpi["إجمالي الدراسات الجارية"] = (kpi["دراسات خطة بحثية جارية"] +
                                       kpi["دراسات استشارية جارية"] +
                                       kpi["مشروعات بحثية جارية"])
    
    s = get_list("التقارير_الصادرة")
    if not s.empty and "النوع" in s.columns:
        kpi["تقرير مرحلي"] = int((s["النوع"] == T_REP_PROGRESS).sum())
        kpi["تقرير نهائي"] = int((s["النوع"] == T_REP_FINAL).sum())
    kpi["إجمالي التقارير"] = kpi["تقرير مرحلي"] + kpi["تقرير نهائي"]
    
    s = get_list("المذكرات_الصادرة")
    kpi["المذكرات"] = len(s) if not s.empty else 0
    
    s = get_list("المقترحات")
    if not s.empty and "النوع" in s.columns:
        kpi["مقترحات دراسات استشارية"] = int((s["النوع"] == T_PROP_CONSULT).sum())
        kpi["مقترحات مشروعات بحثية"] = int((s["النوع"] == T_PROP_PROJECTS).sum())
    kpi["إجمالي المقترحات"] = kpi["مقترحات دراسات استشارية"] + kpi["مقترحات مشروعات بحثية"]
    
    s = get_list("المأموريات_الحقلية")
    if not s.empty and "عدد الأيام" in s.columns:
        kpi["إجمالي أيام المأموريات"] = int(to_num(s["عدد الأيام"]).sum())
    
    s = get_list("التدريب")
    if not s.empty:
        if "عدد المتدربين" in s.columns:
            kpi["المتدربين"] = int(to_num(s["عدد المتدربين"]).sum())
        if "عدد المدربين" in s.columns:
            kpi["المدربين"] = int(to_num(s["عدد المدربين"]).sum())
        if "عدد الأيام" in s.columns and "المكان" in s.columns:
            days = to_num(s["عدد الأيام"])
            kpi["أيام تدريب داخل المعهد"] = int(days[s["المكان"] == T_TRAIN_IN].sum())
            kpi["أيام تدريب خارج المعهد"] = int(days[s["المكان"] == T_TRAIN_OUT].sum())
    
    s = get_list("الأنشطة_العلمية")
    if not s.empty and "عدد المشاركين" in s.columns:
        parts = to_num(s["عدد المشاركين"])
        kpi["مشتركين مؤتمرات"] = int(parts[s["النوع"] == T_ACT_CONF].sum())
        kpi["مشتركين ورش عمل"] = int(parts[s["النوع"] == T_ACT_WORKSHOP].sum())
    kpi["إجمالي المشاركين في أنشطة علمية"] = kpi["مشتركين مؤتمرات"] + kpi["مشتركين ورش عمل"]
    
    s = get_list("الاجتماعات")
    if not s.empty and "النوع" in s.columns:
        kpi["اجتماعات بالوزارة"] = int((s["النوع"] == T_MEET_MINISTRY).sum())
        kpi["اجتماعات بالمركز"] = int((s["النوع"] == T_MEET_CENTER).sum())
        kpi["اجتماعات جهات خارجية"] = int((s["النوع"] == T_MEET_EXTERNAL).sum())
    kpi["إجمالي الاجتماعات"] = (kpi["اجتماعات بالوزارة"] + kpi["اجتماعات بالمركز"] +
                                 kpi["اجتماعات جهات خارجية"])
    
    s = get_list("الأوراق_البحثية")
    if not s.empty and "النوع" in s.columns:
        kpi["أوراق بحثية منشورة"] = int((s["النوع"] == T_PAPER_LOCAL).sum())
        kpi["أوراق بحثية دولية منشورة"] = int((s["النوع"] == T_PAPER_INTL).sum())
    
    s = get_list("الرسائل_العلمية")
    kpi["رسائل ماجستير ودكتوراه منتهية"] = len(s) if not s.empty else 0
    
    return kpi

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

# ============================================================
# Session State
# ============================================================
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
                invalidate_all()
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
        invalidate_all()
        st.rerun()
with c_head[2]:
    if st.button("🚪 خروج"):
        st.session_state.clear()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# ============================================================
# Tabs
# ============================================================
if st.session_state.role == "admin":
    tab_dash, tab_q_dash, tab_data, tab_debug = st.tabs([
        "📊 Dashboard الشهري",
        "📈 التقرير الربع سنوي",
        "📄 البيانات",
        "🔧 تشخيص"
    ])
    tab_input = None
else:
    tab_input, tab_dash, tab_q_dash, tab_data = st.tabs([
        "📥 إدخال البيانات",
        "📊 Dashboard الشهري",
        "📈 التقرير الربع سنوي",
        "📄 البيانات"
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
        
        info_cols = st.columns(4)
        info_cols[0].info(f"🗓️ **{month} {year}**")
        info_cols[1].info(f"💰 السنة المالية: **{fp['fiscal_year']}**")
        if fp["quarter"]:
            info_cols[2].info(f"📅 يُنشئ تقرير: **{fp['quarter']}**")
        else:
            info_cols[2].info("📅 لا تقرير ربع سنوي هذا الشهر")
        if fp["half"]:
            info_cols[3].info(f"📊 يُنشئ: **{fp['half']}**")
        else:
            info_cols[3].info("")
        
        if fp["quarter"]:
            months_str = " + ".join([f"{m} {y}" for m, y in fp["months_for_quarter"]])
            st.success(f"🎯 هذا الشهر يُنشئ تقرير **{fp['quarter']}** للفترة: **{months_str}**")
        
        period_val = f"{month} {year}"
        st.divider()
        
        st.markdown("## 📋 القوائم الشهرية")
        st.caption("يتم احتساب الأرقام تلقائياً من البيانات المُدخلة")
        
        list_tabs = st.tabs([cfg["title"] for cfg in MONTHLY_LISTS.values()])
        
        for idx, (sheet_name, cfg) in enumerate(MONTHLY_LISTS.items()):
            with list_tabs[idx]:
                st.markdown(f"### {cfg['title']}")
                if cfg["hint"]:
                    st.info(f"💡 {cfg['hint']}")
                
                full_cols = cfg["cols"] + ["المعهد", "الفترة"]
                data = load_sheet(sheet_name, full_cols)
                
                if not data.empty and "المعهد" in data.columns and "الفترة" in data.columns:
                    data = data[(data["المعهد"] == st.session_state.institute) &
                                (data["الفترة"] == period_val)]
                
                if data.empty:
                    data_clean = pd.DataFrame(columns=cfg["cols"])
                    st.caption("📝 لا توجد بيانات محفوظة - أضف صفوفاً جديدة")
                else:
                    data_clean = data.reindex(columns=cfg["cols"]).fillna("").reset_index(drop=True)
                    st.success(f"✅ تم استرجاع {len(data_clean)} صف")
                
                editor_key = f"{sheet_name}_ed_{period_val}_{st.session_state.editor_counter}"
                
                if not data_clean.empty:
                    display_df = rtl_display(data_clean)
                else:
                    display_df = pd.DataFrame(columns=list(reversed(cfg["cols"])))
                
                input_rtl = st.data_editor(
                    display_df, num_rows="dynamic", use_container_width=True,
                    key=editor_key, hide_index=True
                )
                
                if not input_rtl.empty:
                    input_df = input_rtl.reindex(columns=cfg["cols"]).fillna("")
                else:
                    input_df = pd.DataFrame(columns=cfg["cols"])
                
                if st.button(f"💾 حفظ {cfg['title']}", key=f"{sheet_name}_sv"):
                    if save_list(sheet_name, input_df, cfg["cols"],
                                 st.session_state.institute, "الفترة", period_val):
                        st.session_state.editor_counter = st.session_state.get("editor_counter", 0) + 1
                        st.success("✅ تم الحفظ")
                        st.balloons()
                        time.sleep(0.5)
                        st.rerun()
        
        # المدخلات الربع سنوية
        if fp["is_quarter_month"]:
            st.divider()
            st.markdown(f"## 📊 المدخلات الربع سنوية — {fp['quarter']}")
            
            df_q = load_sheet("البيانات_الربع_سنوية", QUARTERLY_COLUMNS)
            df_q_filtered = pd.DataFrame()
            if not df_q.empty and "المعهد" in df_q.columns and "الربع" in df_q.columns and "السنة المالية" in df_q.columns:
                df_q_filtered = df_q[(df_q["المعهد"] == st.session_state.institute) &
                                     (df_q["الربع"] == fp["quarter"]) &
                                     (df_q["السنة المالية"] == fp["fiscal_year"])]
            
            existing = df_q_filtered.iloc[0] if not df_q_filtered.empty else None
            
            def qv(col, default=0):
                if existing is None or col not in existing.index:
                    return default
                try:
                    v = existing[col]
                    return int(float(v)) if v and str(v) not in ["", "nan"] else default
                except Exception:
                    return default
            
            def qvf(col, default=0.0):
                if existing is None or col not in existing.index:
                    return default
                try:
                    v = existing[col]
                    return float(v) if v and str(v) not in ["", "nan"] else default
                except Exception:
                    return default
            
            kp = f"{fp['quarter']}_{fp['fiscal_year']}".replace("/", "_").replace(" ", "_")
            
            c1, c2, c3, c4 = st.columns(4)
            q_res = c1.number_input("عدد الباحثين", min_value=0, value=qv("عدد الباحثين"), key=f"q_res_{kp}")
            q_prof = c2.number_input("عدد الأساتذة بدون المتفرغين", min_value=0, value=qv("عدد الأساتذة بدون المتفرغين"), key=f"q_prof_{kp}")
            q_eng = c3.number_input("عدد المهندسين", min_value=0, value=qv("عدد المهندسين"), key=f"q_eng_{kp}")
            q_total = c4.number_input("إجمالي عدد العاملين", min_value=0, value=qv("إجمالي عدد العاملين"), key=f"q_total_{kp}")
            
            c1, c2, c3, c4 = st.columns(4)
            q_budget = c1.number_input("المنصرف من الموازنة الاستثمارية", min_value=0.0,
                                        value=qvf("المبلغ المنصرف من الموازنة الاستثمارية"),
                                        format="%.2f", key=f"q_bud_{kp}")
            q_periodic = c2.number_input("عدد الاجتماعات الدورية", min_value=0, value=qv("عدد الاجتماعات الدورية"), key=f"q_pm_{kp}")
            q_board = c3.number_input("عدد اجتماعات مجلس الإدارة", min_value=0, value=qv("عدد اجتماعات مجلس الإدارة"), key=f"q_bm_{kp}")
            q_think = c4.number_input("عدد اجتماعات وحدة الفكر", min_value=0, value=qv("عدد اجتماعات وحدة الفكر"), key=f"q_tk_{kp}")
            
            q_notes = st.text_area("ملاحظات", value=str(existing["ملاحظات"]) if existing is not None and "ملاحظات" in existing.index else "", key=f"q_nt_{kp}")
            
            if st.button("💾 حفظ البيانات الربع سنوية", type="primary", key="save_q"):
                q_data = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "الربع": fp["quarter"],
                    "السنة المالية": fp["fiscal_year"],
                    "عدد الباحثين": q_res,
                    "عدد الأساتذة بدون المتفرغين": q_prof,
                    "عدد المهندسين": q_eng,
                    "إجمالي عدد العاملين": q_total,
                    "المبلغ المنصرف من الموازنة الاستثمارية": q_budget,
                    "عدد الاجتماعات الدورية": q_periodic,
                    "عدد اجتماعات مجلس الإدارة": q_board,
                    "عدد اجتماعات وحدة الفكر": q_think,
                    "ملاحظات": q_notes,
                }
                result = save_or_update_row("البيانات_الربع_سنوية", QUARTERLY_COLUMNS, q_data,
                                            ["المعهد", "الربع", "السنة المالية"])
                if result:
                    invalidate_all()
                    st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} البيانات الربع سنوية")
                    time.sleep(0.5)
                    st.rerun()
        
        # المدخلات النصف سنوية
        if fp["is_half_month"]:
            st.divider()
            st.markdown(f"## 📊 المدخلات النصف سنوية — {fp['half']}")
            
            df_h = load_sheet("البيانات_النصف_سنوية", HALF_COLUMNS)
            df_h_f = pd.DataFrame()
            if not df_h.empty and "المعهد" in df_h.columns and "النصف" in df_h.columns and "السنة المالية" in df_h.columns:
                df_h_f = df_h[(df_h["المعهد"] == st.session_state.institute) &
                              (df_h["النصف"] == fp["half"]) &
                              (df_h["السنة المالية"] == fp["fiscal_year"])]
            
            existing_h = df_h_f.iloc[0] if not df_h_f.empty else None
            
            def hv(col, default=0):
                if existing_h is None or col not in existing_h.index:
                    return default
                try:
                    v = existing_h[col]
                    return int(float(v)) if v and str(v) not in ["", "nan"] else default
                except Exception:
                    return default
            
            def hvf(col, default=0.0):
                if existing_h is None or col not in existing_h.index:
                    return default
                try:
                    v = existing_h[col]
                    return float(v) if v and str(v) not in ["", "nan"] else default
                except Exception:
                    return default
            
            kp_h = f"{fp['half']}_{fp['fiscal_year']}".replace("/", "_").replace(" ", "_")
            
            c1, c2 = st.columns(2)
            h_studies = c1.number_input("إجمالي عدد دراسات الخطة البحثية المنجزة",
                                          min_value=0, value=hv("إجمالي عدد دراسات الخطة البحثية المنجزة"),
                                          key=f"h_st_{kp_h}")
            h_outputs = c2.number_input("إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات",
                                          min_value=0, value=hv("إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات"),
                                          key=f"h_out_{kp_h}")
            
            h_revenue = st.number_input("إجمالي مبلغ الإيرادات الذاتية",
                                          min_value=0.0, value=hvf("إجمالي مبلغ الإيرادات الذاتية"),
                                          format="%.2f", key=f"h_rev_{kp_h}")
            
            if st.button("💾 حفظ البيانات النصف سنوية", type="primary", key="save_h"):
                h_data = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "النصف": fp["half"],
                    "السنة المالية": fp["fiscal_year"],
                    "إجمالي عدد دراسات الخطة البحثية المنجزة": h_studies,
                    "إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات": h_outputs,
                    "إجمالي مبلغ الإيرادات الذاتية": h_revenue,
                }
                result = save_or_update_row("البيانات_النصف_سنوية", HALF_COLUMNS, h_data,
                                            ["المعهد", "النصف", "السنة المالية"])
                if result:
                    invalidate_all()
                    st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} البيانات النصف سنوية")
                    time.sleep(0.5)
                    st.rerun()
        
        # المدخلات السنوية
        if fp["is_annual_month"]:
            st.divider()
            st.markdown("## 📊 المدخلات السنوية")
            
            df_a = load_sheet("البيانات_السنوية", ANNUAL_COLUMNS)
            df_a_f = pd.DataFrame()
            if not df_a.empty and "المعهد" in df_a.columns and "السنة المالية" in df_a.columns:
                df_a_f = df_a[(df_a["المعهد"] == st.session_state.institute) &
                              (df_a["السنة المالية"] == fp["fiscal_year"])]
            
            existing_a = df_a_f.iloc[0] if not df_a_f.empty else None
            
            def av(col, default=0):
                if existing_a is None or col not in existing_a.index:
                    return default
                try:
                    v = existing_a[col]
                    return int(float(v)) if v and str(v) not in ["", "nan"] else default
                except Exception:
                    return default
            
            a_patents = st.number_input("عدد براءات الاختراع",
                                          min_value=0, value=av("عدد براءات الاختراع"),
                                          key=f"a_pat_{fp['fiscal_year'].replace('/', '_')}")
            
            if st.button("💾 حفظ البيانات السنوية", type="primary", key="save_a"):
                a_data = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "السنة المالية": fp["fiscal_year"],
                    "عدد براءات الاختراع": a_patents,
                }
                result = save_or_update_row("البيانات_السنوية", ANNUAL_COLUMNS, a_data,
                                            ["المعهد", "السنة المالية"])
                if result:
                    invalidate_all()
                    st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} البيانات السنوية")
                    time.sleep(0.5)
                    st.rerun()
        
        # معاينة الأرقام
        st.divider()
        st.markdown("## 📊 معاينة الأرقام المحسوبة تلقائياً")
        
        kpi_preview = compute_kpi_from_lists(st.session_state.institute, month, year)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📚 إجمالي الدراسات", kpi_preview["إجمالي الدراسات الجارية"])
        c2.metric("📄 إجمالي التقارير", kpi_preview["إجمالي التقارير"])
        c3.metric("📋 إجمالي المقترحات", kpi_preview["إجمالي المقترحات"])
        c4.metric("🤝 إجمالي الاجتماعات", kpi_preview["إجمالي الاجتماعات"])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏃 أيام المأموريات", kpi_preview["إجمالي أيام المأموريات"])
        c2.metric("👨‍🎓 المتدربين", kpi_preview["المتدربين"])
        c3.metric("📝 الأوراق المنشورة", kpi_preview["أوراق بحثية منشورة"])
        c4.metric("🎓 الرسائل المنتهية", kpi_preview["رسائل ماجستير ودكتوراه منتهية"])
        
        if st.button("💾 حفظ/تحديث مؤشرات الأداء الشهرية", type="primary", key="save_kpi"):
            kpi_data = {
                "المعهد": st.session_state.institute,
                "المستخدم": st.session_state.username,
                "الشهر": month,
                "السنة": int(year),
            }
            kpi_data.update(kpi_preview)
            
            result = save_or_update_row("KPI_Data", KPI_COLUMNS, kpi_data,
                                        ["المعهد", "الشهر", "السنة"])
            if result:
                invalidate_all()
                st.success(f"✅ تم {'تحديث' if result == 'updated' else 'حفظ'} مؤشرات الأداء")
                st.balloons()
                time.sleep(0.5)
                st.rerun()

# ============================================================
# 📊 Dashboard
# ============================================================
if 'tab_dash' in dir() and tab_dash is not None:
    with tab_dash:
        st.title("📊 Dashboard الشهري")
        
        df_m = load_sheet("KPI_Data", KPI_COLUMNS)
        if not df_m.empty and st.session_state.role != "admin" and "المعهد" in df_m.columns:
            df_m = df_m[df_m["المعهد"] == st.session_state.institute]
        
        if df_m.empty:
            st.info("📭 لا توجد بيانات - ابدأ بإدخال البيانات من تبويب (إدخال البيانات) ثم اضغط على زر (حفظ مؤشرات الأداء)")
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
            c5.metric("👨‍🎓 المتدربين", int(df_m["المتدربين"].sum()))
            
            st.divider()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏃 المأموريات (أيام)", int(df_m["إجمالي أيام المأموريات"].sum()))
            c2.metric("📝 الأوراق البحثية", int(df_m["أوراق بحثية منشورة"].sum()))
            c3.metric("🌍 الأوراق الدولية", int(df_m["أوراق بحثية دولية منشورة"].sum()))
            c4.metric("🎓 الرسائل المنتهية", int(df_m["رسائل ماجستير ودكتوراه منتهية"].sum()))
            
            st.divider()
            
            if "المعهد" in df_m.columns and df_m["المعهد"].nunique() > 0:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 📚 الدراسات")
                    fig = px.bar(df_m, x="المعهد",
                                y=["دراسات خطة بحثية جارية", "دراسات استشارية جارية", "مشروعات بحثية جارية"],
                                barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 📄 التقارير")
                    fig = px.bar(df_m, x="المعهد",
                                y=["تقرير مرحلي", "تقرير نهائي"], barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🤝 الاجتماعات")
                    fig = px.bar(df_m, x="المعهد",
                                y=["اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية"],
                                barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 👥 التدريب")
                    fig = px.bar(df_m, x="المعهد", y=["المتدربين", "المدربين"], barmode="group")
                    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 📈 التقرير الربع سنوي
# ============================================================
if tab_q_dash is not None:
    with tab_q_dash:
        st.title("📈 التقرير الربع سنوي")
        st.caption("يُبنى تلقائياً من البيانات الشهرية + الربع سنوية + النصف سنوية + السنوية")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            q_options = ["الربع الأول", "الربع الثاني", "الربع الثالث", "الربع الرابع"]
            sel_q = st.selectbox("الربع", q_options, key="report_q")
        with c2:
            fy_opts = ["2025/2026", "2026/2027", "2027/2028"]
            sel_fy = st.selectbox("السنة المالية", fy_opts, key="report_fy")
        with c3:
            if st.session_state.role == "admin":
                kpi_all = load_sheet("KPI_Data", KPI_COLUMNS)
                institutes = ["الكل"]
                if not kpi_all.empty and "المعهد" in kpi_all.columns:
                    institutes += sorted(kpi_all["المعهد"].unique())
                sel_inst = st.selectbox("المعهد", institutes, key="report_inst")
            else:
                sel_inst = st.session_state.institute
        
        fy_start = int(sel_fy.split("/")[0])
        fy_end = int(sel_fy.split("/")[1])
        
        if sel_q == "الربع الأول":
            q_months = [("يوليو", fy_start), ("أغسطس", fy_start), ("سبتمبر", fy_start)]
        elif sel_q == "الربع الثاني":
            q_months = [("أكتوبر", fy_start), ("نوفمبر", fy_start), ("ديسمبر", fy_start)]
        elif sel_q == "الربع الثالث":
            q_months = [("يناير", fy_end), ("فبراير", fy_end), ("مارس", fy_end)]
        else:
            q_months = [("أبريل", fy_end), ("مايو", fy_end), ("يونيو", fy_end)]
        
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
                c5.metric("👨‍🎓 المتدربين", int(agg["المتدربين"].sum()))
                
                # البيانات الربع سنوية
                df_q_data = load_sheet("البيانات_الربع_سنوية", QUARTERLY_COLUMNS)
                if not df_q_data.empty and "الربع" in df_q_data.columns:
                    df_q_data = df_q_data[(df_q_data["الربع"] == sel_q) &
                                          (df_q_data["السنة المالية"] == sel_fy)]
                    if sel_inst != "الكل":
                        df_q_data = df_q_data[df_q_data["المعهد"] == sel_inst]
                    elif st.session_state.role != "admin":
                        df_q_data = df_q_data[df_q_data["المعهد"] == st.session_state.institute]
                    
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
                                c1.metric("💰 المنصرف من الموازنة",
                                          f"{float(row.get('المبلغ المنصرف من الموازنة الاستثمارية', 0) or 0):.2f}")
                                c2.metric("📅 اجتماعات دورية", row.get("عدد الاجتماعات الدورية", 0))
                                c3.metric("🏛️ مجلس الإدارة", row.get("عدد اجتماعات مجلس الإدارة", 0))
                                c4.metric("💡 وحدة الفكر", row.get("عدد اجتماعات وحدة الفكر", 0))
                
                # النصف سنوي - يظهر في Q2 (نهاية ديسمبر) و Q4 (نهاية يونيو)
                half_to_show = None
                if sel_q == "الربع الثاني":
                    half_to_show = "النصف الأول"
                elif sel_q == "الربع الرابع":
                    half_to_show = "النصف الثاني"
                
                if half_to_show:
                    st.markdown(f"## 📊 البيانات النصف سنوية — {half_to_show}")
                    df_h = load_sheet("البيانات_النصف_سنوية", HALF_COLUMNS)
                    if not df_h.empty and "النصف" in df_h.columns:
                        df_h = df_h[(df_h["السنة المالية"] == sel_fy) &
                                    (df_h["النصف"] == half_to_show)]
                        if sel_inst != "الكل":
                            df_h = df_h[df_h["المعهد"] == sel_inst]
                        elif st.session_state.role != "admin":
                            df_h = df_h[df_h["المعهد"] == st.session_state.institute]
                        
                        if df_h.empty:
                            st.warning("لا توجد بيانات نصف سنوية محفوظة")
                        else:
                            for _, row in df_h.iterrows():
                                with st.expander(f"🏢 {row['المعهد']}", expanded=False):
                                    c1, c2, c3 = st.columns(3)
                                    c1.metric("📚 الدراسات المنجزة",
                                              row.get("إجمالي عدد دراسات الخطة البحثية المنجزة", 0))
                                    c2.metric("🔬 المخرجات التطبيقية",
                                              row.get("إجمالي عدد المخرجات التطبيقية من دراسات ومشروعات", 0))
                                    c3.metric("💰 الإيرادات الذاتية",
                                              f"{float(row.get('إجمالي مبلغ الإيرادات الذاتية', 0) or 0):.2f}")
                
                # السنوي - يظهر في Q4
                if sel_q == "الربع الرابع":
                    st.markdown("## 📊 البيانات السنوية")
                    df_a = load_sheet("البيانات_السنوية", ANNUAL_COLUMNS)
                    if not df_a.empty and "السنة المالية" in df_a.columns:
                        df_a = df_a[df_a["السنة المالية"] == sel_fy]
                        if sel_inst != "الكل":
                            df_a = df_a[df_a["المعهد"] == sel_inst]
                        elif st.session_state.role != "admin":
                            df_a = df_a[df_a["المعهد"] == st.session_state.institute]
                        
                        if df_a.empty:
                            st.warning("لا توجد بيانات سنوية محفوظة")
                        else:
                            for _, row in df_a.iterrows():
                                with st.expander(f"🏢 {row['المعهد']}", expanded=False):
                                    st.metric("🔬 عدد براءات الاختراع",
                                              row.get("عدد براءات الاختراع", 0))
                
                st.divider()
                st.markdown("## 📄 الجدول الشامل")
                st.dataframe(rtl_display(q_df), use_container_width=True, hide_index=True)
                
                def to_excel(d):
                    out = BytesIO()
                    with pd.ExcelWriter(out, engine="openpyxl") as w:
                        d.to_excel(w, index=False, sheet_name="Quarterly")
                    return out.getvalue()
                
                st.download_button("📥 تحميل Excel",
                                  data=to_excel(q_df),
                                  file_name=f"quarterly_{sel_q}_{sel_fy}.xlsx".replace("/", "_"),
                                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
# 🔧 تشخيص (للأدمن فقط)
# ============================================================
if tab_debug is not None:
    with tab_debug:
        st.title("🔧 تشخيص البيانات")
        
        st.markdown("### 📋 حالة الأوراق في Google Sheets")
        
        sheets_to_check = [
            "KPI_Data", "البيانات_الربع_سنوية", "البيانات_النصف_سنوية",
            "البيانات_السنوية"
        ] + list(MONTHLY_LISTS.keys())
        
        for sname in sheets_to_check:
            try:
                all_v = fetch_data(sname)
                rows_count = max(0, len(all_v) - 1) if all_v else 0
                has_headers = len(all_v) > 0
                status = "✅" if rows_count > 0 else "⚠️"
                st.write(f"{status} **{sname}** — {rows_count} صف بيانات، العناوين: {'نعم' if has_headers else 'لا'}")
            except Exception as e:
                st.write(f"❌ **{sname}** — خطأ: {e}")
        
        st.divider()
        st.markdown("### 📊 محتوى KPI_Data الخام")
        kpi_raw = fetch_data("KPI_Data")
        if kpi_raw:
            st.write(f"عدد الصفوف: {len(kpi_raw)}")
            if len(kpi_raw) > 0:
                st.write("**العناوين:**")
                st.write(kpi_raw[0])
            if len(kpi_raw) > 1:
                st.write("**أول صف بيانات:**")
                st.write(kpi_raw[1])
        else:
            st.warning("KPI_Data فارغة تماماً")
