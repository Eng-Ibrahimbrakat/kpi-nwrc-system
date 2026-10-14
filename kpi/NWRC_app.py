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
[data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td,
[data-testid="stDataEditor"] th, [data-testid="stDataEditor"] td {
    text-align: right !important; direction: rtl !important;
}
[data-testid="stDataFrame"] thead th, [data-testid="stDataEditor"] thead th {
    background-color: #f0f2f6 !important; font-weight: bold !important;
}
h1, h2, h3, h4, h5, h6 { direction: rtl; text-align: right; }
.stTabs [data-baseweb="tab-list"] { direction: rtl; }
.stTextInput input, .stNumberInput input, .stTextArea textarea { direction: rtl; text-align: right; }
.stSelectbox div[data-baseweb="select"] { direction: rtl; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Google Sheets - نظام Cache
# ============================================================
SPREADSHEET_KEY = "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"

@st.cache_resource(show_spinner=False)
def _get_client():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def _get_spreadsheet(_bust=0):
    return _get_client().open_by_key(SPREADSHEET_KEY)

@st.cache_resource(show_spinner=False)
def _get_worksheet_cached(name, _bust=0):
    try:
        return _get_spreadsheet(_bust=_bust).worksheet(name)
    except gspread.WorksheetNotFound:
        return None
    except Exception:
        return None

def get_spreadsheet():
    return _get_spreadsheet(_bust=st.session_state.get("gs_bust", 0))

def get_worksheet(name):
    return _get_worksheet_cached(name, _bust=st.session_state.get("gs_bust", 0))

def get_or_create_sheet(name, headers=None):
    ws = get_worksheet(name)
    if ws is not None:
        return ws
    time.sleep(0.5)
    try:
        return get_spreadsheet().worksheet(name)
    except gspread.WorksheetNotFound:
        pass
    except Exception:
        pass
    try:
        ss = get_spreadsheet()
        ws = ss.add_worksheet(title=name, rows=1000, cols=30)
        if headers:
            ws.append_row(headers)
        st.session_state.gs_bust = st.session_state.get("gs_bust", 0) + 1
        return ws
    except Exception as e:
        err = str(e).lower()
        if "already exists" in err:
            time.sleep(1)
            try:
                return get_spreadsheet().worksheet(name)
            except Exception:
                return None
        st.error(f"❌ خطأ في الوصول للورقة {name}: {e}")
        return None

@st.cache_data(ttl=180, show_spinner=False)
def _fetch_cached(name, _bust=0):
    try:
        ws = get_worksheet(name)
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

def fetch_data(name):
    return _fetch_cached(name, _bust=st.session_state.get("gs_bust", 0))

def invalidate_all():
    st.session_state.gs_bust = st.session_state.get("gs_bust", 0) + 1
    st.session_state.data_bust = st.session_state.get("data_bust", 0) + 1
    _fetch_cached.clear()

# ============================================================
# دوال مساعدة
# ============================================================
def fix_encoding(t):
    if isinstance(t, str):
        try:
            return t.encode('latin1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return t
    return t

def rtl_display(df):
    if df.empty:
        return df
    return df[list(reversed(df.columns))]

def load_data(sheet, cols):
    key = f"_cd_{sheet}"
    bust = st.session_state.get("data_bust", 0)
    if st.session_state.get(f"_cb_{sheet}") == bust and key in st.session_state:
        return st.session_state[key].copy()
    vals = fetch_data(sheet)
    if len(vals) <= 1:
        df = pd.DataFrame(columns=cols)
    else:
        headers = [fix_encoding(h) for h in vals[0]]
        df = pd.DataFrame(vals[1:], columns=headers)
        for c in df.columns:
            if df[c].dtype == 'object' and c not in cols:
                df[c] = df[c].apply(fix_encoding)
    st.session_state[key] = df.copy()
    st.session_state[f"_cb_{sheet}"] = bust
    return df

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

def get_existing(df, filters):
    if df.empty:
        return None
    m = df.copy()
    for c, v in filters.items():
        if c in m.columns:
            m = m[m[c] == v]
    return None if m.empty else m.iloc[0]

def safe_sum(df, col):
    if df.empty or col not in df.columns:
        return 0
    return int(pd.to_numeric(df[col], errors='coerce').fillna(0).sum())

def update_or_append(sheet, data, key_cols, all_cols):
    try:
        ws = get_or_create_sheet(sheet, all_cols)
        if ws is None:
            return None
        vals = ws.get_all_values()
        if len(vals) <= 1:
            ws.append_row([str(data.get(c, "")) for c in all_cols])
            return "added"
        headers = vals[0]
        for idx, row in enumerate(vals[1:]):
            if all(headers.index(k) < len(row) and str(row[headers.index(k)]) == str(data.get(k, ""))
                   for k in key_cols if k in headers):
                ws.update(f"A{idx + 2}", [[str(data.get(c, "")) for c in headers]])
                return "updated"
        ws.append_row([str(data.get(c, "")) for c in headers])
        return "added"
    except Exception as e:
        st.error(f"خطأ: {e}")
        return None

def save_list(sheet, df, base_cols, institute, period_val):
    try:
        full = base_cols + ["المعهد", "الفترة"]
        ws = get_or_create_sheet(sheet, full)
        if ws is None:
            return
        vals = ws.get_all_values()
        kept = []
        if len(vals) > 1:
            ex = pd.DataFrame(vals[1:], columns=vals[0])
            if "المعهد" in ex.columns and "الفترة" in ex.columns:
                mask = ~((ex["المعهد"] == institute) & (ex["الفترة"] == period_val))
                kept = ex[mask].values.tolist()
        ws.clear()
        ws.append_row(full)
        if kept:
            ws.append_rows([[str(v) for v in r] for r in kept])
        new = []
        for _, r in df.iterrows():
            v = [str(x) if pd.notna(x) else "" for x in r.tolist()]
            if all(x.strip() in ["", "nan", "None"] for x in v):
                continue
            new.append(v + [institute, period_val])
        if new:
            ws.append_rows(new)
        invalidate_all()
        st.session_state.editor_counter = st.session_state.get("editor_counter", 0) + 1
        st.success(f"✅ تم حفظ البيانات في {sheet}")
        time.sleep(0.4)
        st.rerun()
    except Exception as e:
        st.error(f"❌ خطأ: {e}")

# ============================================================
# الأعمدة الموحدة
# ============================================================
MONTHLY_COLUMNS = [
    "المعهد", "المستخدم", "الشهر", "السنة",
    # شهري
    "عدد الدراسات الجارية - خطة بحثية",
    "عدد الدراسات الجارية - دراسات استشارية",
    "عدد الدراسات الجارية - مشروعات بحثية",
    "إجمالي عدد الدراسات الجارية",
    "عدد التقارير الصادرة - تقرير مرحلي",
    "عدد التقارير الصادرة - تقرير نهائي",
    "عدد المذكرات الصادرة",
    "عدد المقترحات الفنية والمالية - مقترحات دراسات استشارية",
    "عدد المقترحات الفنية والمالية - مقترحات مشروعات بحثية",
    "المأموريات الحقلية - إجمالي عدد الأيام الفعلية",
    "عدد المشتركين في التدريب - كمتدربين",
    "عدد المشاركين في التدريب - كمدربين",
    "إجمالي عدد أيام التدريب للمتدربين - من داخل المعهد",
    "إجمالي عدد أيام التدريب للمتدربين - من خارج المعهد",
    "عدد المشتركين في حضور أنشطة علمية - مؤتمرات",
    "عدد المشتركين في حضور أنشطة علمية - ورش عمل",
    "إجمالي عدد المشاركين في أنشطة علمية",
    "الاجتماعات - بالوزارة",
    "الاجتماعات - بالمركز",
    "الاجتماعات - جهات خارجية",
    "إجمالي الاجتماعات",
    "إجمالي عدد الأوراق البحثية - المنشورة",
    "عدد الأوراق البحثية دولياً - المنشورة",
    "رسائل الماجستير والدكتوراة - المنتهية",
    # نصف سنوي (يناير، يوليو)
    "إجمالي عدد دراسات الخطة البحثية المنجزة",
    "إجمالي عدد المخرجات التطبيقية",
    "إجمالي مبلغ الإيرادات الذاتية",
    # ربع سنوي (يناير، أبريل، يوليو، أكتوبر)
    "احصائيات الكادر البحثي والتخصصي - عدد الباحثين",
    "احصائيات الكادر البحثي والتخصصي - عدد الأساتذة بدون المتفرغين",
    "احصائيات الكادر البحثي والتخصصي - عدد المهندسين",
    "احصائيات الكادر البحثي والتخصصي - إجمالي عدد العاملين",
    "المبلغ المنصرف من الموازنة الاستثمارية",
    # سنوي (يوليو)
    "عدد براءات الاختراع",
]

# ربط المدخل الرقمي بالقائمة
NUMERIC_TO_LIST = {
    "عدد الدراسات الجارية - خطة بحثية":
        ("دراسات_خطة_بحثية", ["م", "عنوان الدراسة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]),
    "عدد الدراسات الجارية - دراسات استشارية":
        ("دراسات_استشارية", ["م", "عنوان الدراسة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]),
    "عدد الدراسات الجارية - مشروعات بحثية":
        ("مشروعات_بحثية", ["م", "عنوان المشروع", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]),
    "عدد التقارير الصادرة - تقرير مرحلي":
        ("تقارير_مرحلية", ["م", "عنوان التقرير", "الجهة المستفيدة", "تاريخ الإصدار", "ملخص التقرير"]),
    "عدد التقارير الصادرة - تقرير نهائي":
        ("تقارير_نهائية", ["م", "عنوان التقرير", "الجهة المستفيدة", "تاريخ الإصدار", "ملخص التقرير"]),
    "عدد المذكرات الصادرة":
        ("مذكرات", ["م", "عنوان المذكرة", "الجهة المستفيدة", "التاريخ", "ملخص المذكرة"]),
    "عدد المقترحات الفنية والمالية - مقترحات دراسات استشارية":
        ("مقترحات_استشارية", ["م", "عنوان المقترح", "الجهة المقدمة لها", "تاريخ التقديم", "حالة المقترح"]),
    "عدد المقترحات الفنية والمالية - مقترحات مشروعات بحثية":
        ("مقترحات_بحثية", ["م", "عنوان المقترح", "الجهة المقدمة لها", "تاريخ التقديم", "حالة المقترح"]),
    "عدد المشتركين في حضور أنشطة علمية - مؤتمرات":
        ("مؤتمرات", ["م", "عنوان المؤتمر", "المكان", "التاريخ", "عدد المشاركين"]),
    "عدد المشتركين في حضور أنشطة علمية - ورش عمل":
        ("ورش_عمل", ["م", "عنوان الورشة", "المكان", "التاريخ", "عدد المشاركين"]),
    "الاجتماعات - بالوزارة":
        ("اجتماعات_وزارة", ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض من الاجتماع"]),
    "الاجتماعات - بالمركز":
        ("اجتماعات_مركز", ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض من الاجتماع"]),
    "الاجتماعات - جهات خارجية":
        ("اجتماعات_خارجية", ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض من الاجتماع"]),
    "إجمالي عدد الأوراق البحثية - المنشورة":
        ("أوراق_بحثية", ["م", "عنوان البحث", "المجلة", "التصنيف", "تاريخ النشر", "الباحث الرئيسي"]),
    "عدد الأوراق البحثية دولياً - المنشورة":
        ("أوراق_دولية", ["م", "عنوان البحث", "المجلة", "التصنيف", "تاريخ النشر", "الباحث الرئيسي"]),
    "رسائل الماجستير والدكتوراة - المنتهية":
        ("رسائل_علمية", ["م", "عنوان الرسالة", "اسم الباحث", "الدرجة العلمية", "تاريخ المناقشة"]),
}

# مجموعات الأشهر
QUARTER_MONTHS = ["يناير", "أبريل", "يوليو", "أكتوبر"]
SEMI_MONTHS = ["يناير", "يوليو"]
ANNUAL_MONTHS = ["يوليو"]
ALL_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

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
        u = st.text_input("اسم المستخدم")
        p = st.text_input("كلمة المرور", type="password")
        if st.button("🚪 دخول", type="primary"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = USERS[u]["role"]
                st.session_state.institute = USERS[u]["institute"]
                invalidate_all()
                st.rerun()
            else:
                st.error("❌ بيانات الدخول غير صحيحة")
    st.stop()

# ============================================================
# الهيدر
# ============================================================
hc = st.columns([5, 1, 1])
with hc[0]:
    st.success(f"👤 **{st.session_state.username}** — 🏢 {st.session_state.institute}")
with hc[1]:
    if st.button("🔄 تحديث"):
        invalidate_all()
        st.rerun()
with hc[2]:
    if st.button("🚪 خروج"):
        st.session_state.clear()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# ============================================================
# تحميل البيانات
# ============================================================
df_monthly = load_data("KPI_Monthly", MONTHLY_COLUMNS)
if not df_monthly.empty and st.session_state.role != "admin" and "المعهد" in df_monthly.columns:
    df_monthly = df_monthly[df_monthly["المعهد"] == st.session_state.institute]

# ============================================================
# التبويبات
# ============================================================
if st.session_state.role == "admin":
    tabs = st.tabs(["📊 التقارير الربع سنوية", "📈 لوحة المؤشرات", "📉 التغير الشهري", "📄 البيانات الشهرية"])
    tab_q_report, tab_dash, tab_trend, tab_data = tabs
    tab_input = tab_lists = None
else:
    tabs = st.tabs(["📥 إدخال شهري", "📝 القوائم الشهرية", "📊 التقارير الربع سنوية",
                    "📈 لوحة المؤشرات", "📉 التغير الشهري", "📄 البيانات"])
    tab_input, tab_lists, tab_q_report, tab_dash, tab_trend, tab_data = tabs

# ============================================================
# 📥 إدخال شهري
# ============================================================
if tab_input is not None:
    with tab_input:
        st.header("📥 إدخال البيانات الشهرية")
        
        c1, c2 = st.columns(2)
        with c1:
            month = st.selectbox("الشهر", ALL_MONTHS, key="m_month")
        with c2:
            year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="m_year")
        
        existing = get_existing(df_monthly, {
            "المعهد": st.session_state.institute,
            "الشهر": month, "السنة": str(int(year))
        })
        
        # معلومات الشهر
        info_msgs = []
        if month in QUARTER_MONTHS: info_msgs.append("ربع سنوي")
        if month in SEMI_MONTHS: info_msgs.append("نصف سنوي")
        if month in ANNUAL_MONTHS: info_msgs.append("سنوي")
        if info_msgs:
            st.info(f"📅 شهر **{month}** يشمل بيانات: **{', '.join(info_msgs)}**")
        if existing is not None:
            st.warning("ℹ️ توجد بيانات محفوظة لهذا الشهر - سيتم تحديثها")
        
        kp = f"{month}_{year}"
        st.divider()
        
        # ============ 1. الدراسات الجارية ============
        st.subheader("📚 الدراسات الجارية")
        c1, c2, c3 = st.columns(3)
        n_studies_plan = c1.number_input("خطة بحثية", min_value=0, value=get_int(existing, "عدد الدراسات الجارية - خطة بحثية"), key=f"sp_{kp}")
        n_studies_consult = c2.number_input("دراسات استشارية", min_value=0, value=get_int(existing, "عدد الدراسات الجارية - دراسات استشارية"), key=f"sc_{kp}")
        n_studies_proj = c3.number_input("مشروعات بحثية", min_value=0, value=get_int(existing, "عدد الدراسات الجارية - مشروعات بحثية"), key=f"spr_{kp}")
        total_studies = n_studies_plan + n_studies_consult + n_studies_proj
        st.info(f"**إجمالي عدد الدراسات الجارية:** {total_studies}")
        
        # ============ 2. التقارير والمذكرات ============
        st.divider()
        st.subheader("📄 التقارير والمذكرات")
        c1, c2, c3 = st.columns(3)
        n_rep_prog = c1.number_input("تقرير مرحلي", min_value=0, value=get_int(existing, "عدد التقارير الصادرة - تقرير مرحلي"), key=f"rp_{kp}")
        n_rep_final = c2.number_input("تقرير نهائي", min_value=0, value=get_int(existing, "عدد التقارير الصادرة - تقرير نهائي"), key=f"rf_{kp}")
        n_memos = c3.number_input("عدد المذكرات", min_value=0, value=get_int(existing, "عدد المذكرات الصادرة"), key=f"mm_{kp}")
        
        # ============ 3. المقترحات ============
        st.divider()
        st.subheader("📋 المقترحات الفنية والمالية")
        c1, c2 = st.columns(2)
        n_prop_consult = c1.number_input("مقترحات دراسات استشارية", min_value=0, value=get_int(existing, "عدد المقترحات الفنية والمالية - مقترحات دراسات استشارية"), key=f"pc_{kp}")
        n_prop_research = c2.number_input("مقترحات مشروعات بحثية", min_value=0, value=get_int(existing, "عدد المقترحات الفنية والمالية - مقترحات مشروعات بحثية"), key=f"pr_{kp}")
        
        # ============ 4. المأموريات ============
        st.divider()
        st.subheader("🏃 المأموريات الحقلية")
        n_missions = st.number_input("إجمالي عدد الأيام الفعلية", min_value=0, value=get_int(existing, "المأموريات الحقلية - إجمالي عدد الأيام الفعلية"), key=f"mi_{kp}")
        
        # ============ 5. التدريب ============
        st.divider()
        st.subheader("👥 التدريب")
        c1, c2 = st.columns(2)
        n_trainees = c1.number_input("عدد المشتركين - كمتدربين", min_value=0, value=get_int(existing, "عدد المشتركين في التدريب - كمتدربين"), key=f"tr_{kp}")
        n_trainers = c2.number_input("عدد المشاركين - كمدربين", min_value=0, value=get_int(existing, "عدد المشاركين في التدريب - كمدربين"), key=f"trn_{kp}")
        c1, c2 = st.columns(2)
        n_train_days_in = c1.number_input("أيام التدريب - من داخل المعهد", min_value=0, value=get_int(existing, "إجمالي عدد أيام التدريب للمتدربين - من داخل المعهد"), key=f"tdi_{kp}")
        n_train_days_out = c2.number_input("أيام التدريب - من خارج المعهد", min_value=0, value=get_int(existing, "إجمالي عدد أيام التدريب للمتدربين - من خارج المعهد"), key=f"tdo_{kp}")
        
        # ============ 6. الأنشطة العلمية ============
        st.divider()
        st.subheader("🔬 الأنشطة العلمية")
        c1, c2 = st.columns(2)
        n_conf = c1.number_input("مؤتمرات", min_value=0, value=get_int(existing, "عدد المشتركين في حضور أنشطة علمية - مؤتمرات"), key=f"cn_{kp}")
        n_ws = c2.number_input("ورش عمل", min_value=0, value=get_int(existing, "عدد المشتركين في حضور أنشطة علمية - ورش عمل"), key=f"ws_{kp}")
        st.info(f"**إجمالي عدد المشاركين في أنشطة علمية:** {n_conf + n_ws}")
        
        # ============ 7. الاجتماعات ============
        st.divider()
        st.subheader("🤝 الاجتماعات")
        c1, c2, c3 = st.columns(3)
        n_meet_min = c1.number_input("بالوزارة", min_value=0, value=get_int(existing, "الاجتماعات - بالوزارة"), key=f"mm1_{kp}")
        n_meet_cen = c2.number_input("بالمركز", min_value=0, value=get_int(existing, "الاجتماعات - بالمركز"), key=f"mm2_{kp}")
        n_meet_ext = c3.number_input("جهات خارجية", min_value=0, value=get_int(existing, "الاجتماعات - جهات خارجية"), key=f"mm3_{kp}")
        st.info(f"**إجمالي الاجتماعات:** {n_meet_min + n_meet_cen + n_meet_ext}")
        
        # ============ 8. الأوراق البحثية والرسائل ============
        st.divider()
        st.subheader("📝 الأوراق البحثية والرسائل العلمية")
        c1, c2, c3 = st.columns(3)
        n_papers = c1.number_input("الأوراق البحثية - المنشورة", min_value=0, value=get_int(existing, "إجمالي عدد الأوراق البحثية - المنشورة"), key=f"pp_{kp}")
        n_papers_intl = c2.number_input("الأوراق البحثية دولياً", min_value=0, value=get_int(existing, "عدد الأوراق البحثية دولياً - المنشورة"), key=f"pi_{kp}")
        n_theses = c3.number_input("رسائل الماجستير والدكتوراة - المنتهية", min_value=0, value=get_int(existing, "رسائل الماجستير والدكتوراة - المنتهية"), key=f"th_{kp}")
        
        # ============ المدخلات الربع سنوية (يناير، أبريل، يوليو، أكتوبر) ============
        if month in QUARTER_MONTHS:
            st.divider()
            st.header("📊 المدخلات الربع سنوية")
            st.caption(f"تظهر في أشهر: يناير، أبريل، يوليو، أكتوبر")
            
            st.subheader("👤 احصائيات الكادر البحثي والتخصصي")
            c1, c2 = st.columns(2)
            n_researchers = c1.number_input("عدد الباحثين", min_value=0, value=get_int(existing, "احصائيات الكادر البحثي والتخصصي - عدد الباحثين"), key=f"qr_{kp}")
            n_profs = c2.number_input("عدد الأساتذة بدون المتفرغين", min_value=0, value=get_int(existing, "احصائيات الكادر البحثي والتخصصي - عدد الأساتذة بدون المتفرغين"), key=f"qp_{kp}")
            c1, c2 = st.columns(2)
            n_eng = c1.number_input("عدد المهندسين", min_value=0, value=get_int(existing, "احصائيات الكادر البحثي والتخصصي - عدد المهندسين"), key=f"qe_{kp}")
            n_staff = c2.number_input("إجمالي عدد العاملين", min_value=0, value=get_int(existing, "احصائيات الكادر البحثي والتخصصي - إجمالي عدد العاملين"), key=f"qs_{kp}")
            
            st.subheader("💰 الميزانية")
            n_budget = st.number_input("المبلغ المنصرف من الموازنة الاستثمارية (ألف ج)",
                                      min_value=0.0, value=get_float(existing, "المبلغ المنصرف من الموازنة الاستثمارية"),
                                      format="%.2f", key=f"qb_{kp}")
        else:
            n_researchers = get_int(existing, "احصائيات الكادر البحثي والتخصصي - عدد الباحثين")
            n_profs = get_int(existing, "احصائيات الكادر البحثي والتخصصي - عدد الأساتذة بدون المتفرغين")
            n_eng = get_int(existing, "احصائيات الكادر البحثي والتخصصي - عدد المهندسين")
            n_staff = get_int(existing, "احصائيات الكادر البحثي والتخصصي - إجمالي عدد العاملين")
            n_budget = get_float(existing, "المبلغ المنصرف من الموازنة الاستثمارية")
        
        # ============ المدخلات النصف سنوية (يناير، يوليو) ============
        if month in SEMI_MONTHS:
            st.divider()
            st.header("📊 المدخلات النصف سنوية")
            st.caption("تظهر في شهري: يناير، يوليو")
            
            n_studies_done = st.number_input("إجمالي عدد دراسات الخطة البحثية المنجزة",
                                            min_value=0, value=get_int(existing, "إجمالي عدد دراسات الخطة البحثية المنجزة"),
                                            key=f"hsd_{kp}")
            n_outputs = st.number_input("إجمالي عدد المخرجات التطبيقية",
                                       min_value=0, value=get_int(existing, "إجمالي عدد المخرجات التطبيقية"),
                                       key=f"ho_{kp}")
            n_revenues = st.number_input("إجمالي مبلغ الإيرادات الذاتية (ألف ج)",
                                        min_value=0.0, value=get_float(existing, "إجمالي مبلغ الإيرادات الذاتية"),
                                        format="%.2f", key=f"hr_{kp}")
        else:
            n_studies_done = get_int(existing, "إجمالي عدد دراسات الخطة البحثية المنجزة")
            n_outputs = get_int(existing, "إجمالي عدد المخرجات التطبيقية")
            n_revenues = get_float(existing, "إجمالي مبلغ الإيرادات الذاتية")
        
        # ============ المدخلات السنوية (يوليو فقط) ============
        if month in ANNUAL_MONTHS:
            st.divider()
            st.header("📊 المدخلات السنوية")
            st.caption("تظهر في شهر: يوليو فقط")
            n_patents = st.number_input("عدد براءات الاختراع",
                                       min_value=0, value=get_int(existing, "عدد براءات الاختراع"),
                                       key=f"pa_{kp}")
        else:
            n_patents = get_int(existing, "عدد براءات الاختراع")
        
        # ============ حفظ ============
        st.divider()
        if st.button("💾 حفظ البيانات الشهرية", type="primary", key="save_monthly"):
            try:
                data = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "الشهر": month, "السنة": int(year),
                    "عدد الدراسات الجارية - خطة بحثية": n_studies_plan,
                    "عدد الدراسات الجارية - دراسات استشارية": n_studies_consult,
                    "عدد الدراسات الجارية - مشروعات بحثية": n_studies_proj,
                    "إجمالي عدد الدراسات الجارية": total_studies,
                    "عدد التقارير الصادرة - تقرير مرحلي": n_rep_prog,
                    "عدد التقارير الصادرة - تقرير نهائي": n_rep_final,
                    "عدد المذكرات الصادرة": n_memos,
                    "عدد المقترحات الفنية والمالية - مقترحات دراسات استشارية": n_prop_consult,
                    "عدد المقترحات الفنية والمالية - مقترحات مشروعات بحثية": n_prop_research,
                    "المأموريات الحقلية - إجمالي عدد الأيام الفعلية": n_missions,
                    "عدد المشتركين في التدريب - كمتدربين": n_trainees,
                    "عدد المشاركين في التدريب - كمدربين": n_trainers,
                    "إجمالي عدد أيام التدريب للمتدربين - من داخل المعهد": n_train_days_in,
                    "إجمالي عدد أيام التدريب للمتدربين - من خارج المعهد": n_train_days_out,
                    "عدد المشتركين في حضور أنشطة علمية - مؤتمرات": n_conf,
                    "عدد المشتركين في حضور أنشطة علمية - ورش عمل": n_ws,
                    "إجمالي عدد المشاركين في أنشطة علمية": n_conf + n_ws,
                    "الاجتماعات - بالوزارة": n_meet_min,
                    "الاجتماعات - بالمركز": n_meet_cen,
                    "الاجتماعات - جهات خارجية": n_meet_ext,
                    "إجمالي الاجتماعات": n_meet_min + n_meet_cen + n_meet_ext,
                    "إجمالي عدد الأوراق البحثية - المنشورة": n_papers,
                    "عدد الأوراق البحثية دولياً - المنشورة": n_papers_intl,
                    "رسائل الماجستير والدكتوراة - المنتهية": n_theses,
                    "إجمالي عدد دراسات الخطة البحثية المنجزة": n_studies_done,
                    "إجمالي عدد المخرجات التطبيقية": n_outputs,
                    "إجمالي مبلغ الإيرادات الذاتية": n_revenues,
                    "احصائيات الكادر البحثي والتخصصي - عدد الباحثين": n_researchers,
                    "احصائيات الكادر البحثي والتخصصي - عدد الأساتذة بدون المتفرغين": n_profs,
                    "احصائيات الكادر البحثي والتخصصي - عدد المهندسين": n_eng,
                    "احصائيات الكادر البحثي والتخصصي - إجمالي عدد العاملين": n_staff,
                    "المبلغ المنصرف من الموازنة الاستثمارية": n_budget,
                    "عدد براءات الاختراع": n_patents,
                }
                
                result = update_or_append("KPI_Monthly", data,
                                         ["المعهد", "الشهر", "السنة"], MONTHLY_COLUMNS)
                
                if result == "updated":
                    st.success("✅ تم تحديث البيانات بنجاح")
                elif result == "added":
                    st.success("✅ تم حفظ البيانات بنجاح")
                
                invalidate_all()
                time.sleep(0.4)
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# ============================================================
# 📝 القوائم الشهرية - مربوطة بعدد المدخلات
# ============================================================
if tab_lists is not None:
    with tab_lists:
        st.header("📝 القوائم التفصيلية الشهرية")
        st.caption("يتم توليد عدد الصفوف تلقائياً بناءً على الأعداد المدخلة")
        
        c1, c2 = st.columns(2)
        with c1:
            ml_month = st.selectbox("الشهر", ALL_MONTHS, key="ml_m")
        with c2:
            ml_year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="ml_y")
        
        period_val = f"{ml_month} {ml_year}"
        
        # البحث عن بيانات الشهر
        month_data = get_existing(df_monthly, {
            "المعهد": st.session_state.institute,
            "الشهر": ml_month, "السنة": str(int(ml_year))
        })
        
        if month_data is None:
            st.warning("⚠️ لم يتم إدخال البيانات الرقمية لهذا الشهر بعد. يرجى إدخالها أولاً من تبويب الإدخال الشهري.")
            st.stop()
        
        st.success(f"📌 {st.session_state.institute} — {period_val}")
        st.divider()
        
        # قائمة التبويبات الفرعية
        list_tabs = st.tabs([v[0].replace("_", " ") for v in NUMERIC_TO_LIST.values()])
        
        for idx, (numeric_col, (sheet_name, cols)) in enumerate(NUMERIC_TO_LIST.items()):
            with list_tabs[idx]:
                # عدد الصفوف المطلوبة من المدخل الرقمي
                required_count = get_int(month_data, numeric_col)
                
                st.markdown(f"### 📝 {sheet_name.replace('_', ' ')}")
                
                if required_count == 0:
                    st.info(f"ℹ️ لم يتم إدخال أي عدد لـ **{numeric_col}** - لا توجد صفوف مطلوبة")
                    continue
                
                st.info(f"📊 **العدد المُدخل:** {required_count} - سيتم عرض {required_count} صف مع مسلسل تلقائي")
                st.divider()
                
                # تحميل البيانات المحفوظة
                full = cols + ["المعهد", "الفترة"]
                existing_data = load_data(sheet_name, full)
                
                if not existing_data.empty and "المعهد" in existing_data.columns and "الفترة" in existing_data.columns:
                    existing_data = existing_data[
                        (existing_data["المعهد"] == st.session_state.institute) &
                        (existing_data["الفترة"] == period_val)
                    ]
                    existing_data = existing_data[cols].fillna("").reset_index(drop=True)
                else:
                    existing_data = pd.DataFrame(columns=cols)
                
                # تجهيز الإطار بالعدد المطلوب
                required_df = pd.DataFrame(index=range(required_count), columns=cols).fillna("")
                # المسلسل تلقائي
                for i in range(required_count):
                    required_df.at[i, "م"] = str(i + 1)
                
                # دمج البيانات المحفوظة (استبدال حسب المسلسل)
                if not existing_data.empty:
                    for _, r in existing_data.iterrows():
                        try:
                            m_val = int(float(r["م"]))
                            if 1 <= m_val <= required_count:
                                for col in cols:
                                    if col in r.index and r[col] != "":
                                        required_df.at[m_val - 1, col] = r[col]
                        except (ValueError, TypeError):
                            continue
                
                editor_key = f"{sheet_name}_ed_{period_val}_{st.session_state.editor_counter}"
                
                input_df_rtl = st.data_editor(
                    rtl_display(required_df),
                    num_rows="fixed",
                    use_container_width=True,
                    key=editor_key,
                    hide_index=True,
                    disabled=["م"],
                )
                
                # إعادة ترتيب الأعمدة
                if not input_df_rtl.empty:
                    input_df = input_df_rtl[cols]
                else:
                    input_df = input_df_rtl
                
                if st.button(f"💾 حفظ {sheet_name.replace('_', ' ')}", key=f"{sheet_name}_sv_{period_val}"):
                    save_list(sheet_name, input_df, cols, st.session_state.institute, period_val)

# ============================================================
# 📊 التقارير الربع سنوية - تجميع تلقائي
# ============================================================
if tab_q_report is not None:
    with tab_q_report:
        st.title("📊 التقرير الربع سنوي المُجمَّع")
        
        if df_monthly.empty:
            st.info("📭 لا توجد بيانات شهرية")
            st.stop()
        
        # تحويل الأعمدة الرقمية
        df_q = df_monthly.copy()
        text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
        for c in df_q.columns:
            if c not in text_cols:
                df_q[c] = pd.to_numeric(df_q[c], errors="coerce").fillna(0)
        
        # تحديد الربع
        c1, c2, c3 = st.columns(3)
        with c1:
            year_filter = st.selectbox("السنة",
                sorted(df_q["السنة"].unique()), key="qrep_year")
        with c2:
            quarter_filter = st.selectbox("الربع",
                ["الربع الأول (يناير-مارس)", "الربع الثاني (أبريل-يونيو)",
                 "الربع الثالث (يوليو-سبتمبر)", "الربع الرابع (أكتوبر-ديسمبر)"],
                key="qrep_q")
        with c3:
            if st.session_state.role == "admin":
                institutes = ["الكل"] + sorted(df_q["المعهد"].unique())
                institute_filter = st.selectbox("المعهد", institutes, key="qrep_i")
            else:
                institute_filter = st.session_state.institute
        
        # الأشهر حسب الربع
        q_months_map = {
            "الربع الأول (يناير-مارس)": ["يناير", "فبراير", "مارس"],
            "الربع الثاني (أبريل-يونيو)": ["أبريل", "مايو", "يونيو"],
            "الربع الثالث (يوليو-سبتمبر)": ["يوليو", "أغسطس", "سبتمبر"],
            "الربع الرابع (أكتوبر-ديسمبر)": ["أكتوبر", "نوفمبر", "ديسمبر"],
        }
        target_months = q_months_map[quarter_filter]
        
        filtered = df_q[df_q["الشهر"].isin(target_months)]
        if institute_filter != "الكل":
            filtered = filtered[filtered["المعهد"] == institute_filter]
        
        st.divider()
        
        if filtered.empty:
            st.warning(f"لا توجد بيانات للربع المحدد ({', '.join(target_months)})")
            st.stop()
        
        # ====== البيانات الربع سنوية ======
        st.markdown("## 📊 البيانات الربع سنوية المُجمَّعة")
        
        # احصائيات الكادر
        q_stats_fields = [
            "احصائيات الكادر البحثي والتخصصي - عدد الباحثين",
            "احصائيات الكادر البحثي والتخصصي - عدد الأساتذة بدون المتفرغين",
            "احصائيات الكادر البحثي والتخصصي - عدد المهندسين",
            "احصائيات الكادر البحثي والتخصصي - إجمالي عدد العاملين",
            "المبلغ المنصرف من الموازنة الاستثمارية",
        ]
        
        # أحدث قيمة لكل شهر ربع سنوي
        q_data = filtered[filtered["الشهر"].isin(QUARTER_MONTHS)]
        
        if not q_data.empty:
            latest = q_data.sort_values(["السنة", "الشهر"]).iloc[-1]
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("👤 الباحثون", int(latest.get("احصائيات الكادر البحثي والتخصصي - عدد الباحثين", 0)))
            c2.metric("👨‍🏫 الأساتذة", int(latest.get("احصائيات الكادر البحثي والتخصصي - عدد الأساتذة بدون المتفرغين", 0)))
            c3.metric("👷 المهندسون", int(latest.get("احصائيات الكادر البحثي والتخصصي - عدد المهندسين", 0)))
            c4.metric("👥 العاملون", int(latest.get("احصائيات الكادر البحثي والتخصصي - إجمالي عدد العاملين", 0)))
            c5.metric("💰 الموازنة (ألف ج)", f"{latest.get('المبلغ المنصرف من الموازنة الاستثمارية', 0):.1f}")
        
        # ====== البيانات النصف سنوية ======
        st.markdown("## 📊 البيانات النصف سنوية المُجمَّعة")
        semi_data = filtered[filtered["الشهر"].isin(SEMI_MONTHS)]
        
        if not semi_data.empty:
            latest_h = semi_data.sort_values(["السنة", "الشهر"]).iloc[-1]
            c1, c2, c3 = st.columns(3)
            c1.metric("📚 دراسات منجزة", int(latest_h.get("إجمالي عدد دراسات الخطة البحثية المنجزة", 0)))
            c2.metric("🔬 المخرجات التطبيقية", int(latest_h.get("إجمالي عدد المخرجات التطبيقية", 0)))
            c3.metric("💵 الإيرادات الذاتية", f"{latest_h.get('إجمالي مبلغ الإيرادات الذاتية', 0):.1f}")
        else:
            st.info(f"ℹ️ لا توجد بيانات نصف سنوية في هذا الربع (تظهر في يناير ويوليو فقط)")
        
        # ====== البيانات السنوية ======
        st.markdown("## 📊 البيانات السنوية")
        annual_data = filtered[filtered["الشهر"].isin(ANNUAL_MONTHS)]
        
        if not annual_data.empty:
            latest_a = annual_data.iloc[-1]
            c1, = st.columns(1)
            c1.metric("🎯 براءات الاختراع", int(latest_a.get("عدد براءات الاختراع", 0)))
        else:
            st.info("ℹ️ لا توجد بيانات سنوية في هذا الربع (تظهر في يوليو فقط)")
        
        # ====== ملخص المدخلات الشهرية ======
        st.divider()
        st.markdown("## 📈 ملخص المدخلات الشهرية للربع")
        
        monthly_summary = filtered.groupby("الشهر").agg({
            "عدد الدراسات الجارية - خطة بحثية": "sum",
            "عدد الدراسات الجارية - دراسات استشارية": "sum",
            "عدد الدراسات الجارية - مشروعات بحثية": "sum",
            "عدد التقارير الصادرة - تقرير مرحلي": "sum",
            "عدد التقارير الصادرة - تقرير نهائي": "sum",
            "عدد المذكرات الصادرة": "sum",
            "إجمالي عدد المشاركين في أنشطة علمية": "sum",
            "إجمالي الاجتماعات": "sum",
        }).reset_index()
        
        st.dataframe(rtl_display(monthly_summary), use_container_width=True, hide_index=True)
        
        # ====== الرسوم البيانية ======
        if "المعهد" in filtered.columns:
            st.divider()
            st.markdown("## 📊 الرسوم البيانية")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 📚 الدراسات الجارية")
                fig = px.bar(filtered, x="الشهر",
                           y=["عدد الدراسات الجارية - خطة بحثية",
                              "عدد الدراسات الجارية - دراسات استشارية",
                              "عدد الدراسات الجارية - مشروعات بحثية"],
                           barmode="group")
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.markdown("#### 📄 التقارير")
                fig = px.bar(filtered, x="الشهر",
                           y=["عدد التقارير الصادرة - تقرير مرحلي",
                              "عدد التقارير الصادرة - تقرير نهائي"],
                           barmode="stack")
                st.plotly_chart(fig, use_container_width=True)
        
        # ====== الجدول الشامل ======
        st.divider()
        st.markdown("## 📄 الجدول الشامل")
        st.dataframe(rtl_display(filtered), use_container_width=True, hide_index=True)
        
        # تحميل
        def to_excel(d):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as w:
                d.to_excel(w, index=False, sheet_name="Quarterly")
            return out.getvalue()
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 تحميل Excel", data=to_excel(filtered),
                              file_name=f"quarterly_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            st.download_button("📥 تحميل CSV",
                              data=filtered.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'),
                              file_name=f"quarterly_{datetime.now().strftime('%Y%m%d')}.csv",
                              mime="text/csv")

# ============================================================
# 📈 لوحة المؤشرات
# ============================================================
if 'tab_dash' in dir() and tab_dash is not None:
    with tab_dash:
        st.title("📈 لوحة مؤشرات الأداء")
        
        if not df_monthly.empty:
            text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
            df_d = df_monthly.copy()
            for c in df_d.columns:
                if c not in text_cols:
                    df_d[c] = pd.to_numeric(df_d[c], errors="coerce").fillna(0)
            
            st.subheader("🎯 مؤشرات رئيسية")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("📚 الدراسات الجارية", safe_sum(df_d, "إجمالي عدد الدراسات الجارية"))
            c2.metric("📄 التقارير", safe_sum(df_d, "عدد التقارير الصادرة - تقرير مرحلي") +
                                       safe_sum(df_d, "عدد التقارير الصادرة - تقرير نهائي"))
            c3.metric("🤝 الاجتماعات", safe_sum(df_d, "إجمالي الاجتماعات"))
            c4.metric("👨‍🎓 المتدربين", safe_sum(df_d, "عدد المشتركين في التدريب - كمتدربين"))
            c5.metric("🔬 أنشطة علمية", safe_sum(df_d, "إجمالي عدد المشاركين في أنشطة علمية"))
            
            st.divider()
            
            if "المعهد" in df_d.columns:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 📚 الدراسات الجارية")
                    fig = px.bar(df_d, x="المعهد",
                               y=["عدد الدراسات الجارية - خطة بحثية",
                                  "عدد الدراسات الجارية - دراسات استشارية",
                                  "عدد الدراسات الجارية - مشروعات بحثية"],
                               barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 📄 التقارير والمذكرات")
                    fig = px.bar(df_d, x="المعهد",
                               y=["عدد التقارير الصادرة - تقرير مرحلي",
                                  "عدد التقارير الصادرة - تقرير نهائي",
                                  "عدد المذكرات الصادرة"],
                               barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 👥 التدريب")
                    fig = px.bar(df_d, x="المعهد",
                               y=["عدد المشتركين في التدريب - كمتدربين",
                                  "عدد المشاركين في التدريب - كمدربين"],
                               barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.markdown("#### 🤝 الاجتماعات")
                    fig = px.bar(df_d, x="المعهد",
                               y=["الاجتماعات - بالوزارة", "الاجتماعات - بالمركز",
                                  "الاجتماعات - جهات خارجية"],
                               barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📭 لا توجد بيانات")

# ============================================================
# 📉 التغير الشهري
# ============================================================
if tab_trend is not None:
    with tab_trend:
        st.title("📉 التغير الشهري")
        
        if not df_monthly.empty and "الشهر" in df_monthly.columns:
            df_t = df_monthly.copy()
            df_t["شهر-سنة"] = df_t["الشهر"].astype(str) + " - " + df_t["السنة"].astype(str)
            df_t["الشهر_مرتب"] = pd.Categorical(df_t["الشهر"], categories=ALL_MONTHS, ordered=True)
            df_t = df_t.sort_values(["السنة", "الشهر_مرتب"])
            
            avail = [m for m in [
                "إجمالي عدد الدراسات الجارية",
                "عدد التقارير الصادرة - تقرير مرحلي",
                "عدد التقارير الصادرة - تقرير نهائي",
                "عدد المذكرات الصادرة",
                "عدد المشتركين في التدريب - كمتدربين",
                "عدد المشاركين في التدريب - كمدربين",
                "إجمالي عدد المشاركين في أنشطة علمية",
                "إجمالي الاجتماعات",
                "إجمالي عدد الأوراق البحثية - المنشورة",
                "رسائل الماجستير والدكتوراة - المنتهية",
            ] if m in df_t.columns]
            
            if avail:
                metric = st.selectbox("اختر المؤشر", avail, key="trend_m")
                if st.session_state.role == "admin" and "المعهد" in df_t.columns:
                    fig = px.line(df_t, x="شهر-سنة", y=metric, color="المعهد", markers=True)
                else:
                    fig = px.line(df_t, x="شهر-سنة", y=metric, markers=True)
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📭 لا توجد بيانات")

# ============================================================
# 📄 البيانات
# ============================================================
if tab_data is not None:
    with tab_data:
        st.title("📄 البيانات الشهرية")
        
        if not df_monthly.empty:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.session_state.role == "admin" and "المعهد" in df_monthly.columns:
                    fi = st.multiselect("المعهد",
                        options=df_monthly["المعهد"].unique(),
                        default=df_monthly["المعهد"].unique())
                else:
                    fi = [st.session_state.institute]
            with c2:
                fy = st.multiselect("السنة",
                    options=sorted(df_monthly["السنة"].unique()),
                    default=sorted(df_monthly["السنة"].unique()))
            with c3:
                fm = st.multiselect("الشهر",
                    options=df_monthly["الشهر"].unique(),
                    default=df_monthly["الشهر"].unique())
            
            fd = df_monthly.copy()
            if "المعهد" in fd.columns and fi: fd = fd[fd["المعهد"].isin(fi)]
            if "السنة" in fd.columns and fy: fd = fd[fd["السنة"].isin(fy)]
            if "الشهر" in fd.columns and fm: fd = fd[fd["الشهر"].isin(fm)]
            
            st.markdown("### 📊 جدول البيانات")
            st.caption(f"عدد السجلات: {len(fd)}")
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
