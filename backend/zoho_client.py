import httpx
from logger_config import get_logger
from dotenv import load_dotenv
load_dotenv()
logger = get_logger("zoho_client")

import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # 
)
# ---------------- OAuth ----------------
async def refresh_access_token(refresh_token, client_id, client_secret):
    """Refresh Zoho OAuth access token."""
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }
    logger.info("🔁 Refreshing Zoho access token...")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, params=params)
        r.raise_for_status()
        logger.info("Access token refreshed successfully")
        return r.json()


# ---------------- Zoho People API ----------------
async def fetch_user_info(api_domain: str, access_token: str):
    """
    Fetch employee info from Zoho People using /people/api/forms/P_EmployeeView/records
    """
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    # 1️⃣ Get current user info from Zoho Accounts (this still works to get email)
    info_url = "https://accounts.zoho.in/oauth/user/info"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(info_url, headers=headers)
        if r.status_code != 200:
            logger.error(f"Failed to fetch user info: {r.status_code} - {r.text}")
            r.raise_for_status()
        data = r.json()
    email = data.get("Email") or data.get("email") or data.get("useremail")
    if not email:
        raise Exception("Email not found in Zoho user info response")

    logger.info(f"📧 Logged-in email: {email}")

    # 2️⃣ Query Zoho People employee view using that email
    employee_url = f"{api_domain}/people/api/forms/P_EmployeeView/records"
    params = {
        "searchColumn": "EMPLOYEEMAILALIASs",
        "searchValue": email
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(employee_url, headers=headers, params=params)
        if r.status_code != 200:
            logger.error(f"Failed to fetch employee record: {r.status_code} - {r.text}")
            r.raise_for_status()
        data = r.json()

    records = data.get("data", [])
    if not records:
        raise Exception(f"No employee record found for {email}")

    emp = records[0]
    user_info = {
        "zoho_id": emp.get("EMPLOYEEID"),
        "name": emp.get("FULLNAME"),
        "email": email,
        "department": emp.get("DEPARTMENTNAME"),
        "designation": emp.get("DESIGNATION"),
        "role": emp.get("ROLE"),
        "location": emp.get("LOCATION"),
        "date_of_joining": emp.get("DATEOFJOIN"),
        "status": emp.get("EMPLOYEESTATUS")
    }

    logger.info(f" Employee info fetched successfully: {user_info}")
    return user_info



    
import datetime


async def get_leaves(access_token: str, emp_id: str = None):
    """Fetch leave records from Zoho People within a valid date range."""
    url = "https://people.zoho.com/api/v2/leavetracker/leaves/records"

    today = datetime.date.today()
    start_of_year = datetime.date(today.year, 1, 1)

    params = {
        "from": start_of_year.strftime("%Y-%m-%d"),
        "to": today.strftime("%Y-%m-%d"),
    }
    if emp_id:
        params["employeeId"] = emp_id

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    logger.info(f"Fetching leave records from {params['from']} to {params['to']}")

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params)
        if r.status_code != 200:
            logger.error(f"Failed to fetch leaves: {r.status_code} - {r.text}")
            r.raise_for_status()
        return r.json()



async def apply_leave(access_token: str, input_data: dict):
    """Apply leave using Zoho People Leave form API."""
    url = "https://people.zoho.com/people/api/forms/json/Leave/insertRecord"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    # Zoho expects JSON string in "inputData" param
    import json
    params = {"inputData": json.dumps(input_data)}

    logger.info(f"📝 Applying leave for employee {input_data.get('employeeId')}")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, params=params)
        if r.status_code != 200:
            logger.error(f"Leave apply failed: {r.status_code} - {r.text}")
            r.raise_for_status()
        return r.json()



async def delete_leave(access_token: str, record_id: str):
    """Cancel a leave record."""
    url = f"https://people.zoho.com/people/api/v2/leavetracker/leaves/records/cancel/{record_id}"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    logger.info(f"Deleting leave record {record_id}")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers)
        if r.status_code != 200:
            logger.error(f"Failed to delete leave: {r.status_code} - {r.text}")
            r.raise_for_status()
        return r.json()


async def get_attendance(access_token, sdate, edate, empId=None, emailId=None):
    """Fetch user attendance report."""
    url = f"https://people.zoho.com/people/api/attendance/getUserReport?sdate={sdate}&edate={edate}"
    if empId:
        url += f"&empId={empId}"
    if emailId:
        url += f"&emailId={emailId}"

    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    logger.info(f"Fetching attendance from {sdate} to {edate}")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            logger.error(f"Attendance fetch failed: {r.status_code} - {r.text}")
            r.raise_for_status()
        return r.json()


async def get_user_report(access_token: str, employee: str):
    """Fetch detailed user leave report (available/taken days per leave type)."""
    url = "https://people.zoho.com/people/api/v2/leavetracker/reports/user"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }
    params = {"employee": employee}
    logger.info(f"FETCHING user leave report for {employee}")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        if r.status_code != 200:
            logger.error(f"User report fetch failed {r.status_code}: {r.text}")
            r.raise_for_status()
        data = r.json()
        logger.info(f"User report received for {data.get('employeeName')}")
        return data
