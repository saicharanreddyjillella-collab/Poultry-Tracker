from rest_framework.response import Response
from datetime import date as date_cls


def err(e):
    """Turn a ValidationError into a clean 400 body."""
    msg = e.message_dict if hasattr(e, 'message_dict') else (
        e.messages[0] if hasattr(e, 'messages') else str(e))
    return Response({'error': msg}, status=400)


def today_or(d):
    return d or date_cls.today()
