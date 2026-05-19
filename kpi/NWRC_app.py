import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from io import BytesIO

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
# ترتيب الأعمدة
# ==============================
COLUMNS_ORDER = [
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

    st.success(
        f"مرحباً {st.session_state.username} - "
        f"{st.session_state.institute}"
    )

    # تسجيل خروج
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

        df = df[
            df["المعهد"] == st.session_state.institute
        ]

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
    # Tab الإدخال
    # ==============================
    if st.session_state.role != "admin":

        with tab_input:

            month = st.selectbox(
                "الشهر",
                [
                    "يناير",
                    "فبراير",
                    "مارس",
                    "أبريل",
                    "مايو",
                    "يونيو",
                    "يوليو",
                    "أغسطس",
                    "سبتمبر",
                    "أكتوبر",
                    "نوفمبر",
                    "ديسمبر"
                ]
            )

            year = st.number_input(
                "السنة",
                min_value=2020,
                max_value=2035,
                value=2026
            )

            st.divider()

            data_input = {

                "تقارير مرحلية":
                    st.number_input("تقارير مرحلية", min_value=0),

                "تقارير نهائية":
                    st.number_input("تقارير نهائية", min_value=0),

                "متدربين":
                    st.number_input("متدربين", min_value=0),

                "مدربين":
                    st.number_input("مدربين", min_value=0),

                "اجتماعات وزارة":
                    st.number_input("اجتماعات وزارة", min_value=0),

                "اجتماعات مركز":
                    st.number_input("اجتماعات مركز", min_value=0),

                "اجتماعات خارجية":
                    st.number_input("اجتماعات خارجية", min_value=0)
            }

            # ==============================
            # حفظ البيانات
            # ==============================
            if st.button("💾 حفظ البيانات"):

                new_row = pd.DataFrame([data_input])

                new_row["المعهد"] = st.session_state.institute
                new_row["المستخدم"] = st.session_state.username
                new_row["الشهر"] = month
                new_row["السنة"] = int(year)

                # ترتيب الأعمدة
                new_row = new_row[COLUMNS_ORDER]

                # ==============================
                # منع التكرار
                # ==============================
                if not df.empty:

                    cond = (
                        (df["المعهد"] == st.session_state.institute)
                        &
                        (df["الشهر"] == month)
                        &
                        (
                            pd.to_numeric(
                                df["السنة"],
                                errors="coerce"
                            ).fillna(0).astype(int)
                            ==
                            int(year)
                        )
                    )

                    if cond.any():

                        st.error(
                            "❌ تم إدخال بيانات هذا الشهر مسبقاً"
                        )

                        st.stop()

                # ==============================
                # إنشاء Header أول مرة
                # ==============================
                if len(sheet.get_all_values()) == 0:

                    sheet.append_row(COLUMNS_ORDER)

                # ==============================
                # تحويل القيم لنصوص
                # ==============================
                row_values = [
                    str(v) for v in new_row.iloc[0].tolist()
                ]

                # ==============================
                # رفع البيانات
                # ==============================
                sheet.append_row(row_values)

                st.success("✅ تم حفظ البيانات بنجاح")

    # ==============================
    # تجهيز البيانات
    # ==============================
    if not df.empty:

        numeric_cols = [
            "تقارير مرحلية",
            "تقارير نهائية",
            "متدربين",
            "مدربين",
            "اجتماعات وزارة",
            "اجتماعات مركز",
            "اجتماعات خارجية"
        ]

        for c in numeric_cols:

            df[c] = pd.to_numeric(
                df[c],
                errors="coerce"
            ).fillna(0)

        df["إجمالي التقارير"] = (
            df["تقارير مرحلية"]
            +
            df["تقارير نهائية"]
        )

        df["إجمالي الاجتماعات"] = (
            df["اجتماعات وزارة"]
            +
            df["اجتماعات مركز"]
            +
            df["اجتماعات خارجية"]
        )

    # ==============================
    # Dashboard
    # ==============================
    with tab_dashboard:

        st.title("📊 Dashboard")

        if not df.empty:

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "📄 التقارير",
                int(df["إجمالي التقارير"].sum())
            )

            col2.metric(
                "👨‍🏫 المدربين",
                int(df["مدربين"].sum())
            )

            col3.metric(
                "👨‍🎓 المتدربين",
                int(df["متدربين"].sum())
            )

            col4.metric(
                "📅 الاجتماعات",
                int(df["إجمالي الاجتماعات"].sum())
            )

            st.divider()

            fig1 = px.bar(
                df,
                x="المعهد",
                y="إجمالي التقارير",
                color="المعهد",
                title="إجمالي التقارير"
            )

            st.plotly_chart(
                fig1,
                use_container_width=True
            )

            fig2 = px.bar(
                df,
                x="المعهد",
                y="متدربين",
                color="المعهد",
                title="المتدربين"
            )

            st.plotly_chart(
                fig2,
                use_container_width=True
            )

            fig3 = px.bar(
                df,
                x="المعهد",
                y="إجمالي الاجتماعات",
                color="المعهد",
                title="الاجتماعات"
            )

            st.plotly_chart(
                fig3,
                use_container_width=True
            )

        else:

            st.info("لا توجد بيانات")

    # ==============================
    # التغير الشهري
    # ==============================
    with tab_trend:

        st.title("📈 التغير الشهري")

        if not df.empty:

            df["شهر-سنة"] = (
                df["الشهر"].astype(str)
                +
                " - "
                +
                df["السنة"].astype(str)
            )

            metric_choice = st.selectbox(
                "اختر المؤشر",
                [
                    "إجمالي التقارير",
                    "إجمالي الاجتماعات",
                    "متدربين",
                    "مدربين"
                ]
            )

            fig_trend = px.line(
                df,
                x="شهر-سنة",
                y=metric_choice,
                color="المعهد",
                markers=True,
                title=f"التغير الشهري - {metric_choice}"
            )

            st.plotly_chart(
                fig_trend,
                use_container_width=True
            )

        else:

            st.info("لا توجد بيانات")

    # ==============================
    # البيانات + تحميل Excel
    # ==============================
    with tab_data:

        st.title("📄 البيانات")

        st.dataframe(
            df,
            use_container_width=True
        )

        # ==============================
        # تحميل Excel
        # ==============================
        def to_excel(dataframe):

            output = BytesIO()

            with pd.ExcelWriter(
                output,
                engine="openpyxl"
            ) as writer:

                dataframe.to_excel(
                    writer,
                    index=False,
                    sheet_name="KPI_Data"
                )

            return output.getvalue()

        st.download_button(
            label="📥 تحميل Excel",
            data=to_excel(df),
            file_name="kpi_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
