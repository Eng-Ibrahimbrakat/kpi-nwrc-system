import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# ==============================
# إعداد الصفحة
# ==============================
st.set_page_config(
    page_title="نظام مؤشرات الأداء - المركز القومي لبحوث المياه",
    layout="wide"
)
columns_order = [
    "تقارير مرحلية",
    "تقارير نهائية",
    "متدربين",
    "مدربين",
    "اجتماعات وزارة",
    "اجتماعات مركز",
    "اجتماعات خارجية",
    "المعهد",
    "المستخدم",
    "الشهر",
    "السنة"
]
sheet.append_row(new_row.iloc[0].tolist())

new_row = new_row[columns_order]
# ==============================
# الشعار
# ==============================
current_dir = os.path.dirname(__file__)
logo_path = os.path.join(current_dir, "logo.png")

if os.path.exists(logo_path):
    st.image(logo_path, width=150)

# ==============================
# RTL عربي
# ==============================
st.markdown("""
<style>
html, body {
    direction: rtl;
    text-align: right;
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
        st.secrets["gcp_service_account"], scope
    )

    client = gspread.authorize(credentials)
    sheet = client.open_by_key("1QSfmNo9U0TNvdwRgLhLBgVNZbiL8wVcoWlffBz6cSfg").sheet1

    return sheet

# ==============================
# المستخدمين (كل المعاهد)
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
            st.error("❌ بيانات غير صحيحة")

# ==============================
# بعد تسجيل الدخول
# ==============================
else:

    st.success(f"مرحباً {st.session_state.username} - {st.session_state.institute}")

    if st.button("تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    sheet = connect_to_gsheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # ==============================
    # صلاحيات
    # ==============================
    if not df.empty and st.session_state.role != "admin":
        df = df[df["المعهد"] == st.session_state.institute]

    # ==============================
    # Tabs
    # ==============================
    if st.session_state.role == "admin":
        tab_dashboard, tab_data = st.tabs(["📊 Dashboard", "📄 البيانات"])
    else:
        tab_input, tab_dashboard, tab_data = st.tabs(
            ["📥 إدخال البيانات", "📊 Dashboard", "📄 البيانات"]
        )

    # ==============================
    # الإدخال (فقط user)
    # ==============================
    if st.session_state.role != "admin":
        with tab_input:

            month = st.selectbox("الشهر",
                ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
            )

            year = st.number_input("السنة", 2020, 2035, 2026)

            data_input = {
                "تقارير مرحلية": st.number_input("تقارير مرحلية", 0),
                "تقارير نهائية": st.number_input("تقارير نهائية", 0),
                "متدربين": st.number_input("متدربين", 0),
                "مدربين": st.number_input("مدربين", 0),
                "اجتماعات وزارة": st.number_input("اجتماعات وزارة", 0),
                "اجتماعات مركز": st.number_input("اجتماعات مركز", 0),
                "اجتماعات خارجية": st.number_input("اجتماعات خارجية", 0),
            }

            if st.button("💾 حفظ"):

                new_row = pd.DataFrame([data_input])
                new_row["المعهد"] = st.session_state.institute
                new_row["المستخدم"] = st.session_state.username
                new_row["الشهر"] = month
                new_row["السنة"] = year

                # منع التكرار
                if not df.empty:
                    cond = (
                        (df["المعهد"] == st.session_state.institute) &
                        (df["الشهر"] == month) &
                        (df["السنة"] == year)
                    )
                    if cond.any():
                        st.error("❌ تم إدخال هذا الشهر مسبقاً")
                        st.stop()

                # أول مرة
                if len(sheet.get_all_values()) == 0:
                    sheet.append_row(new_row.columns.tolist())

                sheet.append_row(new_row.iloc[0].astype(str).tolist())

                st.success("✅ تم الحفظ")

    # ==============================
    # Dashboard
    # ==============================
    with tab_dashboard:

        st.title("📊 Dashboard")

        if not df.empty:

            cols = ["تقارير مرحلية","تقارير نهائية","متدربين","مدربين",
                    "اجتماعات وزارة","اجتماعات مركز","اجتماعات خارجية"]

            for c in cols:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            df["إجمالي التقارير"] = df["تقارير مرحلية"] + df["تقارير نهائية"]
            df["إجمالي الاجتماعات"] = df["اجتماعات وزارة"] + df["اجتماعات مركز"] + df["اجتماعات خارجية"]

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("📄 التقارير", int(df["إجمالي التقارير"].sum()))
            col2.metric("👨‍🏫 المدربين", int(df["مدربين"].sum()))
            col3.metric("👨‍🎓 المتدربين", int(df["متدربين"].sum()))
            col4.metric("📅 الاجتماعات", int(df["إجمالي الاجتماعات"].sum()))

            st.divider()

            fig = px.bar(df, x="المعهد", y="إجمالي التقارير", color="المعهد")
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("لا توجد بيانات")

    # ==============================
    # عرض + تحميل
    # ==============================
    with tab_data:
         
        from io import BytesIO
    
        def to_excel(df):
            output = BytesIO()
            df.to_excel(output, index=False)
            return output.getvalue()
    
        st.download_button(
            "📥 تحميل Excel",
            to_excel(df),
            "kpi_data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
