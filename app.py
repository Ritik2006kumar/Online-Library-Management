import streamlit as st
from datetime import date, datetime
import pandas as pd
import json, os, random, smtplib
from email.mime.text import MIMEText

# =========================
# Config
# =========================
st.set_page_config(page_title="Library Management", page_icon="📚", layout="wide")

STUDENT_FILE = "students.json"
BOOK_FILE = "books.json"
RECORD_FILE = "records.json"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# ---- Email (OTP) configuration: replace with your creds ----
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "youremail@gmail.com"        # <-- change
SMTP_APP_PASSWORD = "your-app-password"  # <-- change (Gmail App Password)

# =========================
# Utilities: Load / Save
# =========================
def load_data(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def next_id(d):
    return (max([int(k) for k in d.keys()], default=0) + 1)

# Initialize persistent dicts
if "students" not in st.session_state:
    st.session_state.students = load_data(STUDENT_FILE)
if "books" not in st.session_state:
    st.session_state.books = load_data(BOOK_FILE)
if "records" not in st.session_state:
    st.session_state.records = load_data(RECORD_FILE)

students = st.session_state.students
books = st.session_state.books
records = st.session_state.records

# =========================
# Auth helpers
# =========================
def send_otp(email: str) -> str | None:
    otp = str(random.randint(100000, 999999))
    msg = MIMEText(f"Your Library Login OTP is: {otp}")
    msg["Subject"] = "Library Login OTP"
    msg["From"] = SMTP_USER
    msg["To"] = email
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_USER, email, msg.as_string())
        server.quit()
        return otp
    except Exception as e:
        st.error(f"❌ Failed to send OTP: {e}")
        return None

def logout():
    for k in ["role", "student_id", "otp"]:
        if k in st.session_state:
            del st.session_state[k]

# =========================
# UI: Sidebar Login
# =========================
st.sidebar.title("🔑 Login")
login_choice = st.sidebar.radio("Login as", ["Admin", "Student (Password)", "Student (OTP)"])

if "role" not in st.session_state:
    if login_choice == "Admin":
        u = st.sidebar.text_input("Username")
        p = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login as Admin"):
            if u == ADMIN_USER and p == ADMIN_PASS:
                st.session_state.role = "admin"
                st.success("✅ Logged in as Admin")
            else:
                st.sidebar.error("❌ Invalid Admin Credentials!")

    elif login_choice == "Student (Password)":
        enroll = st.sidebar.text_input("Enrollment No")
        pwd = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login as Student"):
            sid = None
            for k, s in students.items():
                if s.get("enrollment_no") == enroll and s.get("password") == pwd:
                    sid = k
                    break
            if sid:
                st.session_state.role = "student"
                st.session_state.student_id = sid
                st.success(f"✅ Logged in as {students[sid]['name']}")
            else:
                st.sidebar.error("❌ Invalid Enrollment or Password!")

    else:  # Student (OTP)
        enroll = st.sidebar.text_input("Enrollment No")
        email = st.sidebar.text_input("Registered Email")
        if st.sidebar.button("Send OTP"):
            sid = None
            for k, s in students.items():
                if s.get("enrollment_no") == enroll and s.get("email") == email:
                    sid = k
                    break
            if sid:
                code = send_otp(email)
                if code:
                    st.session_state.otp = code
                    st.session_state.student_id = sid
                    st.info("📨 OTP sent to your email. Enter below:")
            else:
                st.sidebar.error("❌ Enrollment No or Email not found!")
        if "otp" in st.session_state:
            otp_entered = st.sidebar.text_input("Enter OTP")
            if st.sidebar.button("Verify OTP"):
                if otp_entered == st.session_state.otp:
                    st.session_state.role = "student"
                    st.success(f"✅ Logged in as {students[st.session_state.student_id]['name']}")
                else:
                    st.sidebar.error("❌ Invalid OTP!")

# Top bar
colA, colB = st.columns([1,1])
with colA:
    st.title("📚 Online Library Management System")
with colB:
    if "role" in st.session_state:
        st.write("")
        st.write("")
        st.button("Logout", on_click=logout)

