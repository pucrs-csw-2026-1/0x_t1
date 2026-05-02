from passlib.context import CryptContext

from app.ports.password_hasher import PasswordHasher

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return _ctx.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return _ctx.verify(password, hashed)
