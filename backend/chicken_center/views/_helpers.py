from rest_framework.response import Response


def err(e):
    msg = e.message_dict if hasattr(e, 'message_dict') else (
        e.messages[0] if hasattr(e, 'messages') else str(e))
    return Response({'error': msg}, status=400)