# =========================
# Helpers: DataFrames (joined for readability)
# =========================
def df_students(hide_password=True):
    if not students:
        return pd.DataFrame()
    df = pd.DataFrame(students.values())
    if hide_password and "password" in df.columns:
        df = df.drop(columns=["password"])
    return df

def df_books_filtered(search_query="", filter_option="All Books"):
    if not books:
        return pd.DataFrame()
    df = pd.DataFrame(books.values())
    # Filter
    if filter_option == "Available Only":
        df = df[df["available_copies"] > 0]
    elif filter_option == "Issued Only":
        df = df[df["available_copies"] < df["total_copies"]]
    # Search
    if search_query:
        mask = df["title"].str.contains(search_query, case=False, na=False) | \
               df["author"].str.contains(search_query, case=False, na=False)
        df = df[mask]
    return df

def df_records_joined():
    if not records:
        return pd.DataFrame()
    recs = pd.DataFrame(records.values())
    if recs.empty:
        return recs
    # Map ids to names/titles
    sid_to_name = {int(k): v["name"] for k, v in students.items()}
    bid_to_title = {int(k): v["title"] for k, v in books.items()}
    recs["student_name"] = recs["student_id"].map(sid_to_name)
    recs["book_title"] = recs["book_id"].map(bid_to_title)
    # Order
    cols = ["id","student_id","student_name","book_id","book_title","issue_date","return_date","fine"]
    return recs[cols]

# =========================
# Admin Area
# =========================
def admin_area():
    st.success("👤 Role: Admin")
    tabs = st.tabs(["👨‍🎓 Manage Students", "📚 Manage Books", "📕 Issue Book", "📗 Return Book", "📊 View Records"])

    # --- Manage Students ---
    with tabs[0]:
        st.subheader("➕ Add New Student")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            s_name = st.text_input("Name")
        with c2:
            s_enroll = st.text_input("Enrollment No")
        with c3:
            s_course = st.text_input("Course")
        with c4:
            s_email = st.text_input("Email")
        s_pass = st.text_input("Set Password", type="password")

        if st.button("Add Student"):
            if any(s.get("enrollment_no")==s_enroll for s in students.values()):
                st.error("⚠️ Enrollment number must be unique.")
            elif not s_name or not s_enroll or not s_pass:
                st.error("⚠️ Name, Enrollment, Password are required.")
            else:
                sid = next_id(students)
                students[str(sid)] = {
                    "id": sid,
                    "name": s_name,
                    "enrollment_no": s_enroll,
                    "course": s_course,
                    "email": s_email,
                    "password": s_pass
                }
                save_data(STUDENT_FILE, students)
                st.success(f"✅ Student added (ID: {sid})")

        st.divider()
        st.subheader("👨‍🎓 All Students")
        df = df_students()
        if df.empty:
            st.info("No students yet.")
        else:
            st.dataframe(df, use_container_width=True)

    # --- Manage Books ---
    with tabs[1]:
        st.subheader("📖 Add New Book")
        c1, c2, c3 = st.columns(3)
        with c1:
            b_title = st.text_input("Title")
        with c2:
            b_author = st.text_input("Author")
        with c3:
            b_total = st.number_input("Total Copies", min_value=1, step=1, value=1)
        if st.button("Add Book"):
            bid = next_id(books)
            books[str(bid)] = {
                "id": bid,
                "title": b_title,
                "author": b_author,
                "total_copies": int(b_total),
                "available_copies": int(b_total)
            }
            save_data(BOOK_FILE, books)
            st.success(f"✅ Book added (ID: {bid})")

        st.divider()
        st.subheader("📚 Books in Library")
        search = st.text_input("🔍 Search Title/Author")
        filt = st.selectbox("📌 Filter", ["All Books", "Available Only", "Issued Only"])
        dfb = df_books_filtered(search, filt)
        if dfb.empty:
            st.info("No books to show.")
        else:
            st.dataframe(dfb, use_container_width=True)

    # --- Issue Book ---
    with tabs[2]:
        st.subheader("📕 Issue a Book")
        c1, c2 = st.columns(2)
        with c1:
            sid = st.number_input("Student ID", min_value=1, step=1)
        with c2:
            bid = st.number_input("Book ID", min_value=1, step=1)
        if st.button("Issue Book"):
            if str(sid) not in students:
                st.error("⚠️ Invalid Student ID.")
            elif str(bid) not in books:
                st.error("⚠️ Invalid Book ID.")
            elif books[str(bid)]["available_copies"] <= 0:
                st.error("⚠️ Book not available.")
            else:
                rid = next_id(records)
                records[str(rid)] = {
                    "id": rid,
                    "student_id": int(sid),
                    "book_id": int(bid),
                    "issue_date": date.today().strftime("%Y-%m-%d"),
                    "return_date": None,
                    "fine": 0
                }
                books[str(bid)]["available_copies"] -= 1
                save_data(RECORD_FILE, records)
                save_data(BOOK_FILE, books)
                st.success(f"✅ Issued (Record ID: {rid})")

        st.caption("Tip: Use the Books tab search+filter to find IDs quickly.")

    # --- Return Book ---
    with tabs[3]:
        st.subheader("📗 Return a Book")
        rid = st.number_input("Issue Record ID", min_value=1, step=1)
        if st.button("Return Book"):
            if str(rid) not in records:
                st.error("⚠️ Invalid Record ID.")
            else:
                rec = records[str(rid)]
                if rec["return_date"] is not None:
                    st.error("⚠️ Already returned.")
                else:
                    issued = datetime.strptime(rec["issue_date"], "%Y-%m-%d").date()
                    days = (date.today() - issued).days
                    fine = (days - 7) * 10 if days > 7 else 0
                    rec["return_date"] = date.today().strftime("%Y-%m-%d")
                    rec["fine"] = fine
                    # increment availability
                    bid = str(rec["book_id"])
                    if bid in books:
                        books[bid]["available_copies"] += 1
                    save_data(RECORD_FILE, records)
                    save_data(BOOK_FILE, books)
                    st.success(f"✅ Returned. Fine: ₹{fine}")

        st.caption("Fine rule: 7 days free, then ₹10/day.")

    # --- View Records ---
    with tabs[4]:
        st.subheader("📊 Issue/Return Records")
        dfr = df_records_joined()
        if dfr.empty:
            st.info("No records yet.")
        else:
            st.dataframe(dfr.sort_values("id", ascending=False), use_container_width=True)

