import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from io import BytesIO
import streamlit as st
import json
from datetime import datetime

# ==============================
# إعداد الصفحة
# ==============================
st.set_page_config(
    page_title="نظام مؤشرات الأداء - المركز القومي لبحوث المياه",
    layout="wide"
)

current_dir = os.path.dirname(__file__)
logo_path = os.path.join(current_dir, "logo.png")
if os.path.exists(logo_path):
    st.image(logo_path, width=150)

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; }
.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ==============================
# الاتصال بـ Google Sheets
# ==============================
SPREADSHEET_KEY = "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"

@st.cache_resource
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(credentials)

def get_spreadsheet():
    return get_client().open_by_key(SPREADSHEET_KEY)

def get_or_create_sheet(sheet_name, headers=None):
    """الحصول على ورقة أو إنشاؤها مع العناوين"""
    try:
        ss = get_spreadsheet()
        try:
            ws = ss.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=sheet_name, rows=1000, cols=20)
            if headers:
                ws.append_row(headers)
        return ws
    except Exception as e:
        st.error(f"خطأ في الاتصال: {e}")
        return None

# ==============================
# الأعمدة الرقمية الرئيسية (موسعة)
# ==============================
COLUMNS_ORDER = [
    "المعهد", "المستخدم", "الشهر", "السنة",
    # الدراسات الجارية
    "دراسات خطة بحثية جارية",
    "دراسات استشارية جارية",
    "دراسات بتمويل ذاتي جارية",
    "إجمالي الدراسات الجارية",
    # التقارير
    "تقرير مرحلي",
    "تقرير نهائي",
    "تقرير معاينة",
    "تقرير معايرة",
    "تقرير أخرى",
    "إجمالي التقارير",
    # المذكرات
    "عدد المذكرات",
    # المقترحات
    "مقترحات استشارات",
    "مقترحات تمويل أبحاث",
    "إجمالي المقترحات",
    # المأموريات
    "إجمالي عدد المأموريات",
    "إجمالي عدد أيام المأموريات",
    # المعاينات
    "إجمالي عدد المعاينات",
    # التدريب
    "متدربين",
    "مدربين",
    "أيام تدريب متدربين داخل المعهد",
    "أيام تدريب متدربين خارج المعهد",
    # الأنشطة العلمية
    "مشتركين مؤتمرات",
    "مشتركين ورش عمل",
    "إجمالي المشاركين في أنشطة علمية",
    # الاجتماعات
    "اجتماعات بالوزارة",
    "اجتماعات بالمركز",
    "اجتماعات جهات خارجية",
    "اجتماعات مع العاملين",
    "اجتماعات جهات أخرى",
    "إجمالي الاجتماعات",
    # الأوراق البحثية
    "أوراق بحثية منشورة",
    "أوراق بحثية جاري العمل عليها",
    "إجمالي الأوراق البحثية",
    # الرسائل العلمية
    "رسائل منتهية",
    "رسائل جاري العمل عليها",
    "إجمالي الرسائل",
    # العاملون
    "إجمالي عدد العاملين الفعلي",
    "الأساتذة المتفرغين",
    "الأساتذة",
    "الأساتذة المساعدون",
    "الباحثون",
    "الباحث المساعد",
    "مساعد باحث",
    "الفنيون",
    "الإداريون",
    "السائقون",
    # بيانات إضافية
    "إجمالي الإيرادات الذاتية",
    "عدد براءات الاختراع",
    "المبلغ المنصرف من الموازنة الاستثمارية"
]

