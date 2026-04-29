import streamlit as st
import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
def connect_to_gsheet():
    scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(credentials)
    sheet = client.open("KPI_Data").sheet1  # اسم الشيت
    return sheet
       

st.set_page_config(
    page_title="نظام مؤشرات الأداء - المركز القومي لبحوث المياه",
    layout="wide"
)

# ====== تحديد مسار الشعار ======
current_dir = os.path.dirname(__file__)
logo_path = os.path.join(current_dir, "logo.png")

st.image(logo_path, width=180)
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
    
        sheet = connect_to_gsheet()
    
        if len(sheet.get_all_values()) == 0:
            sheet.append_row(df_new.columns.tolist())
    
        sheet.append_row(df_new.iloc[0].tolist())
    
        st.success("تم حفظ البيانات بنجاح ✅")

        

    
