import streamlit as st
import requests

BACKEND = "http://localhost:8002"
st.set_page_config(page_title="Zoho Leave Manager", layout="centered")
st.title("Zoho Leave Management")

# --- Extract session_id from URL ---
def get_session_id_from_url():
    query_params = st.experimental_get_query_params()
    return query_params.get("session_id", [None])[0]

# --- Maintain session ---
if "session_id" not in st.session_state:
    st.session_state.session_id = get_session_id_from_url()

# --- If not logged in ---
if not st.session_state.session_id:
    st.write("### Please log in with Zoho")
    if st.button("🔐 Login with Zoho"):
        r = requests.get(f"{BACKEND}/auth/zoho/login")
        auth_url = r.json().get("auth_url", "")
        st.markdown(f"[Click here to authenticate Zoho →]({auth_url})", unsafe_allow_html=True)
    st.stop()

st.success("✅ Logged in successfully!")

# --- Sign Out ---
if st.button("🚪 Sign Out"):
    try:
        requests.get(f"{BACKEND}/auth/zoho/logout", params={"session_id": st.session_state.session_id})
        st.success("You have been signed out.")
    except Exception as e:
        st.error(f"Error signing out: {e}")
    finally:
        st.session_state.session_id = None
        st.experimental_set_query_params()
        st.rerun()

# --- Menu ---
choice = st.radio(
    "Choose an action",
    ["View Leaves", "Apply Leave", "Delete Leave", "Check Attendance", "User Report"]
)

# --- Features ---
if choice == "View Leaves":
    r = requests.get(f"{BACKEND}/api/leaves", params={"session_id": st.session_state.session_id})
    st.json(r.json())

elif choice == "Apply Leave":
    st.subheader("Apply for Leave")
    leave_type = st.selectbox("Leave Type", ["Casual Leave", "Sick Leave", "Earned Leave"])
    from_date = st.date_input("From Date")
    to_date = st.date_input("To Date")
    reason = st.text_area("Reason for leave")

    if st.button("Submit Leave"):
        r = requests.post(
            f"{BACKEND}/api/leave/apply",
            params={"session_id": st.session_state.session_id},
            json={
                "leave_type": leave_type,
                "from_date": str(from_date),
                "to_date": str(to_date),
                "reason": reason
            }
        )
        st.json(r.json())


elif choice == "Delete Leave":
    record_id = st.text_input("Enter Record ID to Delete")
    if st.button("Delete"):
        r = requests.post(
            f"{BACKEND}/api/leave/delete/{record_id}",
            params={"session_id": st.session_state.session_id}
        )
        st.json(r.json())

elif choice == "Check Attendance":
    sdate = st.date_input("Start Date")
    edate = st.date_input("End Date")
    if st.button("Fetch Attendance"):
        r = requests.get(
            f"{BACKEND}/api/attendance",
            params={"session_id": st.session_state.session_id, "sdate": sdate, "edate": edate}
        )
        st.json(r.json())

elif choice == "User Report":
    r = requests.get(
        f"{BACKEND}/api/user/report",
        params={"session_id": st.session_state.session_id}
    )
    st.json(r.json())