# ==============================
# أعمدة القوائم النصية
# ==============================
STUDIES_COLUMNS = ["م", "عنوان الدراسة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
PROJECTS_COLUMNS = ["م", "عنوان المشروع", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
CONSULT_COLUMNS = ["م", "عنوان الاستشارة", "الجهة المستفيدة", "تاريخ إصدار التقرير", "ملخص التقرير"]
REPORTS_COLUMNS = ["م", "عنوان التقرير", "تاريخ الإصدار", "الجهة المستفيدة", "الدائرة طبقاً للخطة البحثية", "ملخص التقرير"]
MEETINGS_COLUMNS = ["م", "التاريخ", "الاسم", "الوظيفة", "مكان الانعقاد", "الغرض من الاجتماع", "النوع"]
TRAINING_COLUMNS = ["م", "عنوان البرنامج", "النوع", "عدد المشاركين", "مكان الانعقاد", "مدة البرنامج"]
PERF_MEETINGS_COLUMNS = ["م", "التاريخ", "عنوان الاجتماع", "الغرض من الاجتماع", "السادة الحضور"]

# ==============================
# المستخدمين
# ==============================
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

# ==============================
# دوال مساعدة
# ==============================
def load_main_data():
    """تحميل البيانات الرقمية الرئيسية"""
    try:
        ws = get_or_create_sheet("KPI_Data", COLUMNS_ORDER)
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            return pd.DataFrame(columns=all_values[0] if all_values else COLUMNS_ORDER)
        return pd.DataFrame(all_values[1:], columns=all_values[0])
    except Exception as e:
        st.error(f"خطأ في تحميل البيانات: {e}")
        return pd.DataFrame()

def load_list_data(sheet_name, columns):
    """تحميل بيانات قائمة نصية"""
    try:
        ws = get_or_create_sheet(sheet_name, columns)
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(all_values[1:], columns=all_values[0])
    except Exception:
        return pd.DataFrame(columns=columns)

def safe_sum(df, column):
    if df.empty or column not in df.columns:
        return 0
    return int(pd.to_numeric(df[column], errors='coerce').fillna(0).sum())

# ==============================
# Session State
# ==============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ==============================
# تسجيل الدخول
# ==============================
if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    
    if st.button("دخول"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = USERS[username]["role"]
            st.session_state.institute = USERS[username]["institute"]
            st.rerun()
        else:
            st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# ==============================
# بعد تسجيل الدخول
# ==============================
df = load_main_data()

st.success(f"مرحباً {st.session_state.username} - {st.session_state.institute}")

col_logout = st.columns([6, 1])
with col_logout[1]:
    if st.button("تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

# تصفية حسب الصلاحيات
if not df.empty and st.session_state.role != "admin" and "المعهد" in df.columns:
    df = df[df["المعهد"] == st.session_state.institute]

# ==============================
# التبويبات
# ==============================
if st.session_state.role == "admin":
    tab_dashboard, tab_lists, tab_data = st.tabs([
        "📊 Dashboard", "📋 القوائم التفصيلية", "📄 البيانات الرقمية"
    ])
    tab_input = None
else:
    tab_input, tab_lists_input, tab_dashboard, tab_lists, tab_data = st.tabs([
        "📥 إدخال البيانات الرقمية",
        "📝 إدخال القوائم التفصيلية",
        "📊 Dashboard",
        "📋 القوائم التفصيلية",
        "📄 البيانات الرقمية"
    ])

# ============================================================
# Tab الإدخال الرقمي
# ============================================================
if tab_input is not None:
    with tab_input:
        st.header("📥 إدخال البيانات الرقمية الشهرية")
        
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("الشهر", [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ])
        with col2:
            year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026)

        st.divider()
        
        # الدراسات الجارية
        st.subheader("📚 الدراسات الجارية")
        c1, c2, c3 = st.columns(3)
        research_studies = c1.number_input("خطة بحثية", min_value=0, key="rs")
        consult_studies = c2.number_input("استشارية", min_value=0, key="cs")
        self_funded = c3.number_input("دراسات بتمويل ذاتي", min_value=0, key="sf")
        total_studies = research_studies + consult_studies + self_funded
        st.info(f"إجمالي الدراسات الجارية: {total_studies}")
        
        st.divider()
        
        # التقارير
        st.subheader("📄 التقارير الصادرة خلال الشهر")
        c1, c2, c3, c4, c5 = st.columns(5)
        rep_progress = c1.number_input("تقرير مرحلي", min_value=0)
        rep_final = c2.number_input("تقرير نهائي", min_value=0)
        rep_survey = c3.number_input("تقرير معاينة", min_value=0)
        rep_calib = c4.number_input("تقرير معايرة", min_value=0)
        rep_other = c5.number_input("أخرى", min_value=0)
        total_reports = rep_progress + rep_final + rep_survey + rep_calib + rep_other
        st.info(f"إجمالي التقارير: {total_reports}")
        
        st.divider()
        
        # المذكرات والمقترحات
        st.subheader("📋 المذكرات والمقترحات")
        c1, c2, c3 = st.columns(3)
        memos = c1.number_input("عدد المذكرات", min_value=0)
        prop_consult = c2.number_input("مقترحات استشارات", min_value=0)
        prop_fund = c3.number_input("مقترحات تمويل أبحاث", min_value=0)
        total_props = prop_consult + prop_fund
        st.info(f"إجمالي المقترحات: {total_props}")
        
        st.divider()
        
        # المأموريات والمعاينات
        st.subheader("🏃 المأموريات والمعاينات الحقلية")
        c1, c2, c3 = st.columns(3)
        missions_count = c1.number_input("إجمالي عدد المأموريات", min_value=0)
        missions_days = c2.number_input("إجمالي عدد الأيام الفعلية", min_value=0)
        surveys_count = c3.number_input("إجمالي عدد المعاينات", min_value=0)
        
        st.divider()
        
        # التدريب
        st.subheader("👥 التدريب")
        c1, c2, c3, c4 = st.columns(4)
        trainees = c1.number_input("متدربين", min_value=0)
        trainers = c2.number_input("مدربين", min_value=0)
        train_days_in = c3.number_input("أيام تدريب (داخل المعهد)", min_value=0)
        train_days_out = c4.number_input("أيام تدريب (خارج المعهد)", min_value=0)
        
        st.divider()
        
        # الأنشطة العلمية
        st.subheader("🔬 الأنشطة العلمية")
        c1, c2 = st.columns(2)
        conf_att = c1.number_input("مشتركين مؤتمرات", min_value=0)
        work_att = c2.number_input("مشتركين ورش عمل", min_value=0)
        total_activities = conf_att + work_att
        
        st.divider()
        
        # الاجتماعات
        st.subheader("🤝 الاجتماعات")
        c1, c2, c3, c4, c5 = st.columns(5)
        m_ministry = c1.number_input("بالوزارة", min_value=0)
        m_center = c2.number_input("بالمركز", min_value=0)
        m_external = c3.number_input("جهات خارجية", min_value=0)
        m_staff = c4.number_input("مع العاملين", min_value=0)
        m_other = c5.number_input("جهات أخرى", min_value=0)
        total_meetings = m_ministry + m_center + m_external + m_staff + m_other
        
        st.divider()
        
        # الأوراق البحثية والرسائل
        st.subheader("📝 الأوراق البحثية والرسائل العلمية")
        c1, c2, c3, c4 = st.columns(4)
        papers_pub = c1.number_input("أوراق منشورة", min_value=0)
        papers_ongoing = c2.number_input("أوراق جاري العمل عليها", min_value=0)
        theses_done = c3.number_input("رسائل منتهية", min_value=0)
        theses_ongoing = c4.number_input("رسائل جاري العمل عليها", min_value=0)
        
        st.divider()
        
        # العاملون بالمعهد
        st.subheader("👤 عدد العاملين بالمعهد")
        c1, c2, c3 = st.columns(3)
        total_staff = c1.number_input("إجمالي عدد العاملين الفعلي", min_value=0)
        profs_emeritus = c2.number_input("الأساتذة المتفرغين", min_value=0)
        profs = c3.number_input("الأساتذة", min_value=0)
        
        c1, c2, c3 = st.columns(3)
        assoc_profs = c1.number_input("الأساتذة المساعدون", min_value=0)
        researchers = c2.number_input("الباحثون", min_value=0)
        assist_researchers = c3.number_input("الباحث المساعد", min_value=0)
        
        c1, c2, c3 = st.columns(3)
        assist_researcher2 = c1.number_input("مساعد باحث", min_value=0)
        technicians = c2.number_input("الفنيون", min_value=0)
        admins = c3.number_input("الإداريون", min_value=0)
        
        drivers = st.number_input("السائقون", min_value=0)
        
        st.divider()
        
        # بيانات إضافية
        st.subheader("💰 بيانات إضافية")
        c1, c2, c3 = st.columns(3)
        revenues = c1.number_input("إجمالي الإيرادات الذاتية", min_value=0.0, format="%.2f")
        patents = c2.number_input("عدد براءات الاختراع", min_value=0)
        budget = c3.number_input("المبلغ المنصرف من الموازنة الاستثمارية", min_value=0.0, format="%.2f")
        
        st.divider()
        
        if st.button("💾 حفظ البيانات الرقمية", type="primary"):
            try:
                ws = get_or_create_sheet("KPI_Data", COLUMNS_ORDER)
                all_values = ws.get_all_values()
                
                # منع التكرار
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
                
                data_input = {
                    "المعهد": st.session_state.institute,
                    "المستخدم": st.session_state.username,
                    "الشهر": month,
                    "السنة": int(year),
                    "دراسات خطة بحثية جارية": research_studies,
                    "دراسات استشارية جارية": consult_studies,
                    "دراسات بتمويل ذاتي جارية": self_funded,
                    "إجمالي الدراسات الجارية": total_studies,
                    "تقرير مرحلي": rep_progress,
                    "تقرير نهائي": rep_final,
                    "تقرير معاينة": rep_survey,
                    "تقرير معايرة": rep_calib,
                    "تقرير أخرى": rep_other,
                    "إجمالي التقارير": total_reports,
                    "عدد المذكرات": memos,
                    "مقترحات استشارات": prop_consult,
                    "مقترحات تمويل أبحاث": prop_fund,
                    "إجمالي المقترحات": total_props,
                    "إجمالي عدد المأموريات": missions_count,
                    "إجمالي عدد أيام المأموريات": missions_days,
                    "إجمالي عدد المعاينات": surveys_count,
                    "متدربين": trainees,
                    "مدربين": trainers,
                    "أيام تدريب متدربين داخل المعهد": train_days_in,
                    "أيام تدريب متدربين خارج المعهد": train_days_out,
                    "مشتركين مؤتمرات": conf_att,
                    "مشتركين ورش عمل": work_att,
                    "إجمالي المشاركين في أنشطة علمية": total_activities,
                    "اجتماعات بالوزارة": m_ministry,
                    "اجتماعات بالمركز": m_center,
                    "اجتماعات جهات خارجية": m_external,
                    "اجتماعات مع العاملين": m_staff,
                    "اجتماعات جهات أخرى": m_other,
                    "إجمالي الاجتماعات": total_meetings,
                    "أوراق بحثية منشورة": papers_pub,
                    "أوراق بحثية جاري العمل عليها": papers_ongoing,
                    "إجمالي الأوراق البحثية": papers_pub + papers_ongoing,
                    "رسائل منتهية": theses_done,
                    "رسائل جاري العمل عليها": theses_ongoing,
                    "إجمالي الرسائل": theses_done + theses_ongoing,
                    "إجمالي عدد العاملين الفعلي": total_staff,
                    "الأساتذة المتفرغين": profs_emeritus,
                    "الأساتذة": profs,
                    "الأساتذة المساعدون": assoc_profs,
                    "الباحثون": researchers,
                    "الباحث المساعد": assist_researchers,
                    "مساعد باحث": assist_researcher2,
                    "الفنيون": technicians,
                    "الإداريون": admins,
                    "السائقون": drivers,
                    "إجمالي الإيرادات الذاتية": revenues,
                    "عدد براءات الاختراع": patents,
                    "المبلغ المنصرف من الموازنة الاستثمارية": budget
                }
                
                new_row = [str(data_input.get(col, "0")) for col in COLUMNS_ORDER]
                ws.append_row(new_row)
                st.success("✅ تم حفظ البيانات الرقمية بنجاح")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ: {e}")

# ============================================================
# Tab إدخال القوائم النصية
# ============================================================
if tab_input is not None:
    with tab_lists_input:
        st.header("📝 إدخال القوائم التفصيلية")
        
        col1, col2 = st.columns(2)
        with col1:
            month_list = st.selectbox("الشهر", [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ], key="month_list")
        with col2:
            year_list = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="year_list")
        
        st.info(f"📌 سيتم حفظ القوائم للمعهد: **{st.session_state.institute}** - **{month_list} {year_list}**")
        
        st.divider()
        
        # القوائم الفرعية
        list_tabs = st.tabs([
            "📚 الدراسات البحثية",
            "💼 مشروعات بحثية ممولة",
            "🎯 استشارات بحثية ممولة",
            "📄 التقارير الفنية",
            "🤝 الاجتماعات",
            "🎓 التدريب والندوات",
            "👥 اجتماعات تحسين الأداء"
        ])
        
        # 1. الدراسات البحثية
        with list_tabs[0]:
            st.subheader("الدراسات البحثية التي تمت خلال الشهر")
            studies_df = load_list_data("الدراسات_البحثية", STUDIES_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not studies_df.empty:
                studies_df = studies_df[
                    (studies_df.get("المعهد", "") == st.session_state.institute) &
                    (studies_df.get("الشهر", "") == month_list) &
                    (studies_df.get("السنة", "") == str(int(year_list)))
                ] if "المعهد" in studies_df.columns else pd.DataFrame(columns=STUDIES_COLUMNS)
            else:
                studies_df = pd.DataFrame(columns=STUDIES_COLUMNS)
            
            studies_input = st.data_editor(
                studies_df[STUDIES_COLUMNS] if not studies_df.empty else pd.DataFrame(columns=STUDIES_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="studies_editor"
            )
            
            if st.button("💾 حفظ الدراسات البحثية", key="save_studies"):
                save_list_data("الدراسات_البحثية", studies_input, STUDIES_COLUMNS,
                              st.session_state.institute, month_list, year_list)
        
        # 2. المشروعات
        with list_tabs[1]:
            st.subheader("مشروعات بحثية ممولة")
            projects_df = load_list_data("مشروعات_ممولة", PROJECTS_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not projects_df.empty and "المعهد" in projects_df.columns:
                projects_df = projects_df[
                    (projects_df["المعهد"] == st.session_state.institute) &
                    (projects_df["الشهر"] == month_list) &
                    (projects_df["السنة"] == str(int(year_list)))
                ]
            else:
                projects_df = pd.DataFrame(columns=PROJECTS_COLUMNS)
            
            projects_input = st.data_editor(
                projects_df[PROJECTS_COLUMNS] if not projects_df.empty else pd.DataFrame(columns=PROJECTS_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="projects_editor"
            )
            
            if st.button("💾 حفظ المشروعات", key="save_projects"):
                save_list_data("مشروعات_ممولة", projects_input, PROJECTS_COLUMNS,
                              st.session_state.institute, month_list, year_list)
        
        # 3. الاستشارات
        with list_tabs[2]:
            st.subheader("استشارات بحثية ممولة")
            consult_df = load_list_data("استشارات_ممولة", CONSULT_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not consult_df.empty and "المعهد" in consult_df.columns:
                consult_df = consult_df[
                    (consult_df["المعهد"] == st.session_state.institute) &
                    (consult_df["الشهر"] == month_list) &
                    (consult_df["السنة"] == str(int(year_list)))
                ]
            else:
                consult_df = pd.DataFrame(columns=CONSULT_COLUMNS)
            
            consult_input = st.data_editor(
                consult_df[CONSULT_COLUMNS] if not consult_df.empty else pd.DataFrame(columns=CONSULT_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="consult_editor"
            )
            
            if st.button("💾 حفظ الاستشارات", key="save_consult"):
                save_list_data("استشارات_ممولة", consult_input, CONSULT_COLUMNS,
                              st.session_state.institute, month_list, year_list)
        
        # 4. التقارير الفنية
        with list_tabs[3]:
            st.subheader("التقارير الفنية التي تم دراستها")
            reports_df = load_list_data("التقارير_الفنية", REPORTS_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not reports_df.empty and "المعهد" in reports_df.columns:
                reports_df = reports_df[
                    (reports_df["المعهد"] == st.session_state.institute) &
                    (reports_df["الشهر"] == month_list) &
                    (reports_df["السنة"] == str(int(year_list)))
                ]
            else:
                reports_df = pd.DataFrame(columns=REPORTS_COLUMNS)
            
            reports_input = st.data_editor(
                reports_df[REPORTS_COLUMNS] if not reports_df.empty else pd.DataFrame(columns=REPORTS_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="reports_editor"
            )
            
            if st.button("💾 حفظ التقارير الفنية", key="save_reports"):
                save_list_data("التقارير_الفنية", reports_input, REPORTS_COLUMNS,
                              st.session_state.institute, month_list, year_list)
        
        # 5. الاجتماعات
        with list_tabs[4]:
            st.subheader("الاجتماعات")
            st.caption("النوع: بالوزارة / بالمركز / جهات خارجية / بمقر المعهد / جهات أخرى / افتراضية")
            meetings_df = load_list_data("الاجتماعات", MEETINGS_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not meetings_df.empty and "المعهد" in meetings_df.columns:
                meetings_df = meetings_df[
                    (meetings_df["المعهد"] == st.session_state.institute) &
                    (meetings_df["الشهر"] == month_list) &
                    (meetings_df["السنة"] == str(int(year_list)))
                ]
            else:
                meetings_df = pd.DataFrame(columns=MEETINGS_COLUMNS)
            
            meetings_input = st.data_editor(
                meetings_df[MEETINGS_COLUMNS] if not meetings_df.empty else pd.DataFrame(columns=MEETINGS_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="meetings_editor"
            )
            
            if st.button("💾 حفظ الاجتماعات", key="save_meetings"):
                save_list_data("الاجتماعات", meetings_input, MEETINGS_COLUMNS,
                              st.session_state.institute, month_list, year_list)
        
        # 6. التدريب
        with list_tabs[5]:
            st.subheader("الدورات التدريبية / ورش العمل / الندوات / المؤتمرات")
            training_df = load_list_data("التدريب", TRAINING_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not training_df.empty and "المعهد" in training_df.columns:
                training_df = training_df[
                    (training_df["المعهد"] == st.session_state.institute) &
                    (training_df["الشهر"] == month_list) &
                    (training_df["السنة"] == str(int(year_list)))
                ]
            else:
                training_df = pd.DataFrame(columns=TRAINING_COLUMNS)
            
            training_input = st.data_editor(
                training_df[TRAINING_COLUMNS] if not training_df.empty else pd.DataFrame(columns=TRAINING_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="training_editor"
            )
            
            if st.button("💾 حفظ التدريب", key="save_training"):
                save_list_data("التدريب", training_input, TRAINING_COLUMNS,
                              st.session_state.institute, month_list, year_list)
        
        # 7. اجتماعات تحسين الأداء
        with list_tabs[6]:
            st.subheader("اجتماعات تحسين الأداء وتعزيز الروح الجماعية")
            perf_df = load_list_data("اجتماعات_تحسين_الأداء", PERF_MEETINGS_COLUMNS + ["المعهد", "الشهر", "السنة"])
            if not perf_df.empty and "المعهد" in perf_df.columns:
                perf_df = perf_df[
                    (perf_df["المعهد"] == st.session_state.institute) &
                    (perf_df["الشهر"] == month_list) &
                    (perf_df["السنة"] == str(int(year_list)))
                ]
            else:
                perf_df = pd.DataFrame(columns=PERF_MEETINGS_COLUMNS)
            
            perf_input = st.data_editor(
                perf_df[PERF_MEETINGS_COLUMNS] if not perf_df.empty else pd.DataFrame(columns=PERF_MEETINGS_COLUMNS),
                num_rows="dynamic", use_container_width=True, key="perf_editor"
            )
            
            if st.button("💾 حفظ اجتماعات تحسين الأداء", key="save_perf"):
                save_list_data("اجتماعات_تحسين_الأداء", perf_input, PERF_MEETINGS_COLUMNS,
                              st.session_state.institute, month_list, year_list)


# ==============================
# دالة حفظ القوائم
# ==============================
def save_list_data(sheet_name, input_df, base_columns, institute, month, year):
    """حفظ بيانات قائمة نصية"""
    try:
        ws = get_or_create_sheet(sheet_name, base_columns + ["المعهد", "الشهر", "السنة"])
        all_values = ws.get_all_values()
        
        # حذف الصفوف القديمة لنفس المعهد/الشهر/السنة
        if len(all_values) > 1:
            existing = pd.DataFrame(all_values[1:], columns=all_values[0])
            mask = ~(
                (existing["المعهد"] == institute) &
                (existing["الشهر"] == month) &
                (existing["السنة"] == str(int(year)))
            )
            kept = existing[mask]
            
            # إعادة كتابة الورقة
            ws.clear()
            ws.append_row(base_columns + ["المعهد", "الشهر", "السنة"])
            for _, row in kept.iterrows():
                ws.append_row([str(v) for v in row.tolist()])
        
        # إضافة الصفوف الجديدة
        for _, row in input_df.iterrows():
            # تجاهل الصفوف الفارغة
            if all(str(v).strip() in ["", "nan", "None"] for v in row.tolist() if pd.notna(v)):
                continue
            new_row = [str(v) if pd.notna(v) else "" for v in row.tolist()]
            new_row += [institute, month, str(int(year))]
            ws.append_row(new_row)
        
        st.success(f"✅ تم حفظ البيانات في {sheet_name}")
        st.balloons()
        st.rerun()
    except Exception as e:
        st.error(f"❌ خطأ في الحفظ: {e}")


# ============================================================
# Tab Dashboard
# ============================================================
with tab_dashboard:
    st.title("📊 لوحة مؤشرات الأداء")
    
    if not df.empty:
        # تحويل الأعمدة الرقمية
        for col in df.columns:
            if col not in ["المعهد", "المستخدم", "الشهر", "السنة"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        st.subheader("مؤشرات رئيسية")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📚 الدراسات الجارية", safe_sum(df, "إجمالي الدراسات الجارية"))
        c2.metric("📄 التقارير", safe_sum(df, "إجمالي التقارير"))
        c3.metric("📋 المقترحات", safe_sum(df, "إجمالي المقترحات"))
        c4.metric("🤝 الاجتماعات", safe_sum(df, "إجمالي الاجتماعات"))
        c5.metric("👨‍🎓 المتدربين", safe_sum(df, "متدربين"))
        
        st.divider()
        
        st.subheader("مؤشرات تفصيلية")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🏃 المأموريات", safe_sum(df, "إجمالي عدد المأموريات"))
        c2.metric("🔍 المعاينات", safe_sum(df, "إجمالي عدد المعاينات"))
        c3.metric("📝 الأوراق البحثية", safe_sum(df, "إجمالي الأوراق البحثية"))
        c4.metric("🎓 الرسائل العلمية", safe_sum(df, "إجمالي الرسائل"))
        c5.metric("👥 العاملون", safe_sum(df, "إجمالي عدد العاملين الفعلي"))
        
        st.divider()
        
        # رسوم بيانية
        if "المعهد" in df.columns:
            c1, c2 = st.columns(2)
            
            with c1:
                fig1 = px.bar(df, x="المعهد",
                             y=["دراسات خطة بحثية جارية", "دراسات استشارية جارية", "دراسات بتمويل ذاتي جارية"],
                             title="الدراسات الجارية", barmode="group")
                st.plotly_chart(fig1, use_container_width=True)
            
            with c2:
                fig2 = px.bar(df, x="المعهد",
                             y=["تقرير مرحلي", "تقرير نهائي", "تقرير معاينة", "تقرير معايرة"],
                             title="التقارير", barmode="stack")
                st.plotly_chart(fig2, use_container_width=True)
            
            c1, c2 = st.columns(2)
            with c1:
                fig3 = px.bar(df, x="المعهد",
                             y=["متدربين", "مدربين"],
                             title="التدريب", barmode="group")
                st.plotly_chart(fig3, use_container_width=True)
            
            with c2:
                fig4 = px.bar(df, x="المعهد",
                             y=["اجتماعات بالوزارة", "اجتماعات بالمركز", "اجتماعات جهات خارجية",
                                "اجتماعات مع العاملين", "اجتماعات جهات أخرى"],
                             title="الاجتماعات", barmode="stack")
                st.plotly_chart(fig4, use_container_width=True)
            
            c1, c2 = st.columns(2)
            with c1:
                fig5 = px.bar(df, x="المعهد",
                             y=["أوراق بحثية منشورة", "أوراق بحثية جاري العمل عليها"],
                             title="الأوراق البحثية", barmode="group")
                st.plotly_chart(fig5, use_container_width=True)
            
            with c2:
                fig6 = px.bar(df, x="المعهد",
                             y=["الأساتذة المتفرغين", "الأساتذة", "الأساتذة المساعدون",
                                "الباحثون", "الباحث المساعد", "مساعد باحث", "الفنيون", "الإداريون", "السائقون"],
                             title="توزيع العاملين", barmode="stack")
                st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("📭 لا توجد بيانات متاحة")


# ============================================================
# Tab عرض القوائم النصية
# ============================================================
with tab_lists:
    st.title("📋 القوائم التفصيلية")
    
    c1, c2 = st.columns(2)
    with c1:
        view_month = st.selectbox("الشهر", [
            "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
        ], key="view_month")
    with c2:
        view_year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026, key="view_year")
    
    st.divider()
    
    list_view_tabs = st.tabs([
        "📚 الدراسات البحثية",
        "💼 المشروعات الممولة",
        "🎯 الاستشارات الممولة",
        "📄 التقارير الفنية",
        "🤝 الاجتماعات",
        "🎓 التدريب والندوات",
        "👥 اجتماعات تحسين الأداء"
    ])
    
    def display_list(sheet_name, columns, tab_key):
        data = load_list_data(sheet_name, columns + ["المعهد", "الشهر", "السنة"])
        if data.empty:
            st.info("لا توجد بيانات")
            return
        
        filtered = data[
            (data["الشهر"] == view_month) &
            (data["السنة"] == str(int(view_year)))
        ]
        
        if st.session_state.role != "admin":
            filtered = filtered[filtered["المعهد"] == st.session_state.institute]
        
        if filtered.empty:
            st.info("لا توجد بيانات للفترة المحددة")
        else:
            st.dataframe(filtered[columns], use_container_width=True)
    
    with list_view_tabs[0]:
        display_list("الدراسات_البحثية", STUDIES_COLUMNS, "v1")
    with list_view_tabs[1]:
        display_list("مشروعات_ممولة", PROJECTS_COLUMNS, "v2")
    with list_view_tabs[2]:
        display_list("استشارات_ممولة", CONSULT_COLUMNS, "v3")
    with list_view_tabs[3]:
        display_list("التقارير_الفنية", REPORTS_COLUMNS, "v4")
    with list_view_tabs[4]:
        display_list("الاجتماعات", MEETINGS_COLUMNS, "v5")
    with list_view_tabs[5]:
        display_list("التدريب", TRAINING_COLUMNS, "v6")
    with list_view_tabs[6]:
        display_list("اجتماعات_تحسين_الأداء", PERF_MEETINGS_COLUMNS, "v7")


# ============================================================
# Tab البيانات الرقمية
# ============================================================
with tab_data:
    st.title("📄 البيانات الرقمية")
    
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.session_state.role == "admin" and "المعهد" in df.columns:
                fi = st.multiselect("المعهد", options=df["المعهد"].unique(), default=df["المعهد"].unique())
            else:
                fi = [st.session_state.institute]
        with c2:
            fy = st.multiselect("السنة", options=sorted(df["السنة"].unique()), default=sorted(df["السنة"].unique()))
        with c3:
            fm = st.multiselect("الشهر", options=df["الشهر"].unique(), default=df["الشهر"].unique())
        
        fdf = df.copy()
        if "المعهد" in fdf.columns and fi:
            fdf = fdf[fdf["المعهد"].isin(fi)]
        if "السنة" in fdf.columns and fy:
            fdf = fdf[fdf["السنة"].isin(fy)]
        if "الشهر" in fdf.columns and fm:
            fdf = fdf[fdf["الشهر"].isin(fm)]
        
        st.dataframe(fdf, use_container_width=True)
        
        def to_excel(d):
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as w:
                d.to_excel(w, index=False, sheet_name="KPI_Data")
            return out.getvalue()
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 تحميل Excel",
                              data=to_excel(fdf),
                              file_name=f"kpi_data_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            st.download_button("📥 تحميل CSV",
                              data=fdf.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig'),
                              file_name=f"kpi_data_{datetime.now().strftime('%Y%m%d')}.csv",
                              mime="text/csv")
    else:
        st.info("📭 لا توجد بيانات")
