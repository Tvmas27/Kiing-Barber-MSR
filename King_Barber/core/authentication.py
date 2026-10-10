from dataclasses import dataclass
import os

from firebase_admin import auth
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


@dataclass(frozen=True)
class FirebaseUser:
    uid: str
    username: str
    is_authenticated: bool = True


class FirebaseAuthentication(BaseAuthentication):
    def authenticate(self, request):
        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith('Bearer '):
            return None

        token = authorization[7:].strip()
        if not token:
            raise AuthenticationFailed('Token no válido')

        try:
            claims = auth.verify_id_token(token, check_revoked=True)
        except Exception as exc:
            raise AuthenticationFailed('Token no válido o caducado') from exc

        uid = claims.get('uid')
        username = claims.get('email') or uid
        admin_uid = os.getenv('FIREBASE_ADMIN_UID')
        if not uid or not username or not admin_uid or uid != admin_uid:
            raise AuthenticationFailed('Identidad de Firebase incompleta')

        return FirebaseUser(uid=uid, username=username), token
