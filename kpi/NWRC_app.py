import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import streamlit as st

# ==============================
# إعداد الصفحة
# ==============================
st.set_page_config(
    page_title="نظام مؤشرات الأداء - المركز القومي لبحوث المياه",
    layout="wide"
)

# ==============================
# الشعار
# ==============================
current_dir = os.path.dirname(__file__)
logo_path = os.path.join(current_dir, "logo.png")

if os.path.exists(logo_path):
    st.image(logo_path, width=150)

# ==============================
# RTL
# ==============================
st.markdown("""
<style>
html, body, [class*="css"] {
    direction: rtl;
    text-align: right;
}
.stButton > button {
    width: 100%;
}
.metric-card {
    background-color: #f0f2f6;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# الاتصال بـ Google Sheets
# ==============================
@st.cache_resource
def connect_to_gsheet():
    """الاتصال بـ Google Sheets مرة واحدة"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(
        "1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg"
    ).sheet1
    return sheet

# ==============================
# ترتيب الأعمدة الكامل
# ==============================
COLUMNS_ORDER = [
    "المعهد",
    "المستخدم",
    "الشهر",
    "السنة",
    
    # الدراسات الجارية
    "دراسات خطة بحثية جارية",
    "دراسات استشارية جارية",
    "مشروعات بحثية جارية",
    
    # الدراسات المنجزة (نصف سنوي)
    "دراسات خطة بحثية منجزة",
    
    # المخرجات التطبيقية (نصف سنوي)
    "مخرجات تطبيقية من دراسات ومشروعات",
    "نظام مراقبة Monitoring Network",
    
    # إجمالي الدراسات الجارية
    "إجمالي الدراسات الجارية",
    
    # التقارير
    "تقارير مرحلية",
    "تقارير نهائية",
    
    # المذكرات
    "مذكرات",
    
    # المقترحات
    "مقترحات دراسات استشارية",
    "مقترحات مشروعات بحثية",
    
    # المأموريات الحقلية
    "أيام فعلية مأموريات حقلية",
    
    # التدريب
    "متدربين",
    "مدربين",
    "أيام تدريب متدربين داخل المعهد",
    "أيام تدريب متدربين خارج المعهد",
    
    # أنشطة علمية
    "مشتركين مؤتمرات",
    "مشتركين ورش عمل",
    "إجمالي مشاركين أنشطة علمية",
    
    # الاجتماعات
    "اجتماعات وزارة",
    "اجتماعات مركز",
    "اجتماعات خارجية",
    "إجمالي اجتماعات",
    
    # أوراق بحثية
    "أوراق بحثية منشورة",
    "أوراق بحثية دولية منشورة",
    
    # رسائل علمية
    "رسائل ماجستير ودكتوراة منتهية",
    
    # إحصائيات الكادر (ربع سنوي)
    "عدد الباحثيين",
    "عدد الأساتذة",
    "عدد المهندسين",
    "إجمالي عدد العاملين",
    
    # إيرادات (نصف سنوي)
    "إجمالي الإيرادات الذاتية",
    
    # براءات اختراع (سنوي)
    "عدد براءات الاختراع",
    
    # موازنة استثمارية (ربع سنوي)
    "المبلغ المنصرف من الموازنة الاستثمارية"
]

# ==============================
# المستخدمين
# ==============================
USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "institute": "الجميع"
    },
    "wmri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث إدارة المياه"
    },
    "dri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث الصرف"
    },
    "wrri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث الموارد المائية"
    },
    "nri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث النيل"
    },
    "hri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث الهيدروليكا"
    },
    "cori": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث الشواطئ"
    },
    "gwri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث المياه الجوفية"
    },
    "chri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث صيانة القنوات"
    },
    "eri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث الإنشاءات"
    },
    "mri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث الميكانيكا"
    },
    "sri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد بحوث المساحة"
    },
    "ecri": {
        "password": "1234",
        "role": "user",
        "institute": "معهد البيئة وتغير المناخ"
    }
}

