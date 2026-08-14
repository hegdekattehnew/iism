from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass
class GoogleUserInfo:
    google_id: str
    email: str
    full_name: str


class GoogleOAuthAdapter:
    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{AUTHORIZATION_URL}?{urlencode(params)}"

    async def exchange_code_for_access_token(self, code: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def fetch_user_info(self, access_token: str) -> GoogleUserInfo:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            return GoogleUserInfo(
                google_id=data["sub"], email=data["email"], full_name=data.get("name", "")
            )


def get_google_oauth_adapter() -> GoogleOAuthAdapter:
    return GoogleOAuthAdapter()
