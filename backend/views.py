from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .utils import send_whatsapp_otp, verify_otp
from .gemini_utils import get_gemini_response
from .mongo_utils import (
    create_chat_session,
    save_message,
    get_chat_sessions,
    get_chat_messages,
    delete_chat_session,
    find_user_by_phone,
    create_or_update_user,
    validate_session as db_validate_session,
    clear_session_token,
)


@csrf_exempt
@require_http_methods(["POST"])
def send_otp(request):
    """
    API endpoint to send OTP to a phone number via WhatsApp.
    
    Request body:
        {
            "phone_number": "+919876543210"
        }
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return JsonResponse({
                "success": False,
                "message": "Phone number is required"
            }, status=400)
        
        result = send_whatsapp_otp(phone_number)
        
        if result.get("success"):
            return JsonResponse({
                "success": True,
                "message": "OTP sent successfully",
                "otp": result.get("otp")  # included for dev/debug; remove in production
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Failed to send OTP",
                "error": result.get("error")
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def verify_otp_view(request):
    """
    API endpoint to verify OTP.
    
    Request body:
        {
            "phone_number": "+919876543210",
            "otp": "123456",
            "name": "John Doe"
        }
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        otp = data.get('otp')
        name = data.get('name', '')
        
        if not phone_number or not otp:
            return JsonResponse({
                "success": False,
                "message": "Phone number and OTP are required"
            }, status=400)
        
        if verify_otp(phone_number, otp):
            # Generate a simple session token
            import hashlib
            import time
            token_string = f"{phone_number}{time.time()}"
            session_token = hashlib.sha256(token_string.encode()).hexdigest()

            # Save or update user in MongoDB (persist session token)
            if name:
                create_or_update_user(phone_number, name, session_token=session_token)
            else:
                # Returning user – fetch name from DB
                existing = find_user_by_phone(phone_number)
                if existing:
                    name = existing.get('name', '')
                create_or_update_user(phone_number, name or '', session_token=session_token)

            return JsonResponse({
                "success": True,
                "message": "OTP verified successfully",
                "user": {
                    "name": name,
                    "phone_number": phone_number,
                    "session_token": session_token
                }
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Invalid or expired OTP"
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def check_user(request):
    """
    Check if a user already exists by phone number.

    Request body:
        {
            "phone_number": "+919876543210"
        }

    Returns:
        - exists: bool
        - name: str (if user exists)
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')

        if not phone_number:
            return JsonResponse({
                "success": False,
                "message": "Phone number is required"
            }, status=400)

        user = find_user_by_phone(phone_number)

        if user:
            return JsonResponse({
                "success": True,
                "exists": True,
                "name": user.get('name', ''),
            })
        else:
            return JsonResponse({
                "success": True,
                "exists": False,
            })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def chat_with_gemini(request):
    """
    API endpoint for AI chat using Gemini API.
    
    Request body:
        {
            "message": "Hello, I need legal help",
            "conversation_history": [
                {"text": "Previous message", "isUser": true},
                {"text": "Previous response", "isUser": false}
            ]
        }
    """
    try:
        data = json.loads(request.body)
        message = data.get('message')
        conversation_history = data.get('conversation_history', [])
        language = data.get('language')
        
        if not message:
            return JsonResponse({
                "success": False,
                "message": "Message is required"
            }, status=400)
        
        result = get_gemini_response(message, conversation_history, language)
        
        if result.get("success"):
            return JsonResponse({
                "success": True,
                "message": result.get("message")
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Failed to get response",
                "error": result.get("error")
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def create_session(request):
    """
    Create a new chat session.
    
    Request body:
        {
            "phone_number": "+919876543210",
            "title": "Optional title"
        }
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        title = data.get('title')

        if not phone_number:
            return JsonResponse({
                "success": False,
                "message": "Phone number is required"
            }, status=400)

        session = create_chat_session(phone_number, title)
        return JsonResponse({"success": True, **session})

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_chat_message(request):
    """
    Save a message to an existing chat session.
    
    Request body:
        {
            "session_id": "uuid-here",
            "phone_number": "+919876543210",
            "text": "Hello",
            "is_user": true
        }
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        phone_number = data.get('phone_number')
        text = data.get('text')
        is_user = data.get('is_user', True)

        if not all([session_id, phone_number, text]):
            return JsonResponse({
                "success": False,
                "message": "session_id, phone_number and text are required"
            }, status=400)

        saved = save_message(session_id, text, is_user, phone_number)
        return JsonResponse({"success": saved})

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def list_sessions(request):
    """
    Get all chat sessions for a user.
    
    Request body:
        {
            "phone_number": "+919876543210"
        }
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')

        if not phone_number:
            return JsonResponse({
                "success": False,
                "message": "Phone number is required"
            }, status=400)

        sessions = get_chat_sessions(phone_number)
        return JsonResponse({"success": True, "sessions": sessions})

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_session_messages(request):
    """
    Get all messages for a specific chat session.
    
    Request body:
        {
            "session_id": "uuid-here",
            "phone_number": "+919876543210"
        }
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        phone_number = data.get('phone_number')

        if not session_id or not phone_number:
            return JsonResponse({
                "success": False,
                "message": "session_id and phone_number are required"
            }, status=400)

        result = get_chat_messages(session_id, phone_number)
        if result is None:
            return JsonResponse({
                "success": False,
                "message": "Session not found"
            }, status=404)

        return JsonResponse({"success": True, **result})

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_session(request):
    """
    Delete a chat session.
    
    Request body:
        {
            "session_id": "uuid-here",
            "phone_number": "+919876543210"
        }
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        phone_number = data.get('phone_number')

        if not session_id or not phone_number:
            return JsonResponse({
                "success": False,
                "message": "session_id and phone_number are required"
            }, status=400)

        deleted = delete_chat_session(session_id, phone_number)
        return JsonResponse({
            "success": deleted,
            "message": "Session deleted" if deleted else "Session not found"
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def validate_session_view(request):
    """
    Validate a stored session token for silent sign-in.

    Request body:
        {
            "phone_number": "+919876543210",
            "session_token": "sha256-hash-here"
        }
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        session_token = data.get('session_token')

        if not phone_number or not session_token:
            return JsonResponse({
                "success": False,
                "message": "phone_number and session_token are required"
            }, status=400)

        user = db_validate_session(phone_number, session_token)

        if user:
            return JsonResponse({
                "success": True,
                "valid": True,
                "user": {
                    "name": user.get('name', ''),
                    "phone_number": user.get('phone_number', phone_number),
                }
            })
        else:
            return JsonResponse({
                "success": True,
                "valid": False,
                "message": "Invalid or expired session"
            })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def logout_user(request):
    """
    Logout a user by clearing their session token.

    Request body:
        {
            "phone_number": "+919876543210"
        }
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')

        if not phone_number:
            return JsonResponse({
                "success": False,
                "message": "phone_number is required"
            }, status=400)

        cleared = clear_session_token(phone_number)
        return JsonResponse({
            "success": True,
            "message": "Logged out successfully" if cleared else "No active session found"
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)
