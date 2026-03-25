"""
MongoDB utility functions for storing and retrieving chat history.
Uses MongoDB Atlas for persistent chat storage.

NOTE: Requires OPENSSL_CONF to point to openssl.cnf (in project root) when
running on Python 3.13 + OpenSSL 3.x on Windows, to lower SECLEVEL from 2→1.
This is done automatically below before MongoClient is imported.
"""

import os
import pathlib

# ── OpenSSL 3.x / Python 3.13 TLS fix ─────────────────────────────────────
# Without this, pymongo gets TLSV1_ALERT_INTERNAL_ERROR when connecting to
# MongoDB Atlas because OpenSSL 3's default SECLEVEL=2 rejects certain cipher
# suites that Atlas negotiates.  Setting SECLEVEL=1 via a custom openssl.cnf
# file resolves it.  Must be set BEFORE pymongo/ssl are imported.
_openssl_cnf = pathlib.Path(__file__).resolve().parent.parent / "openssl.cnf"
if _openssl_cnf.exists() and not os.environ.get("OPENSSL_CONF"):
    os.environ["OPENSSL_CONF"] = str(_openssl_cnf)
# ───────────────────────────────────────────────────────────────────────────

import certifi
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime, timezone
import uuid

# MongoDB connection URI
# Priority: MONGO_URL env var (Railway auto-set) > fallback
# Internal URI (when backend runs on Railway): mongodb.railway.internal
# External URI (for local dev): centerbeam.proxy.rlwy.net:15831
RAILWAY_INTERNAL_URI = "mongodb://mongo:uYSqlxdvFkhkBgEMQzFtLCimkLdCkZIR@mongodb.railway.internal:27017"
RAILWAY_EXTERNAL_URI = "mongodb://mongo:uYSqlxdvFkhkBgEMQzFtLCimkLdCkZIR@centerbeam.proxy.rlwy.net:15831"
ATLAS_URI = "mongodb+srv://sudharsan1429_db_user:12xc2MRGRvqZFCuA@arivorahdb.biyxz3a.mongodb.net/?appName=ArivoraHDB"

# On Railway: use env var or internal URI. Locally: use external proxy URI
MONGO_URI = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URL") or RAILWAY_EXTERNAL_URI

# Singleton client (connection pooling)
_client = None
_db = None


def get_db():
    """Get the MongoDB database instance (lazy singleton)."""
    global _client, _db
    if _client is None:
        is_atlas = "mongodb.net" in MONGO_URI

        if is_atlas:
            # Atlas needs TLS + certifi
            _client = MongoClient(
                MONGO_URI,
                server_api=ServerApi('1'),
                tlsCAFile=certifi.where(),
                tlsAllowInvalidCertificates=True,
                serverSelectionTimeoutMS=20000,
            )
            print("[MongoDB] Connecting to Atlas...")
        else:
            # Railway MongoDB — no TLS workarounds needed
            _client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=20000,
            )
            print("[MongoDB] Connecting to Railway MongoDB...")

        _db = _client["arivora"]
        # Verify connection
        try:
            _client.admin.command('ping')
            print("[MongoDB] Connected successfully.")
        except Exception as e:
            print(f"[MongoDB] Connection failed: {e}")
            _client = None
            _db = None
            raise
    return _db


# ─── Chat Session CRUD ───────────────────────────────────────────────


def create_chat_session(phone_number, title=None):
    """
    Create a new chat session for a user.

    Args:
        phone_number: User's phone number (unique identifier)
        title: Optional session title (auto-generated if None)

    Returns:
        dict with session_id and metadata
    """
    db = get_db()
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    session = {
        "session_id": session_id,
        "phone_number": phone_number,
        "title": title or "New Chat",
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }

    db.chat_sessions.insert_one(session)
    return {
        "session_id": session_id,
        "title": session["title"],
        "created_at": now.isoformat(),
    }


