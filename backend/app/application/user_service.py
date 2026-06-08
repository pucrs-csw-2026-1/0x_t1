import logging

from app.adapters.bcrypt_password_hasher import BcryptPasswordHasher
from app.domain.access_level import Role
from app.domain.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidPaginationError,
    SamePasswordError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from app.domain.user import (
    Email,
    Gender,
    HashedPassword,
    User,
    Username,
    validate_raw_password,
)
from app.ports.password_hasher import PasswordHasher
from app.ports.refresh_token_repository import RefreshTokenRepository
from app.ports.user_event_publisher import UserEventPublisher
from app.ports.user_repository import UserPage, UserRepository

logger = logging.getLogger(__name__)


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher | None = None,
        refresh_token_repo: RefreshTokenRepository | None = None,
        event_publisher: UserEventPublisher | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._hasher: PasswordHasher = password_hasher or BcryptPasswordHasher()
        self._refresh_token_repo = refresh_token_repo
        self._event_publisher = event_publisher

    def _publish_profile_changed(self, user: User) -> None:
        """Publica ``UserProfileChanged`` de forma best-effort.

        Falha na publicação é logada e ignorada: o ciclo de
        cadastro/atualização do usuário nunca é quebrado por indisponibilidade
        da mensageria. Sem publisher injetado, é no-op.
        """
        if self._event_publisher is None:
            return
        try:
            self._event_publisher.publish_profile_changed(user)
        except Exception:
            logger.warning(
                "Falha ao publicar UserProfileChanged para user=%s; ignorado.",
                user.id,
                exc_info=True,
            )

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
        age: int | None = None,
        area: str | None = None,
        gender: Gender | None = None,
        city: str | None = None,
    ) -> User:
        """Registra um novo usuário validando dados, hasheando a senha e persistindo.

        Os campos demográficos (age, area, gender, city) são opcionais.
        Cadastro público sempre cria o usuário com papel PARTICIPANT — o
        papel nunca vem do cliente (anti-promoção por construção).

        Raises:
            EmailAlreadyExistsError: se já existir usuário com o mesmo e-mail.
            InvalidEmailError, WeakPasswordError, InvalidUsernameError,
            InvalidAgeError, InvalidProfileFieldError: propagadas do domínio.
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

        # Cria entidade e persiste. Papel fixo PARTICIPANT: o cadastro público
        # nunca aceita papel vindo do cliente.
        user = User(
            username=username_vo,
            email=email_vo,
            hashed_password=hashed_vo,
            first_name=first_name,
            last_name=last_name,
            age=age,
            area=area,
            gender=gender,
            city=city,
            access_level=Role.PARTICIPANT,
        )

        saved = self._user_repo.save(user)
        # Novo usuário → publica o perfil (best-effort) para consumidores.
        self._publish_profile_changed(saved)
        return saved

    def update_profile(
        self,
        user_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        username: str | None = None,
        age: int | None = None,
        area: str | None = None,
        gender: Gender | None = None,
        city: str | None = None,
    ) -> User:
        """Atualiza campos do perfil do próprio usuário.

        Atualização parcial: apenas os campos informados (não-None) são
        alterados, incluindo os demográficos (age, area, gender, city).

        Raises:
            UserNotFoundError: se o usuário não for encontrado.
            EmailAlreadyExistsError: se o novo email já estiver em uso.
            UsernameAlreadyExistsError: se o novo username já estiver em uso.
            InvalidEmailError, InvalidUsernameError, InvalidNameError,
            InvalidAgeError, InvalidProfileFieldError: propagadas do domínio.
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

        demographics_changed = any(v is not None for v in (age, area, gender, city))
        if demographics_changed:
            user.change_demographics(age=age, area=area, gender=gender, city=city)

        saved = self._user_repo.save(user)
        # Só publica quando a demografia mudou — o evento existe para alimentar
        # métricas demográficas; mudanças de nome/email/username não interessam
        # ao consumidor (Metrics).
        if demographics_changed:
            self._publish_profile_changed(saved)
        return saved

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> User:
        """Troca a senha do usuário autenticado.

        Raises:
            UserNotFoundError: se o usuário não for encontrado.
            InvalidCredentialsError: se current_password estiver incorreta.
            SamePasswordError: se new_password for igual à senha atual.
            WeakPasswordError: se new_password não atender às regras de domínio.
        """
        user = self.get_user_by_id(user_id)

        if not self._hasher.verify(current_password, user.hashed_password.value):
            raise InvalidCredentialsError()

        if self._hasher.verify(new_password, user.hashed_password.value):
            raise SamePasswordError()

        validate_raw_password(new_password)

        hashed = self._hasher.hash(new_password)
        user.change_password(HashedPassword(hashed))

        return self._user_repo.save(user)

    def admin_update(
        self,
        admin_id: str,
        target_user_id: str,
        access_level: Role | None = None,
        is_active: bool | None = None,
    ) -> User:
        """Atualiza o papel (access_level) e/ou is_active de um usuário como admin.

        Raises:
            ValueError: se admin_id == target_user_id.
            UserNotFoundError: se o usuário alvo não for encontrado.
        """
        if admin_id == target_user_id:
            raise ValueError("Admin não pode alterar a si mesmo.")

        user = self.get_user_by_id(target_user_id)

        role_changed = access_level is not None
        if access_level is not None:
            user.change_role(access_level)

        if is_active is not None:
            if is_active:
                user.activate()
            else:
                user.deactivate()

        saved = self._user_repo.save(user)
        # access_level (papel) faz parte do payload demográfico do Metrics —
        # publica quando o papel muda. Mudança apenas de is_active não publica.
        if role_changed:
            self._publish_profile_changed(saved)
        return saved

    def deactivate(self, user_id: str) -> User:
        """Desativa um usuário (soft delete). Bloqueia logins e refreshes.

        Marca is_active=False e atualiza updated_at (idempotente). O registro
        físico é preservado.

        A chamada a revoke_all_by_user é mantida para compatibilidade com o
        contrato do RefreshTokenRepository, mas o adapter atual
        (InMemoryRefreshTokenRepository) não rastreia tokens emitidos no
        fluxo de login, então a revogação explícita é no-op. O bloqueio
        efetivo da sessão é feito em dois pontos:
        - AuthService.login rejeita credenciais de usuários inativos;
        - AuthService.refresh verifica is_active antes de emitir novo
          access token (impede refresh de tokens emitidos pré-deactivate).

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