# ==============================
# دوال مساعدة
# ==============================
def fix_encoding(text):
    """إصلاح مشاكل الترميز للنص العربي"""
    if isinstance(text, str):
        try:
            # محاولة إصلاح الترميز إذا كان النص مشوهاً
            return text.encode('latin1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            # إذا فشل الإصلاح، إرجاع النص كما هو
            return text
    return text

def load_data():
    """تحميل البيانات من Google Sheets بشكل آمن مع معالجة الترميز"""
    try:
        sheet = connect_to_gsheet()
        # الحصول على جميع القيم كمصفوفة
        all_values = sheet.get_all_values()
        
        if len(all_values) == 0:
            # Sheet فارغ - إرجاع DataFrame فارغ
            return pd.DataFrame()
        
        if len(all_values) == 1:
            # فقط صف العناوين موجود - إرجاع DataFrame فارغ مع الأعمدة
            columns = [fix_encoding(col) for col in all_values[0]]
            return pd.DataFrame(columns=columns)
        
        # استخراج العناوين والبيانات
        headers = [fix_encoding(col) for col in all_values[0]]
        data_rows = all_values[1:]
        
        # إنشاء DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        # إصلاح ترميز جميع القيم النصية
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(fix_encoding)
        
        return df
    
    except Exception as e:
        st.error(f"خطأ في تحميل البيانات: {str(e)}")
        return pd.DataFrame()

def safe_get(df, column, default=0):
    """الحصول على قيمة العمود بشكل آمن مع قيمة افتراضية"""
    if isinstance(df, pd.DataFrame) and not df.empty and column in df.columns:
        return df[column]
    return default

def safe_sum(df, column, default=0):
    """حساب مجموع العمود بشكل آمن"""
    if isinstance(df, pd.DataFrame) and not df.empty and column in df.columns:
        return int(pd.to_numeric(df[column], errors='coerce').fillna(0).sum())
    return default

def initialize_sheet():
    """تهيئة الـ Sheet بعناوين الأعمدة إذا كانت فارغة"""
    try:
        sheet = connect_to_gsheet()
        all_values = sheet.get_all_values()
        
        if len(all_values) == 0:
            # Sheet فارغ تماماً - إضافة صف العناوين
            sheet.append_row(COLUMNS_ORDER)
            return True
        return True
    except Exception as e:
        st.error(f"خطأ في تهيئة الـ Sheet: {str(e)}")
        return False

# ==============================
# Session State
# ==============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

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
            
            # تهيئة الـ Sheet عند تسجيل الدخول لأول مرة
            if not st.session_state.data_loaded:
                if initialize_sheet():
                    st.session_state.data_loaded = True
            
            st.rerun()
        else:
            st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")

# ==============================
# بعد تسجيل الدخول
# ==============================
else:
    # تحميل البيانات
    df = load_data()
    
    st.success(f"مرحباً {st.session_state.username} - {st.session_state.institute}")
    
    # تسجيل خروج
    col_logout = st.columns([6, 1])
    with col_logout[1]:
        if st.button("تسجيل خروج"):
            st.session_state.clear()
            st.rerun()

    # ==============================
    # صلاحيات المستخدم
    # ==============================
    if not df.empty and st.session_state.role != "admin":
        if "المعهد" in df.columns:
            df = df[df["المعهد"] == st.session_state.institute]

    # ==============================
    # Tabs
    # ==============================
    if st.session_state.role == "admin":
        tab_dashboard, tab_trend, tab_data = st.tabs([
            "📊 Dashboard",
            "📈 التغير الشهري",
            "📄 البيانات"
        ])
    else:
        tab_input, tab_dashboard, tab_trend, tab_data = st.tabs([
            "📥 إدخال البيانات",
            "📊 Dashboard",
            "📈 التغير الشهري",
            "📄 البيانات"
        ])

    # ==============================
    # Tab الإدخال (للمستخدمين فقط)
    # ==============================
    if st.session_state.role != "admin":
        with tab_input:
            st.header("إدخال البيانات الشهرية")
            
            col1, col2 = st.columns(2)
            with col1:
                month = st.selectbox("الشهر", [
                    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
                ])
            with col2:
                year = st.number_input("السنة", min_value=2020, max_value=2035, value=2026)

            st.divider()
            
            # القسم الأول: الدراسات الجارية
            st.subheader("📚 الدراسات الجارية")
            col1, col2, col3 = st.columns(3)
            with col1:
                studies_research = st.number_input("دراسات خطة بحثية جارية", min_value=0)
            with col2:
                studies_consult = st.number_input("دراسات استشارية جارية", min_value=0)
            with col3:
                projects_research = st.number_input("مشروعات بحثية جارية", min_value=0)
            
            total_studies = studies_research + studies_consult + projects_research
            st.info(f"إجمالي الدراسات الجارية: {total_studies}")
            
            st.divider()
            
            # القسم الثاني: التقارير والمذكرات
            st.subheader("📄 التقارير والمذكرات")
            col1, col2, col3 = st.columns(3)
            with col1:
                reports_progress = st.number_input("تقارير مرحلية", min_value=0)
            with col2:
                reports_final = st.number_input("تقارير نهائية", min_value=0)
            with col3:
                memos = st.number_input("مذكرات", min_value=0)
            
            st.divider()
            
            # القسم الثالث: المقترحات والمأموريات
            st.subheader("📋 المقترحات والمأموريات الحقلية")
            col1, col2, col3 = st.columns(3)
            with col1:
                proposals_consult = st.number_input("مقترحات دراسات استشارية", min_value=0)
            with col2:
                proposals_research = st.number_input("مقترحات مشروعات بحثية", min_value=0)
            with col3:
                field_days = st.number_input("أيام فعلية للمأموريات الحقلية", min_value=0)
            
            st.divider()
            
            # القسم الرابع: التدريب
            st.subheader("👥 التدريب")
            col1, col2 = st.columns(2)
            with col1:
                trainees = st.number_input("عدد المتدربين", min_value=0)
                training_days_internal = st.number_input("أيام تدريب متدربين من داخل المعهد", min_value=0)
            with col2:
                trainers = st.number_input("عدد المدربين", min_value=0)
                training_days_external = st.number_input("أيام تدريب متدربين من خارج المعهد", min_value=0)
            
            st.divider()
            
            # القسم الخامس: الأنشطة العلمية
            st.subheader("🔬 الأنشطة العلمية")
            col1, col2 = st.columns(2)
            with col1:
                conferences_attendees = st.number_input("مشتركين في مؤتمرات", min_value=0)
            with col2:
                workshops_attendees = st.number_input("مشتركين في ورش عمل", min_value=0)
            
            total_attendees = conferences_attendees + workshops_attendees
            st.info(f"إجمالي المشاركين في أنشطة علمية: {total_attendees}")
            
            st.divider()
            
            # القسم السادس: الاجتماعات
            st.subheader("🤝 الاجتماعات")
            col1, col2, col3 = st.columns(3)
            with col1:
                meetings_ministry = st.number_input("اجتماعات بالوزارة", min_value=0)
            with col2:
                meetings_center = st.number_input("اجتماعات بالمركز", min_value=0)
            with col3:
                meetings_external = st.number_input("اجتماعات جهات خارجية", min_value=0)
            
            total_meetings = meetings_ministry + meetings_center + meetings_external
            st.info(f"إجمالي الاجتماعات: {total_meetings}")
            
            st.divider()
            
            # القسم السابع: الأوراق البحثية والرسائل
            st.subheader("📝 الأوراق البحثية والرسائل العلمية")
            col1, col2, col3 = st.columns(3)
            with col1:
                papers_published = st.number_input("أوراق بحثية منشورة", min_value=0)
            with col2:
                papers_international = st.number_input("أوراق بحثية دولية منشورة", min_value=0)
            with col3:
                theses_completed = st.number_input("رسائل ماجستير ودكتوراة منتهية", min_value=0)
            
            # ==============================
            # بيانات نصف سنوية وربع سنوية (اختيارية)
            # ==============================
            st.divider()
            st.subheader("📊 بيانات دورية (اختيارية)")
            
            with st.expander("بيانات نصف سنوية"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    studies_completed = st.number_input("دراسات خطة بحثية منجزة (نصف سنوي)", min_value=0)
                with col2:
                    applied_outputs = st.number_input("مخرجات تطبيقية من دراسات ومشروعات (نصف سنوي)", min_value=0)
                with col3:
                    monitoring_system = st.number_input("نظام مراقبة Monitoring Network (نصف سنوي)", min_value=0)
                
                revenues = st.number_input("إجمالي الإيرادات الذاتية (نصف سنوي)", min_value=0.0, format="%.2f")
            
            with st.expander("بيانات ربع سنوية"):
                col1, col2 = st.columns(2)
                with col1:
                    researchers_count = st.number_input("عدد البحثيين (ربع سنوي)", min_value=0)
                    professors_count = st.number_input("عدد الأساتذة (ربع سنوي)", min_value=0)
                with col2:
                    engineers_count = st.number_input("عدد المهندسين (ربع سنوي)", min_value=0)
                    total_staff = st.number_input("إجمالي عدد العاملين (ربع سنوي)", min_value=0)
                
                investment_budget = st.number_input("المبلغ المنصرف من الموازنة الاستثمارية (ربع سنوي)", min_value=0.0, format="%.2f")
            
            with st.expander("بيانات سنوية"):
                patents_count = st.number_input("عدد براءات الاختراع (سنوي)", min_value=0)

            # ==============================
            # حفظ البيانات
            # ==============================
            st.divider()
            if st.button("💾 حفظ البيانات", type="primary"):
                
                try:
                    # تجميع البيانات
                    data_input = {
                        "المعهد": st.session_state.institute,
                        "المستخدم": st.session_state.username,
                        "الشهر": month,
                        "السنة": int(year),
                        
                        # الدراسات
                        "دراسات خطة بحثية جارية": studies_research,
                        "دراسات استشارية جارية": studies_consult,
                        "مشروعات بحثية جارية": projects_research,
                        "إجمالي الدراسات الجارية": total_studies,
                        
                        # الدراسات المنجزة
                        "دراسات خطة بحثية منجزة": studies_completed,
                        
                        # المخرجات التطبيقية
                        "مخرجات تطبيقية من دراسات ومشروعات": applied_outputs,
                        "نظام مراقبة Monitoring Network": monitoring_system,
                        
                        # التقارير والمذكرات
                        "تقارير مرحلية": reports_progress,
                        "تقارير نهائية": reports_final,
                        "مذكرات": memos,
                        
                        # المقترحات
                        "مقترحات دراسات استشارية": proposals_consult,
                        "مقترحات مشروعات بحثية": proposals_research,
                        
                        # المأموريات
                        "أيام فعلية مأموريات حقلية": field_days,
                        
                        # التدريب
                        "متدربين": trainees,
                        "مدربين": trainers,
                        "أيام تدريب متدربين داخل المعهد": training_days_internal,
                        "أيام تدريب متدربين خارج المعهد": training_days_external,
                        
                        # أنشطة علمية
                        "مشتركين مؤتمرات": conferences_attendees,
                        "مشتركين ورش عمل": workshops_attendees,
                        "إجمالي مشاركين أنشطة علمية": total_attendees,
                        
                        # الاجتماعات
                        "اجتماعات وزارة": meetings_ministry,
                        "اجتماعات مركز": meetings_center,
                        "اجتماعات خارجية": meetings_external,
                        "إجمالي اجتماعات": total_meetings,
                        
                        # أوراق بحثية
                        "أوراق بحثية منشورة": papers_published,
                        "أوراق بحثية دولية منشورة": papers_international,
                        
                        # رسائل
                        "رسائل ماجستير ودكتوراة منتهية": theses_completed,
                        
                        # إحصائيات الكادر
                        "عدد الباحثيين": researchers_count,
                        "عدد الأساتذة": professors_count,
                        "عدد المهندسين": engineers_count,
                        "إجمالي عدد العاملين": total_staff,
                        
                        # إيرادات
                        "إجمالي الإيرادات الذاتية": revenues,
                        
                        # براءات اختراع
                        "عدد براءات الاختراع": patents_count,
                        
                        # موازنة
                        "المبلغ المنصرف من الموازنة الاستثمارية": investment_budget
                    }
                    
                    # الاتصال بالـ Sheet
                    sheet = connect_to_gsheet()
                    
                    # منع التكرار - التحقق من البيانات الموجودة
                    all_values = sheet.get_all_values()
                    if len(all_values) > 1:  # يوجد بيانات سابقة
                        # الحصول على البيانات الحالية
                        headers = all_values[0]
                        data_rows = all_values[1:]
                        current_df = pd.DataFrame(data_rows, columns=headers)
                        
                        if not current_df.empty:
                            # التحقق من التكرار
                            duplicate = (
                                (current_df["المعهد"] == st.session_state.institute) &
                                (current_df["الشهر"] == month) &
                                (current_df["السنة"] == str(int(year)))
                            )
                            if duplicate.any():
                                st.error("❌ تم إدخال بيانات هذا الشهر مسبقاً")
                                st.stop()
                    
                    # تجهيز الصف الجديد
                    new_row = []
                    for col in COLUMNS_ORDER:
                        if col in data_input:
                            new_row.append(str(data_input[col]))
                        else:
                            new_row.append("0")
                    
                    # إضافة الصف
                    sheet.append_row(new_row)
                    
                    st.success("✅ تم حفظ البيانات بنجاح")
                    st.balloons()
                    
                    # إعادة تحميل البيانات
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ حدث خطأ أثناء حفظ البيانات: {str(e)}")

    # ==============================
    # تجهيز البيانات للعرض
    # ==============================
    if not df.empty:
        # تحويل الأعمدة الرقمية الموجودة
        numeric_cols = [
            "تقارير مرحلية", "تقارير نهائية", "مذكرات",
            "متدربين", "مدربين", "أيام تدريب متدربين داخل المعهد", "أيام تدريب متدربين خارج المعهد",
            "اجتماعات وزارة", "اجتماعات مركز", "اجتماعات خارجية",
            "دراسات خطة بحثية جارية", "دراسات استشارية جارية", "مشروعات بحثية جارية",
            "مقترحات دراسات استشارية", "مقترحات مشروعات بحثية",
            "أيام فعلية مأموريات حقلية",
            "مشتركين مؤتمرات", "مشتركين ورش عمل",
            "أوراق بحثية منشورة", "أوراق بحثية دولية منشورة",
            "رسائل ماجستير ودكتوراة منتهية",
            "عدد الباحثيين", "عدد الأساتذة", "عدد المهندسين", "إجمالي عدد العاملين",
            "عدد براءات الاختراع"
        ]
        
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # ==============================
    # Dashboard
    # ==============================
    with tab_dashboard:
        st.title("📊 لوحة مؤشرات الأداء")
        
        if not df.empty:
            # صف أول: مؤشرات رئيسية
            st.subheader("مؤشرات رئيسية")
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            with col1:
                total_studies = safe_sum(df, "إجمالي الدراسات الجارية")
                if total_studies == 0:
                    total_studies = safe_sum(df, "دراسات خطة بحثية جارية") + safe_sum(df, "دراسات استشارية جارية") + safe_sum(df, "مشروعات بحثية جارية")
                st.metric("📚 إجمالي الدراسات", total_studies)
            
            with col2:
                total_reports = safe_sum(df, "تقارير مرحلية") + safe_sum(df, "تقارير نهائية")
                st.metric("📄 إجمالي التقارير", total_reports)
            
            with col3:
                st.metric("👨‍🏫 المدربين", safe_sum(df, "مدربين"))
            
            with col4:
                st.metric("👨‍🎓 المتدربين", safe_sum(df, "متدربين"))
            
            with col5:
                total_meetings = safe_sum(df, "إجمالي اجتماعات")
                if total_meetings == 0:
                    total_meetings = safe_sum(df, "اجتماعات وزارة") + safe_sum(df, "اجتماعات مركز") + safe_sum(df, "اجتماعات خارجية")
                st.metric("📅 الاجتماعات", total_meetings)
            
            with col6:
                st.metric("📝 أوراق بحثية", safe_sum(df, "أوراق بحثية منشورة"))
            
            st.divider()
            
            # صف ثاني: مؤشرات إضافية
            st.subheader("مؤشرات تفصيلية")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_proposals = safe_sum(df, "مقترحات دراسات استشارية") + safe_sum(df, "مقترحات مشروعات بحثية")
                st.metric("📋 المقترحات", total_proposals)
            
            with col2:
                st.metric("🏃 المأموريات (أيام)", safe_sum(df, "أيام فعلية مأموريات حقلية"))
            
            with col3:
                total_activities = safe_sum(df, "إجمالي مشاركين أنشطة علمية")
                if total_activities == 0:
                    total_activities = safe_sum(df, "مشتركين مؤتمرات") + safe_sum(df, "مشتركين ورش عمل")
                st.metric("🔬 أنشطة علمية", total_activities)
            
            with col4:
                st.metric("🎓 رسائل علمية", safe_sum(df, "رسائل ماجستير ودكتوراة منتهية"))
            
            st.divider()
            
            # رسوم بيانية - فقط للأعمدة الموجودة
            col1, col2 = st.columns(2)
            
            with col1:
                # الدراسات الجارية
                study_cols = [col for col in ["دراسات خطة بحثية جارية", "دراسات استشارية جارية", "مشروعات بحثية جارية"] if col in df.columns]
                
                if study_cols and "المعهد" in df.columns:
                    fig_studies = px.bar(
                        df,
                        x="المعهد",
                        y=study_cols,
                        title="توزيع الدراسات الجارية حسب المعهد",
                        barmode="group"
                    )
                    st.plotly_chart(fig_studies, use_container_width=True)
                else:
                    st.info("لا توجد بيانات للدراسات الجارية")
            
            with col2:
                # التقارير
                report_cols = [col for col in ["تقارير مرحلية", "تقارير نهائية"] if col in df.columns]
                
                if report_cols and "المعهد" in df.columns:
                    fig_reports = px.bar(
                        df,
                        x="المعهد",
                        y=report_cols,
                        title="التقارير حسب المعهد",
                        barmode="stack"
                    )
                    st.plotly_chart(fig_reports, use_container_width=True)
                else:
                    st.info("لا توجد بيانات للتقارير")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # التدريب
                training_cols = [col for col in ["متدربين", "مدربين"] if col in df.columns]
                
                if training_cols and "المعهد" in df.columns:
                    fig_training = px.bar(
                        df,
                        x="المعهد",
                        y=training_cols,
                        title="التدريب حسب المعهد",
                        barmode="group"
                    )
                    st.plotly_chart(fig_training, use_container_width=True)
                else:
                    st.info("لا توجد بيانات للتدريب")
            
            with col2:
                # الاجتماعات
                meeting_cols = [col for col in ["اجتماعات وزارة", "اجتماعات مركز", "اجتماعات خارجية"] if col in df.columns]
                
                if meeting_cols and "المعهد" in df.columns:
                    fig_meetings = px.bar(
                        df,
                        x="المعهد",
                        y=meeting_cols,
                        title="الاجتماعات حسب المعهد",
                        barmode="stack"
                    )
                    st.plotly_chart(fig_meetings, use_container_width=True)
                else:
                    st.info("لا توجد بيانات للاجتماعات")
            
            # الأوراق البحثية
            paper_cols = [col for col in ["أوراق بحثية منشورة", "أوراق بحثية دولية منشورة"] if col in df.columns]
            
            if paper_cols and "المعهد" in df.columns:
                fig_papers = px.bar(
                    df,
                    x="المعهد",
                    y=paper_cols,
                    title="الأوراق البحثية حسب المعهد",
                    barmode="group"
                )
                st.plotly_chart(fig_papers, use_container_width=True)
            
        else:
            st.info("📭 لا توجد بيانات متاحة حالياً. يرجى إدخال البيانات أولاً.")

    # ==============================
    # التغير الشهري
    # ==============================
    with tab_trend:
        st.title("📈 التغير الشهري")
        
        if not df.empty and "الشهر" in df.columns and "السنة" in df.columns:
            df["شهر-سنة"] = df["الشهر"].astype(str) + " - " + df["السنة"].astype(str)
            
            # ترتيب زمني
            months_order = [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ]
            df["الشهر_مرتب"] = pd.Categorical(df["الشهر"], categories=months_order, ordered=True)
            df = df.sort_values(["السنة", "الشهر_مرتب"])
            
            # قائمة المؤشرات المتاحة
            available_metrics = [metric for metric in [
                "إجمالي الدراسات الجارية",
                "تقارير مرحلية",
                "تقارير نهائية",
                "مذكرات",
                "متدربين",
                "مدربين",
                "مشتركين مؤتمرات",
                "مشتركين ورش عمل",
                "أيام فعلية مأموريات حقلية",
                "أوراق بحثية منشورة",
                "أوراق بحثية دولية منشورة",
                "رسائل ماجستير ودكتوراة منتهية"
            ] if metric in df.columns]
            
            if available_metrics:
                metric_choice = st.selectbox("اختر المؤشر", available_metrics)
                
                if st.session_state.role == "admin" and "المعهد" in df.columns:
                    fig_trend = px.line(
                        df,
                        x="شهر-سنة",
                        y=metric_choice,
                        color="المعهد",
                        markers=True,
                        title=f"التغير الشهري - {metric_choice}"
                    )
                else:
                    fig_trend = px.line(
                        df,
                        x="شهر-سنة",
                        y=metric_choice,
                        markers=True,
                        title=f"التغير الشهري - {metric_choice} - {st.session_state.institute}"
                    )
                
                fig_trend.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_trend, use_container_width=True)
                
                # مقارنة تراكمية (للأدمن فقط)
                if st.session_state.role == "admin" and "المعهد" in df.columns:
                    st.divider()
                    st.subheader("مقارنة تراكمية بين المعاهد")
                    
                    fig_cumulative = px.area(
                        df,
                        x="شهر-سنة",
                        y=metric_choice,
                        color="المعهد",
                        title=f"المجموع التراكمي - {metric_choice}",
                        groupnorm=None
                    )
                    st.plotly_chart(fig_cumulative, use_container_width=True)
            else:
                st.info("لا توجد مؤشرات متاحة للعرض")
        else:
            st.info("📭 لا توجد بيانات متاحة للعرض")

    # ==============================
    # عرض البيانات مع التحميل
    # ==============================
    with tab_data:
        st.title("📄 البيانات")
        
        if not df.empty:
            # إضافة فلاتر
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.session_state.role == "admin" and "المعهد" in df.columns:
                    filter_institute = st.multiselect(
                        "تصفية حسب المعهد",
                        options=df["المعهد"].unique(),
                        default=df["المعهد"].unique()
                    )
                else:
                    filter_institute = [st.session_state.institute] if "المعهد" in df.columns else []
            
            with col2:
                if "السنة" in df.columns:
                    years = sorted(df["السنة"].unique())
                    filter_year = st.multiselect(
                        "تصفية حسب السنة",
                        options=years,
                        default=years
                    )
                else:
                    filter_year = []
            
            with col3:
                if "الشهر" in df.columns:
                    filter_month = st.multiselect(
                        "تصفية حسب الشهر",
                        options=df["الشهر"].unique(),
                        default=df["الشهر"].unique()
                    )
                else:
                    filter_month = []
            
            # تطبيق الفلاتر
            filtered_df = df.copy()
            if "المعهد" in filtered_df.columns and filter_institute:
                filtered_df = filtered_df[filtered_df["المعهد"].isin(filter_institute)]
            if "السنة" in filtered_df.columns and filter_year:
                filtered_df = filtered_df[filtered_df["السنة"].isin(filter_year)]
            if "الشهر" in filtered_df.columns and filter_month:
                filtered_df = filtered_df[filtered_df["الشهر"].isin(filter_month)]
            
            # عرض ملخص إحصائي
            st.subheader("ملخص إحصائي")
            numeric_filtered = filtered_df.select_dtypes(include=['float64', 'int64'])
            if not numeric_filtered.empty:
                st.dataframe(numeric_filtered.describe(), use_container_width=True)
            else:
                st.info("لا توجد بيانات رقمية للعرض الإحصائي")
            
            st.divider()
            
            # عرض البيانات الكاملة
            st.subheader("البيانات الكاملة")
            st.dataframe(filtered_df, use_container_width=True)
            
            # تحميل Excel مع ترميز UTF-8
            def to_excel(dataframe):
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    dataframe.to_excel(writer, index=False, sheet_name="KPI_Data")
                return output.getvalue()
            
            # تحميل CSV مع ترميز UTF-8
            def to_csv(dataframe):
                return dataframe.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(
                    label="📥 تحميل Excel",
                    data=to_excel(filtered_df),
                    file_name=f"kpi_data_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col2:
                st.download_button(
                    label="📥 تحميل CSV (UTF-8)",
                    data=to_csv(filtered_df),
                    file_name=f"kpi_data_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            with col3:
                st.download_button(
                    label="📥 تحميل كل البيانات Excel",
                    data=to_excel(df),
                    file_name=f"kpi_data_all_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        else:
            st.info("📭 لا توجد بيانات متاحة. يرجى إدخال البيانات أولاً.")
            
            # زر لتهيئة الـ Sheet إذا كانت المشكلة في البيانات
            if st.button("🔄 إعادة تهيئة قاعدة البيانات"):
                if initialize_sheet():
                    st.success("✅ تم تهيئة قاعدة البيانات بنجاح")
                    st.rerun()
