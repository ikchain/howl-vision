"""GET /api/v1/qr — Generate QR code with server's local IP for mobile connection."""
import io
import socket

from fastapi import APIRouter
from fastapi.responses import Response

from src.config import settings

router = APIRouter(prefix="/api/v1")


def get_local_ip() -> str:
    """Get the machine's local network IP address.

    Uses a UDP connect trick — no actual packet is sent, but the OS
    selects the outbound interface, revealing the local IP.
    Falls back to loopback if no network route is available.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@router.get("/qr")
async def qr_code():
    import qrcode
    local_ip = get_local_ip()
    url = f"http://{local_ip}:{settings.backend_port}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"X-Server-URL": url},
    )
