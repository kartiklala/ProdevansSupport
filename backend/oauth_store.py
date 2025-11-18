import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict
from logger_config import get_logger
import logging
import sys
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  
)
logger = get_logger("oauth_store")

STORE_FILE = os.path.join(os.path.dirname(__file__), "sessions.json")
_sessions: Dict[str, Dict] = {} # _sessions is populated from disk at startup




def load_sessions() -> Dict[str, Dict]:
    global _sessions
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, "r") as f:
                _sessions = json.load(f)
                logger.info(f"Loaded {len(_sessions)} sessions from disk")
        except json.JSONDecodeError:
            logger.error("Session file corrupted, starting fresh.")
            _sessions = {}
    else:
        logger.info("No existing session file found. Starting fresh.")
        _sessions = {}
    return _sessions

load_sessions()  

def save_sessions():
    try:
        with open(STORE_FILE, "w") as f:
            json.dump(_sessions, f, indent=4)
        logger.info(f"Saved {len(_sessions)} sessions to disk")
    except Exception as e:
        logger.exception(f"Failed to save sessions: {e}")


def create_session(data: Dict) -> str:
    global _sessions
    session_id = str(uuid.uuid4())
    data["created_at"] = datetime.utcnow().isoformat()
    _sessions[session_id] = data
    save_sessions()
    logger.info(f"Created session {session_id}")
    return session_id


def get_session(session_id: str) -> Optional[Dict]:
    s = _sessions.get(session_id)
    if s:
        logger.info(f"Loaded session {session_id}")
    else:
        logger.warning(f"Attempted to load non-existent session {session_id}")
    return s


def update_session(session_id: str, data: Dict):
    global _sessions
    if session_id in _sessions:
        _sessions[session_id].update(data)
        save_sessions()
        logger.info(f"Updated session {session_id}")
    else:
        logger.warning(f"Attempted to update missing session {session_id}")


def delete_session(session_id: str) -> bool:
    global _sessions
    if session_id in _sessions:
        del _sessions[session_id]
        save_sessions()
        logger.info(f"Deleted session {session_id}")
        return True
    logger.warning(f"Attempted to delete missing session {session_id}")
    return False


def clear_all_sessions():
    """Delete all sessions from memory and disk immediately."""
    global _sessions
    _sessions.clear()
    if os.path.exists(STORE_FILE):
        os.remove(STORE_FILE)
        logger.info("Deleted sessions.json file.")
    logger.info("Cleared all sessions from memory.")
