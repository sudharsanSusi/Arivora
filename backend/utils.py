import requests
import random
from django.core.cache import cache
from django.conf import settings


def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))


def send_whatsapp_otp(phone_number):
    """
    Send OTP via WhatsApp using UltraMsg API.
    
    Args:
        phone_number: Phone number with country code (e.g., +919876543210)
    
    Returns:
        dict: Response from the API
    """
    otp = generate_otp()
    
    # Save OTP in cache for 5 minutes
    cache.set(f"otp_{phone_number}", otp, timeout=300)

    # UltraMsg API configuration
    instance_id = getattr(settings, 'ULTRAMSG_INSTANCE_ID', 'instance161285')
    token = getattr(settings, 'ULTRAMSG_TOKEN', 'tvrfj31kd5lpacyw')
    
    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    
    # Build payload string and encode properly
    payload = f"token={token}&to={phone_number}&body=Your Arivora Verification Code is: {otp}"
    payload = payload.encode('utf8').decode('iso-8859-1')
    
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    
    try:
        response = requests.request("POST", url, data=payload, headers=headers)
        return {
            "success": True,
            "response": response.json(),
            "otp": otp  # For debugging, remove in production
        }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": str(e)
        }


def verify_otp(phone_number, otp):
    """
    Verify the OTP entered by the user.
    
    Args:
        phone_number: Phone number with country code
        otp: OTP entered by the user
    
    Returns:
        bool: True if OTP is valid, False otherwise
    """
    cached_otp = cache.get(f"otp_{phone_number}")
    
    if cached_otp and cached_otp == otp:
        # Delete OTP after successful verification
        cache.delete(f"otp_{phone_number}")
        return True
    
    return False
