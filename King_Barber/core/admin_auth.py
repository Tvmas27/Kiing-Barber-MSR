import os

from django.contrib.auth.hashers import check_password
from django.core import signing
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class AdminUser:
    is_authenticated = True

    def __init__(self, username):
        self.username = username


class AdminTokenAuthentication(BaseAuthentication):
    token_max_age = 3600

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return None

        token = header[7:].strip()
        username = os.getenv('ADMIN_USER', '').strip()
        if not token or not username:
            raise AuthenticationFailed('Token no valido')

        try:
            token_username = signing.TimestampSigner().unsign(
                token,
                max_age=self.token_max_age,
            )
        except signing.BadSignature as exc:
            raise AuthenticationFailed('Token no valido o caducado') from exc

        if token_username != username:
            raise AuthenticationFailed('Token no autorizado')

        return AdminUser(username), token


def authenticate_admin(username, password):
    expected_username = os.getenv('ADMIN_USER', '').strip()
    password_hash = os.getenv('ADMIN_PASSWORD_HASH', '').strip()
    if not expected_username or not password_hash:
        return False
    return username == expected_username and check_password(password, password_hash)