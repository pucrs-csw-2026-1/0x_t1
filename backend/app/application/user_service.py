from app.adapters.bcrypt_password_hasher import BcryptPasswordHasher
from app.domain.exceptions import (
    AccessLevelNotFoundError,
    EmailAlreadyExistsError,
    InvalidPaginationError,
    UserNotFoundError,
)
from app.domain.user import (
    Email,
    HashedPassword,
    User,
    Username,
    validate_raw_password,
)
from app.ports.access_level_repository import AccessLevelRepository
from app.ports.password_hasher import PasswordHasher
from app.ports.user_repository import UserPage, UserRepository


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        access_level_repo: AccessLevelRepository,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._hasher: PasswordHasher = password_hasher or BcryptPasswordHasher()
        self._access_level_repo = access_level_repo

    def get_user_by_id(self, user_id: str) -> User:
        """Busca e retorna o usuário pelo ID.

        Raises:
            UserNotFoundError: se nenhum usuário for encontrado com o ID fornecido.
        """
        user = self._user_repo.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    def list_users(self, limit: int = 20, cursor: str | None = None) -> UserPage:
        """Lista usuários paginadamente.

        Raises:
            InvalidPaginationError: se cursor for fornecido e não corresponder
            a um usuário existente;
        """
        if cursor is not None and self._user_repo.find_by_id(cursor) is None:
            raise InvalidPaginationError(f"Cursor inválido: {cursor}")
        return self._user_repo.find_all(limit=limit, cursor=cursor)

    def register(
        self,
        first_name: str,
        last_name: str,
        username: str,
        email: str,
        password: str,
    ) -> User:
        """Registra um novo usuário validando dados, hasheando a senha e persistindo.

        Raises:
            EmailAlreadyExistsError: se já existir usuário com o mesmo e-mail.
            AccessLevelNotFoundError: se o nível de acesso não for encontrado.
            InvalidEmailError, WeakPasswordError, InvalidUsernameError:
                propagadas do domínio.
        """
        # Cria value objects (validam email/username)
        email_vo = Email(email)
        username_vo = Username(username)

        # Verifica duplicidade de email
        existing = self._user_repo.find_by_email(email_vo)
        if existing is not None:
            raise EmailAlreadyExistsError(email)

        # Valida senha crua conforme regras de domínio
        validate_raw_password(password)

        # Hash da senha (spy tests dependem que seja chamado exatamente 1 vez)
        hashed = self._hasher.hash(password)
        hashed_vo = HashedPassword(hashed)

        # Busca IDs de níveis de acesso
        level = self._access_level_repo.find_by_title("user")
        if not level:
            raise AccessLevelNotFoundError("user")

        # Cria entidade e persiste
        user = User(
            username=username_vo,
            email=email_vo,
            hashed_password=hashed_vo,
            first_name=first_name,
            last_name=last_name,
            access_level=[level.id],
        )

        saved = self._user_repo.save(user)
        return saved
