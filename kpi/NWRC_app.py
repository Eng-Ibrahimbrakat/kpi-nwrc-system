import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==============================
# Google Sheets
# ==============================
def connect_to_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )

    client = gspread.authorize(credentials)
    sheet = client.open_by_key("1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg").sheet1
    return sheet

# ==============================
# إعداد الصفحة
# ==============================
st.set_page_config(page_title="KPI System", layout="wide")

# ==============================
# Logo
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
html, body, [class*="css"]  {
    direction: rtl;
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# Users
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
    "mri": {"password": "1234", "role": "user", "institute": "معهد بحوث الميكانيكا والكهرباء"},
    "sri": {"password": "1234", "role": "user", "institute": "معهد بحوث المساحة"},
    "ecri": {"password": "1234", "role": "user", "institute": "معهد بحوث البيئة وتغير المناخ"},
}

# ==============================
# Session
# ==============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ==============================
# Login
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
            st.error("❌ بيانات غير صحيحة")

# ==============================
# App
# ==============================
else:

    st.success(f"مرحباً {st.session_state.username}")

    if st.button("تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    sheet = connect_to_gsheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    if not df.empty:
        numeric_cols = [
            "تقارير مرحلية","تقارير نهائية","متدربين","مدربين",
            "اجتماعات وزارة","اجتماعات مركز","اجتماعات خارجية"
        ]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df["إجمالي التقارير"] = df["تقارير مرحلية"] + df["تقارير نهائية"]
        df["إجمالي الاجتماعات"] = df["اجتماعات وزارة"] + df["اجتماعات مركز"] + df["اجتماعات خارجية"]

    # صلاحيات
    if st.session_state.role != "admin":
        df = df[df["المعهد"] == st.session_state.institute]

    # Tabs
    if st.session_state.role == "admin":
        tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📈 التغير الشهري", "📄 البيانات"])
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📥 إدخال", "📊 Dashboard", "📈 التغير الشهري", "📄 البيانات"])

    # =========================
    # الإدخال
    # =========================
    if st.session_state.role != "admin":
        with tab1:

            month = st.selectbox("الشهر",
                ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
            )

            year = st.number_input("السنة", 2020, 2035, 2026)

            data_input = {
                "دراسات خطة": st.number_input("دراسات خطة", 0),
                "دراسات استشارية": st.number_input("استشارية", 0),
                "تمويل ذاتي": st.number_input("تمويل ذاتي", 0),
                "تقارير مرحلية": st.number_input("تقارير مرحلية", 0),
                "تقارير نهائية": st.number_input("تقارير نهائية", 0),
                "متدربين": st.number_input("متدربين", 0),
                "مدربين": st.number_input("مدربين", 0),
                "اجتماعات وزارة": st.number_input("وزارة", 0),
                "اجتماعات مركز": st.number_input("مركز", 0),
                "اجتماعات خارجية": st.number_input("خارجية", 0),
            }

            if st.button("💾 حفظ"):

                # منع التكرار
                if not df.empty:
                    cond = (
                        (df["المعهد"] == st.session_state.institute) &
                        (df["الشهر"] == month) &
                        (df["السنة"] == int(year))
                    )
            
                    if cond.any():
                        st.error("❌ تم الإدخال مسبقاً")
                        st.stop()
            
                # ترتيب الأعمدة الثابت
                columns_order = [
                    "المعهد",
                    "المستخدم",
                    "الشهر",
                    "السنة",
                    "دراسات خطة",
                    "دراسات استشارية",
                    "تمويل ذاتي",
                    "تقارير مرحلية",
                    "تقارير نهائية",
                    "متدربين",
                    "مدربين",
                    "اجتماعات وزارة",
                    "اجتماعات مركز",
                    "اجتماعات خارجية"
                ]
            
                # بيانات الصف
                row_data = [
                    st.session_state.institute,
                    st.session_state.username,
                    month,
                    int(year),
                    data_input["دراسات خطة"],
                    data_input["دراسات استشارية"],
                    data_input["تمويل ذاتي"],
                    data_input["تقارير مرحلية"],
                    data_input["تقارير نهائية"],
                    data_input["متدربين"],
                    data_input["مدربين"],
                    data_input["اجتماعات وزارة"],
                    data_input["اجتماعات مركز"],
                    data_input["اجتماعات خارجية"]
                ]
            
                try:
            
                    # إنشاء الهيدر إذا الملف فارغ
                    if len(sheet.get_all_values()) == 0:
                        sheet.append_row(columns_order)
            
                    # إضافة صف جديد
                    sheet.append_row(
                        row_data,
                        value_input_option="USER_ENTERED"
                    )
            
                    st.success("✅ تم الحفظ بنجاح")
            
                except Exception as e:
                    st.error(f"حدث خطأ: {e}")
    # =========================
    # Dashboard
    # =========================
    with tab2:

        st.title("📊 Dashboard")

        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("التقارير", int(df["إجمالي التقارير"].sum()))
            col2.metric("المدربين", int(df["مدربين"].sum()))
            col3.metric("المتدربين", int(df["متدربين"].sum()))
            col4.metric("الاجتماعات", int(df["إجمالي الاجتماعات"].sum()))

    # =========================
    # التغير الشهري
    # =========================
    with tab3:

        st.title("📈 التغير الشهري")
        # ==============================
        # ترتيب الشهور عربي
        # ==============================
        
        month_order = {
            "يناير": 1,
            "فبراير": 2,
            "مارس": 3,
            "أبريل": 4,
            "مايو": 5,
            "يونيو": 6,
            "يوليو": 7,
            "أغسطس": 8,
            "سبتمبر": 9,
            "أكتوبر": 10,
            "نوفمبر": 11,
            "ديسمبر": 12
        }
        
        # إنشاء عمود ترتيب
        df["ترتيب_الشهر"] = df["الشهر"].map(month_order)
        
        # ترتيب البيانات
        df = df.sort_values(
            by=["السنة", "ترتيب_الشهر"]
        )
        
        # إنشاء اسم للشهر + السنة
        df["شهر_سنة"] = df["الشهر"] + " - " + df["السنة"].astype(str)    
        if not df.empty:

            import plotly.express as px
            # تحويل القيم الرقمية
            numeric_cols = [
                "إجمالي التقارير",
                "إجمالي الاجتماعات",
                "متدربين",
                "مدربين"
            ]
            
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            
            # إنشاء ترتيب الشهر
            df["ترتيب_الشهر"] = df["الشهر"].map(month_order)
            
            # تجميع البيانات
            df_group = df.groupby(
                ["السنة", "ترتيب_الشهر", "الشهر", "المعهد"]
            ).sum(numeric_only=True).reset_index()
            
            # ترتيب البيانات
            df_group = df_group.sort_values(
                by=["السنة", "ترتيب_الشهر"]
            )
            
            # ==============================
            # رسم التقارير
            # ==============================
            
            fig1 = px.line(
                df,
                x="شهر_سنة",
                y="إجمالي التقارير",
                color="المعهد",
                markers=True,
                title="التغير الشهري للتقارير"
            )
            
            st.plotly_chart(fig1, use_container_width=True)
            
            # ==============================
            # رسم الاجتماعات
            # ==============================
            
            fig2 = px.line(
                df,
                x="شهر_سنة",
                y="إجمالي الاجتماعات",
                color="المعهد",
                markers=True,
                title="التغير الشهري للاجتماعات"
            )
            
            st.plotly_chart(fig2, use_container_width=True)
            
            # ==============================
            # رسم المتدربين
            # ==============================
            
            fig3 = px.line(
                df,
                x="شهر_سنة",
                y="متدربين",
                color="المعهد",
                markers=True,
                title="التغير الشهري للمتدربين"
            )
            
            st.plotly_chart(fig3, use_container_width=True)
            
            # ==============================
            # رسم المدربين
            # ==============================
            
            fig4 = px.line(
                df,
                x="شهر_سنة",
                y="مدربين",
                color="المعهد",
                markers=True,
                title="التغير الشهري للمدربين"
            )
            
            st.plotly_chart(fig4, use_container_width=True)
          
    # =========================
    # البيانات
    # =========================
    with tab4:

        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8-sig')

        st.download_button(
            "📥 تحميل Excel",
            csv,
            "kpi_data.csv",
            "text/csv"
        )
