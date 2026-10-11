import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import streamlit as st
from datetime import datetime

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
</style>
""", unsafe_allow_html=True)

# ============================================================
# الاتصال بـ Google Sheets
# ============================================================
SPREADSHEET_KEY = "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"

@st.cache_resource
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

def get_spreadsheet():
    return get_client().open_by_key(SPREADSHEET_KEY)

def get_or_create_sheet(sheet_name, headers=None):
    try:
        ss = get_spreadsheet()
        try:
            ws = ss.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=sheet_name, rows=1000, cols=30)
            if headers:
                ws.append_row(headers)
        return ws
    except Exception as e:
        st.error(f"خطأ في الاتصال: {e}")
        return None

def fix_encoding(text):
    if isinstance(text, str):
        try:
            return text.encode('latin1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return text
    return text

# ============================================================
# الأعمدة - البيانات الشهرية
# ============================================================
MONTHLY_COLUMNS = [
    "المعهد", "المستخدم", "الشهر", "السنة",
    "دراسات خطة بحثية جارية", "دراسات استشارية جارية", "دراسات بتمويل ذاتي جارية",
    "إجمالي الدراسات الجارية",
    "تقرير مرحلي", "تقرير نهائي", "تقرير معاينة", "تقرير معايرة", "تقرير أخرى",
    "إجمالي التقارير",
    "عدد المذكرات",
    "مقترحات استشارات", "مقترحات تمويل أبحاث", "إجمالي المقترحات",
    "إجمالي عدد المأموريات", "إجمالي عدد أيام المأموريات",
    "إجمالي عدد المعاينات",
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

# ============================================================
# الأعمدة - البيانات الربع سنوية (كاملة)
# ============================================================
QUARTERLY_COLUMNS = [
    "المعهد", "المستخدم", "الربع", "السنة المالية",
    # 1. الأداء التنفيذي
    "فردي - عدد المشاريع", "فردي - نسبة المنفذ %", "فردي - عدد التقارير",
    "مشترك - عدد المشاريع", "مشترك - نسبة المنفذ %",
    "مشترك - نسبة المشاركة %", "مشترك - عدد التقارير",
    # 2. الاستشارات
    "مشاريع ممولة محلياً", "مشاريع ممولة دولياً", "تكليفات من الوزارة",
    "استشارات من الوزارة", "استشارات من جهات حكومية/خاصة",
    "إجمالي المشاريع خارج الخطة",
    "مقترحات محلية", "مقترحات دولية", "مقترحات للوزارة", "مقترحات خارج الوزارة",
    "إجمالي المقترحات",
    # 3. التعاون
    "تعاون داخلي مع المعاهد", "تعاون داخلي مع جهات خارج المعاهد",
    "تعاون خارجي مع جهات أجنبية",
    # 4. الإنتاج العلمي
    "أبحاث منشورة", "أبحاث في مجلات متميزة Q1/Q2",
    "أبحاث حصلت على موافقة النشر", "أبحاث حصلت على مكافأة نشر",
    "باحثون حصلوا على مكافأة نشر",
    "رسائل ماجستير", "رسائل دكتوراه",
    "مراجعة وتحكيم أبحاث بمجلات",
    "إشراف/تحكيم رسائل لباحثي المعهد",
    "إشراف/تحكيم رسائل لباحثين خارج المعهد",
    "عضوية في منظمات دولية", "عضوية في منظمات محلية",
    # 5. التدريب
    "دورات بالداخل - عدد", "دورات بالداخل - متدربين",
    "دورات بالخارج - عدد", "دورات بالخارج - متدربين",
    "دورات online - عدد", "دورات online - متدربين",
    "ورش عمل بالداخل - عدد", "ورش عمل بالداخل - متدربين",
    "ورش عمل بالخارج - عدد", "ورش عمل بالخارج - متدربين",
    "مؤتمرات بالداخل - عدد", "مؤتمرات بالداخل - متدربين",
    "مؤتمرات بالخارج - عدد", "مؤتمرات بالخارج - متدربين",
    "دورات نظمها المعهد - عدد", "دورات نظمها المعهد - متدربين",
    "إجمالي التدريب - عدد", "إجمالي التدريب - متدربين",
    # 6. التمويل
    "تمويل الخطة البحثية - مبلغ", "تمويل الخطة البحثية - نسبة %",
    "تمويل خارجي - مبلغ", "تمويل خارجي - نسبة %",
    "المنصرف الفعلي - مبلغ", "المنصرف الفعلي - نسبة %",
    "تمويل نشر علمي - دراسات", "تمويل نشر علمي - أبحاث",
    "تمويل نشر علمي - مكافآت", "إجمالي تمويل النشر العلمي",
    # 7. الموارد البشرية
    "اجتماعات دورية مع الهيئة البحثية والعاملين",
    "اجتماعات مجلس إدارة المعهد", "اجتماعات وحدة الفكر",
    "آليات تسويق إمكانات المعهد", "آليات الثواب والعقاب",
    # 8. الاجتماعات الوزارية
    "عدد الاجتماعات الوزارية", "ملاحظات عامة"
]

# ============================================================
# أعمدة القوائم النصية الشهرية
# ============================================================
STUDIES_COLUMNS = ["م", "عنوان الدراسة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
PROJECTS_COLUMNS = ["م", "عنوان المشروع", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
CONSULT_COLUMNS = ["م", "عنوان الاستشارة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
REPORTS_COLUMNS = ["م", "عنوان التقرير", "تاريخ الإصدار", "الجهة المستفيدة",
                   "الدائرة طبقاً للخطة البحثية", "ملخص التقرير"]
MEETINGS_COLUMNS = ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد",
                    "الغرض من الاجتماع", "النوع"]
TRAINING_COLUMNS = ["م", "عنوان البرنامج", "النوع", "عدد المشاركين",
                    "مكان الانعقاد", "مدة البرنامج"]
PERF_MEETINGS_COLUMNS = ["م", "التاريخ", "عنوان الاجتماع",
                         "الغرض من الاجتماع", "السادة الحضور"]

# أعمدة القوائم الربع سنوية
Q_STUDIES_INDIV = ["م", "عنوان المشروع البحثي", "نسبة المنفذ %",
                   "عدد التقارير", "هدف الدراسة", "النتائج"]
Q_STUDIES_JOINT = ["م", "عنوان المشروع البحثي", "نسبة المنفذ %",
                   "عدد التقارير", "الهدف", "النتائج"]
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
Q_PUBLICATIONS = ["م", "عنوان البحث", "المجلة", "التصنيف",
                  "تاريخ النشر", "الباحث الرئيسي"]
Q_ORGS_INTL = ["م", "المنظمة الدولية", "نوع العضوية", "تاريخ العضوية"]
Q_ORGS_LOCAL = ["م", "المنظمة المحلية", "نوع العضوية", "تاريخ العضوية"]
Q_MINISTRY_MEETINGS = ["م", "التاريخ", "الاسم", "الوظيفة",
                       "مكان الانعقاد", "الغرض من الاجتماع"]

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
# الدوال المساعدة
# ============================================================
def load_sheet_data(sheet_name, columns):
    try:
        ws = get_or_create_sheet(sheet_name, columns)
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            return pd.DataFrame(columns=all_values[0] if all_values else columns)
        return pd.DataFrame(all_values[1:], columns=all_values[0])
    except Exception:
        return pd.DataFrame(columns=columns)

def safe_sum(df, column):
    if df.empty or column not in df.columns:
        return 0
    return int(pd.to_numeric(df[column], errors='coerce').fillna(0).sum())

def save_list_data(sheet_name, input_df, base_columns, institute, period_key, period_val):
    """حفظ قائمة نصية مع مراعاة المعهد والفترة"""
    try:
        full_cols = base_columns + ["المعهد", period_key]
        ws = get_or_create_sheet(sheet_name, full_cols)
        all_values = ws.get_all_values()
        
        # حذف الصفوف القديمة لنفس المعهد/الفترة
        kept_rows = []
        if len(all_values) > 1:
            existing = pd.DataFrame(all_values[1:], columns=all_values[0])
            if "المعهد" in existing.columns and period_key in existing.columns:
                mask = ~(
                    (existing["المعهد"] == institute) &
                    (existing[period_key] == period_val)
                )
                kept_rows = existing[mask].values.tolist()
        
        # إعادة الكتابة
        ws.clear()
        ws.append_row(full_cols)
        for row in kept_rows:
            ws.append_row([str(v) for v in row])
        
        # إضافة الجديدة
        for _, row in input_df.iterrows():
            vals = [str(v) if pd.notna(v) else "" for v in row.tolist()]
            if all(v.strip() in ["", "nan", "None"] for v in vals):
                continue
            ws.append_row(vals + [institute, period_val])
        
        st.success(f"✅ تم حفظ البيانات في {sheet_name}")
        st.balloons()
        st.rerun()
    except Exception as e:
        st.error(f"❌ خطأ في الحفظ: {e}")

# ============================================================
# Session State
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

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
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# ============================================================
# بعد تسجيل الدخول
# ============================================================
st.success(f"👤 مرحباً **{st.session_state.username}** — 🏢 {st.session_state.institute}")

c_logout = st.columns([6, 1])
with c_logout[1]:
    if st.button("🚪 تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

# تحميل البيانات الشهرية
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
        
        st.divider()
        
        # الدراسات
        st.subheader("📚 الدراسات الجارية")
        c1, c2, c3 = st.columns(3)
        rs = c1.number_input("خطة بحثية", min_value=0, key="rs")
        cs = c2.number_input("استشارية", min_value=0, key="cs")
        sf = c3.number_input("دراسات بتمويل ذاتي", min_value=0, key="sf")
        total_studies = rs + cs + sf
        st.info(f"إجمالي الدراسات الجارية: **{total_studies}**")
        
        st.divider()
        
        # التقارير
        st.subheader("📄 التقارير الصادرة")
        c1, c2, c3, c4, c5 = st.columns(5)
        r1 = c1.number_input("مرحلي", min_value=0, key="r1")
        r2 = c2.number_input("نهائي", min_value=0, key="r2")
        r3 = c3.number_input("معاينة", min_value=0, key="r3")
        r4 = c4.number_input("معايرة", min_value=0, key="r4")
        r5 = c5.number_input("أخرى", min_value=0, key="r5")
        total_reports = r1 + r2 + r3 + r4 + r5
        st.info(f"إجمالي التقارير: **{total_reports}**")
        
        st.divider()
        
        # المذكرات والمقترحات
        st.subheader("📋 المذكرات والمقترحات")
        c1, c2, c3 = st.columns(3)
        memos = c1.number_input("عدد المذكرات", min_value=0, key="memos")
        pc = c2.number_input("مقترحات استشارات", min_value=0, key="pc")
        pf = c3.number_input("مقترحات تمويل أبحاث", min_value=0, key="pf")
        total_props = pc + pf
        st.info(f"إجمالي المقترحات: **{total_props}**")
        
        st.divider()
        
        # المأموريات والمعاينات
        st.subheader("🏃 المأموريات والمعاينات")
        c1, c2, c3 = st.columns(3)
        missions = c1.number_input("إجمالي عدد المأموريات", min_value=0, key="miss")
        m_days = c2.number_input("إجمالي أيام المأموريات", min_value=0, key="m_days")
        surveys = c3.number_input("إجمالي عدد المعاينات", min_value=0, key="surv")
        
        st.divider()
        
        # التدريب
        st.subheader("👥 التدريب")
        c1, c2, c3, c4 = st.columns(4)
        trainees = c1.number_input("متدربين", min_value=0, key="tr")
        trainers = c2.number_input("مدربين", min_value=0, key="trn")
        td_in = c3.number_input("أيام تدريب (داخلي)", min_value=0, key="tdi")
        td_out = c4.number_input("أيام تدريب (خارجي)", min_value=0, key="tdo")
        
        st.divider()
        
        # الأنشطة العلمية
        st.subheader("🔬 الأنشطة العلمية")
        c1, c2 = st.columns(2)
        conf = c1.number_input("مشتركين مؤتمرات", min_value=0, key="conf")
        ws_a = c2.number_input("مشتركين ورش عمل", min_value=0, key="wsa")
        total_act = conf + ws_a
        
        st.divider()
        
        # الاجتماعات
        st.subheader("🤝 الاجتماعات")
        c1, c2, c3, c4, c5 = st.columns(5)
        mt1 = c1.number_input("بالوزارة", min_value=0, key="mt1")
        mt2 = c2.number_input("بالمركز", min_value=0, key="mt2")
        mt3 = c3.number_input("جهات خارجية", min_value=0, key="mt3")
        mt4 = c4.number_input("مع العاملين", min_value=0, key="mt4")
        mt5 = c5.number_input("جهات أخرى", min_value=0, key="mt5")
        total_meet = mt1 + mt2 + mt3 + mt4 + mt5
        
        st.divider()
        
        # الأوراق البحثية
        st.subheader("📝 الأوراق البحثية والرسائل")
        c1, c2, c3, c4 = st.columns(4)
        pp = c1.number_input("أوراق منشورة", min_value=0, key="pp")
        po = c2.number_input("أوراق جاري العمل عليها", min_value=0, key="po")
        th_done = c3.number_input("رسائل منتهية", min_value=0, key="thd")
        th_ongo = c4.number_input("رسائل جاري العمل عليها", min_value=0, key="tho")
        
        st.divider()
        
        # العاملون
        st.subheader("👤 عدد العاملين بالمعهد")
        c1, c2, c3 = st.columns(3)
        tot_staff = c1.number_input("إجمالي العاملين الفعلي", min_value=0, key="ts")
        prof_em = c2.number_input("الأساتذة المتفرغين", min_value=0, key="pem")
        profs = c3.number_input("الأساتذة", min_value=0, key="prf")
        
        c1, c2, c3 = st.columns(3)
        asst_pr = c1.number_input("الأساتذة المساعدون", min_value=0, key="asp")
        resrch = c2.number_input("الباحثون", min_value=0, key="rsc")
        asst_res = c3.number_input("الباحث المساعد", min_value=0, key="asr")
        
        c1, c2, c3 = st.columns(3)
        res_ast = c1.number_input("مساعد باحث", min_value=0, key="rsa")
        tech = c2.number_input("الفنيون", min_value=0, key="tch")
        admins = c3.number_input("الإداريون", min_value=0, key="adm")
        
        drivers = st.number_input("السائقون", min_value=0, key="drv")
        
        st.divider()
        
        # بيانات إضافية
        st.subheader("💰 بيانات إضافية")
        c1, c2, c3 = st.columns(3)
        revenues = c1.number_input("إجمالي الإيرادات الذاتية", min_value=0.0, format="%.2f", key="rev")
        patents = c2.number_input("عدد براءات الاختراع", min_value=0, key="pat")
        budget = c3.number_input("المنصرف من الموازنة الاستثمارية", min_value=0.0, format="%.2f", key="bud")
        
        st.divider()
        
        if st.button("💾 حفظ البيانات الشهرية", type="primary", key="save_monthly"):
            try:
                ws = get_or_create_sheet("KPI_Data", MONTHLY_COLUMNS)
                all_values = ws.get_all_values()
                if len(all_values) > 1:
                    existing = pd.DataFrame(all_values[1:], columns=all_values[0])
                    dup = (
                        (existing["المعهد"] == st.session_state.institute) &
                        (existing["الشهر"] == month) &
                        (existing["السنة"] == str(int(year)))
                    )
                    if dup.any():
                        st.error("❌ تم إدخال بيانات هذا الشهر مسبقاً")
                        st.stop()
                
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
                
                row = [str(data.get(c, "0")) for c in MONTHLY_COLUMNS]
                ws.append_row(row)
                st.success("✅ تم حفظ البيانات الشهرية بنجاح")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# ============================================================
# 📊 إدخال البيانات الربع سنوية
# ============================================================
if tab_q_input is not None:
    with tab_q_input:
        st.header("📊 إدخال البيانات الربع سنوية")
        
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
        
        st.divider()
        
        # 1. الأداء التنفيذي
        st.subheader("1️⃣ الأداء التنفيذي للخطة البحثية")
        with st.expander("1-1-1 مشروع فردي خاص بالمعهد", expanded=True):
            c1, c2, c3 = st.columns(3)
            ind_cnt = c1.number_input("عدد المشاريع", min_value=0, key="q_ind_cnt")
            ind_pct = c2.number_input("نسبة المنفذ %", min_value=0.0, max_value=100.0,
                                      value=0.0, format="%.1f", key="q_ind_pct")
            ind_rep = c3.number_input("عدد التقارير", min_value=0, key="q_ind_rep")
        
        with st.expander("1-1-2 مشروع مشترك مع معاهد أخرى"):
            c1, c2, c3, c4 = st.columns(4)
            jnt_cnt = c1.number_input("عدد المشاريع", min_value=0, key="q_jnt_cnt")
            jnt_pct = c2.number_input("نسبة المنفذ %", min_value=0.0, max_value=100.0,
                                      value=0.0, format="%.1f", key="q_jnt_pct")
            jnt_share = c3.number_input("نسبة المشاركة %", min_value=0.0, max_value=100.0,
                                        value=0.0, format="%.1f", key="q_jnt_shr")
            jnt_rep = c4.number_input("عدد التقارير", min_value=0, key="q_jnt_rep")
        
        st.divider()
        
        # 2. الاستشارات
        st.subheader("2️⃣ الاستشارات والدراسات خارج الخطة")
        c1, c2, c3 = st.columns(3)
        q_local = c1.number_input("مشاريع ممولة محلياً (STDF)", min_value=0, key="q_loc")
        q_intl = c2.number_input("مشاريع ممولة دولياً (PRIMA)", min_value=0, key="q_intl")
        q_min_a = c3.number_input("تكليفات من الوزارة (بدون مقابل)", min_value=0, key="q_mina")
        
        c1, c2, c3 = st.columns(3)
        q_min_c = c1.number_input("استشارات من الوزارة (بمقابل)", min_value=0, key="q_minc")
        q_gov = c2.number_input("استشارات من جهات حكومية/خاصة", min_value=0, key="q_gov")
        q_total_out = q_local + q_intl + q_min_a + q_min_c + q_gov
        c3.metric("إجمالي المشاريع خارج الخطة", q_total_out)
        
        st.markdown("**المقترحات البحثية:**")
        c1, c2, c3, c4 = st.columns(4)
        q_p_loc = c1.number_input("مقترحات محلية", min_value=0, key="q_ploc")
        q_p_int = c2.number_input("مقترحات دولية", min_value=0, key="q_pint")
        q_p_min = c3.number_input("مقترحات للوزارة", min_value=0, key="q_pmin")
        q_p_out = c4.number_input("مقترحات خارج الوزارة", min_value=0, key="q_pout")
        q_total_p = q_p_loc + q_p_int + q_p_min + q_p_out
        st.info(f"**إجمالي المقترحات:** {q_total_p}")
        
        st.divider()
        
        # 3. التعاون
        st.subheader("3️⃣ التعاون الداخلي والخارجي")
        c1, c2, c3 = st.columns(3)
        q_col_in = c1.number_input("تعاون داخلي مع المعاهد", min_value=0, key="q_cin")
        q_col_out = c2.number_input("تعاون داخلي مع جهات خارج المعاهد", min_value=0, key="q_cout")
        q_col_frgn = c3.number_input("تعاون خارجي (خارج مصر)", min_value=0, key="q_cfr")
        
        st.divider()
        
        # 4. الإنتاج العلمي
        st.subheader("4️⃣ الإنتاج العلمي والنشر والابتكار")
        c1, c2, c3, c4 = st.columns(4)
        q_pub = c1.number_input("أبحاث منشورة", min_value=0, key="q_pub")
        q_q1 = c2.number_input("أبحاث Q1/Q2", min_value=0, key="q_q1")
        q_appr = c3.number_input("أبحاث موافقة نشر", min_value=0, key="q_appr")
        q_rew = c4.number_input("أبحاث مكافأة نشر", min_value=0, key="q_rew")
        
        c1, c2, c3 = st.columns(3)
        q_res_rew = c1.number_input("باحثون بمكافأة", min_value=0, key="q_rrw")
        q_mas = c2.number_input("رسائل ماجستير", min_value=0, key="q_mas")
        q_phd = c3.number_input("رسائل دكتوراه", min_value=0, key="q_phd")
        
        c1, c2, c3 = st.columns(3)
        q_rev = c1.number_input("مراجعة/تحكيم بمجلات", min_value=0, key="q_rev")
        q_sup_in = c2.number_input("إشراف/تحكيم لباحثي المعهد", min_value=0, key="q_supin")
        q_sup_out = c3.number_input("إشراف/تحكيم لباحثين خارجيين", min_value=0, key="q_supout")
        
        c1, c2 = st.columns(2)
        q_mem_int = c1.number_input("عضوية منظمات دولية", min_value=0, key="q_memint")
        q_mem_loc = c2.number_input("عضوية منظمات محلية", min_value=0, key="q_memloc")
        
        st.divider()
        
        # 5. التدريب
        st.subheader("5️⃣ التدريب / التعليم")
        training_types = [
            ("دورات بالداخل", "tr_in"),
            ("دورات بالخارج", "tr_out"),
            ("دورات online", "tr_onl"),
            ("ورش عمل/ندوات بالداخل", "tr_ws_in"),
            ("ورش عمل/ندوات بالخارج", "tr_ws_out"),
            ("مؤتمرات بالداخل", "tr_cf_in"),
            ("مؤتمرات بالخارج", "tr_cf_out"),
            ("دورات نظمها المعهد", "tr_org"),
        ]
        
        q_training_data = {}
        q_tot_train_cnt = 0
        q_tot_train_trn = 0
        for label, key in training_types:
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"**{label}**")
            cnt = c2.number_input("عدد", min_value=0, key=f"q_{key}_c")
            trn = c3.number_input("متدربين", min_value=0, key=f"q_{key}_t")
            q_training_data[f"{key}_count"] = cnt
            q_training_data[f"{key}_trainees"] = trn
            q_tot_train_cnt += cnt
            q_tot_train_trn += trn
        
        st.info(f"**إجمالي التدريب:** {q_tot_train_cnt} فعالية — {q_tot_train_trn} متدرب")
        
        st.divider()
        
        # 6. التمويل
        st.subheader("6️⃣ التمويل والأداء المالي")
        c1, c2 = st.columns(2)
        q_rf_amt = c1.number_input("تمويل الخطة البحثية (ألف ج)", min_value=0.0, format="%.2f", key="q_rfa")
        q_rf_pct = c2.number_input("نسبة من إجمالي التمويل %", min_value=0.0, max_value=100.0,
                                   value=0.0, format="%.1f", key="q_rfp")
        
        c1, c2 = st.columns(2)
        q_ef_amt = c1.number_input("التمويل الخارجي (ألف ج)", min_value=0.0, format="%.2f", key="q_efa")
        q_ef_pct = c2.number_input("نسبة التمويل الخارجي %", min_value=0.0, max_value=100.0,
                                   value=0.0, format="%.1f", key="q_efp")
        
        c1, c2 = st.columns(2)
        q_sp_amt = c1.number_input("المنصرف الفعلي (ألف ج)", min_value=0.0, format="%.2f", key="q_spa")
        q_sp_pct = c2.number_input("نسبة المنصرف %", min_value=0.0, max_value=200.0,
                                   value=0.0, format="%.1f", key="q_spp")
        
        st.markdown("**تمويل النشر العلمي والدراسات العليا:**")
        c1, c2, c3 = st.columns(3)
        q_pf_th = c1.number_input("دراسات (ماجستير/دكتوراه)", min_value=0.0, format="%.2f", key="q_pfth")
        q_pf_rs = c2.number_input("أبحاث", min_value=0.0, format="%.2f", key="q_pfrs")
        q_pf_rw = c3.number_input("مكافآت", min_value=0.0, format="%.2f", key="q_pfrw")
        q_tot_pf = q_pf_th + q_pf_rs + q_pf_rw
        
        st.divider()
        
        # 7. الموارد البشرية
        st.subheader("7️⃣ مؤشرات الأداء للموارد البشرية")
        c1, c2, c3 = st.columns(3)
        q_per_meet = c1.number_input("اجتماعات دورية مع الهيئة والعاملين", min_value=0, key="q_pm")
        q_brd_meet = c2.number_input("اجتماعات مجلس الإدارة", min_value=0, key="q_bm")
        q_think = c3.number_input("اجتماعات وحدة الفكر", min_value=0, key="q_tk")
        
        q_marketing = st.text_area("آليات تسويق إمكانات المعهد", height=80, key="q_mkt")
        q_rewards = st.text_area("آليات الثواب والعقاب", height=80, key="q_rwd")
        
        st.divider()
        
        # 8. الاجتماعات الوزارية
        st.subheader("8️⃣ الاجتماعات الوزارية")
        q_min_meet = st.number_input("عدد الاجتماعات الوزارية", min_value=0, key="q_mm")
        q_notes = st.text_area("ملاحظات عامة", height=80, key="q_nt")
        
        st.divider()
        
        if st.button("💾 حفظ البيانات الربع سنوية", type="primary", key="save_q"):
            try:
                ws = get_or_create_sheet("Quarterly_KPI", QUARTERLY_COLUMNS)
                all_values = ws.get_all_values()
                if len(all_values) > 1:
                    existing = pd.DataFrame(all_values[1:], columns=all_values[0])
                    dup = (
                        (existing["المعهد"] == st.session_state.institute) &
                        (existing["الربع"] == quarter) &
                        (existing["السنة المالية"] == fiscal_year)
                    )
                    if dup.any():
                        st.error("❌ تم إدخال بيانات هذا الربع مسبقاً")
                        st.stop()
                
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
                
                row = [str(data.get(c, "")) for c in QUARTERLY_COLUMNS]
                ws.append_row(row)
                st.success("✅ تم حفظ البيانات الربع سنوية بنجاح")
                st.balloons()
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
            ml_year = st.number_input("السنة", min_value=2020, max_value=2035,
                                      value=2026, key="ml_y")
        
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
                st.subheader(title)
                full_cols = base_cols + ["المعهد", "الفترة"]
                data = load_sheet_data(sheet_name, full_cols)
                if not data.empty and "المعهد" in data.columns and "الفترة" in data.columns:
                    data = data[
                        (data["المعهد"] == st.session_state.institute) &
                        (data["الفترة"] == period_val)
                    ]
                else:
                    data = pd.DataFrame(columns=base_cols)
                
                input_df = st.data_editor(
                    data[base_cols] if not data.empty else pd.DataFrame(columns=base_cols),
                    num_rows="dynamic", use_container_width=True, key=f"{key_prefix}_ed"
                )
                
                if st.button(f"💾 حفظ {title}", key=f"{key_prefix}_sv"):
                    save_list_data(sheet_name, input_df, base_cols,
                                   st.session_state.institute, "الفترة", period_val)
        
        render_list_editor(list_tabs[0], "الدراسات_البحثية", STUDIES_COLUMNS,
                          "الدراسات البحثية", "st")
        render_list_editor(list_tabs[1], "مشروعات_ممولة", PROJECTS_COLUMNS,
                          "المشروعات الممولة", "pr")
        render_list_editor(list_tabs[2], "استشارات_ممولة", CONSULT_COLUMNS,
                          "الاستشارات الممولة", "cn")
        render_list_editor(list_tabs[3], "التقارير_الفنية", REPORTS_COLUMNS,
                          "التقارير الفنية", "rp")
        render_list_editor(list_tabs[4], "الاجتماعات", MEETINGS_COLUMNS,
                          "الاجتماعات", "mt")
        render_list_editor(list_tabs[5], "التدريب", TRAINING_COLUMNS,
                          "التدريب والندوات", "tr")
        render_list_editor(list_tabs[6], "اجتماعات_تحسين_الأداء", PERF_MEETINGS_COLUMNS,
                          "اجتماعات تحسين الأداء", "pf")

# ============================================================
# 📋 إدخال القوائم الربع سنوية
# ============================================================
if tab_q_input is not None:
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
            "1-1 مشاريع فردية", "1-2 مشاريع مشتركة",
            "2-1-1 ممولة محلياً", "2-1-2 ممولة دولياً",
            "2-1-3 تكليفات وزارة", "2-1-4 استشارات وزارة",
            "2-2-1 مقترحات محلية", "2-2-2 مقترحات دولية",
            "2-2-3 مقترحات للوزارة", "2-2-4 مقترحات خارج الوزارة",
            "3-1 تعاون داخلي", "3-2 تعاون خارجي",
            "4-1 الأبحاث المنشورة", "4-2 عضويات دولية", "4-3 عضويات محلية",
            "8 الاجتماعات الوزارية"
        ])
        
        def render_q_list(tab_obj, sheet_name, cols, title, key):
            with tab_obj:
                st.subheader(title)
                full_cols = cols + ["المعهد", "الفترة"]
                data = load_sheet_data(sheet_name, full_cols)
                if not data.empty and "المعهد" in data.columns and "الفترة" in data.columns:
                    data = data[
                        (data["المعهد"] == st.session_state.institute) &
                        (data["الفترة"] == ql_period)
                    ]
                else:
                    data = pd.DataFrame(columns=cols)
                
                inp = st.data_editor(
                    data[cols] if not data.empty else pd.DataFrame(columns=cols),
                    num_rows="dynamic", use_container_width=True, key=f"{key}_ed"
                )
                if st.button(f"💾 حفظ", key=f"{key}_sv"):
                    save_list_data(sheet_name, inp, cols,
                                   st.session_state.institute, "الفترة", ql_period)
        
        render_q_list(q_tabs[0], "Q_مشاريع_فردية", Q_STUDIES_INDIV,
                     "مشاريع الخطة البحثية - فردية", "q1")
        render_q_list(q_tabs[1], "Q_مشاريع_مشتركة", Q_STUDIES_JOINT,
                     "مشاريع مشتركة مع معاهد", "q2")
        render_q_list(q_tabs[2], "Q_ممولة_محلياً", Q_FUNDED_LOCAL,
                     "مشاريع ممولة محلياً", "q3")
        render_q_list(q_tabs[3], "Q_ممولة_دولياً", Q_FUNDED_INTL,
                     "مشاريع ممولة دولياً", "q4")
        render_q_list(q_tabs[4], "Q_تكليفات_وزارة", Q_MINISTRY_ASSIGN,
                     "تكليفات من الوزارة", "q5")
        render_q_list(q_tabs[5], "Q_استشارات_وزارة", Q_MINISTRY_CONSULT,
                     "استشارات من الوزارة", "q6")
        render_q_list(q_tabs[6], "Q_مقترحات_محلية", Q_PROPOSALS_LOCAL,
                     "مقترحات محلية", "q7")
        render_q_list(q_tabs[7], "Q_مقترحات_دولية", Q_PROPOSALS_INTL,
                     "مقترحات دولية", "q8")
        render_q_list(q_tabs[8], "Q_مقترحات_وزارة", Q_PROPOSALS_MINISTRY,
                     "مقترحات للوزارة", "q9")
        render_q_list(q_tabs[9], "Q_مقترحات_خارج_الوزارة", Q_PROPOSALS_OUTSIDE,
                     "مقترحات خارج الوزارة", "q10")
        render_q_list(q_tabs[10], "Q_تعاون_داخلي", Q_COLLAB_INTERNAL,
                     "التعاون الداخلي", "q11")
        render_q_list(q_tabs[11], "Q_تعاون_خارجي", Q_COLLAB_EXTERNAL,
                     "التعاون الخارجي", "q12")
        render_q_list(q_tabs[12], "Q_أبحاث_منشورة", Q_PUBLICATIONS,
                     "الأبحاث المنشورة", "q13")
        render_q_list(q_tabs[13], "Q_عضويات_دولية", Q_ORGS_INTL,
                     "العضويات الدولية", "q14")
        render_q_list(q_tabs[14], "Q_عضويات_محلية", Q_ORGS_LOCAL,
                     "العضويات المحلية", "q15")
        render_q_list(q_tabs[15], "Q_اجتماعات_وزارية", Q_MINISTRY_MEETINGS,
                     "الاجتماعات الوزارية", "q16")

# ============================================================
# 📈 Dashboard الشهري
# ============================================================
if 'tab_m_dashboard' in dir() and tab_m_dashboard is not None:
    with tab_m_dashboard:
        st.title("📈 لوحة مؤشرات الأداء الشهرية")
        
        if not df_monthly.empty:
            # تحويل الأعمدة
            text_cols = ["المعهد", "المستخدم", "الشهر", "السنة"]
            for col in df_monthly.columns:
                if col not in text_cols:
                    df_monthly[col] = pd.to_numeric(df_monthly[col], errors="coerce").fillna(0)
            
            st.subheader("🎯 مؤشرات رئيسية")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("📚 الدراسات الجارية", safe_sum(df_monthly, "إجمالي الدراسات الجارية"))
            c2.metric("📄 التقارير", safe_sum(df_monthly, "إجمالي التقارير"))
            c3.metric("📋 المقترحات", safe_sum(df_monthly, "إجمالي المقترحات"))
            c4.metric("🤝 الاجتماعات", safe_sum(df_monthly, "إجمالي الاجتماعات"))
            c5.metric("👨‍🎓 المتدربين", safe_sum(df_monthly, "متدربين"))
            
            st.divider()
            
            st.subheader("📊 مؤشرات تفصيلية")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("🏃 المأموريات", safe_sum(df_monthly, "إجمالي عدد المأموريات"))
            c2.metric("🔍 المعاينات", safe_sum(df_monthly, "إجمالي عدد المعاينات"))
            c3.metric("📝 الأوراق البحثية", safe_sum(df_monthly, "إجمالي الأوراق البحثية"))
            c4.metric("🎓 الرسائل العلمية", safe_sum(df_monthly, "إجمالي الرسائل"))
            c5.metric("👥 العاملون", safe_sum(df_monthly, "إجمالي عدد العاملين الفعلي"))
            
            st.divider()
            
            if "المعهد" in df_monthly.columns:
                c1, c2 = st.columns(2)
                with c1:
                    fig = px.bar(df_monthly, x="المعهد",
                                y=["دراسات خطة بحثية جارية", "دراسات استشارية جارية",
                                   "دراسات بتمويل ذاتي جارية"],
                                title="الدراسات الجارية", barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    fig = px.bar(df_monthly, x="المعهد",
                                y=["تقرير مرحلي", "تقرير نهائي", "تقرير معاينة",
                                   "تقرير معايرة", "تقرير أخرى"],
                                title="التقارير", barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    fig = px.bar(df_monthly, x="المعهد",
                                y=["متدربين", "مدربين"],
                                title="التدريب", barmode="group")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    fig = px.bar(df_monthly, x="المعهد",
                                y=["اجتماعات بالوزارة", "اجتماعات بالمركز",
                                   "اجتماعات جهات خارجية", "اجتماعات مع العاملين",
                                   "اجتماعات جهات أخرى"],
                                title="الاجتماعات", barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📭 لا توجد بيانات شهرية")

# ============================================================
# 📊 لوحة التقارير الربع سنوية (احترافية للأدمن)
# ============================================================
if tab_q_dashboard is not None:
    with tab_q_dashboard:
        st.title("📊 التقارير الربع سنوية — عرض احترافي")
        
        try:
            ws = get_or_create_sheet("Quarterly_KPI", QUARTERLY_COLUMNS)
            all_values = ws.get_all_values()
            if len(all_values) <= 1:
                st.info("📭 لا توجد بيانات ربع سنوية")
                st.stop()
            df_q = pd.DataFrame(all_values[1:], columns=all_values[0])
        except Exception as e:
            st.error(f"خطأ في التحميل: {e}")
            st.stop()
        
        # تحويل الأعمدة الرقمية
        q_text_cols = ["المعهد", "المستخدم", "الربع", "السنة المالية",
                       "آليات تسويق إمكانات المعهد", "آليات الثواب والعقاب",
                       "ملاحظات عامة"]
        for col in df_q.columns:
            if col not in q_text_cols:
                df_q[col] = pd.to_numeric(df_q[col], errors="coerce").fillna(0)
        
        # الفلاتر
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
        if sel_q != "الكل":
            fq = fq[fq["الربع"] == sel_q]
        if sel_y != "الكل":
            fq = fq[fq["السنة المالية"] == sel_y]
        if st.session_state.role == "admin" and sel_i != "الكل":
            fq = fq[fq["المعهد"] == sel_i]
        elif st.session_state.role != "admin":
            fq = fq[fq["المعهد"] == st.session_state.institute]
        
        st.divider()
        
        if fq.empty:
            st.warning("لا توجد بيانات للفلاتر المحددة")
            st.stop()
        
        # نظرة عامة
        st.markdown("## 📌 نظرة عامة")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🏢 عدد المعاهد", fq["المعهد"].nunique())
        c2.metric("📅 عدد السجلات", len(fq))
        c3.metric("🔬 أبحاث منشورة", int(fq["أبحاث منشورة"].sum()))
        c4.metric("📋 مقترحات", int(fq["إجمالي المقترحات"].sum()))
        c5.metric("🎓 فعاليات تدريب", int(fq["إجمالي التدريب - عدد"].sum()))
        
        st.divider()
        
        # الأقسام الثمانية
        # 1
        st.markdown("## 1️⃣ الأداء التنفيذي للخطة البحثية")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد",
                        y=["فردي - عدد المشاريع", "مشترك - عدد المشاريع"],
                        barmode="group", title="عدد المشاريع البحثية",
                        color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد",
                        y=["فردي - نسبة المنفذ %", "مشترك - نسبة المنفذ %",
                           "مشترك - نسبة المشاركة %"],
                        barmode="group", title="نسب التنفيذ والمشاركة")
            st.plotly_chart(fig, use_container_width=True)
        
        # 2
        st.markdown("## 2️⃣ الاستشارات والدراسات خارج الخطة")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد",
                        y=["مشاريع ممولة محلياً", "مشاريع ممولة دولياً",
                           "تكليفات من الوزارة", "استشارات من الوزارة",
                           "استشارات من جهات حكومية/خاصة"],
                        barmode="stack", title="المشاريع خارج الخطة")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد",
                        y=["مقترحات محلية", "مقترحات دولية",
                           "مقترحات للوزارة", "مقترحات خارج الوزارة"],
                        barmode="stack", title="المقترحات البحثية (Pipeline)")
            st.plotly_chart(fig, use_container_width=True)
        
        # 3
        st.markdown("## 3️⃣ التعاون الداخلي والخارجي")
        fig = px.bar(fq, x="المعهد",
                    y=["تعاون داخلي مع المعاهد",
                       "تعاون داخلي مع جهات خارج المعاهد",
                       "تعاون خارجي مع جهات أجنبية"],
                    barmode="group", title="أوجه التعاون")
        st.plotly_chart(fig, use_container_width=True)
        
        # 4
        st.markdown("## 4️⃣ الإنتاج العلمي والنشر والابتكار")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد",
                        y=["أبحاث منشورة", "أبحاث في مجلات متميزة Q1/Q2",
                           "أبحاث حصلت على موافقة النشر"],
                        barmode="group", title="الأبحاث والنشر")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد",
                        y=["رسائل ماجستير", "رسائل دكتوراه"],
                        barmode="group", title="الرسائل العلمية")
            st.plotly_chart(fig, use_container_width=True)
        
        # 5
        st.markdown("## 5️⃣ التدريب / التعليم")
        tr_cols = [c for c in fq.columns if "- عدد" in c and c != "إجمالي التدريب - عدد"]
        if tr_cols:
            fig = px.bar(fq, x="المعهد", y=tr_cols,
                        barmode="stack", title="أنواع التدريب")
            st.plotly_chart(fig, use_container_width=True)
        
        # 6
        st.markdown("## 6️⃣ التمويل والأداء المالي")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد",
                        y=["تمويل الخطة البحثية - مبلغ",
                           "تمويل خارجي - مبلغ",
                           "المنصرف الفعلي - مبلغ"],
                        barmode="group", title="مصادر التمويل (ألف ج)")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(fq, x="المعهد",
                        y=["تمويل نشر علمي - دراسات",
                           "تمويل نشر علمي - أبحاث",
                           "تمويل نشر علمي - مكافآت"],
                        barmode="stack", title="تمويل النشر العلمي")
            st.plotly_chart(fig, use_container_width=True)
        
        # 7
        st.markdown("## 7️⃣ مؤشرات الأداء للموارد البشرية")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(fq, x="المعهد",
                        y=["اجتماعات دورية مع الهيئة البحثية والعاملين",
                           "اجتماعات مجلس إدارة المعهد",
                           "اجتماعات وحدة الفكر"],
                        barmode="group", title="الاجتماعات الدورية")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            disp = fq[["المعهد", "الربع", "آليات تسويق إمكانات المعهد",
                       "آليات الثواب والعقاب"]].copy()
            st.dataframe(disp, use_container_width=True)
        
        # 8
        st.markdown("## 8️⃣ الاجتماعات الوزارية")
        fig = px.bar(fq, x="المعهد", y="عدد الاجتماعات الوزارية",
                    title="عدد الاجتماعات الوزارية", color="الربع")
        st.plotly_chart(fig, use_container_width=True)
        
        # ملخص تنفيذي
        st.divider()
        st.markdown("## 📋 الملخص التنفيذي لكل معهد")
        
        for inst in fq["المعهد"].unique():
            i_df = fq[fq["المعهد"] == inst]
            with st.expander(f"🏢 {inst}", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📚 مشاريع بحثية",
                          int(i_df["فردي - عدد المشاريع"].sum() +
                              i_df["مشترك - عدد المشاريع"].sum()))
                c2.metric("📄 تقارير",
                          int(i_df["فردي - عدد التقارير"].sum() +
                              i_df["مشترك - عدد التقارير"].sum()))
                c3.metric("🔬 أبحاث منشورة", int(i_df["أبحاث منشورة"].sum()))
                c4.metric("📋 مقترحات", int(i_df["إجمالي المقترحات"].sum()))
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("🎓 ماجستير", int(i_df["رسائل ماجستير"].sum()))
                c2.metric("🎓 دكتوراه", int(i_df["رسائل دكتوراه"].sum()))
                c3.metric("💰 تمويل الخطة (ألف ج)",
                          f"{i_df['تمويل الخطة البحثية - مبلغ'].sum():.1f}")
                c4.metric("💵 المنصرف (ألف ج)",
                          f"{i_df['المنصرف الفعلي - مبلغ'].sum():.1f}")
        
        # الجدول الشامل + التحميل
        st.divider()
        st.markdown("## 📄 الجدول الشامل")
        
        main_cols = ["المعهد", "الربع", "السنة المالية",
                     "فردي - عدد المشاريع", "مشترك - عدد المشاريع",
                     "إجمالي المشاريع خارج الخطة", "إجمالي المقترحات",
                     "أبحاث منشورة", "رسائل ماجستير", "رسائل دكتوراه",
                     "إجمالي التدريب - عدد", "إجمالي التدريب - متدربين",
                     "تمويل الخطة البحثية - مبلغ", "تمويل خارجي - مبلغ",
                     "عدد الاجتماعات الوزارية"]
        disp_cols = [c for c in main_cols if c in fq.columns]
        st.dataframe(fq[disp_cols], use_container_width=True)
        
        def to_excel(d):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as w:
                d.to_excel(w, index=False, sheet_name="Quarterly")
            return out.getvalue()
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 تحميل Excel شامل",
                              data=to_excel(fq),
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
                metric = st.selectbox("اختر المؤشر", avail_metrics, key="trend_m")
                
                if st.session_state.role == "admin" and "المعهد" in df_t.columns:
                    fig = px.line(df_t, x="شهر-سنة", y=metric, color="المعهد",
                                 markers=True, title=f"التغير الشهري - {metric}")
                else:
                    fig = px.line(df_t, x="شهر-سنة", y=metric, markers=True,
                                 title=f"التغير الشهري - {metric} - {st.session_state.institute}")
                
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
            if "المعهد" in fd.columns and fi:
                fd = fd[fd["المعهد"].isin(fi)]
            if "السنة" in fd.columns and fy:
                fd = fd[fd["السنة"].isin(fy)]
            if "الشهر" in fd.columns and fm:
                fd = fd[fd["الشهر"].isin(fm)]
            
            st.dataframe(fd, use_container_width=True)
            
            def to_excel_m(d):
                out = BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as w:
                    d.to_excel(w, index=False, sheet_name="Monthly")
                return out.getvalue()
            
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 تحميل Excel",
                                  data=to_excel_m(fd),
                                  file_name=f"monthly_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with c2:
                st.download_button("📥 تحميل CSV",
                                  data=fd.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'),
                                  file_name=f"monthly_{datetime.now().strftime('%Y%m%d')}.csv",
                                  mime="text/csv")
        else:
            st.info("📭 لا توجد بيانات شهرية")

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
            v_year = st.number_input("السنة", min_value=2020, max_value=2035,
                                     value=2026, key="v_y")
        
        v_period = f"{v_month} {v_year}"
        
        v_tabs = st.tabs([
            "📚 الدراسات", "💼 مشروعات", "🎯 استشارات",
            "📄 تقارير فنية", "🤝 اجتماعات", "🎓 تدريب",
            "👥 تحسين الأداء"
        ])
        
        def view_list(tab_obj, sheet_name, cols, key):
            with tab_obj:
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
                    st.dataframe(data[cols], use_container_width=True)
        
        view_list(v_tabs[0], "الدراسات_البحثية", STUDIES_COLUMNS, "v1")
        view_list(v_tabs[1], "مشروعات_ممولة", PROJECTS_COLUMNS, "v2")
        view_list(v_tabs[2], "استشارات_ممولة", CONSULT_COLUMNS, "v3")
        view_list(v_tabs[3], "التقارير_الفنية", REPORTS_COLUMNS, "v4")
        view_list(v_tabs[4], "الاجتماعات", MEETINGS_COLUMNS, "v5")
        view_list(v_tabs[5], "التدريب", TRAINING_COLUMNS, "v6")
        view_list(v_tabs[6], "اجتماعات_تحسين_الأداء", PERF_MEETINGS_COLUMNS, "v7")
