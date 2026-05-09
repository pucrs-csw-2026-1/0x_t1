"""Testes unitários para UserService (US-10)."""

from unittest.mock import MagicMock

import pytest

from app.adapters.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from app.application.user_service import UserService
from app.domain.exceptions import (
    EmailAlreadyExistsError,
    InvalidEmailError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.user import Email, HashedPassword, User, Username
from app.ports.password_hasher import PasswordHasher
from tests.fakes.user_repository import FakeUserRepository


class TestUserService:
    @pytest.fixture
    def service(self, fake_repo: FakeUserRepository) -> UserService:
        return UserService(user_repo=fake_repo)

    # CT-01 (partição — existente): get_user_by_id retorna o usuário correto
    def test_get_user_by_id_existente_retorna_usuario(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)

        result = service.get_user_by_id(valid_user.id)

        assert result.id == valid_user.id
        assert result.first_name == valid_user.first_name
        assert result.last_name == valid_user.last_name
        assert result.username == valid_user.username
        assert result.email == valid_user.email
        assert result.access_level == valid_user.access_level
        assert result.is_active == valid_user.is_active
        assert result.created_at == valid_user.created_at

    # CT-02: senha nunca é retornada (hashed_password não exposta na entidade retornada)
    def test_get_user_by_id_nao_expoe_senha(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)

        result = service.get_user_by_id(valid_user.id)

        assert not hasattr(result, "password")
        assert repr(result.hashed_password) == "HashedPassword(***)"

    # CT-03 (partição — inexistente): get_user_by_id lança UserNotFoundError
    def test_get_user_by_id_inexistente_lanca_excecao(
        self,
        service: UserService,
    ) -> None:
        with pytest.raises(UserNotFoundError):
            service.get_user_by_id("id-que-nao-existe")

    # CT-04: UserNotFoundError carrega o ID informado na mensagem
    def test_user_not_found_error_contem_id_na_mensagem(
        self,
        service: UserService,
    ) -> None:
        missing_id = "id-ausente-42"

        with pytest.raises(UserNotFoundError) as exc_info:
            service.get_user_by_id(missing_id)

        assert missing_id in exc_info.value.message


class TestUserServiceRegister:
    # Spy + Fake: verifica que PasswordHasher.hash é chamado exatamente 1 vez
    def test_register_calls_hasher_once_and_persists(
        self, fake_repo: FakeUserRepository
    ) -> None:
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.hash.return_value = "$2b$12$fakehash"

        service = UserService(user_repo=fake_repo, password_hasher=spy)

        user = service.register(
            first_name="Joao",
            last_name="Silva",
            username="joao.silva",
            email="joao@example.com",
            password="S3nh@Forte!",
            access_level=["user"],
        )

        spy.hash.assert_called_once_with("S3nh@Forte!")
        # senha não é exposta
        assert not hasattr(user, "password")
        # persistido no fake repo
        fetched = fake_repo.find_by_email(Email("joao@example.com"))
        assert fetched is not None
        assert fetched.id == user.id

    # Stub: controla find_by_email para simular email duplicado
    def test_register_with_duplicate_email_raises(self) -> None:
        class StubRepo(FakeUserRepository):
            def __init__(self, existing_user: User) -> None:
                super().__init__()
                self._existing = existing_user

            def find_by_email(self, email: Email) -> User | None:
                return self._existing

        # cria um usuário existente (constrói com valores válidos)
        existing = User(
            username=Username("exist.user"),
            email=Email("exist@example.com"),
            hashed_password=HashedPassword("$2b$12$existhash"),
            first_name="Exist",
            last_name="User",
        )

        stub = StubRepo(existing)
        service = UserService(
            user_repo=stub, password_hasher=MagicMock(spec=PasswordHasher)
        )

        with pytest.raises(EmailAlreadyExistsError):
            service.register(
                first_name="New",
                last_name="User",
                username="new.user",
                email="exist@example.com",
                password="S3nh@Forte!",
            )

    # Validação de e-mail inválido
    def test_register_invalid_email_raises(self, fake_repo: FakeUserRepository) -> None:
        service = UserService(
            user_repo=fake_repo, password_hasher=MagicMock(spec=PasswordHasher)
        )

        with pytest.raises(InvalidEmailError):
            service.register(
                first_name="Ana",
                last_name="Lima",
                username="ana.lima",
                email="invalid-email",
                password="S3nh@Forte!",
            )

    # Senha fraca deve lançar WeakPasswordError
    def test_register_weak_password_raises(self, fake_repo: FakeUserRepository) -> None:
        service = UserService(
            user_repo=fake_repo, password_hasher=MagicMock(spec=PasswordHasher)
        )

        with pytest.raises(WeakPasswordError):
            service.register(
                first_name="Pedro",
                last_name="Oliveira",
                username="pedro.olive",
                email="pedro@example.com",
                password="weak",
            )

    # Transição de estado: não cadastrado -> cadastrado -> tentativa duplicada -> erro
    def test_state_transition(self, fake_repo: FakeUserRepository) -> None:
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.hash.return_value = "$2b$12$fakehash"
        service = UserService(user_repo=fake_repo, password_hasher=spy)

        # inicialmente não existe
        assert fake_repo.find_by_email(Email("tst@example.com")) is None

        service.register(
            first_name="Tst",
            last_name="User",
            username="tst.user",
            email="tst@example.com",
            password="S3nh@Forte!",
        )

        assert fake_repo.find_by_email(Email("tst@example.com")) is not None

        # tentativa duplicada
        with pytest.raises(EmailAlreadyExistsError):
            service.register(
                first_name="Tst2",
                last_name="User2",
                username="tst2.user",
                email="tst@example.com",
                password="S3nh@Forte!",
            )


class TestUserServiceDeactivate:
    """Testes para UserService.deactivate() (US-17)."""

    # CT-01: Desativação bem-sucedida marca is_active=False
    def test_deactivate_marks_inactive(
        self, fake_repo: FakeUserRepository, valid_user: User
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(user_repo=fake_repo)

        deactivated = service.deactivate(valid_user.id)

        assert deactivated.is_active is False
        # Persisted
        fetched = fake_repo.find_by_id(valid_user.id)
        assert fetched is not None
        assert fetched.is_active is False

    # CT-02: Desativação atualiza updated_at
    def test_deactivate_updates_updated_at(
        self, fake_repo: FakeUserRepository, valid_user: User
    ) -> None:
        original_updated_at = valid_user.updated_at
        fake_repo.save(valid_user)
        service = UserService(user_repo=fake_repo)

        deactivated = service.deactivate(valid_user.id)

        assert deactivated.updated_at > original_updated_at

    # CT-03: Registro físico é preservado (soft delete)
    def test_deactivate_preserves_record(
        self, fake_repo: FakeUserRepository, valid_user: User
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(user_repo=fake_repo)

        service.deactivate(valid_user.id)

        # Registro ainda existe no repositório
        fetched = fake_repo.find_by_id(valid_user.id)
        assert fetched is not None
        assert fetched.id == valid_user.id
        assert fetched.email == valid_user.email
        assert fetched.username == valid_user.username

    # CT-04: Idempotência - chamar duas vezes não falha
    def test_deactivate_is_idempotent(
        self, fake_repo: FakeUserRepository, valid_user: User
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(user_repo=fake_repo)

        result1 = service.deactivate(valid_user.id)
        result2 = service.deactivate(valid_user.id)

        assert result1.is_active is False
        assert result2.is_active is False

    # CT-05: Revoga todos os refresh tokens do usuário
    def test_deactivate_revokes_all_refresh_tokens(
        self, fake_repo: FakeUserRepository, valid_user: User
    ) -> None:
        fake_repo.save(valid_user)
        refresh_repo = InMemoryRefreshTokenRepository()

        # Simula tokens criados para este usuário
        refresh_repo.register_token_for_user(valid_user.id, "token1")
        refresh_repo.register_token_for_user(valid_user.id, "token2")

        service = UserService(user_repo=fake_repo, refresh_token_repo=refresh_repo)

        service.deactivate(valid_user.id)

        # Todos os tokens foram revogados
        assert refresh_repo.is_revoked("token1") is True
        assert refresh_repo.is_revoked("token2") is True

    # CT-06: Lança exceção se usuário não existe
    def test_deactivate_user_not_found_raises(
        self, fake_repo: FakeUserRepository
    ) -> None:
        service = UserService(user_repo=fake_repo)

        with pytest.raises(UserNotFoundError):
            service.deactivate("id-que-nao-existe")

    # CT-07: Transição de estado - ativo -> inativo
    def test_deactivate_state_transition(
        self, fake_repo: FakeUserRepository, valid_user: User
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(user_repo=fake_repo)

        # Inicialmente ativo
        assert valid_user.is_active is True

        # Após desativação
        deactivated = service.deactivate(valid_user.id)
        assert deactivated.is_active is False

        # Fetch confirmação
        fetched = fake_repo.find_by_id(valid_user.id)
        assert fetched is not None
        assert fetched.is_active is False

