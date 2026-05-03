"""Testes unitários para UserService (US-10)."""

import pytest

from app.application.user_service import UserService
from app.domain.exceptions import UserNotFoundError
from app.domain.user import User
from tests.fakes.user_repository import FakeUserRepository
from unittest.mock import MagicMock

from app.ports.password_hasher import PasswordHasher
from app.domain.user import Email
from app.domain.exceptions import (
    EmailAlreadyExistsError,
    InvalidEmailError,
    WeakPasswordError,
)


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
    def test_register_calls_hasher_once_and_persists(self, fake_repo: FakeUserRepository) -> None:
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
        from app.domain.user import HashedPassword, Username

        existing = User(
            username=Username("exist.user"),
            email=Email("exist@example.com"),
            hashed_password=HashedPassword("$2b$12$existhash"),
            first_name="Exist",
            last_name="User",
        )

        stub = StubRepo(existing)
        service = UserService(user_repo=stub, password_hasher=MagicMock(spec=PasswordHasher))

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
        service = UserService(user_repo=fake_repo, password_hasher=MagicMock(spec=PasswordHasher))

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
        service = UserService(user_repo=fake_repo, password_hasher=MagicMock(spec=PasswordHasher))

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

        user = service.register(
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
