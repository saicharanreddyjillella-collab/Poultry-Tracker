"""
WhatsApp messaging — pluggable provider.

Automatic on save, but a failed send NEVER blocks or reverses a transaction.
Until a real provider is configured, ConsoleProvider logs what would be sent
so the app is fully usable today. Flip WHATSAPP_PROVIDER + credentials in the
server env to go live — no code change.

Env:
  WHATSAPP_PROVIDER = console | interakt
  WHATSAPP_API_KEY  = <provider key>          (interakt)
  WHATSAPP_BUSINESS_NAME = Sai Charan Chicken Center
"""
import os
import logging

logger = logging.getLogger('whatsapp')

BUSINESS_NAME = os.environ.get('WHATSAPP_BUSINESS_NAME', 'Sai Charan Chicken Center')


# ─── message builders (single source of wording) ───

def build_sale_message(*, customer_name, weight_kg, amount, balance):
    return (
        f"*{BUSINESS_NAME}*\n"
        f"Namaste {customer_name},\n"
        f"Sale: {weight_kg} kg — ₹{amount:,.0f}\n"
        f"Outstanding balance: ₹{balance:,.0f}\n"
        f"Thank you!"
    )


def build_collection_message(*, customer_name, amount, mode, balance):
    return (
        f"*{BUSINESS_NAME}*\n"
        f"Namaste {customer_name},\n"
        f"Payment received: ₹{amount:,.0f} ({mode})\n"
        f"Balance remaining: ₹{balance:,.0f}\n"
        f"Thank you!"
    )


# ─── providers ───

class ConsoleProvider:
    """Default. Logs the message; sends nothing. App works fully today."""
    name = 'console'

    def send(self, to, text):
        logger.info("[WhatsApp:console] to=%s\n%s", to, text)
        return {'status': 'disabled', 'detail': 'console provider (no send)'}


class InteraktProvider:
    """Interakt WhatsApp Business API. Requires WHATSAPP_API_KEY and
    Meta-approved templates. Session (free-form) text works only inside the
    24h customer-service window; outside it, template messages are required.
    This uses Interakt's message endpoint; wire your template name once
    approved."""
    name = 'interakt'
    ENDPOINT = 'https://api.interakt.ai/v1/public/message/'

    def __init__(self):
        self.api_key = os.environ.get('WHATSAPP_API_KEY', '')

    def send(self, to, text):
        import requests  # imported lazily so console mode needs no dependency
        if not self.api_key:
            return {'status': 'failed', 'detail': 'no api key'}
        phone = to.lstrip('+')
        # Interakt expects country code + number.
        payload = {
            'countryCode': '+91',
            'phoneNumber': phone[-10:],
            'type': 'Text',
            'data': {'message': text},
        }
        try:
            r = requests.post(
                self.ENDPOINT, json=payload,
                headers={'Authorization': f'Basic {self.api_key}'},
                timeout=10,
            )
            if r.status_code // 100 == 2:
                return {'status': 'sent', 'detail': r.text[:200]}
            return {'status': 'failed', 'detail': f'{r.status_code}: {r.text[:200]}'}
        except Exception as e:  # never propagate — messaging must not break a sale
            return {'status': 'failed', 'detail': str(e)[:200]}


def get_provider():
    name = os.environ.get('WHATSAPP_PROVIDER', 'console').lower()
    if name == 'interakt':
        return InteraktProvider()
    return ConsoleProvider()


def send_whatsapp(to, text):
    """Best-effort send. Returns a status dict; never raises."""
    if not to:
        return {'status': 'failed', 'detail': 'no phone number'}
    try:
        return get_provider().send(to, text)
    except Exception as e:
        logger.exception("WhatsApp send crashed")
        return {'status': 'failed', 'detail': str(e)[:200]}
