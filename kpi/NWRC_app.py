import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
# إعداد الصفحة
# ==============================
st.set_page_config(page_title="نظام KPI", layout="wide")

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
html, body, [class*="css"]  {
    direction: rtl;
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# المستخدمين + مدير
# ==============================
USERS = {
    "admin": {"password": "admin123", "role": "admin", "institute": "الكل"},
    "wmri": {"password": "1234", "role": "user", "institute": "معهد إدارة المياه"},
    "dri": {"password": "1234", "role": "user", "institute": "معهد الصرف"},
    "hri": {"password": "1234", "role": "user", "institute": "معهد الهيدروليكا"},
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

    st.success(f"مرحباً {st.session_state.username}")

    if st.button("تسجيل خروج"):
        st.session_state.clear()
        st.rerun()

    sheet = connect_to_gsheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # ==============================
    # صلاحيات
    # ==============================
    if st.session_state.role != "admin":
        df = df[df["المعهد"] == st.session_state.institute]

    # ==============================
    # Tabs
    # ==============================
    tab1, tab2, tab3 = st.tabs(["📥 إدخال البيانات", "📊 Dashboard", "📄 البيانات"])
    if st.session_state.role == "admin":
        page = st.sidebar.radio("اختر الصفحة", ["📊 Dashboard", "📄 البيانات"])
    else:
        page = st.sidebar.radio("اختر الصفحة", ["📥 إدخال البيانات", "📊 Dashboard", "📄 البيانات"])
    # ==============================
    # الإدخال
    # ==============================
    with tab1:

        month = st.selectbox("الشهر",
            ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
        )
        year = st.number_input("السنة", 2020, 2035, 2026)

        data_input = {}

        data_input["دراسات خطة"] = st.number_input("دراسات خطة", 0)
        data_input["دراسات استشارية"] = st.number_input("استشارية", 0)
        data_input["تمويل ذاتي"] = st.number_input("تمويل ذاتي", 0)

        data_input["تقارير مرحلية"] = st.number_input("تقارير مرحلية", 0)
        data_input["تقارير نهائية"] = st.number_input("تقارير نهائية", 0)

        data_input["متدربين"] = st.number_input("متدربين", 0)
        data_input["مدربين"] = st.number_input("مدربين", 0)

        data_input["اجتماعات وزارة"] = st.number_input("وزارة", 0)
        data_input["اجتماعات مركز"] = st.number_input("مركز", 0)
        data_input["اجتماعات خارجية"] = st.number_input("خارجية", 0)

        if st.button("💾 حفظ"):

            new_row = pd.DataFrame([data_input])
            new_row["المعهد"] = st.session_state.institute
            new_row["المستخدم"] = st.session_state.username
            new_row["الشهر"] = month
            new_row["السنة"] = year

            # ❌ منع التكرار
            existing = sheet.get_all_records()
            df_exist = pd.DataFrame(existing)

            if not df_exist.empty:
                cond = (
                    (df_exist["المعهد"] == st.session_state.institute) &
                    (df_exist["الشهر"] == month) &
                    (df_exist["السنة"] == year)
                )
                if cond.any():
                    st.error("❌ تم إدخال هذا الشهر مسبقاً")
                    st.stop()

            # إنشاء الأعمدة أول مرة
            if len(sheet.get_all_values()) == 0:
                sheet.append_row(new_row.columns.tolist())

            sheet.append_row(new_row.iloc[0].astype(str).tolist())

            st.success("✅ تم الحفظ")

    # ==============================
    # Dashboard
    # ==============================
    with tab2:

        st.title("📊 Dashboard")

    if not df.empty:
    
        # تحويل القيم لأرقام
        cols = ["تقارير مرحلية","تقارير نهائية","متدربين","مدربين",
                "اجتماعات وزارة","اجتماعات مركز","اجتماعات خارجية"]
    
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    
        # حساب الإجماليات
        df["إجمالي التقارير"] = df["تقارير مرحلية"] + df["تقارير نهائية"]
        df["إجمالي الاجتماعات"] = df["اجتماعات وزارة"] + df["اجتماعات مركز"] + df["اجتماعات خارجية"]
    
        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
    
        col1.metric("📄 التقارير", int(df["إجمالي التقارير"].sum()))
        col2.metric("👨‍🏫 المدربين", int(df["مدربين"].sum()))
        col3.metric("👨‍🎓 المتدربين", int(df["متدربين"].sum()))
        col4.metric("📅 الاجتماعات", int(df["إجمالي الاجتماعات"].sum()))
    
        st.divider()
    
        # الرسوم
        import plotly.express as px
    
        fig1 = px.bar(df, x="المعهد", y="إجمالي التقارير", color="المعهد", title="التقارير")
        st.plotly_chart(fig1, use_container_width=True)
    
        fig2 = px.bar(df, x="المعهد", y="متدربين", color="المعهد", title="التدريب")
        st.plotly_chart(fig2, use_container_width=True)
    
        fig3 = px.bar(df, x="المعهد", y="إجمالي الاجتماعات", color="المعهد", title="الاجتماعات")
        st.plotly_chart(fig3, use_container_width=True)
    
    else:
        st.info("لا توجد بيانات")

    # ==============================
    # عرض البيانات + تحميل
    # ==============================
    with tab3:

        st.dataframe(df)

        # تحميل Excel
        def convert_excel(df):
            return df.to_csv(index=False).encode('utf-8')

        st.download_button(
            "📥 تحميل Excel",
            convert_excel(df),
            "kpi_data.csv",
            "text/csv"
        )