# =========================
# Student Area
# =========================
def student_area():
    sid = st.session_state.get("student_id")
    if not sid or str(sid) not in students:
        st.error("Student not found. Please login again.")
        return
    s = students[str(sid)]
    st.success(f"👤 Role: Student | {s['name']} ({s.get('enrollment_no','')})")

    t1, t2 = st.tabs(["📚 Your Issued Books", "🔎 Search Books"])
    with t1:
        my = [r for r in records.values() if str(r["student_id"]) == str(sid)]
        if not my:
            st.info("No books issued yet.")
        else:
            dfr = pd.DataFrame(my)
            if not dfr.empty:
                # join titles for clarity
                bid_to_title = {int(k): v["title"] for k, v in books.items()}
                dfr["book_title"] = dfr["book_id"].map(bid_to_title)
                dfr = dfr[["id","book_id","book_title","issue_date","return_date","fine"]]
                st.dataframe(dfr.sort_values("id", ascending=False), use_container_width=True)

    with t2:
        search = st.text_input("🔍 Search Title/Author")
        filt = st.selectbox("📌 Filter", ["All Books", "Available Only", "Issued Only"])
        dfb = df_books_filtered(search, filt)
        if dfb.empty:
            st.info("No books to show.")
        else:
            st.dataframe(dfb, use_container_width=True)

# =========================
# Main Area Router
# =========================
if "role" not in st.session_state:
    st.info("Please login from the sidebar to continue.")
else:
    if st.session_state.role == "admin":
        admin_area()
    elif st.session_state.role == "student":
        student_area()
    else:
        st.error("Unknown role. Please logout and login again.")