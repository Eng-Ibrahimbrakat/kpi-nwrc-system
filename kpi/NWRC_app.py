import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go
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

# ============================================================
# CSS محسّن لدعم RTL
# ============================================================
st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; }
.stButton > button { width: 100%; }
[data-testid="stMetricValue"] { font-size: 1.5rem; }
[data-testid="stDataFrame"] { direction: rtl !important; }
[data-testid="stDataFrame"] table { direction: rtl !important; text-align: right !important; }
[data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td { text-align: right !important; direction: rtl !important; }
[data-testid="stDataFrame"] thead th { text-align: right !important; background-color: #f0f2f6 !important; font-weight: bold !important; }
[data-testid="stDataEditor"] { direction: rtl !important; }
[data-testid="stDataEditor"] table { direction: rtl !important; }
[data-testid="stDataEditor"] th, [data-testid="stDataEditor"] td { text-align: right !important; direction: rtl !important; }
h1, h2, h3, h4, h5, h6 { direction: rtl; text-align: right; }
.stTabs [data-baseweb="tab-list"] { direction: rtl; }
.js-plotly-plot .plotly .main-svg { direction: ltr; }
.stTextInput input, .stNumberInput input, .stTextArea textarea { direction: rtl; text-align: right; }
.stSelectbox div[data-baseweb="select"] { direction: rtl; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Google Sheets - نظام Cache محسّن
# ============================================================
SPREADSHEET_KEY = "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"

# -------- Level 1: Client (cache دائم) --------
@st.cache_resource(show_spinner=False)
def _get_client():
    """تخزين مؤقت لكائن العميل المُصرح - Cache دائم"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

# -------- Level 2: Spreadsheet (cache مع bust) --------
@st.cache_resource(show_spinner=False)
def _get_spreadsheet_cached(_bust=0):
    """Cache Spreadsheet object - يتجدد فقط عند تغيير _bust"""
    return _get_client().open_by_key(SPREADSHEET_KEY)

def get_spreadsheet():
    """الحصول على Spreadsheet من Cache"""
    bust = st.session_state.get("gs_bust", 0)
    return _get_spreadsheet_cached(_bust=bust)

# -------- Level 3: Worksheet (cache مع bust) --------
@st.cache_resource(show_spinner=False)
def _get_worksheet_cached(sheet_name, _bust=0):
    """Cache Worksheet object"""
    try:
        return _get_spreadsheet_cached(_bust=_bust).worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        return None
    except Exception:
        return None

def get_worksheet(sheet_name):
    """الحصول على worksheet من Cache"""
    bust = st.session_state.get("gs_bust", 0)
    return _get_worksheet_cached(sheet_name, _bust=bust)

def get_or_create_sheet(sheet_name, headers=None):
    """الحصول على ورقة موجودة - الإنشاء فقط إذا لم توجد فعلاً"""
    ws = get_worksheet(sheet_name)
    if ws is not None:
        return ws
    
    # محاولة ثانية (cache قد يكون قديماً)
    time.sleep(0.5)
    try:
        ws = get_spreadsheet().worksheet(sheet_name)
        return ws
    except gspread.WorksheetNotFound:
        pass
    except Exception:
        pass
    
    # محاولة الإنشاء
    try:
        ss = get_spreadsheet()
        ws = ss.add_worksheet(title=sheet_name, rows=1000, cols=30)
        if headers:
            ws.append_row(headers)
        # تجديد cache لرؤية الورقة الجديدة
        st.session_state.gs_bust = st.session_state.get("gs_bust", 0) + 1
        return ws
    except Exception as e:
        err = str(e).lower()
        if "already exists" in err:
            try:
                time.sleep(1)
                return get_spreadsheet().worksheet(sheet_name)
            except Exception:
                return None
        st.error(f"❌ خطأ في الوصول للورقة {sheet_name}: {e}")
        return None

# -------- Level 4: Data (cache مع TTL و bust) --------
@st.cache_data(ttl=180, show_spinner=False)
def _fetch_data_cached(sheet_name, _bust=0):
    """قراءة بيانات ورقة مع cache لمدة 3 دقائق"""
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

def fetch_sheet_data(sheet_name):
    """جلب بيانات ورقة"""
    bust = st.session_state.get("gs_bust", 0)
    return _fetch_data_cached(sheet_name, _bust=bust)

def invalidate_all_cache():
    """مسح جميع أنواع Cache"""
    st.session_state.gs_bust = st.session_state.get("gs_bust", 0) + 1
    st.session_state.data_bust = st.session_state.get("data_bust", 0) + 1

def invalidate_data_cache():
    """مسح cache البيانات فقط (أخف من الكامل)"""
    st.session_state.data_bust = st.session_state.get("data_bust", 0) + 1

# ============================================================
# دوال مساعدة
# ============================================================
def fix_encoding(text):
    if isinstance(text, str):
        try:
            return text.encode('latin1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return text
    return text

def rtl_display(df):
    if df.empty:
        return df
    return df[list(reversed(df.columns))]

def load_sheet_data(sheet_name, columns):
    """تحميل بيانات ورقة - مع cache متعدد المستويات"""
    # Cache البيانات المحمّلة في session_state
    cache_key = f"_cached_data_{sheet_name}"
    bust_key = f"_cache_bust_{sheet_name}"
    current_bust = st.session_state.get("data_bust", 0)
    
    cached_bust = st.session_state.get(bust_key, -1)
    if cached_bust == current_bust and cache_key in st.session_state:
        return st.session_state[cache_key].copy()
    
    # قراءة البيانات
    all_values = fetch_sheet_data(sheet_name)
    
    if len(all_values) <= 1:
        df = pd.DataFrame(columns=columns)
    else:
        headers = [fix_encoding(h) for h in all_values[0]]
        df = pd.DataFrame(all_values[1:], columns=headers)
        for col in df.columns:
            if df[col].dtype == 'object' and col not in columns:
                df[col] = df[col].apply(fix_encoding)
    
    # تخزين في session_state
    st.session_state[cache_key] = df.copy()
    st.session_state[bust_key] = current_bust
    
    return df

def get_existing_row(df, filters):
    if df.empty:
        return None
    match = df.copy()
    for col, val in filters.items():
        if col in match.columns:
            match = match[match[col] == val]
    if match.empty:
        return None
    return match.iloc[0]

def get_int(row, col, default=0):
    if row is None or col not in row.index:
        return default
    try:
        v = row[col]
        if pd.isna(v) or v == "":
            return default
        return int(float(v))
    except (ValueError, TypeError):
        return default

def get_float(row, col, default=0.0):
    if row is None or col not in row.index:
        return default
    try:
        v = row[col]
        if pd.isna(v) or v == "":
            return default
        return float(v)
    except (ValueError, TypeError):
        return default

def get_str(row, col, default=""):
    if row is None or col not in row.index:
        return default
    try:
        v = row[col]
        if pd.isna(v):
            return default
        return str(v)
    except Exception:
        return default

def safe_sum(df, column):
    if df.empty or column not in df.columns:
        return 0
    return int(pd.to_numeric(df[column], errors='coerce').fillna(0).sum())

def save_list_data(sheet_name, input_df, base_columns, institute, period_key, period_val):
    """حفظ قائمة نصية"""
    try:
        full_cols = base_columns + ["المعهد", period_key]
        ws = get_or_create_sheet(sheet_name, full_cols)
        if ws is None:
            st.error("فشل الاتصال بالورقة")
            return
        
        all_values = ws.get_all_values()
        kept_rows = []
        if len(all_values) > 1:
            existing = pd.DataFrame(all_values[1:], columns=all_values[0])
            if "المعهد" in existing.columns and period_key in existing.columns:
                mask = ~(
                    (existing["المعهد"] == institute) &
                    (existing[period_key] == period_val)
                )
                kept_rows = existing[mask].values.tolist()
        
        ws.clear()
        ws.append_row(full_cols)
        
        if kept_rows:
            rows_to_add = [[str(v) for v in r] for r in kept_rows]
            ws.append_rows(rows_to_add)
        
        new_rows = []
        for _, row in input_df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row.tolist()]
            if all(v.strip() in ["", "nan", "None"] for v in vals):
                continue
            new_rows.append(vals + [institute, period_val])
        
        if new_rows:
            ws.append_rows(new_rows)
        
        invalidate_all_cache()
        st.success(f"✅ تم حفظ البيانات في {sheet_name}")
        st.balloons()
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"❌ خطأ في الحفظ: {e}")

def update_or_append_row(sheet_name, new_data, key_cols, all_cols):
    """تحديث صف أو إضافة جديد"""
    try:
        ws = get_or_create_sheet(sheet_name, all_cols)
        if ws is None:
            return None
        
        all_values = ws.get_all_values()
        
        if len(all_values) <= 1:
            ws.append_row([str(new_data.get(c, "")) for c in all_cols])
            return "added"
        
        headers = all_values[0]
        data = all_values[1:]
        
        found_idx = None
        for idx, row in enumerate(data):
            match = True
            for col in key_cols:
                if col not in headers:
                    match = False
                    break
                col_idx = headers.index(col)
                if col_idx >= len(row) or str(row[col_idx]) != str(new_data.get(col, "")):
                    match = False
                    break
            if match:
                found_idx = idx
                break
        
        new_row = [str(new_data.get(c, "")) for c in headers]
        
        if found_idx is not None:
            ws.update(f"A{found_idx + 2}", [new_row])
            return "updated"
        else:
            ws.append_row(new_row)
            return "added"
    except Exception as e:
        st.error(f"خطأ: {e}")
        return None

# ============================================================
# الأعمدة
# ============================================================
MONTHLY_COLUMNS = [
    "المعهد", "المستخدم", "الشهر", "السنة",
    "دراسات خطة بحثية جارية", "دراسات استشارية جارية", "دراسات بتمويل ذاتي جارية",
    "إجمالي الدراسات الجارية",
    "تقرير مرحلي", "تقرير نهائي", "تقرير معاينة", "تقرير معايرة", "تقرير أخرى",
    "إجمالي التقارير", "عدد المذكرات",
    "مقترحات استشارات", "مقترحات تمويل أبحاث", "إجمالي المقترحات",
    "إجمالي عدد المأموريات", "إجمالي عدد أيام المأموريات", "إجمالي عدد المعاينات",
    "متدربين", "مدربين",
    "أيام تدريب متدربين داخل المعهد", "أيام تدريب متدربين خارج المعهد",
    "مشتركين مؤتمرات", "مشتركين ورش عمل", "إجمالي المشاركين في أنشطة علمية",
    "اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية",
    "اجتماعات مع العاملين", "اجتماعات جهات أخرى", "إجمالي الاجتماعات",
    "أوراق بحثية منشورة", "أوراق بحثية جاري العمل عليها", "إجمالي الأوراق البحثية",
    "رسائل منتهية", "رسائل جاري العمل عليها", "إجمالي الرسائل",
    "إجمالي عدد العاملين الفعلي",
    "الأساتذة المتفرغين", "الأساتذة", "الأساتذة المساعدون",
    "الباحثون", "الباحث المساعد", "مساعد باحث",
    "الفنيون", "الإداريون", "السائقون",
    "إجمالي الإيرادات الذاتية", "عدد براءات الاختراع",
    "المبلغ المنصرف من الموازنة الاستثمارية"
]

QUARTERLY_COLUMNS = [
    "المعهد", "المستخدم", "الربع", "السنة المالية",
    "فردي - عدد المشاريع", "فردي - نسبة المنفذ %", "فردي - عدد التقارير",
    "مشترك - عدد المشاريع", "مشترك - نسبة المنفذ %",
    "مشترك - نسبة المشاركة %", "مشترك - عدد التقارير",
    "مشاريع ممولة محلياً", "مشاريع ممولة دولياً", "تكليفات من الوزارة",
    "استشارات من الوزارة", "استشارات من جهات حكومية/خاصة",
    "إجمالي المشاريع خارج الخطة",
    "مقترحات محلية", "مقترحات دولية", "مقترحات للوزارة", "مقترحات خارج الوزارة",
    "إجمالي المقترحات",
    "تعاون داخلي مع المعاهد", "تعاون داخلي مع جهات خارج المعاهد",
    "تعاون خارجي مع جهات أجنبية",
    "أبحاث منشورة", "أبحاث في مجلات متميزة Q1/Q2",
    "أبحاث حصلت على موافقة النشر", "أبحاث حصلت على مكافأة نشر",
    "باحثون حصلوا على مكافأة نشر",
    "رسائل ماجستير", "رسائل دكتوراه",
    "مراجعة وتحكيم أبحاث بمجلات",
    "إشراف/تحكيم رسائل لباحثي المعهد",
    "إشراف/تحكيم رسائل لباحثين خارج المعهد",
    "عضوية في منظمات دولية", "عضوية في منظمات محلية",
    "دورات بالداخل - عدد", "دورات بالداخل - متدربين",
    "دورات بالخارج - عدد", "دورات بالخارج - متدربين",
    "دورات online - عدد", "دورات online - متدربين",
    "ورش عمل بالداخل - عدد", "ورش عمل بالداخل - متدربين",
    "ورش عمل بالخارج - عدد", "ورش عمل بالخارج - متدربين",
    "مؤتمرات بالداخل - عدد", "مؤتمرات بالداخل - متدربين",
    "مؤتمرات بالخارج - عدد", "مؤتمرات بالخارج - متدربين",
    "دورات نظمها المعهد - عدد", "دورات نظمها المعهد - متدربين",
    "إجمالي التدريب - عدد", "إجمالي التدريب - متدربين",
    "تمويل الخطة البحثية - مبلغ", "تمويل الخطة البحثية - نسبة %",
    "تمويل خارجي - مبلغ", "تمويل خارجي - نسبة %",
    "المنصرف الفعلي - مبلغ", "المنصرف الفعلي - نسبة %",
    "تمويل نشر علمي - دراسات", "تمويل نشر علمي - أبحاث",
    "تمويل نشر علمي - مكافآت", "إجمالي تمويل النشر العلمي",
    "اجتماعات دورية مع الهيئة البحثية والعاملين",
    "اجتماعات مجلس إدارة المعهد", "اجتماعات وحدة الفكر",
    "آليات تسويق إمكانات المعهد", "آليات الثواب والعقاب",
    "عدد الاجتماعات الوزارية", "ملاحظات عامة"
]

STUDIES_COLUMNS = ["م", "عنوان الدراسة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
PROJECTS_COLUMNS = ["م", "عنوان المشروع", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
CONSULT_COLUMNS = ["م", "عنوان الاستشارة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
REPORTS_COLUMNS = ["م", "عنوان التقرير", "تاريخ الإصدار", "الجهة المستفيدة", "الدائرة طبقاً للخطة البحثية", "ملخص التقرير"]
MEETINGS_COLUMNS = ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض من الاجتماع", "النوع"]
TRAINING_COLUMNS = ["م", "عنوان البرنامج", "النوع", "عدد المشاركين", "مكان الانعقاد", "مدة البرنامج"]
PERF_MEETINGS_COLUMNS = ["م", "التاريخ", "عنوان الاجتماع", "الغرض من الاجتماع", "السادة الحضور"]

Q_STUDIES_INDIV = ["م", "عنوان المشروع البحثي", "نسبة المنفذ %", "عدد التقارير", "هدف الدراسة", "النتائج"]
Q_STUDIES_JOINT = ["م", "عنوان المشروع البحثي", "نسبة المنفذ %", "عدد التقارير", "الهدف", "النتائج"]
Q_FUNDED_LOCAL = ["م", "عنوان المشروع", "الجهة الممولة", "الأهداف"]
Q_FUNDED_INTL = ["م", "عنوان المشروع", "الجهة الخارجية", "موقف المقترح"]
Q_MINISTRY_ASSIGN = ["م", "عنوان الدراسة", "الجهة المكلفة", "الموقف"]
Q_MINISTRY_CONSULT = ["م", "عنوان الدراسة", "القطاع/الهيئة", "الموقف", "المدة"]
Q_PROPOSALS_LOCAL = ["م", "عنوان المقترح", "الجهة التمويل", "موقف المقترح"]
Q_PROPOSALS_INTL = ["م", "عنوان المقترح", "الجهة التمويل", "موقف المقترح"]
Q_PROPOSALS_MINISTRY = ["م", "عنوان المقترح", "القطاع/الهيئة", "موقف المقترح"]
Q_PROPOSALS_OUTSIDE = ["م", "عنوان المقترح", "الوزارة/الهيئة", "موقف المقترح"]
Q_COLLAB_INTERNAL = ["م", "اسم الدراسة/المشروع/بروتوكول", "المعهد", "تاريخ بدء التعاون"]
Q_COLLAB_EXTERNAL = ["م", "اسم الدراسة/المشروع/بروتوكول", "الجهة", "تاريخ بدء التعاون"]
Q_PUBLICATIONS = ["م", "عنوان البحث", "المجلة", "التصنيف", "تاريخ النشر", "الباحث الرئيسي"]
Q_ORGS_INTL = ["م", "المنظمة الدولية", "نوع العضوية", "تاريخ العضوية"]
Q_ORGS_LOCAL = ["م", "المنظمة المحلية", "نوع العضوية", "تاريخ العضوية"]
Q_MINISTRY_MEETINGS = ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض من الاجتماع"]

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
    "ecri": {"password": "1234", "role": "user", "institute": "معهد البيئة وتغير المناخ"}
}

# ============================================================
# Session State
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "gs_bust" not in st.session_state:
    st.session_state.gs_bust = 0
if "data_bust" not in st.session_state:
    st.session_state.data_bust = 0
if "editor_counter" not in st.session_state:
    st.session_state.editor_counter = 0

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
                invalidate_all_cache()
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# ============================================================
# بعد تسجيل الدخول
# ============================================================
c_header = st.columns([5, 1, 1])
with c_header[0]:
    st.success(f"👤 مرحباً **{st.session_state.username}** — 🏢 {st.session_state.institute}")
with c_header[1]:
    if st.button("🔄 تحديث"):
        invalidate_all_cache()
        st.rerun()
with c_header[2]:
    if st.button("🚪 خروج"):
        st.session_state.clear()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# تحميل البيانات الشهرية مرة واحدة
df_monthly = load_sheet_data("KPI_Data", MONTHLY_COLUMNS)
if not df_monthly.empty and st.session_state.role != "admin" and "المعهد" in df_monthly.columns:
    df_monthly = df_monthly[df_monthly["المعهد"] == st.session_state.institute]

# ============================================================
# التبويبات
# ============================================================
if st.session_state.role == "admin":
    tab_q_dashboard, tab_m_dashboard, tab_trend, tab_data, tab_lists = st.tabs([
        "📊 التقارير الربع سنوية",
        "📈 Dashboard الشهري",
        "📉 التغير الشهري",
        "📄 البيانات الشهرية",
        "📋 القوائم التفصيلية"
    ])
    tab_input = None
    tab_q_input = None
    tab_lists_input = None
    tab_q_lists_input = None
else:
    tabs = st.tabs([
        "📥 إدخال شهري",
        "📊 إدخال ربع سنوي",
        "📝 القوائم الشهرية",
        "📋 القوائم الربع سنوية",
        "📈 Dashboard شهري",
        "📊 التقارير الربع سنوية",
        "📉 التغير الشهري",
        "📄 البيانات"
    ])
    tab_input = tabs[0]
    tab_q_input = tabs[1]
    tab_lists_input = tabs[2]
    tab_q_lists_input = tabs[3]
    tab_m_dashboard = tabs[4]
    tab_q_dashboard = tabs[5]
    tab_trend = tabs[6]
    tab_data = tabs[7]
    tab_lists = None

# ============================================================
# 📥 إدخال البيانات الشهرية
# ============================================================
if tab_input is not None:
    with tab_input:
        st.header("📥 إدخال البيانات الشهرية")
        
        c1, c2 = st.columns(2)
        with c1:
            month = st.selectbox("الشهر", [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ], key="m_month")
        with c2:
            year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="m_year")
        
        existing_m = get_existing_row(df_monthly, {
            "المعهد": st.session_state.institute,
            "الشهر": month,
            "السنة": str(int(year))
        })
        
        if existing_m is not None:
            st.warning(f"ℹ️ توجد بيانات محفوظة لهذا الشهر - سيتم تحديثها عند الحفظ")
        else:
            st.info(f"📝 إدخال بيانات جديدة لشهر **{month} {year}**")
        
        kp = f"{month}_{year}"
        
        st.divider()
        
        st.subheader("📚 الدراسات الجارية")
        c1, c2, c3 = st.columns(3)
        rs = c1.number_input("خطة بحثية", min_value=0, value=get_int(existing_m, "دراسات خطة بحثية جارية"), key=f"rs_{kp}")
        cs = c2.number_input("استشارية", min_value=0, value=get_int(existing_m, "دراسات استشارية جارية"), key=f"cs_{kp}")
        sf = c3.number_input("دراسات بتمويل ذاتي", min_value=0, value=get_int(existing_m, "دراسات بتمويل ذاتي جارية"), key=f"sf_{kp}")
        total_studies = rs + cs + sf
        st.info(f"إجمالي الدراسات الجارية: **{total_studies}**")
        
        st.divider()
        
        st.subheader("📄 التقارير الصادرة")
        c1, c2, c3, c4, c5 = st.columns(5)
        r1 = c1.number_input("مرحلي", min_value=0, value=get_int(existing_m, "تقرير مرحلي"), key=f"r1_{kp}")
        r2 = c2.number_input("نهائي", min_value=0, value=get_int(existing_m, "تقرير نهائي"), key=f"r2_{kp}")
        r3 = c3.number_input("معاينة", min_value=0, value=get_int(existing_m, "تقرير معاينة"), key=f"r3_{kp}")
        r4 = c4.number_input("معايرة", min_value=0, value=get_int(existing_m, "تقرير معايرة"), key=f"r4_{kp}")
        r5 = c5.number_input("أخرى", min_value=0, value=get_int(existing_m, "تقرير أخرى"), key=f"r5_{kp}")
        total_reports = r1 + r2 + r3 + r4 + r5
        st.info(f"إجمالي التقارير: **{total_reports}**")
        
        st.divider()
        
        st.subheader("📋 المذكرات والمقترحات")
        c1, c2, c3 = st.columns(3)
        memos = c1.number_input("عدد المذكرات", min_value=0, value=get_int(existing_m, "عدد المذكرات"), key=f"memos_{kp}")
        pc = c2.number_input("مقترحات استشارات", min_value=0, value=get_int(existing_m, "مقترحات استشارات"), key=f"pc_{kp}")
        pf = c3.number_input("مقترحات تمويل أبحاث", min_value=0, value=get_int(existing_m, "مقترحات تمويل أبحاث"), key=f"pf_{kp}")
        total_props = pc + pf
        
        st.divider()
        
        st.subheader("🏃 المأموريات والمعاينات")
        c1, c2, c3 = st.columns(3)
        missions = c1.number_input("إجمالي عدد المأموريات", min_value=0, value=get_int(existing_m, "إجمالي عدد المأموريات"), key=f"miss_{kp}")
        m_days = c2.number_input("إجمالي أيام المأموريات", min_value=0, value=get_int(existing_m, "إجمالي عدد أيام المأموريات"), key=f"m_days_{kp}")
        surveys = c3.number_input("إجمالي عدد المعاينات", min_value=0, value=get_int(existing_m, "إجمالي عدد المعاينات"), key=f"surv_{kp}")
        
        st.divider()
        
        st.subheader("👥 التدريب")
        c1, c2, c3, c4 = st.columns(4)
        trainees = c1.number_input("متدربين", min_value=0, value=get_int(existing_m, "متدربين"), key=f"tr_{kp}")
        trainers = c2.number_input("مدربين", min_value=0, value=get_int(existing_m, "مدربين"), key=f"trn_{kp}")
        td_in = c3.number_input("أيام تدريب (داخلي)", min_value=0, value=get_int(existing_m, "أيام تدريب متدربين داخل المعهد"), key=f"tdi_{kp}")
        td_out = c4.number_input("أيام تدريب (خارجي)", min_value=0, value=get_int(existing_m, "أيام تدريب متدربين خارج المعهد"), key=f"tdo_{kp}")
        
        st.divider()
        
        st.subheader("🔬 الأنشطة العلمية")
        c1, c2 = st.columns(2)
        conf = c1.number_input("مشتركين مؤتمرات", min_value=0, value=get_int(existing_m, "مشتركين مؤتمرات"), key=f"conf_{kp}")
        ws_a = c2.number_input("مشتركين ورش عمل", min_value=0, value=get_int(existing_m, "مشتركين ورش عمل"), key=f"wsa_{kp}")
        total_act = conf + ws_a
        
        st.divider()
        
        st.subheader("🤝 الاجتماعات")
        c1, c2, c3, c4, c5 = st.columns(5)
        mt1 = c1.number_input("بالوزارة", min_value=0, value=get_int(existing_m, "اجتماعات بالوزارة"), key=f"mt1_{kp}")
        mt2 = c2.number_input("بالمركز", min_value=0, value=get_int(existing_m, "اجتماعات بالمركز"), key=f"mt2_{kp}")
        mt3 = c3.number_input("جهات خارجية", min_value=0, value=get_int(existing_m, "اجتماعات جهات خارجية"), key=f"mt3_{kp}")
        mt4 = c4.number_input("مع العاملين", min_value=0, value=get_int(existing_m, "اجتماعات مع العاملين"), key=f"mt4_{kp}")
        mt5 = c5.number_input("جهات أخرى", min_value=0, value=get_int(existing_m, "اجتماعات جهات أخرى"), key=f"mt5_{kp}")
        total_meet = mt1 + mt2 + mt3 + mt4 + mt5
        
        st.divider()
        
        st.subheader("📝 الأوراق البحثية والرسائل")
        c1, c2, c3, c4 = st.columns(4)
        pp = c1.number_input("أوراق منشورة", min_value=0, value=get_int(existing_m, "أوراق بحثية منشورة"), key=f"pp_{kp}")
        po = c2.number_input("أوراق جاري العمل عليها", min_value=0, value=get_int(existing_m, "أوراق بحثية جاري العمل عليها"), key=f"po_{kp}")
        th_done = c3.number_input("رسائل منتهية", min_value=0, value=get_int(existing_m, "رسائل منتهية"), key=f"thd_{kp}")
        th_ongo = c4.number_input("رسائل جاري العمل عليها", min_value=0, value=get_int(existing_m, "رسائل جاري العمل عليها"), key=f"tho_{kp}")
        
        st.divider()
        
        st.subheader("👤 عدد العاملين بالمعهد")
        c1, c2, c3 = st.columns(3)
        tot_staff = c1.number_input("إجمالي العاملين الفعلي", min_value=0, value=get_int(existing_m, "إجمالي عدد العاملين الفعلي"), key=f"ts_{kp}")
        prof_em = c2.number_input("الأساتذة المتفرغين", min_value=0, value=get_int(existing_m, "الأساتذة المتفرغين"), key=f"pem_{kp}")
        profs = c3.number_input("الأساتذة", min_value=0, value=get_int(existing_m, "الأساتذة"), key=f"prf_{kp}")
        
        c1, c2, c3 = st.columns(3)
        asst_pr = c1.number_input("الأساتذة المساعدون", min_value=0, value=get_int(existing_m, "الأساتذة المساعدون"), key=f"asp_{kp}")
        resrch = c2.number_input("الباحثون", min_value=0, value=get_int(existing_m, "الباحثون"), key=f"rsc_{kp}")
        asst_res = c3.number_input("الباحث المساعد", min_value=0, value=get_int(existing_m, "الباحث المساعد"), key=f"asr_{kp}")
        
        c1, c2, c3 = st.columns(3)
        res_ast = c1.number_input("مساعد باحث", min_value=0, value=get_int(existing_m, "مساعد باحث"), key=f"rsa_{kp}")
        tech = c2.number_input("الفنيون", min_value=0, value=get_int(existing_m, "الفنيون"), key=f"tch_{kp}")
        admins = c3.number_input("الإداريون", min_value=0, value=get_int(existing_m, "الإداريون"), key=f"adm_{kp}")
        
        drivers = st.number_input("السائقون", min_value=0, value=get_int(existing_m, "السائقون"), key=f"drv_{kp}")
        
        st.divider()
        
        st.subheader("💰 بيانات إضافية")
        c1, c2, c3 = st.columns(3)
        revenues = c1.number_input("إجمالي الإيرادات الذاتية", min_value=0.0, value=get_float(existing_m, "إجمالي الإيرادات الذاتية"), format="%.2f", key=f"rev_{kp}")
        patents = c2.number_input("عدد براءات الاختراع", min_value=0, value=get_int(existing_m, "عدد براءات الاختراع"), key=f"pat_{kp}")
        budget = c3.number_input("المنصرف من الموازنة الاستثمارية", min_value=0.0, value=get_float(existing_m, "المبلغ المنصرف من الموازنة الاستثمارية"), format="%.2f", key=f"bud_{kp}")
        
        st.divider()
        
        if st.button("💾 حفظ البيانات الشهرية", type="primary", key="save_monthly"):
            try:
                data = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "الشهر": month, "السنة": int(year),
                    "دراسات خطة بحثية جارية": rs,
                    "دراسات استشارية جارية": cs,
                    "دراسات بتمويل ذاتي جارية": sf,
                    "إجمالي الدراسات الجارية": total_studies,
                    "تقرير مرحلي": r1, "تقرير نهائي": r2,
                    "تقرير معاينة": r3, "تقرير معايرة": r4, "تقرير أخرى": r5,
                    "إجمالي التقارير": total_reports,
                    "عدد المذكرات": memos,
                    "مقترحات استشارات": pc, "مقترحات تمويل أبحاث": pf,
                    "إجمالي المقترحات": total_props,
                    "إجمالي عدد المأموريات": missions,
                    "إجمالي عدد أيام المأموريات": m_days,
                    "إجمالي عدد المعاينات": surveys,
                    "متدربين": trainees, "مدربين": trainers,
                    "أيام تدريب متدربين داخل المعهد": td_in,
                    "أيام تدريب متدربين خارج المعهد": td_out,
                    "مشتركين مؤتمرات": conf, "مشتركين ورش عمل": ws_a,
                    "إجمالي المشاركين في أنشطة علمية": total_act,
                    "اجتماعات بالوزارة": mt1, "اجتماعات بالمركز": mt2,
                    "اجتماعات جهات خارجية": mt3, "اجتماعات مع العاملين": mt4,
                    "اجتماعات جهات أخرى": mt5, "إجمالي الاجتماعات": total_meet,
                    "أوراق بحثية منشورة": pp,
                    "أوراق بحثية جاري العمل عليها": po,
                    "إجمالي الأوراق البحثية": pp + po,
                    "رسائل منتهية": th_done,
                    "رسائل جاري العمل عليها": th_ongo,
                    "إجمالي الرسائل": th_done + th_ongo,
                    "إجمالي عدد العاملين الفعلي": tot_staff,
                    "الأساتذة المتفرغين": prof_em, "الأساتذة": profs,
                    "الأساتذة المساعدون": asst_pr, "الباحثون": resrch,
                    "الباحث المساعد": asst_res, "مساعد باحث": res_ast,
                    "الفنيون": tech, "الإداريون": admins, "السائقون": drivers,
                    "إجمالي الإيرادات الذاتية": revenues,
                    "عدد براءات الاختراع": patents,
                    "المبلغ المنصرف من الموازنة الاستثمارية": budget
                }
                
                result = update_or_append_row(
                    "KPI_Data", data,
                    ["المعهد", "الشهر", "السنة"],
                    MONTHLY_COLUMNS
                )
                
                if result == "updated":
                    st.success("✅ تم تحديث البيانات الشهرية بنجاح")
                elif result == "added":
                    st.success("✅ تم حفظ البيانات الشهرية بنجاح")
                
                invalidate_all_cache()
                st.balloons()
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# ============================================================
# 📊 إدخال البيانات الربع سنوية
# ============================================================
if tab_q_input is not None:
    with tab_q_input:
        st.header("📊 إدخال البيانات الربع سنوية")
        
        df_q_existing = load_sheet_data("Quarterly_KPI", QUARTERLY_COLUMNS)
        if not df_q_existing.empty and st.session_state.role != "admin" and "المعهد" in df_q_existing.columns:
            df_q_existing = df_q_existing[df_q_existing["المعهد"] == st.session_state.institute]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            quarter = st.selectbox("الربع", 
                ["الربع الأول", "الربع الثاني", "الربع الثالث", "الربع الرابع"],
                key="q_quarter")
        with c2:
            fiscal_year = st.selectbox("السنة المالية",
                ["2025/2026", "2026/2027", "2027/2028"], key="q_fy")
        with c3:
            st.info(f"🏢 {st.session_state.institute}")
        
        existing_q = get_existing_row(df_q_existing, {
            "المعهد": st.session_state.institute,
            "الربع": quarter,
            "السنة المالية": fiscal_year
        })
        
        if existing_q is not None:
            st.warning(f"ℹ️ توجد بيانات محفوظة لهذا الربع - سيتم تحديثها عند الحفظ")
        else:
            st.info(f"📝 إدخال بيانات جديدة لـ **{quarter} - {fiscal_year}**")
        
        kp = f"{quarter}_{fiscal_year}".replace("/", "_").replace(" ", "_")
        
        st.divider()
        
        st.subheader("1️⃣ الأداء التنفيذي للخطة البحثية")
        with st.expander("1-1-1 مشروع فردي خاص بالمعهد", expanded=True):
            c1, c2, c3 = st.columns(3)
            ind_cnt = c1.number_input("عدد المشاريع", min_value=0, value=get_int(existing_q, "فردي - عدد المشاريع"), key=f"q_ind_cnt_{kp}")
            ind_pct = c2.number_input("نسبة المنفذ %", min_value=0.0, max_value=100.0, value=get_float(existing_q, "فردي - نسبة المنفذ %"), format="%.1f", key=f"q_ind_pct_{kp}")
            ind_rep = c3.number_input("عدد التقارير", min_value=0, value=get_int(existing_q, "فردي - عدد التقارير"), key=f"q_ind_rep_{kp}")
        
        with st.expander("1-1-2 مشروع مشترك مع معاهد أخرى"):
            c1, c2, c3, c4 = st.columns(4)
            jnt_cnt = c1.number_input("عدد المشاريع", min_value=0, value=get_int(existing_q, "مشترك - عدد المشاريع"), key=f"q_jnt_cnt_{kp}")
            jnt_pct = c2.number_input("نسبة المنفذ %", min_value=0.0, max_value=100.0, value=get_float(existing_q, "مشترك - نسبة المنفذ %"), format="%.1f", key=f"q_jnt_pct_{kp}")
            jnt_share = c3.number_input("نسبة المشاركة %", min_value=0.0, max_value=100.0, value=get_float(existing_q, "مشترك - نسبة المشاركة %"), format="%.1f", key=f"q_jnt_shr_{kp}")
            jnt_rep = c4.number_input("عدد التقارير", min_value=0, value=get_int(existing_q, "مشترك - عدد التقارير"), key=f"q_jnt_rep_{kp}")
        
        st.divider()
        
        st.subheader("2️⃣ الاستشارات والدراسات خارج الخطة")
        c1, c2, c3 = st.columns(3)
        q_local = c1.number_input("مشاريع ممولة محلياً", min_value=0, value=get_int(existing_q, "مشاريع ممولة محلياً"), key=f"q_loc_{kp}")
        q_intl = c2.number_input("مشاريع ممولة دولياً", min_value=0, value=get_int(existing_q, "مشاريع ممولة دولياً"), key=f"q_intl_{kp}")
        q_min_a = c3.number_input("تكليفات من الوزارة", min_value=0, value=get_int(existing_q, "تكليفات من الوزارة"), key=f"q_mina_{kp}")
        
        c1, c2, c3 = st.columns(3)
        q_min_c = c1.number_input("استشارات من الوزارة", min_value=0, value=get_int(existing_q, "استشارات من الوزارة"), key=f"q_minc_{kp}")
        q_gov = c2.number_input("استشارات حكومية/خاصة", min_value=0, value=get_int(existing_q, "استشارات من جهات حكومية/خاصة"), key=f"q_gov_{kp}")
        q_total_out = q_local + q_intl + q_min_a + q_min_c + q_gov
        c3.metric("إجمالي خارج الخطة", q_total_out)
        
        st.markdown("**المقترحات:**")
        c1, c2, c3, c4 = st.columns(4)
        q_p_loc = c1.number_input("محلية", min_value=0, value=get_int(existing_q, "مقترحات محلية"), key=f"q_ploc_{kp}")
        q_p_int = c2.number_input("دولية", min_value=0, value=get_int(existing_q, "مقترحات دولية"), key=f"q_pint_{kp}")
        q_p_min = c3.number_input("للوزارة", min_value=0, value=get_int(existing_q, "مقترحات للوزارة"), key=f"q_pmin_{kp}")
        q_p_out = c4.number_input("خارج الوزارة", min_value=0, value=get_int(existing_q, "مقترحات خارج الوزارة"), key=f"q_pout_{kp}")
        q_total_p = q_p_loc + q_p_int + q_p_min + q_p_out
        
        st.divider()
        
        st.subheader("3️⃣ التعاون الداخلي والخارجي")
        c1, c2, c3 = st.columns(3)
        q_col_in = c1.number_input("تعاون داخلي مع المعاهد", min_value=0, value=get_int(existing_q, "تعاون داخلي مع المعاهد"), key=f"q_cin_{kp}")
        q_col_out = c2.number_input("تعاون داخلي خارج المعاهد", min_value=0, value=get_int(existing_q, "تعاون داخلي مع جهات خارج المعاهد"), key=f"q_cout_{kp}")
        q_col_frgn = c3.number_input("تعاون خارجي", min_value=0, value=get_int(existing_q, "تعاون خارجي مع جهات أجنبية"), key=f"q_cfr_{kp}")
        
        st.divider()
        
        st.subheader("4️⃣ الإنتاج العلمي والنشر والابتكار")
        c1, c2, c3, c4 = st.columns(4)
        q_pub = c1.number_input("أبحاث منشورة", min_value=0, value=get_int(existing_q, "أبحاث منشورة"), key=f"q_pub_{kp}")
        q_q1 = c2.number_input("Q1/Q2", min_value=0, value=get_int(existing_q, "أبحاث في مجلات متميزة Q1/Q2"), key=f"q_q1_{kp}")
        q_appr = c3.number_input("موافقة نشر", min_value=0, value=get_int(existing_q, "أبحاث حصلت على موافقة النشر"), key=f"q_appr_{kp}")
        q_rew = c4.number_input("مكافأة نشر", min_value=0, value=get_int(existing_q, "أبحاث حصلت على مكافأة نشر"), key=f"q_rew_{kp}")
        
        c1, c2, c3 = st.columns(3)
        q_res_rew = c1.number_input("باحثون بمكافأة", min_value=0, value=get_int(existing_q, "باحثون حصلوا على مكافأة نشر"), key=f"q_rrw_{kp}")
        q_mas = c2.number_input("رسائل ماجستير", min_value=0, value=get_int(existing_q, "رسائل ماجستير"), key=f"q_mas_{kp}")
        q_phd = c3.number_input("رسائل دكتوراه", min_value=0, value=get_int(existing_q, "رسائل دكتوراه"), key=f"q_phd_{kp}")
        
        c1, c2, c3 = st.columns(3)
        q_rev = c1.number_input("مراجعة بمجلات", min_value=0, value=get_int(existing_q, "مراجعة وتحكيم أبحاث بمجلات"), key=f"q_rev_{kp}")
        q_sup_in = c2.number_input("إشراف لباحثي المعهد", min_value=0, value=get_int(existing_q, "إشراف/تحكيم رسائل لباحثي المعهد"), key=f"q_supin_{kp}")
        q_sup_out = c3.number_input("إشراف لباحثين خارجيين", min_value=0, value=get_int(existing_q, "إشراف/تحكيم رسائل لباحثين خارج المعهد"), key=f"q_supout_{kp}")
        
        c1, c2 = st.columns(2)
        q_mem_int = c1.number_input("عضوية دولية", min_value=0, value=get_int(existing_q, "عضوية في منظمات دولية"), key=f"q_memint_{kp}")
        q_mem_loc = c2.number_input("عضوية محلية", min_value=0, value=get_int(existing_q, "عضوية في منظمات محلية"), key=f"q_memloc_{kp}")
        
        st.divider()
        
        st.subheader("5️⃣ التدريب / التعليم")
        training_types = [
            ("دورات بالداخل", "tr_in", "دورات بالداخل - عدد", "دورات بالداخل - متدربين"),
            ("دورات بالخارج", "tr_out", "دورات بالخارج - عدد", "دورات بالخارج - متدربين"),
            ("دورات online", "tr_onl", "دورات online - عدد", "دورات online - متدربين"),
            ("ورش عمل بالداخل", "tr_ws_in", "ورش عمل بالداخل - عدد", "ورش عمل بالداخل - متدربين"),
            ("ورش عمل بالخارج", "tr_ws_out", "ورش عمل بالخارج - عدد", "ورش عمل بالخارج - متدربين"),
            ("مؤتمرات بالداخل", "tr_cf_in", "مؤتمرات بالداخل - عدد", "مؤتمرات بالداخل - متدربين"),
            ("مؤتمرات بالخارج", "tr_cf_out", "مؤتمرات بالخارج - عدد", "مؤتمرات بالخارج - متدربين"),
            ("دورات نظمها المعهد", "tr_org", "دورات نظمها المعهد - عدد", "دورات نظمها المعهد - متدربين"),
        ]
        
        q_training_data = {}
        q_tot_train_cnt = 0
        q_tot_train_trn = 0
        for label, key, cnt_col, trn_col in training_types:
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"**{label}**")
            cnt = c2.number_input("عدد", min_value=0, value=get_int(existing_q, cnt_col), key=f"q_{key}_c_{kp}")
            trn = c3.number_input("متدربين", min_value=0, value=get_int(existing_q, trn_col), key=f"q_{key}_t_{kp}")
            q_training_data[f"{key}_count"] = cnt
            q_training_data[f"{key}_trainees"] = trn
            q_tot_train_cnt += cnt
            q_tot_train_trn += trn
        
        st.info(f"**إجمالي التدريب:** {q_tot_train_cnt} فعالية — {q_tot_train_trn} متدرب")
        
        st.divider()
        
        st.subheader("6️⃣ التمويل والأداء المالي")
        c1, c2 = st.columns(2)
        q_rf_amt = c1.number_input("تمويل الخطة (ألف ج)", min_value=0.0, value=get_float(existing_q, "تمويل الخطة البحثية - مبلغ"), format="%.2f", key=f"q_rfa_{kp}")
        q_rf_pct = c2.number_input("نسبة %", min_value=0.0, max_value=100.0, value=get_float(existing_q, "تمويل الخطة البحثية - نسبة %"), format="%.1f", key=f"q_rfp_{kp}")
        
        c1, c2 = st.columns(2)
        q_ef_amt = c1.number_input("التمويل الخارجي", min_value=0.0, value=get_float(existing_q, "تمويل خارجي - مبلغ"), format="%.2f", key=f"q_efa_{kp}")
        q_ef_pct = c2.number_input("نسبة خارجي %", min_value=0.0, max_value=100.0, value=get_float(existing_q, "تمويل خارجي - نسبة %"), format="%.1f", key=f"q_efp_{kp}")
        
        c1, c2 = st.columns(2)
        q_sp_amt = c1.number_input("المنصرف الفعلي", min_value=0.0, value=get_float(existing_q, "المنصرف الفعلي - مبلغ"), format="%.2f", key=f"q_spa_{kp}")
        q_sp_pct = c2.number_input("نسبة المنصرف %", min_value=0.0, max_value=200.0, value=get_float(existing_q, "المنصرف الفعلي - نسبة %"), format="%.1f", key=f"q_spp_{kp}")
        
        st.markdown("**تمويل النشر العلمي:**")
        c1, c2, c3 = st.columns(3)
        q_pf_th = c1.number_input("دراسات", min_value=0.0, value=get_float(existing_q, "تمويل نشر علمي - دراسات"), format="%.2f", key=f"q_pfth_{kp}")
        q_pf_rs = c2.number_input("أبحاث", min_value=0.0, value=get_float(existing_q, "تمويل نشر علمي - أبحاث"), format="%.2f", key=f"q_pfrs_{kp}")
        q_pf_rw = c3.number_input("مكافآت", min_value=0.0, value=get_float(existing_q, "تمويل نشر علمي - مكافآت"), format="%.2f", key=f"q_pfrw_{kp}")
        q_tot_pf = q_pf_th + q_pf_rs + q_pf_rw
        
        st.divider()
        
        st.subheader("7️⃣ مؤشرات الأداء للموارد البشرية")
        c1, c2, c3 = st.columns(3)
        q_per_meet = c1.number_input("اجتماعات مع الهيئة والعاملين", min_value=0, value=get_int(existing_q, "اجتماعات دورية مع الهيئة البحثية والعاملين"), key=f"q_pm_{kp}")
        q_brd_meet = c2.number_input("مجلس الإدارة", min_value=0, value=get_int(existing_q, "اجتماعات مجلس إدارة المعهد"), key=f"q_bm_{kp}")
        q_think = c3.number_input("وحدة الفكر", min_value=0, value=get_int(existing_q, "اجتماعات وحدة الفكر"), key=f"q_tk_{kp}")
        
        q_marketing = st.text_area("آليات تسويق إمكانات المعهد", value=get_str(existing_q, "آليات تسويق إمكانات المعهد"), height=80, key=f"q_mkt_{kp}")
        q_rewards = st.text_area("آليات الثواب والعقاب", value=get_str(existing_q, "آليات الثواب والعقاب"), height=80, key=f"q_rwd_{kp}")
        
        st.divider()
        
        st.subheader("8️⃣ الاجتماعات الوزارية")
        q_min_meet = st.number_input("عدد الاجتماعات الوزارية", min_value=0, value=get_int(existing_q, "عدد الاجتماعات الوزارية"), key=f"q_mm_{kp}")
        q_notes = st.text_area("ملاحظات عامة", value=get_str(existing_q, "ملاحظات عامة"), height=80, key=f"q_nt_{kp}")
        
        st.divider()
        
        if st.button("💾 حفظ البيانات الربع سنوية", type="primary", key="save_q"):
            try:
                data = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "الربع": quarter, "السنة المالية": fiscal_year,
                    "فردي - عدد المشاريع": ind_cnt,
                    "فردي - نسبة المنفذ %": ind_pct,
                    "فردي - عدد التقارير": ind_rep,
                    "مشترك - عدد المشاريع": jnt_cnt,
                    "مشترك - نسبة المنفذ %": jnt_pct,
                    "مشترك - نسبة المشاركة %": jnt_share,
                    "مشترك - عدد التقارير": jnt_rep,
                    "مشاريع ممولة محلياً": q_local,
                    "مشاريع ممولة دولياً": q_intl,
                    "تكليفات من الوزارة": q_min_a,
                    "استشارات من الوزارة": q_min_c,
                    "استشارات من جهات حكومية/خاصة": q_gov,
                    "إجمالي المشاريع خارج الخطة": q_total_out,
                    "مقترحات محلية": q_p_loc, "مقترحات دولية": q_p_int,
                    "مقترحات للوزارة": q_p_min, "مقترحات خارج الوزارة": q_p_out,
                    "إجمالي المقترحات": q_total_p,
                    "تعاون داخلي مع المعاهد": q_col_in,
                    "تعاون داخلي مع جهات خارج المعاهد": q_col_out,
                    "تعاون خارجي مع جهات أجنبية": q_col_frgn,
                    "أبحاث منشورة": q_pub,
                    "أبحاث في مجلات متميزة Q1/Q2": q_q1,
                    "أبحاث حصلت على موافقة النشر": q_appr,
                    "أبحاث حصلت على مكافأة نشر": q_rew,
                    "باحثون حصلوا على مكافأة نشر": q_res_rew,
                    "رسائل ماجستير": q_mas, "رسائل دكتوراه": q_phd,
                    "مراجعة وتحكيم أبحاث بمجلات": q_rev,
                    "إشراف/تحكيم رسائل لباحثي المعهد": q_sup_in,
                    "إشراف/تحكيم رسائل لباحثين خارج المعهد": q_sup_out,
                    "عضوية في منظمات دولية": q_mem_int,
                    "عضوية في منظمات محلية": q_mem_loc,
                    "دورات بالداخل - عدد": q_training_data["tr_in_count"],
                    "دورات بالداخل - متدربين": q_training_data["tr_in_trainees"],
                    "دورات بالخارج - عدد": q_training_data["tr_out_count"],
                    "دورات بالخارج - متدربين": q_training_data["tr_out_trainees"],
                    "دورات online - عدد": q_training_data["tr_onl_count"],
                    "دورات online - متدربين": q_training_data["tr_onl_trainees"],
                    "ورش عمل بالداخل - عدد": q_training_data["tr_ws_in_count"],
                    "ورش عمل بالداخل - متدربين": q_training_data["tr_ws_in_trainees"],
                    "ورش عمل بالخارج - عدد": q_training_data["tr_ws_out_count"],
                    "ورش عمل بالخارج - متدربين": q_training_data["tr_ws_out_trainees"],
                    "مؤتمرات بالداخل - عدد": q_training_data["tr_cf_in_count"],
                    "مؤتمرات بالداخل - متدربين": q_training_data["tr_cf_in_trainees"],
                    "مؤتمرات بالخارج - عدد": q_training_data["tr_cf_out_count"],
                    "مؤتمرات بالخارج - متدربين": q_training_data["tr_cf_out_trainees"],
                    "دورات نظمها المعهد - عدد": q_training_data["tr_org_count"],
                    "دورات نظمها المعهد - متدربين": q_training_data["tr_org_trainees"],
                    "إجمالي التدريب - عدد": q_tot_train_cnt,
                    "إجمالي التدريب - متدربين": q_tot_train_trn,
                    "تمويل الخطة البحثية - مبلغ": q_rf_amt,
                    "تمويل الخطة البحثية - نسبة %": q_rf_pct,
                    "تمويل خارجي - مبلغ": q_ef_amt,
                    "تمويل خارجي - نسبة %": q_ef_pct,
                    "المنصرف الفعلي - مبلغ": q_sp_amt,
                    "المنصرف الفعلي - نسبة %": q_sp_pct,
                    "تمويل نشر علمي - دراسات": q_pf_th,
                    "تمويل نشر علمي - أبحاث": q_pf_rs,
                    "تمويل نشر علمي - مكافآت": q_pf_rw,
                    "إجمالي تمويل النشر العلمي": q_tot_pf,
                    "اجتماعات دورية مع الهيئة البحثية والعاملين": q_per_meet,
                    "اجتماعات مجلس إدارة المعهد": q_brd_meet,
                    "اجتماعات وحدة الفكر": q_think,
                    "آليات تسويق إمكانات المعهد": q_marketing,
                    "آليات الثواب والعقاب": q_rewards,
                    "عدد الاجتماعات الوزارية": q_min_meet,
                    "ملاحظات عامة": q_notes
                }
                
                result = update_or_append_row(
                    "Quarterly_KPI", data,
                    ["المعهد", "الربع", "السنة المالية"],
                    QUARTERLY_COLUMNS
                )
                
                if result == "updated":
                    st.success("✅ تم تحديث البيانات الربع سنوية")
                elif result == "added":
                    st.success("✅ تم حفظ البيانات الربع سنوية")
                
                invalidate_all_cache()
                st.balloons()
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# ============================================================
# 📝 إدخال القوائم الشهرية
# ============================================================
if tab_lists_input is not None:
    with tab_lists_input:
        st.header("📝 إدخال القوائم التفصيلية الشهرية")
        
        c1, c2 = st.columns(2)
        with c1:
            ml_month = st.selectbox("الشهر", [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ], key="ml_m")
        with c2:
            ml_year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="ml_y")
        
        period_val = f"{ml_month} {ml_year}"
        st.info(f"📌 {st.session_state.institute} — {period_val}")
        st.divider()
        
        list_tabs = st.tabs([
            "📚 الدراسات البحثية", "💼 مشروعات ممولة", "🎯 استشارات ممولة",
            "📄 التقارير الفنية", "🤝 الاجتماعات", "🎓 التدريب",
            "👥 اجتماعات تحسين الأداء"
        ])
        
        def render_list_editor(tab_obj, sheet_name, base_cols, title, key_prefix):
            with tab_obj:
                st.markdown(f"### 📝 {title}")
                st.caption("يمكنك إضافة/تعديل الصفوف. سيتم استرجاع البيانات المحفوظة تلقائياً.")
                st.divider()
                
                full_cols = base_cols + ["المعهد", "الفترة"]
                data = load_sheet_data(sheet_name, full_cols)
                
                if not data.empty and "المعهد" in data.columns and "الفترة" in data.columns:
                    data = data[
                        (data["المعهد"] == st.session_state.institute) &
                        (data["الفترة"] == period_val)
                    ]
                
                if data.empty:
                    data_clean = pd.DataFrame(columns=base_cols)
                    st.info("📝 لا توجد بيانات محفوظة لهذه الفترة")
                else:
                    data_clean = data[base_cols].fillna("").reset_index(drop=True)
                    st.success(f"✅ تم استرجاع {len(data_clean)} صف محفوظ")
                
                editor_key = f"{key_prefix}_ed_{period_val}_{st.session_state.editor_counter}"
                
                if not data_clean.empty:
                    display_df = rtl_display(data_clean)
                else:
                    display_df = pd.DataFrame(columns=list(reversed(base_cols)))
                
                input_df_rtl = st.data_editor(
                    display_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=editor_key,
                    hide_index=True
                )
                
                if not input_df_rtl.empty:
                    input_df = input_df_rtl[base_cols]
                else:
                    input_df = input_df_rtl
                
                if st.button(f"💾 حفظ {title}", key=f"{key_prefix}_sv_{period_val}"):
                    save_list_data(sheet_name, input_df, base_cols,
                                   st.session_state.institute, "الفترة", period_val)
        
        render_list_editor(list_tabs[0], "الدراسات_البحثية", STUDIES_COLUMNS, "الدراسات البحثية", "st")
        render_list_editor(list_tabs[1], "مشروعات_ممولة", PROJECTS_COLUMNS, "المشروعات الممولة", "pr")
        render_list_editor(list_tabs[2], "استشارات_ممولة", CONSULT_COLUMNS, "الاستشارات الممولة", "cn")
        render_list_editor(list_tabs[3], "التقارير_الفنية", REPORTS_COLUMNS, "التقارير الفنية", "rp")
        render_list_editor(list_tabs[4], "الاجتماعات", MEETINGS_COLUMNS, "الاجتماعات", "mt")
        render_list_editor(list_tabs[5], "التدريب", TRAINING_COLUMNS, "التدريب والندوات", "tr")
        render_list_editor(list_tabs[6], "اجتماعات_تحسين_الأداء", PERF_MEETINGS_COLUMNS, "اجتماعات تحسين الأداء", "pf")

# ============================================================
# 📋 إدخال القوائم الربع سنوية
# ============================================================
if tab_q_lists_input is not None:
    with tab_q_lists_input:
        st.header("📋 إدخال القوائم الربع سنوية")
        
        c1, c2 = st.columns(2)
        with c1:
            ql_q = st.selectbox("الربع",
                ["الربع الأول", "الربع الثاني", "الربع الثالث", "الربع الرابع"],
                key="ql_q")
        with c2:
            ql_fy = st.selectbox("السنة المالية",
                ["2025/2026", "2026/2027", "2027/2028"], key="ql_fy")
        
        ql_period = f"{ql_q} - {ql_fy}"
        st.info(f"📌 {st.session_state.institute} — {ql_period}")
        st.divider()
        
        q_tabs = st.tabs([
            "1-1 فردية", "1-2 مشتركة",
            "2-1-1 محلياً", "2-1-2 دولياً",
            "2-1-3 تكليفات", "2-1-4 استشارات",
            "2-2-1 مقترحات محلية", "2-2-2 مقترحات دولية",
            "2-2-3 مقترحات للوزارة", "2-2-4 مقترحات خارجية",
            "3-1 تعاون داخلي", "3-2 تعاون خارجي",
            "4-1 أبحاث", "4-2 عضويات دولية", "4-3 عضويات محلية",
            "8 اجتماعات وزارية"
        ])
        
        def render_q_list(tab_obj, sheet_name, cols, title, key):
            with tab_obj:
                st.markdown(f"### 📋 {title}")
                st.divider()
                
                full_cols = cols + ["المعهد", "الفترة"]
                data = load_sheet_data(sheet_name, full_cols)
                
                if not data.empty and "المعهد" in data.columns and "الفترة" in data.columns:
                    data = data[
                        (data["المعهد"] == st.session_state.institute) &
                        (data["الفترة"] == ql_period)
                    ]
                
                if data.empty:
                    data_clean = pd.DataFrame(columns=cols)
                else:
                    data_clean = data[cols].fillna("").reset_index(drop=True)
                    st.success(f"✅ تم استرجاع {len(data_clean)} صف")
                
                editor_key = f"{key}_ed_{ql_period}_{st.session_state.editor_counter}"
                
                if not data_clean.empty:
                    display_df = rtl_display(data_clean)
                else:
                    display_df = pd.DataFrame(columns=list(reversed(cols)))
                
                input_df_rtl = st.data_editor(
                    display_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=editor_key,
                    hide_index=True
                )
                
                if not input_df_rtl.empty:
                    input_df = input_df_rtl[cols]
                else:
                    input_df = input_df_rtl
                
                if st.button(f"💾 حفظ", key=f"{key}_sv_{ql_period}"):
                    save_list_data(sheet_name, input_df, cols,
                                   st.session_state.institute, "الفترة", ql_period)
        
        render_q_list(q_tabs[0], "Q_مشاريع_فردية", Q_STUDIES_INDIV, "مشاريع فردية", "q1")
        render_q_list(q_tabs[1], "Q_مشاريع_مشتركة", Q_STUDIES_JOINT, "مشاريع مشتركة", "q2")
        render_q_list(q_tabs[2], "Q_ممولة_محلياً", Q_FUNDED_LOCAL, "ممولة محلياً", "q3")
        render_q_list(q_tabs[3], "Q_ممولة_دولياً", Q_FUNDED_INTL, "ممولة دولياً", "q4")
        render_q_list(q_tabs[4], "Q_تكليفات_وزارة", Q_MINISTRY_ASSIGN, "تكليفات وزارة", "q5")
        render_q_list(q_tabs[5], "Q_استشارات_وزارة", Q_MINISTRY_CONSULT, "استشارات وزارة", "q6")
        render_q_list(q_tabs[6], "Q_مقترحات_محلية", Q_PROPOSALS_LOCAL, "مقترحات محلية", "q7")
        render_q_list(q_tabs[7], "Q_مقترحات_دولية", Q_PROPOSALS_INTL, "مقترحات دولية", "q8")
        render_q_list(q_tabs[8], "Q_مقترحات_وزارة", Q_PROPOSALS_MINISTRY, "مقترحات للوزارة", "q9")
        render_q_list(q_tabs[9], "Q_مقترحات_خارج_الوزارة", Q_PROPOSALS_OUTSIDE, "مقترحات خارج الوزارة", "q10")
        render_q_list(q_tabs[10], "Q_تعاون_داخلي", Q_COLLAB_INTERNAL, "تعاون داخلي", "q11")
        render_q_list(q_tabs[11], "Q_تعاون_خارجي", Q_COLLAB_EXTERNAL, "تعاون خارجي", "q12")
        render_q_list(q_tabs[12], "Q_أبحاث_منشورة", Q_PUBLICATIONS, "أبحاث منشورة", "q13")
        render_q_list(q_tabs[13], "Q_عضويات_دولية", Q_ORGS_INTL, "عضويات دولية", "q14")
        render_q_list(q_tabs[14], "Q_عضويات_محلية", Q_ORGS_LOCAL, "عضويات محلية", "q15")
        render_q_list(q_tabs[15], "Q_اجتماعات_وزارية", Q_MINISTRY_MEETINGS, "اجتماعات وزارية", "q16")

# ============================================================
# 📈 Dashboard الشهري
# ============================================================
if 'tab_m_dashboard' in dir() and tab_m_dashboard is not None:
    with tab_m_dashboard:
        st.title("📈 لوحة مؤشرات الأداء الشهرية")
        
        if not df_monthly.empty:
            text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
            df_m_disp = df_monthly.copy()
            for col in df_m_disp.columns:
                if col not in text_cols:
                    df_m_disp[col] = pd.to_numeric(df_m_disp[col], errors="coerce").fillna(0)
            
            st.subheader("🎯 مؤشرات رئيسية")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("📚 الدراسات", safe_sum(df_m_disp, "إجمالي الدراسات الجارية"))
            c2.metric("📄 التقارير", safe_sum(df_m_disp, "إجمالي التقارير"))
            c3.metric("📋 المقترحات", safe_sum(df_m_disp, "إجمالي المقترحات"))
            c4.metric("🤝 الاجتماعات", safe_sum(df_m_disp, "إجمالي الاجتماعات"))
            c5.metric("👨‍🎓 المتدربين", safe_sum(df_m_disp, "متدربين"))
            
            st.divider()
            
            st.subheader("📊 مؤشرات تفصيلية")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("🏃 المأموريات", safe_sum(df_m_disp, "إجمالي عدد المأموريات"))
            c2.metric("🔍 المعاينات", safe_sum(df_m_disp, "إجمالي عدد المعاينات"))
            c3.metric("📝 الأوراق", safe_sum(df_m_disp, "إجمالي الأوراق البحثية"))
            c4.metric("🎓 الرسائل", safe_sum(df_m_disp, "إجمالي الرسائل"))
            c5.metric("👥 العاملون", safe_sum(df_m_disp, "إجمالي عدد العاملين الفعلي"))
            
            st.divider()
            
            if "المعهد" in df_m_disp.columns:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 📚 الدراسات الجارية")
                    fig = px.bar(df_m_disp, x="المعهد",
                                y=["دراسات خطة بحثية جارية", "دراسات استشارية جارية", "دراسات بتمويل ذاتي جارية"],
                                barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 📄 التقارير")
                    fig = px.bar(df_m_disp, x="المعهد",
                                y=["تقرير مرحلي", "تقرير نهائي", "تقرير معاينة", "تقرير معايرة", "تقرير أخرى"],
                                barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 👥 التدريب")
                    fig = px.bar(df_m_disp, x="المعهد", y=["متدربين", "مدربين"], barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 🤝 الاجتماعات")
                    fig = px.bar(df_m_disp, x="المعهد",
                                y=["اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية",
                                   "اجتماعات مع العاملين", "اجتماعات جهات أخرى"],
                                barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📭 لا توجد بيانات شهرية")

# ============================================================
# 📊 لوحة التقارير الربع سنوية
# ============================================================
if tab_q_dashboard is not None:
    with tab_q_dashboard:
        st.title("📊 التقارير الربع سنوية")
        
        df_q = load_sheet_data("Quarterly_KPI", QUARTERLY_COLUMNS)
        
        if df_q.empty:
            st.info("📭 لا توجد بيانات ربع سنوية")
            st.stop()
        
        q_text_cols = ["المعهد", "المستخدم", "الربع", "السنة المالية",
                       "آليات تسويق إمكانات المعهد", "آليات الثواب والعقاب", "ملاحظات عامة"]
        for col in df_q.columns:
            if col not in q_text_cols:
                df_q[col] = pd.to_numeric(df_q[col], errors="coerce").fillna(0)
        
        st.markdown("### 🔍 الفلاتر")
        c1, c2, c3 = st.columns(3)
        with c1:
            q_opts = ["الكل"] + sorted(df_q["الربع"].unique())
            sel_q = st.selectbox("الربع", q_opts, key="dq_q")
        with c2:
            y_opts = ["الكل"] + sorted(df_q["السنة المالية"].unique())
            sel_y = st.selectbox("السنة المالية", y_opts, key="dq_y")
        with c3:
            if st.session_state.role == "admin":
                i_opts = ["الكل"] + sorted(df_q["المعهد"].unique())
                sel_i = st.selectbox("المعهد", i_opts, key="dq_i")
            else:
                sel_i = st.session_state.institute
        
        fq = df_q.copy()
        if sel_q != "الكل": fq = fq[fq["الربع"] == sel_q]
        if sel_y != "الكل": fq = fq[fq["السنة المالية"] == sel_y]
        if st.session_state.role == "admin" and sel_i != "الكل":
            fq = fq[fq["المعهد"] == sel_i]
        elif st.session_state.role != "admin":
            fq = fq[fq["المعهد"] == st.session_state.institute]
        
        st.divider()
        
        if fq.empty:
            st.warning("لا توجد بيانات")
            st.stop()
        
        st.markdown("## 📌 نظرة عامة")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🏢 معاهد", fq["المعهد"].nunique())
        c2.metric("📅 سجلات", len(fq))
        c3.metric("🔬 أبحاث", int(fq["أبحاث منشورة"].sum()))
        c4.metric("📋 مقترحات", int(fq["إجمالي المقترحات"].sum()))
        c5.metric("🎓 تدريب", int(fq["إجمالي التدريب - عدد"].sum()))
        
        st.divider()
        
        st.markdown("## 1️⃣ الأداء التنفيذي")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📚 المشاريع البحثية")
            fig = px.bar(fq, x="المعهد", y=["فردي - عدد المشاريع", "مشترك - عدد المشاريع"], barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### 📊 نسب التنفيذ")
            fig = px.bar(fq, x="المعهد", y=["فردي - نسبة المنفذ %", "مشترك - نسبة المنفذ %", "مشترك - نسبة المشاركة %"], barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("## 2️⃣ الاستشارات والدراسات")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد", y=["مشاريع ممولة محلياً", "مشاريع ممولة دولياً", "تكليفات من الوزارة", "استشارات من الوزارة", "استشارات من جهات حكومية/خاصة"], barmode="stack", title="المشاريع")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد", y=["مقترحات محلية", "مقترحات دولية", "مقترحات للوزارة", "مقترحات خارج الوزارة"], barmode="stack", title="المقترحات")
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("## 3️⃣ التعاون")
        fig = px.bar(fq, x="المعهد", y=["تعاون داخلي مع المعاهد", "تعاون داخلي مع جهات خارج المعاهد", "تعاون خارجي مع جهات أجنبية"], barmode="group")
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("## 4️⃣ الإنتاج العلمي")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد", y=["أبحاث منشورة", "أبحاث في مجلات متميزة Q1/Q2", "أبحاث حصلت على موافقة النشر"], barmode="group", title="الأبحاث")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد", y=["رسائل ماجستير", "رسائل دكتوراه"], barmode="group", title="الرسائل")
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("## 5️⃣ التدريب")
        tr_cols = [c for c in fq.columns if "- عدد" in c and c != "إجمالي التدريب - عدد"]
        if tr_cols:
            fig = px.bar(fq, x="المعهد", y=tr_cols, barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("## 6️⃣ التمويل")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد", y=["تمويل الخطة البحثية - مبلغ", "تمويل خارجي - مبلغ", "المنصرف الفعلي - مبلغ"], barmode="group", title="مصادر التمويل")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد", y=["تمويل نشر علمي - دراسات", "تمويل نشر علمي - أبحاث", "تمويل نشر علمي - مكافآت"], barmode="stack", title="تمويل النشر")
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("## 7️⃣ الموارد البشرية")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد", y=["اجتماعات دورية مع الهيئة البحثية والعاملين", "اجتماعات مجلس إدارة المعهد", "اجتماعات وحدة الفكر"], barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            disp = fq[["المعهد", "الربع", "آليات تسويق إمكانات المعهد", "آليات الثواب والعقاب"]].copy()
            st.dataframe(rtl_display(disp), use_container_width=True, hide_index=True)
        
        st.markdown("## 8️⃣ الاجتماعات الوزارية")
        fig = px.bar(fq, x="المعهد", y="عدد الاجتماعات الوزارية", color="الربع")
        st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        st.markdown("## 📋 الملخص التنفيذي")
        for inst in fq["المعهد"].unique():
            i_df = fq[fq["المعهد"] == inst]
            with st.expander(f"🏢 {inst}", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📚 مشاريع", int(i_df["فردي - عدد المشاريع"].sum() + i_df["مشترك - عدد المشاريع"].sum()))
                c2.metric("📄 تقارير", int(i_df["فردي - عدد التقارير"].sum() + i_df["مشترك - عدد التقارير"].sum()))
                c3.metric("🔬 أبحاث", int(i_df["أبحاث منشورة"].sum()))
                c4.metric("📋 مقترحات", int(i_df["إجمالي المقترحات"].sum()))
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("🎓 ماجستير", int(i_df["رسائل ماجستير"].sum()))
                c2.metric("🎓 دكتوراه", int(i_df["رسائل دكتوراه"].sum()))
                c3.metric("💰 تمويل", f"{i_df['تمويل الخطة البحثية - مبلغ'].sum():.1f}")
                c4.metric("💵 منصرف", f"{i_df['المنصرف الفعلي - مبلغ'].sum():.1f}")
        
        st.divider()
        st.markdown("## 📄 الجدول الشامل للتقارير الربع سنوية")
        st.caption(f"عدد المعاهد: {fq['المعهد'].nunique()} | عدد السجلات: {len(fq)}")
        st.divider()
        
        main_cols = ["المعهد", "الربع", "السنة المالية", "فردي - عدد المشاريع", "مشترك - عدد المشاريع",
                     "إجمالي المشاريع خارج الخطة", "إجمالي المقترحات", "أبحاث منشورة",
                     "رسائل ماجستير", "رسائل دكتوراه", "إجمالي التدريب - عدد",
                     "إجمالي التدريب - متدربين", "تمويل الخطة البحثية - مبلغ",
                     "تمويل خارجي - مبلغ", "عدد الاجتماعات الوزارية"]
        disp_cols = [c for c in main_cols if c in fq.columns]
        st.dataframe(rtl_display(fq[disp_cols]), use_container_width=True, hide_index=True)
        
        def to_excel(d):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as w:
                d.to_excel(w, index=False, sheet_name="Quarterly")
            return out.getvalue()
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 تحميل Excel", data=to_excel(fq),
                              file_name=f"quarterly_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            st.download_button("📥 تحميل CSV",
                              data=fq.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'),
                              file_name=f"quarterly_{datetime.now().strftime('%Y%m%d')}.csv",
                              mime="text/csv")

# ============================================================
# 📉 التغير الشهري
# ============================================================
if tab_trend is not None:
    with tab_trend:
        st.title("📉 التغير الشهري")
        
        if not df_monthly.empty and "الشهر" in df_monthly.columns:
            df_t = df_monthly.copy()
            df_t["شهر-سنة"] = df_t["الشهر"].astype(str) + " - " + df_t["السنة"].astype(str)
            months_order = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
            df_t["الشهر_مرتب"] = pd.Categorical(df_t["الشهر"], categories=months_order, ordered=True)
            df_t = df_t.sort_values(["السنة", "الشهر_مرتب"])
            
            avail_metrics = [m for m in [
                "إجمالي الدراسات الجارية", "إجمالي التقارير", "إجمالي المقترحات",
                "إجمالي الاجتماعات", "متدربين", "مدربين",
                "إجمالي عدد المأموريات", "إجمالي عدد المعاينات",
                "إجمالي الأوراق البحثية", "إجمالي الرسائل"
            ] if m in df_t.columns]
            
            if avail_metrics:
                st.markdown("### 📊 اختر المؤشر")
                metric = st.selectbox("اختر المؤشر", avail_metrics, key="trend_m")
                
                if st.session_state.role == "admin" and "المعهد" in df_t.columns:
                    fig = px.line(df_t, x="شهر-سنة", y=metric, color="المعهد", markers=True)
                else:
                    fig = px.line(df_t, x="شهر-سنة", y=metric, markers=True,
                                 title=f"{metric} - {st.session_state.institute}")
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📭 لا توجد بيانات")

# ============================================================
# 📄 البيانات الشهرية
# ============================================================
if tab_data is not None:
    with tab_data:
        st.title("📄 البيانات الشهرية")
        
        if not df_monthly.empty:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.session_state.role == "admin" and "المعهد" in df_monthly.columns:
                    fi = st.multiselect("المعهد", options=df_monthly["المعهد"].unique(), default=df_monthly["المعهد"].unique())
                else:
                    fi = [st.session_state.institute]
            with c2:
                fy = st.multiselect("السنة", options=sorted(df_monthly["السنة"].unique()), default=sorted(df_monthly["السنة"].unique()))
            with c3:
                fm = st.multiselect("الشهر", options=df_monthly["الشهر"].unique(), default=df_monthly["الشهر"].unique())
            
            fd = df_monthly.copy()
            if "المعهد" in fd.columns and fi: fd = fd[fd["المعهد"].isin(fi)]
            if "السنة" in fd.columns and fy: fd = fd[fd["السنة"].isin(fy)]
            if "الشهر" in fd.columns and fm: fd = fd[fd["الشهر"].isin(fm)]
            
            st.markdown("### 📊 جدول البيانات الشهرية")
            st.caption(f"عدد السجلات: {len(fd)} | عدد الأعمدة: {len(fd.columns)}")
            st.divider()
            st.dataframe(rtl_display(fd), use_container_width=True, hide_index=True)
            
            def to_excel_m(d):
                out = BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as w:
                    d.to_excel(w, index=False, sheet_name="Monthly")
                return out.getvalue()
            
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 تحميل Excel", data=to_excel_m(fd),
                                  file_name=f"monthly_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with c2:
                st.download_button("📥 تحميل CSV",
                                  data=fd.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'),
                                  file_name=f"monthly_{datetime.now().strftime('%Y%m%d')}.csv",
                                  mime="text/csv")
        else:
            st.info("📭 لا توجد بيانات")

# ============================================================
# 📋 عرض القوائم (للأدمن)
# ============================================================
if tab_lists is not None:
    with tab_lists:
        st.title("📋 القوائم التفصيلية")
        
        c1, c2 = st.columns(2)
        with c1:
            v_month = st.selectbox("الشهر", [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ], key="v_m")
        with c2:
            v_year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="v_y")
        
        v_period = f"{v_month} {v_year}"
        
        v_tabs = st.tabs([
            "📚 الدراسات", "💼 مشروعات", "🎯 استشارات",
            "📄 تقارير فنية", "🤝 اجتماعات", "🎓 تدريب",
            "👥 تحسين الأداء"
        ])
        
        def view_list(tab_obj, sheet_name, cols, title, key):
            with tab_obj:
                st.markdown(f"### 📋 {title}")
                full = cols + ["المعهد", "الفترة"]
                data = load_sheet_data(sheet_name, full)
                if data.empty:
                    st.info("لا توجد بيانات")
                    return
                if "الفترة" in data.columns:
                    data = data[data["الفترة"] == v_period]
                if st.session_state.role != "admin" and "المعهد" in data.columns:
                    data = data[data["المعهد"] == st.session_state.institute]
                if data.empty:
                    st.info("لا توجد بيانات للفترة المحددة")
                else:
                    st.caption(f"عدد السجلات: {len(data)}")
                    st.divider()
                    st.dataframe(rtl_display(data[cols]), use_container_width=True, hide_index=True)
        
        view_list(v_tabs[0], "الدراسات_البحثية", STUDIES_COLUMNS, "الدراسات البحثية", "v1")
        view_list(v_tabs[1], "مشروعات_ممولة", PROJECTS_COLUMNS, "المشروعات الممولة", "v2")
        view_list(v_tabs[2], "استشارات_ممولة", CONSULT_COLUMNS, "الاستشارات الممولة", "v3")
        view_list(v_tabs[3], "التقارير_الفنية", REPORTS_COLUMNS, "التقارير الفنية", "v4")
        view_list(v_tabs[4], "الاجتماعات", MEETINGS_COLUMNS, "الاجتماعات", "v5")
        view_list(v_tabs[5], "التدريب", TRAINING_COLUMNS, "التدريب والندوات", "v6")
        view_list(v_tabs[6], "اجتماعات_تحسين_الأداء", PERF_MEETINGS_COLUMNS, "اجتماعات تحسين الأداء", "v7")
