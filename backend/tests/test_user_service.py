"""Testes unitarios para UserService (US-10 + US-13)."""

from unittest.mock import MagicMock

import pytest

from app.application.user_service import UserService
from app.domain.access_level import AccessLevel
from app.domain.exceptions import (
    AccessLevelNotFoundError,
    EmailAlreadyExistsError,
    InvalidEmailError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.user import Email, HashedPassword, User, Username
from app.ports.password_hasher import PasswordHasher
from tests.conftest import USER_UUID
from tests.fakes.access_level_repository import FakeAccessLevelRepository
from tests.fakes.user_repository import FakeUserRepository


class TestUserService:
    @pytest.fixture
    def service(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> UserService:
        return UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

    # CT-01 (particao - existente): get_user_by_id retorna o usuario correto
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

    # CT-02: senha nunca eh retornada (hashed_password nao exposta)
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

    # CT-03 (particao - inexistente): get_user_by_id lanca UserNotFoundError
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
    """Testes de UserService.register (US-09 + US-13)."""

    # Spy + Fake: verifica que PasswordHasher.hash eh chamado exatamente 1 vez
    # e que o usuario eh persistido com o UUID do perfil 'user' (US-13).
    def test_register_calls_hasher_once_and_persists_with_user_role(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.hash.return_value = "$2b$12$fakehash"

        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
            password_hasher=spy,
        )

        user = service.register(
            first_name="Joao",
            last_name="Silva",
            username="joao.silva",
            email="joao@example.com",
            password="S3nh@Forte!",
        )

        spy.hash.assert_called_once_with("S3nh@Forte!")
        assert not hasattr(user, "password")
        # US-13: usuario novo sempre cadastrado com perfil 'user'
        assert user.access_level == [USER_UUID]
        # persistido no fake repo com a mesma access_level
        fetched = fake_repo.find_by_email(Email("joao@example.com"))
        assert fetched is not None
        assert fetched.id == user.id
        assert fetched.access_level == [USER_UUID]

    # US-13 - particao 1: register sem campo access_level no payload eh aceito
    # (ja coberto pelo teste acima, que nao passa o parametro).

    # US-13 - particao 2: register com email duplicado lanca antes de tocar
    # no catalogo de access_level
    def test_register_with_duplicate_email_raises(
        self,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        class StubRepo(FakeUserRepository):
            def __init__(self, existing_user: User) -> None:
                super().__init__()
                self._existing = existing_user

            def find_by_email(self, email: Email) -> User | None:
                return self._existing

        existing = User(
            username=Username("exist.user"),
            email=Email("exist@example.com"),
            hashed_password=HashedPassword("$2b$12$existhash"),
            first_name="Exist",
            last_name="User",
        )

        stub = StubRepo(existing)
        service = UserService(
            user_repo=stub,
            access_level_repo=fake_access_level_repo,
            password_hasher=MagicMock(spec=PasswordHasher),
        )

        with pytest.raises(EmailAlreadyExistsError):
            service.register(
                first_name="New",
                last_name="User",
                username="new.user",
                email="exist@example.com",
                password="S3nh@Forte!",
            )

    # Email invalido continua sendo erro de dominio
    def test_register_invalid_email_raises(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
            password_hasher=MagicMock(spec=PasswordHasher),
        )

        with pytest.raises(InvalidEmailError):
            service.register(
                first_name="Ana",
                last_name="Lima",
                username="ana.lima",
                email="invalid-email",
                password="S3nh@Forte!",
            )

    # Senha fraca continua sendo erro de dominio
    def test_register_weak_password_raises(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
            password_hasher=MagicMock(spec=PasswordHasher),
        )

        with pytest.raises(WeakPasswordError):
            service.register(
                first_name="Pedro",
                last_name="Oliveira",
                username="pedro.olive",
                email="pedro@example.com",
                password="weak",
            )

    # Transicao de estado: nao cadastrado -> cadastrado -> tentativa duplicada -> erro
    def test_state_transition(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.hash.return_value = "$2b$12$fakehash"
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
            password_hasher=spy,
        )

        assert fake_repo.find_by_email(Email("tst@example.com")) is None

        service.register(
            first_name="Tst",
            last_name="User",
            username="tst.user",
            email="tst@example.com",
            password="S3nh@Forte!",
        )

        assert fake_repo.find_by_email(Email("tst@example.com")) is not None

        with pytest.raises(EmailAlreadyExistsError):
            service.register(
                first_name="Tst2",
                last_name="User2",
                username="tst2.user",
                email="tst@example.com",
                password="S3nh@Forte!",
            )

    # US-13 CA: catalogo sem o perfil 'user' lanca AccessLevelNotFoundError
    # (sinaliza Terraform fora de sincronia, em vez de fallback silencioso).
    def test_register_sem_catalogo_user_levanta_excecao(
        self,
        fake_repo: FakeUserRepository,
    ) -> None:
        empty_catalog = FakeAccessLevelRepository(levels=[])
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=empty_catalog,
            password_hasher=MagicMock(spec=PasswordHasher),
        )

        with pytest.raises(AccessLevelNotFoundError):
            service.register(
                first_name="Joao",
                last_name="Silva",
                username="joao.silva",
                email="joao@example.com",
                password="S3nh@Forte!",
            )

    # US-13 CA: register sempre atribui o UUID do 'user', mesmo com catalogo
    # contendo 'admin' como primeiro item (ordem do catalogo nao influencia).
    def test_register_busca_titulo_user_e_nao_o_primeiro_do_catalogo(
        self,
        fake_repo: FakeUserRepository,
    ) -> None:
        # admin antes de user proposito de garantir que find_by_title eh
        # chamado, nao um "pega o primeiro"
        catalog = FakeAccessLevelRepository(
            levels=[
                AccessLevel(id="uuid-admin-fake", title="admin"),
                AccessLevel(id="uuid-user-fake", title="user"),
            ]
        )
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.hash.return_value = "$2b$12$fakehash"
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=catalog,
            password_hasher=spy,
        )

        user = service.register(
            first_name="Joao",
            last_name="Silva",
            username="joao.silva",
            email="joao@example.com",
            password="S3nh@Forte!",
        )

        assert user.access_level == ["uuid-user-fake"]
