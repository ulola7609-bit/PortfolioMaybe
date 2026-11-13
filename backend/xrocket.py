import hashlib, hmac, time
import httpx
from .config import settings

class XRocketError(RuntimeError): pass

class XRocketClient:
    """Клиент актуального xRocket Pay API. По умолчанию используйте testnet."""
    def __init__(self): self.base = settings.xrocket_base_url.rstrip("/")
    def _headers(self): return {"Authorization": f"Bearer {settings.xrocket_api_key}", "Content-Type": "application/json", "Accept": "application/json"}
    async def create_invoice(self, amount: str, currency: str, description: str, payload: str) -> dict:
        if not settings.xrocket_live_enabled: raise XRocketError("Provider calls are disabled. Enable only after testnet verification and deployment review.")
        if not settings.xrocket_api_key: raise XRocketError("XROCKET_API_KEY is not configured")
        body = {"priceAmount": amount, "priceCurrency": currency, "payoutCurrency": currency,
                "clientInvoiceId": payload, "description": description[:1000], "expiresIn": 3600000}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{self.base}/api/v1/invoices", json=body, headers=self._headers())
            response.raise_for_status(); data = response.json()
        links = data.get("links") or {}
        data["pay_url"] = links.get("telegramBotLink")
        return data
    async def check_invoice_status(self, invoice_id: str) -> dict:
        if not settings.xrocket_live_enabled or not settings.xrocket_api_key: raise XRocketError("Payment provider is not enabled")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.base}/api/v1/invoice", params={"id": invoice_id}, headers=self._headers())
            response.raise_for_status(); return response.json()
    @staticmethod
    def verify_webhook(raw_body: bytes, signature: str, timestamp: str, version: str) -> bool:
        if not settings.xrocket_webhook_secret or not signature or version != "v1" or not timestamp: return False
        try:
            stamp = int(timestamp)
            if abs(int(time.time() * 1000) - stamp) > 300_000: return False
        except ValueError: return False
        signed = timestamp.encode() + b"." + raw_body
        expected = hmac.new(settings.xrocket_webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

xrocket = XRocketClient()
