import streamlit as st
import pandas as pd
import os
#python -m streamlit run "/workspaces/kpi-nwrc-system/kpi/NWRC_app.py"
#streamlit run "D:/NWRC/NWRC_app.py"--server.address 0.0.0.0
#streamlit run "D:/NWRC/NWRC_app.py" --server.port 8501 --server.address 0.0.0.0
# =====================================
# إعداد الصفحة
# =====================================
st.set_page_config(
    page_title="نظام مؤشرات الأداء - المركز القومي لبحوث المياه",
    layout="wide"
)
st.image("/workspaces/kpi-nwrc-system/kpi/logo.png", width=180)
# =====================================
# RTL عربي كامل
# =====================================
st.markdown("""
<style>
html, body, [class*="css"]  {
    direction: rtl;
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

# =====================================
# قاعدة بيانات المستخدمين (مبدئياً داخل الكود)
# =====================================
USERS = {
    "wmri": {"password": "1234", "institute": "معهد بحوث إدارة المياه"},
    "dri": {"password": "1234", "institute": "معهد بحوث الصرف"},
    "wrri": {"password": "1234", "institute": "معهد بحوث الموارد المائية"},
    "nri": {"password": "1234", "institute": "معهد بحوث النيل"},
    "hri": {"password": "1234", "institute": "معهد بحوث الهيدروليكا"},
    "cori": {"password": "1234", "institute": "معهد بحوث الشواطئ"}
}

# =====================================
# Session State
# =====================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "institute" not in st.session_state:
    st.session_state.institute = ""

# =====================================
# صفحة تسجيل الدخول
# =====================================
if not st.session_state.logged_in:

    st.title("تسجيل الدخول")

    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")

    if st.button("دخول"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.institute = USERS[username]["institute"]
            st.success("تم تسجيل الدخول بنجاح ✅")
            st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

# =====================================
# بعد تسجيل الدخول
# =====================================
else:

    st.success(f"مرحباً بك - {st.session_state.institute}")

    if st.button("تسجيل خروج"):
        st.session_state.logged_in = False
        st.rerun()

    st.divider()

    # اختيار الشهر والسنة
    col1, col2 = st.columns(2)
    with col1:
        month = st.selectbox("اختر الشهر",
            ["يناير","فبراير","مارس","أبريل","مايو","يونيو",
             "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
        )
    with col2:
        year = st.number_input("اختر السنة", min_value=2020, max_value=2035, value=2026)

    st.divider()

    data = {}

    # الدراسات
    with st.expander("عدد الدراسات الجارية", expanded=True):
        data["خطة بحثية"] = st.number_input("عدد الدراسات المرتبطة بخطة بحثية", min_value=0)
        data["استشارية"] = st.number_input("عدد الدراسات الاستشارية", min_value=0)
        data["تمويل ذاتي"] = st.number_input("عدد الدراسات ذات التمويل الذاتي", min_value=0)

    # التقارير
    with st.expander("عدد التقارير الصادرة خلال الشهر"):
        data["تقرير مرحلي"] = st.number_input("عدد التقارير المرحلية", min_value=0)
        data["تقرير نهائي"] = st.number_input("عدد التقارير النهائية", min_value=0)

    
    # التدريب
    with st.expander("عدد المشاركين في التدريب"):

        data["متدربين"] = st.number_input("عدد المتدربين", min_value=0)
        data["مدربين"] = st.number_input("عدد المدربين", min_value=0)

    # الاجتماعات
    with st.expander("الاجتماعات"):

        data["بالوزارة"] = st.number_input("عدد الاجتماعات بالوزارة", min_value=0)
        data["بالمركز"] = st.number_input("عدد الاجتماعات بالمركز", min_value=0)
        data["جهات خارجية"] = st.number_input("عدد الاجتماعات مع جهات خارجية", min_value=0)
    # حفظ
    if st.button("حفظ البيانات"):

        df_new = pd.DataFrame([data])
        df_new["المعهد"] = st.session_state.institute
        df_new["المستخدم"] = st.session_state.username
        df_new["الشهر"] = month
        df_new["السنة"] = year

        file_name = "kpi_data.xlsx"

        if os.path.exists(file_name):
            df_old = pd.read_excel(file_name)
            df_final = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df_final = df_new

        df_final.to_excel(file_name, index=False)

        st.success("تم حفظ البيانات بنجاح ✅")