def save_message(session_id, text, is_user, phone_number):
    """
    Append a message to an existing chat session.

    Args:
        session_id: The chat session ID
        text: Message content
        is_user: True if from user, False if from AI
        phone_number: User's phone number (for ownership check)

    Returns:
        True on success, False on failure
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    message = {
        "text": text,
        "is_user": is_user,
        "timestamp": now,
    }

    result = db.chat_sessions.update_one(
        {"session_id": session_id, "phone_number": phone_number},
        {
            "$push": {"messages": message},
            "$set": {"updated_at": now},
        },
    )

    # Auto-generate title from first user message
    if is_user and result.modified_count > 0:
        session = db.chat_sessions.find_one({"session_id": session_id})
        if session and session.get("title") == "New Chat" and len(session.get("messages", [])) == 1:
            # Use first 40 chars of the first message as title
            auto_title = text[:40] + ("..." if len(text) > 40 else "")
            db.chat_sessions.update_one(
                {"session_id": session_id},
                {"$set": {"title": auto_title}},
            )

    return result.modified_count > 0


def get_chat_sessions(phone_number, limit=50):
    """
    Get all chat sessions for a user, sorted by most recent.

    Args:
        phone_number: User's phone number
        limit: Maximum number of sessions to return

    Returns:
        List of session summaries (without full message bodies)
    """
    db = get_db()

    sessions = (
        db.chat_sessions.find(
            {"phone_number": phone_number},
            {
                "session_id": 1,
                "title": 1,
                "created_at": 1,
                "updated_at": 1,
                "messages": {"$slice": -1},  # Only last message for preview
                "_id": 0,
            },
        )
        .sort("updated_at", -1)
        .limit(limit)
    )

    result = []
    for s in sessions:
        last_msg = s.get("messages", [{}])
        preview = ""
        if last_msg:
            preview = last_msg[0].get("text", "")[:80]

        result.append({
            "session_id": s["session_id"],
            "title": s.get("title", "New Chat"),
            "preview": preview,
            "created_at": s.get("created_at", "").isoformat() if s.get("created_at") else "",
            "updated_at": s.get("updated_at", "").isoformat() if s.get("updated_at") else "",
        })

    return result


def get_chat_messages(session_id, phone_number):
    """
    Get all messages for a specific chat session.

    Args:
        session_id: The chat session ID
        phone_number: User's phone number (for ownership check)

    Returns:
        List of messages or None if session not found
    """
    db = get_db()

    session = db.chat_sessions.find_one(
        {"session_id": session_id, "phone_number": phone_number},
        {"messages": 1, "title": 1, "_id": 0},
    )

    if not session:
        return None

    messages = []
    for m in session.get("messages", []):
        messages.append({
            "text": m["text"],
            "isUser": m["is_user"],
            "time": m.get("timestamp", "").isoformat() if m.get("timestamp") else "",
        })

    return {
        "title": session.get("title", "New Chat"),
        "messages": messages,
    }


def delete_chat_session(session_id, phone_number):
    """
    Delete a chat session.

    Args:
        session_id: The chat session ID
        phone_number: User's phone number (for ownership check)

    Returns:
        True if deleted, False if not found
    """
    db = get_db()
    result = db.chat_sessions.delete_one(
        {"session_id": session_id, "phone_number": phone_number}
    )
    return result.deleted_count > 0


# ─── User Management ─────────────────────────────────────────────────


def find_user_by_phone(phone_number):
    """
    Check if a user exists by phone number.

    Args:
        phone_number: User's phone number with country code

    Returns:
        dict with user data if found, None otherwise
    """
    db = get_db()
    user = db.users.find_one(
        {"phone_number": phone_number},
        {"_id": 0, "phone_number": 1, "name": 1, "created_at": 1},
    )
    return user


def create_or_update_user(phone_number, name, session_token=None):
    """
    Create a new user or update an existing user's name and session token.

    Args:
        phone_number: User's phone number with country code
        name: User's display name
        session_token: Optional session token for silent sign-in

    Returns:
        dict with user data
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    set_fields = {
        "name": name,
        "updated_at": now,
    }
    if session_token:
        set_fields["session_token"] = session_token

    result = db.users.update_one(
        {"phone_number": phone_number},
        {
            "$set": set_fields,
            "$setOnInsert": {
                "phone_number": phone_number,
                "created_at": now,
            },
        },
        upsert=True,
    )

    return {
        "phone_number": phone_number,
        "name": name,
        "is_new": result.upserted_id is not None,
    }


def validate_session(phone_number, session_token):
    """
    Validate a session token for silent sign-in.

    Args:
        phone_number: User's phone number with country code
        session_token: The session token to validate

    Returns:
        dict with user data if valid, None otherwise
    """
    if not phone_number or not session_token:
        return None

    db = get_db()
    user = db.users.find_one(
        {"phone_number": phone_number, "session_token": session_token},
        {"_id": 0, "phone_number": 1, "name": 1},
    )
    return user


def clear_session_token(phone_number):
    """
    Clear the session token for a user (logout).

    Args:
        phone_number: User's phone number with country code

    Returns:
        True if updated, False otherwise
    """
    db = get_db()
    result = db.users.update_one(
        {"phone_number": phone_number},
        {"$unset": {"session_token": ""}},
    )
    return result.modified_count > 0
