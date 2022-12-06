from dataclasses import dataclass

from jose import jwt
from rest_framework.exceptions import APIException

from settings import settings

exception = APIException('Could not validate credentials')


class JWTManager:
    _instance = None

    def __new__(cls, *args, **kwargs) -> "JWTManager":
        if cls._instance is None:
            cls._instance = cls()

        return cls._instance

    @dataclass
    class ParsedHeader:
        cookies: dict
        is_valid: bool = False
        access_token: str | None = None

        def __post_init__(self) -> None:
            authorization = self.cookies.get('Authorization')
            self.refresh_token = self.cookies.get('refresh_token')

            if authorization is not None:
                token_type, self.access_token = authorization.split(' ')
                if self.refresh_token is not None and token_type == 'Bearer':
                    self.is_valid = True

    @classmethod
    def encode_token(cls, cookies: dict) -> dict | None:
        header = cls.ParsedHeader(cookies)
        if not header.is_valid:
            return None

        token = header.refresh_token
        access_token = header.access_token

        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                access_token=access_token
            )
        except Exception:
            return None

        return payload
