"""Testes unitarios para UserService (US-10 + US-13)."""

from unittest.mock import MagicMock

import pytest

from app.adapters.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from app.application.user_service import UserService
from app.domain.access_level import AccessLevel
from app.domain.exceptions import (
    AccessLevelNotFoundError,
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidPaginationError,
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


class TestUserServiceDeactivate:
    """Testes para UserService.deactivate() (US-17)."""

    # CT-01: Desativação bem-sucedida marca is_active=False
    def test_deactivate_marks_inactive(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        deactivated = service.deactivate(valid_user.id)

        assert deactivated.is_active is False
        # Persisted
        fetched = fake_repo.find_by_id(valid_user.id)
        assert fetched is not None
        assert fetched.is_active is False

    # CT-02: Desativação atualiza updated_at
    def test_deactivate_updates_updated_at(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        original_updated_at = valid_user.updated_at
        fake_repo.save(valid_user)
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        deactivated = service.deactivate(valid_user.id)

        assert deactivated.updated_at > original_updated_at

    # CT-03: Registro físico é preservado (soft delete)
    def test_deactivate_preserves_record(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        service.deactivate(valid_user.id)

        # Registro ainda existe no repositório
        fetched = fake_repo.find_by_id(valid_user.id)
        assert fetched is not None
        assert fetched.id == valid_user.id
        assert fetched.email == valid_user.email
        assert fetched.username == valid_user.username

    # CT-04: Idempotência - chamar duas vezes não falha
    def test_deactivate_is_idempotent(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        result1 = service.deactivate(valid_user.id)
        result2 = service.deactivate(valid_user.id)

        assert result1.is_active is False
        assert result2.is_active is False

    # CT-05: Revoga todos os refresh tokens do usuário
    def test_deactivate_revokes_all_refresh_tokens(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)
        refresh_repo = InMemoryRefreshTokenRepository()

        # Simula tokens criados para este usuário
        refresh_repo.register_token_for_user(valid_user.id, "token1")
        refresh_repo.register_token_for_user(valid_user.id, "token2")

        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
            refresh_token_repo=refresh_repo,
        )

        service.deactivate(valid_user.id)

        # Todos os tokens foram revogados
        assert refresh_repo.is_revoked("token1") is True
        assert refresh_repo.is_revoked("token2") is True

    # CT-06: Lança exceção se usuário não existe
    def test_deactivate_user_not_found_raises(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        with pytest.raises(UserNotFoundError):
            service.deactivate("id-que-nao-existe")

    # CT-07: Transição de estado - ativo -> inativo
    def test_deactivate_state_transition(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        fake_repo.save(valid_user)
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        # Inicialmente ativo
        assert valid_user.is_active is True

        # Após desativação
        deactivated = service.deactivate(valid_user.id)
        assert deactivated.is_active is False

        # Fetch confirmação
        fetched = fake_repo.find_by_id(valid_user.id)
        assert fetched is not None
        assert fetched.is_active is False

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


class TestUserServiceListUsers:
    """Testes de UserService.list_users (US-14)."""

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

    @staticmethod
    def _make_user(seq: int) -> User:
        # IDs sequenciais para ordenacao deterministica nos testes.
        return User(
            id=f"user-{seq:04d}",
            username=Username(f"user.{seq:04d}"),
            email=Email(f"user{seq}@example.com"),
            hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
            first_name="Test",
            last_name=f"User{seq}",
        )

    # CT-14.1: lista vazia retorna pagina vazia sem cursor
    def test_repo_vazio_retorna_pagina_vazia_sem_cursor(
        self, service: UserService
    ) -> None:
        page = service.list_users(limit=20)

        assert page.items == []
        assert page.next_cursor is None

    # CT-14.2: quantidade < limit retorna todos sem cursor
    def test_quantidade_menor_que_limit_retorna_todos(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
    ) -> None:
        for i in range(1, 4):
            fake_repo.save(self._make_user(i))

        page = service.list_users(limit=10)

        assert len(page.items) == 3
        assert page.next_cursor is None

    # CT-14.3: quantidade > limit devolve cursor para proxima pagina
    def test_quantidade_maior_que_limit_devolve_cursor(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
    ) -> None:
        for i in range(1, 6):
            fake_repo.save(self._make_user(i))

        page = service.list_users(limit=2)

        assert len(page.items) == 2
        assert page.next_cursor == page.items[-1].id

    # CT-14.4: cursor avanca para a proxima pagina sem repetir items
    def test_cursor_avanca_para_proxima_pagina(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
    ) -> None:
        for i in range(1, 6):
            fake_repo.save(self._make_user(i))

        primeira = service.list_users(limit=2)
        segunda = service.list_users(limit=2, cursor=primeira.next_cursor)

        ids_primeira = {u.id for u in primeira.items}
        ids_segunda = {u.id for u in segunda.items}
        assert ids_primeira.isdisjoint(ids_segunda)
        assert len(segunda.items) == 2

    # CT-14.5: ultima pagina sinaliza fim com next_cursor None
    def test_ultima_pagina_retorna_next_cursor_none(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
    ) -> None:
        for i in range(1, 4):
            fake_repo.save(self._make_user(i))

        primeira = service.list_users(limit=2)
        segunda = service.list_users(limit=2, cursor=primeira.next_cursor)

        assert len(segunda.items) == 1
        assert segunda.next_cursor is None

    # CT-14.6: paginar 5 items de 2 em 2 cobre todos exatamente uma vez
    def test_paginacao_completa_cobre_todos_os_itens(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
    ) -> None:
        ids_criados: list[str] = []
        for i in range(1, 6):
            user = self._make_user(i)
            fake_repo.save(user)
            ids_criados.append(user.id)

        coletados: list[str] = []
        cursor: str | None = None
        while True:
            page = service.list_users(limit=2, cursor=cursor)
            coletados.extend(u.id for u in page.items)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor

        assert sorted(coletados) == sorted(ids_criados)

    # CT-14.7: cursor inexistente lanca InvalidPaginationError
    def test_cursor_inexistente_lanca_excecao(self, service: UserService) -> None:
        with pytest.raises(InvalidPaginationError):
            service.list_users(limit=20, cursor="cursor-que-nao-existe")
