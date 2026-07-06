import streamlit as st
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
def connect_to_gsheet():
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
    "عدد البحثيين",
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

# ==============================
# بعد تسجيل الدخول
# ==============================
else:
    st.success(f"مرحباً {st.session_state.username} - {st.session_state.institute}")
    
    # تسجيل خروج
    col_logout = st.columns([6, 1])
    with col_logout[1]:
        if st.button("تسجيل خروج"):
            st.session_state.clear()
            st.rerun()

    # ==============================
    # قراءة البيانات
    # ==============================
    sheet = connect_to_gsheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # ==============================
    # صلاحيات المستخدم
    # ==============================
    if not df.empty and st.session_state.role != "admin":
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
            
            # إجمالي تلقائي
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
                    "عدد البحثيين": researchers_count,
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
                
                new_row = pd.DataFrame([data_input])
                
                # ترتيب الأعمدة حسب القائمة المحددة
                existing_cols = [col for col in COLUMNS_ORDER if col in new_row.columns]
                new_row = new_row[existing_cols]
                
                # منع التكرار
                if not df.empty:
                    cond = (
                        (df["المعهد"] == st.session_state.institute) &
                        (df["الشهر"] == month) &
                        (pd.to_numeric(df["السنة"], errors="coerce").fillna(0).astype(int) == int(year))
                    )
                    if cond.any():
                        st.error("❌ تم إدخال بيانات هذا الشهر مسبقاً")
                        st.stop()
                
                # إنشاء Header إذا كانت الـ Sheet فارغة
                if len(sheet.get_all_values()) == 0:
                    sheet.append_row(existing_cols)
                
                # تحويل القيم لنصوص ورفعها
                row_values = [str(v) for v in new_row.iloc[0].tolist()]
                sheet.append_row(row_values)
                
                st.success("✅ تم حفظ البيانات بنجاح")
                st.rerun()

    # ==============================
    # تجهيز البيانات للعرض
    # ==============================
    if not df.empty:
        # تحويل الأعمدة الرقمية
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
            "عدد البحثيين", "عدد الأساتذة", "عدد المهندسين", "إجمالي عدد العاملين",
            "عدد براءات الاختراع"
        ]
        
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        
        # حساب الإجماليات
        if "إجمالي الدراسات الجارية" not in df.columns:
            df["إجمالي الدراسات الجارية"] = (
                df.get("دراسات خطة بحثية جارية", 0) + 
                df.get("دراسات استشارية جارية", 0) + 
                df.get("مشروعات بحثية جارية", 0)
            )
        
        if "إجمالي مشاركين أنشطة علمية" not in df.columns:
            df["إجمالي مشاركين أنشطة علمية"] = (
                df.get("مشتركين مؤتمرات", 0) + 
                df.get("مشتركين ورش عمل", 0)
            )

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
                st.metric("📚 إجمالي الدراسات", int(df["إجمالي الدراسات الجارية"].sum()))
            with col2:
                total_reports = int(df["تقارير مرحلية"].sum() + df["تقارير نهائية"].sum())
                st.metric("📄 إجمالي التقارير", total_reports)
            with col3:
                st.metric("👨‍🏫 المدربين", int(df["مدربين"].sum()))
            with col4:
                st.metric("👨‍🎓 المتدربين", int(df["متدربين"].sum()))
            with col5:
                total_meetings = int(df.get("إجمالي اجتماعات", 
                    df["اجتماعات وزارة"] + df["اجتماعات مركز"] + df["اجتماعات خارجية"]).sum())
                st.metric("📅 الاجتماعات", total_meetings)
            with col6:
                st.metric("📝 أوراق بحثية", int(df["أوراق بحثية منشورة"].sum()))
            
            st.divider()
            
            # صف ثاني: مؤشرات إضافية
            st.subheader("مؤشرات تفصيلية")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📋 المقترحات", int(df["مقترحات دراسات استشارية"].sum() + df["مقترحات مشروعات بحثية"].sum()))
            with col2:
                st.metric("🏃 المأموريات (أيام)", int(df["أيام فعلية مأموريات حقلية"].sum()))
            with col3:
                st.metric("🔬 أنشطة علمية", int(df["إجمالي مشاركين أنشطة علمية"].sum()))
            with col4:
                st.metric("🎓 رسائل علمية", int(df["رسائل ماجستير ودكتوراة منتهية"].sum()))
            
            st.divider()
            
            # رسوم بيانية
            col1, col2 = st.columns(2)
            
            with col1:
                # رسم بياني للدراسات الجارية
                fig_studies = px.bar(
                    df,
                    x="المعهد",
                    y=["دراسات خطة بحثية جارية", "دراسات استشارية جارية", "مشروعات بحثية جارية"],
                    title="توزيع الدراسات الجارية حسب المعهد",
                    barmode="group"
                )
                st.plotly_chart(fig_studies, use_container_width=True)
            
            with col2:
                # رسم بياني للتقارير
                fig_reports = px.bar(
                    df,
                    x="المعهد",
                    y=["تقارير مرحلية", "تقارير نهائية"],
                    title="التقارير حسب المعهد",
                    barmode="stack"
                )
                st.plotly_chart(fig_reports, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # رسم بياني للتدريب
                fig_training = px.bar(
                    df,
                    x="المعهد",
                    y=["متدربين", "مدربين"],
                    title="التدريب حسب المعهد",
                    barmode="group"
                )
                st.plotly_chart(fig_training, use_container_width=True)
            
            with col2:
                # رسم بياني للاجتماعات
                fig_meetings = px.bar(
                    df,
                    x="المعهد",
                    y=["اجتماعات وزارة", "اجتماعات مركز", "اجتماعات خارجية"],
                    title="الاجتماعات حسب المعهد",
                    barmode="stack"
                )
                st.plotly_chart(fig_meetings, use_container_width=True)
            
            # رسم بياني للأوراق البحثية
            fig_papers = px.bar(
                df,
                x="المعهد",
                y=["أوراق بحثية منشورة", "أوراق بحثية دولية منشورة"],
                title="الأوراق البحثية حسب المعهد",
                barmode="group"
            )
            st.plotly_chart(fig_papers, use_container_width=True)
            
        else:
            st.info("لا توجد بيانات متاحة")

    # ==============================
    # التغير الشهري
    # ==============================
    with tab_trend:
        st.title("📈 التغير الشهري")
        
        if not df.empty:
            df["شهر-سنة"] = df["الشهر"].astype(str) + " - " + df["السنة"].astype(str)
            
            # ترتيب زمني
            months_order = [
                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
            ]
            df["الشهر_مرتب"] = pd.Categorical(df["الشهر"], categories=months_order, ordered=True)
            df = df.sort_values(["السنة", "الشهر_مرتب"])
            
            metric_choice = st.selectbox(
                "اختر المؤشر",
                [
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
                ]
            )
            
            if st.session_state.role == "admin":
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
            
            # مقارنة بين المعاهد (للأدمن فقط)
            if st.session_state.role == "admin":
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
            st.info("لا توجد بيانات متاحة")

    # ==============================
    # عرض البيانات مع التحميل
    # ==============================
    with tab_data:
        st.title("📄 البيانات")
        
        if not df.empty:
            # إضافة فلاتر
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.session_state.role == "admin":
                    filter_institute = st.multiselect(
                        "تصفية حسب المعهد",
                        options=df["المعهد"].unique(),
                        default=df["المعهد"].unique()
                    )
                else:
                    filter_institute = [st.session_state.institute]
            
            with col2:
                filter_year = st.multiselect(
                    "تصفية حسب السنة",
                    options=sorted(df["السنة"].unique()),
                    default=sorted(df["السنة"].unique())
                )
            
            with col3:
                filter_month = st.multiselect(
                    "تصفية حسب الشهر",
                    options=df["الشهر"].unique(),
                    default=df["الشهر"].unique()
                )
            
            # تطبيق الفلاتر
            filtered_df = df[
                (df["المعهد"].isin(filter_institute)) &
                (df["السنة"].isin(filter_year)) &
                (df["الشهر"].isin(filter_month))
            ]
            
            # عرض ملخص إحصائي
            st.subheader("ملخص إحصائي")
            st.dataframe(filtered_df.describe(), use_container_width=True)
            
            st.divider()
            
            # عرض البيانات الكاملة
            st.subheader("البيانات الكاملة")
            st.dataframe(filtered_df, use_container_width=True)
            
            # تحميل Excel
            def to_excel(dataframe):
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    dataframe.to_excel(writer, index=False, sheet_name="KPI_Data")
                return output.getvalue()
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 تحميل البيانات المصفاة (Excel)",
                    data=to_excel(filtered_df),
                    file_name=f"kpi_data_filtered_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col2:
                st.download_button(
                    label="📥 تحميل كل البيانات (Excel)",
                    data=to_excel(df),
                    file_name=f"kpi_data_all_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
        else:
            st.info("لا توجد بيانات متاحة")
