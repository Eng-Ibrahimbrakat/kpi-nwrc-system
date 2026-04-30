import streamlit as st
import pandas as pd
import os
import gspread
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from oauth2client.service_account import ServiceAccountCredentials

# =============================
# إعداد الصفحة
# =============================
st.set_page_config(page_title="KPI System", layout="wide")

# =============================
# CSS احترافي
# =============================
st.markdown("""
<style>
body {background-color: #f5f7fa;}
.block-container {padding-top: 2rem;}
h1, h2, h3 {color: #0B5394;}
</style>
""", unsafe_allow_html=True)

# =============================
# الاتصال بـ Google Sheets
# =============================
def connect_to_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(credentials)
    return client.open_by_key("YOUR_SHEET_ID").sheet1

# =============================
# المستخدمين (صلاحيات)
# =============================
USERS = {
    "admin": {"password": "admin123", "role": "admin", "institute": "ALL"},
    "wmri": {"password": "1234", "role": "editor", "institute": "إدارة المياه"},
    "dri": {"password": "1234", "role": "editor", "institute": "الصرف"},
    "viewer": {"password": "1234", "role": "viewer", "institute": "ALL"}
}

# =============================
# Session
# =============================
if "login" not in st.session_state:
    st.session_state.login = False

# =============================
# Login Page
# =============================
if not st.session_state.login:

    st.title("🔐 تسجيل الدخول")

    user = st.text_input("اسم المستخدم")
    pw = st.text_input("كلمة المرور", type="password")

    if st.button("دخول"):
        if user in USERS and USERS[user]["password"] == pw:
            st.session_state.login = True
            st.session_state.user = user
            st.session_state.role = USERS[user]["role"]
            st.session_state.inst = USERS[user]["institute"]
            st.rerun()
        else:
            st.error("بيانات خاطئة")

# =============================
# Main App
# =============================
else:

    st.sidebar.title("📊 النظام")
    page = st.sidebar.radio("اختر الصفحة", ["Dashboard", "إدخال", "البيانات", "التقارير"])

    if st.sidebar.button("تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    sheet = connect_to_gsheet()
    df = pd.DataFrame(sheet.get_all_records())

    # صلاحيات
    if st.session_state.role != "admin":
        df = df[df["المعهد"] == st.session_state.inst]

    # =============================
    # Dashboard
    # =============================
    if page == "Dashboard":

        st.title("📊 Dashboard احترافي")

        if not df.empty:
            df["إجمالي"] = df[["دراسات خطة","دراسات استشارية","تمويل ذاتي"]].astype(int).sum(axis=1)

            fig = px.bar(df, x="المعهد", y="إجمالي", color="المعهد", title="إجمالي الدراسات")
            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.line(df, x="الشهر", y="متدربين", color="المعهد", title="التدريب")
            st.plotly_chart(fig2, use_container_width=True)

        else:
            st.info("لا يوجد بيانات")

    # =============================
    # إدخال البيانات
    # =============================
    elif page == "إدخال":

        if st.session_state.role == "viewer":
            st.warning("ليس لديك صلاحية إدخال")
            st.stop()

        st.title("📥 إدخال البيانات")

        month = st.selectbox("الشهر", ["يناير","فبراير","مارس","أبريل"])
        year = st.number_input("السنة", 2020, 2035, 2026)

        data = {
            "دراسات خطة": st.number_input("دراسات خطة", 0),
            "دراسات استشارية": st.number_input("استشارية", 0),
            "تمويل ذاتي": st.number_input("تمويل", 0),
            "متدربين": st.number_input("متدربين", 0),
        }

        uploaded_file = st.file_uploader("📎 رفع ملف")

        if st.button("حفظ"):
            new = pd.DataFrame([data])
            new["المعهد"] = st.session_state.inst
            new["الشهر"] = month
            new["السنة"] = year

            # منع التكرار
            if not df.empty:
                if ((df["المعهد"] == new["المعهد"][0]) &
                    (df["الشهر"] == month) &
                    (df["السنة"] == year)).any():
                    st.error("تم الإدخال مسبقاً")
                    st.stop()

            if len(sheet.get_all_values()) == 0:
                sheet.append_row(new.columns.tolist())

            sheet.append_row(new.iloc[0].astype(str).tolist())

            # حفظ الملف
            if uploaded_file:
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())

            st.success("تم الحفظ")

    # =============================
    # عرض البيانات
    # =============================
    elif page == "البيانات":

        st.title("📄 البيانات")
        st.dataframe(df)

        st.download_button(
            "تحميل CSV",
            df.to_csv(index=False),
            "data.csv"
        )

    # =============================
    # تصدير PDF
    # =============================
    elif page == "التقارير":

        st.title("📑 تصدير تقرير PDF")

        if st.button("إنشاء PDF"):

            file_path = "report.pdf"
            doc = SimpleDocTemplate(file_path)
            styles = getSampleStyleSheet()

            content = []
            content.append(Paragraph("تقرير KPI", styles["Title"]))

            for col in df.columns:
                content.append(Paragraph(col, styles["Normal"]))

            doc.build(content)

            with open(file_path, "rb") as f:
                st.download_button("تحميل التقرير", f, "report.pdf")
