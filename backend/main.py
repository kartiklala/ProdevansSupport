import os
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from logger_config import get_logger
from oauth_store import (
    create_session,
    get_session,
    update_session,
    delete_session,
    load_sessions,
    save_sessions,
)
from zoho_client import fetch_user_info, get_leaves, apply_leave, delete_leave, get_attendance, get_user_report
import logging
from dotenv import load_dotenv
load_dotenv()
import sys
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8' 
)


app = FastAPI()
logger = get_logger("backend")

# Load persistent sessions on startup
sessions = load_sessions()

@app.on_event("startup")
async def startup_event():
    logger.info("Backend starting up. Loaded sessions from disk.")

@app.on_event("shutdown")
async def shutdown_event():
    save_sessions()
    logger.info("Backend shutting down. Saved sessions to disk.")

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")
print (ZOHO_CLIENT_ID)

# ---------------- AUTH ----------------
@app.get("/auth/zoho/login")
async def zoho_login():
    scopes = ",".join([
        "AaaServer.profile.READ",
        "ZohoPeople.employee.READ",
        "ZohoPeople.leave.ALL",
        "ZohoPeople.attendance.READ",
        "ZohoAssist.userapi.READ",
        "ZohoPeople.forms.ALL"
    ])
    url = (
        f"https://accounts.zoho.in/oauth/v2/auth?"
        f"scope={scopes}&"
        f"client_id={ZOHO_CLIENT_ID}&response_type=code&access_type=offline&"
        f"redirect_uri={ZOHO_REDIRECT_URI}"
    )
    return {"auth_url": url}

SESSION_FILE = "session.json"

@app.get("/auth/zoho/callback")
async def zoho_callback(code: str):
    logger.info("Exchanging Zoho auth code for access token...")

    token_url = "https://accounts.zoho.in/oauth/v2/token"
    params = {
        "grant_type": "authorization_code",
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "redirect_uri": ZOHO_REDIRECT_URI,
        "code": code,
    }

    # Step 1: Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, params=params)
        resp.raise_for_status()
        token_data = resp.json()

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    raw_api_domain = token_data.get("api_domain", "")

    # Step 2: Determine API domain
    if "zohoapis.in" in raw_api_domain:
        api_domain = "https://people.zoho.in"
    elif "zohoapis.com" in raw_api_domain:
        api_domain = "https://people.zoho.com"
    else:
        api_domain = "https://people.zoho.in"

    # Step 3: Save session immediately
    session_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "scope": token_data.get("scope"),
        "api_domain": api_domain,
    }
    session_id = create_session(session_data)
    logger.info(f"Session saved: {session_id}")

    # Step 4: Fetch user info (optional, doesn’t block session creation)
    try:
        user_info = await fetch_user_info(api_domain, access_token)
        logger.info(f"User info fetched: {user_info}")
        # Add user_info to existing session file
        with open(SESSION_FILE, "r+", encoding="utf-8") as f:
            sessions = json.load(f)
            sessions[session_id]["user_info"] = user_info
            f.seek(0)
            json.dump(sessions, f, ensure_ascii=False, indent=2)
            f.truncate()
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch user info: {e}")
        # Continue anyway, session already saved

    # Step 5: Redirect to frontend
    return RedirectResponse(url=f"http://localhost:8501/?session_id={session_id}")



@app.get("/auth/zoho/logout")
async def zoho_logout(session_id: str):
    """Logout current session."""
    if delete_session(session_id):
        logger.info(f"Session {session_id} logged out successfully.")
        return {"status": "ok", "message": "Session cleared successfully."}
    raise HTTPException(404, "Session not found")


# ---------------- API ROUTES ----------------
def get_employee_id_from_session(session_id: str) -> str:
    s = get_session(session_id)
    if not s:
        raise HTTPException(401, "Invalid session")
    user_info = s.get("user_info", {})
    emp_id = user_info.get("zoho_id")
    if not emp_id:
        raise HTTPException(500, "Employee ID missing in session")
    return emp_id


@app.get("/api/leaves")
async def api_leaves(session_id: str):
    emp_id = get_employee_id_from_session(session_id)
    s = get_session(session_id)
    try:
        leaves_data = await get_leaves(s["access_token"], emp_id)
        return leaves_data
    except httpx.HTTPStatusError as e:
        logger.error(f"Error fetching leaves: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error fetching leaves")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/api/leave/apply")
async def api_apply_leave(session_id: str, leave_type: str, from_date: str, to_date: str, reason: str):
    """Apply leave using structured input"""
    emp_id = get_employee_id_from_session(session_id)
    s = get_session(session_id)

    input_data = {
        "employeeId": emp_id,
        "leaveType": leave_type,
        "fromDate": from_date,
        "toDate": to_date,
        "reason": reason
    }

    return await apply_leave(s["access_token"], input_data)


@app.post("/api/leave/delete/{record_id}")
async def api_delete_leave(session_id: str, record_id: str):
    s = get_session(session_id)
    return await delete_leave(s["access_token"], record_id)


@app.get("/api/attendance")
async def api_attendance(session_id: str, sdate: str, edate: str):
    s = get_session(session_id)
    user_info = s.get("user_info", {})
    emp_id = user_info.get("zoho_id")
    email = user_info.get("email")
    return await get_attendance(s["access_token"], sdate, edate, empId=emp_id, emailId=email)


@app.get("/api/user/report")
async def api_user_report(session_id: str):
    emp_id = get_employee_id_from_session(session_id)
    s = get_session(session_id)
    return await get_user_report(s["access_token"], emp_id)
