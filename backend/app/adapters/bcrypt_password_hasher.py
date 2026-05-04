from passlib.context import CryptContext

from app.ports.password_hasher import PasswordHasher

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        result: str = _ctx.hash(password)
        return result

    def verify(self, password: str, hashed: str) -> bool:
        result: bool = _ctx.verify(password, hashed)
        return result
