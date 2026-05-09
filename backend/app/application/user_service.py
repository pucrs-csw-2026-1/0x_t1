from app.adapters.bcrypt_password_hasher import BcryptPasswordHasher
from app.domain.exceptions import (
    AccessLevelNotFoundError,
    EmailAlreadyExistsError,
    InvalidPaginationError,
    UsernameAlreadyExistsError,
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
from app.ports.refresh_token_repository import RefreshTokenRepository
from app.ports.user_repository import UserPage, UserRepository


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        access_level_repo: AccessLevelRepository,
        password_hasher: PasswordHasher | None = None,
        refresh_token_repo: RefreshTokenRepository | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._access_level_repo = access_level_repo
        self._hasher: PasswordHasher = password_hasher or BcryptPasswordHasher()
        self._refresh_token_repo = refresh_token_repo

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

    def update_profile(
        self,
        user_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        username: str | None = None,
    ) -> User:
        """Atualiza campos do perfil do próprio usuário.

        Raises:
            UserNotFoundError: se o usuário não for encontrado.
            EmailAlreadyExistsError: se o novo email já estiver em uso.
            UsernameAlreadyExistsError: se o novo username já estiver em uso.
            InvalidEmailError, InvalidUsernameError, InvalidNameError:
                propagadas do domínio.
        """
        user = self.get_user_by_id(user_id)

        if email is not None:
            email_vo = Email(email)
            existing = self._user_repo.find_by_email(email_vo)
            if existing is not None and existing.id != user_id:
                raise EmailAlreadyExistsError(email)
            user.change_email(email_vo)

        if username is not None:
            username_vo = Username(username)
            existing = self._user_repo.find_by_username(username_vo)
            if existing is not None and existing.id != user_id:
                raise UsernameAlreadyExistsError(username)
            user.change_username(username_vo)

        if first_name is not None or last_name is not None:
            user.change_name(
                first_name if first_name is not None else user.first_name,
                last_name if last_name is not None else user.last_name,
            )

        return self._user_repo.save(user)

    def deactivate(self, user_id: str) -> User:
        """Desativa um usuário, revogando todos os seus refresh tokens (idempotente).

        Marks is_active=False e atualiza updated_at. O registro físico é preservado
        (soft delete).

        Raises:
            UserNotFoundError: se o usuário não for encontrado.
        """
        user = self.get_user_by_id(user_id)

        # Revoga todos os refresh tokens ativos do usuário (se repositório foi injetado)
        if self._refresh_token_repo is not None:
            self._refresh_token_repo.revoke_all_by_user(user_id)

        # Marca como inativo
        # (idempotente: se já estava inativo, apenas atualiza updated_at)
        user.deactivate()

        # Persiste a alteração
        saved = self._user_repo.save(user)
        return saved
