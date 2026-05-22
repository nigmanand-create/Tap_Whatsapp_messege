import re

def normalize_phone_number(phone_str: str) -> str:
    """
    Normalizes an Indian phone number to E.164 format (+91XXXXXXXXXX).
    Strips spaces, dashes, and normalizes prefixes.
    """
    if not phone_str:
        return ""
        
    # Strip all non-digit characters except leading '+'
    cleaned = re.sub(r'[^\d+]', '', str(phone_str))
    
    if cleaned.startswith("+91") and len(cleaned) == 13:
        return cleaned
    elif cleaned.startswith("91") and len(cleaned) == 12:
        return f"+{cleaned}"
    elif cleaned.startswith("0") and len(cleaned) == 11:
        return f"+91{cleaned[1:]}"
    elif len(cleaned) == 10:
        return f"+91{cleaned}"
        
    # If we can't normalize it, return as-is (might be invalid or foreign)
    return cleaned
