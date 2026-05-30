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
    InvalidAgeError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidNameError,
    InvalidPaginationError,
    InvalidUsernameError,
    SamePasswordError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.user import Email, Gender, HashedPassword, User, Username
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

    # US-26: register com demografia persiste os 4 campos
    def test_register_com_demografia_persiste_os_campos(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        user = service.register(
            first_name="Ana",
            last_name="Souza",
            username="ana.souza",
            email="ana@example.com",
            password="S3nh@Forte!",
            age=28,
            area="Saúde",
            gender=Gender.F,
            city="Curitiba",
        )

        assert user.age == 28
        assert user.area == "Saúde"
        assert user.gender is Gender.F
        assert user.city == "Curitiba"
        fetched = fake_repo.find_by_id(user.id)
        assert fetched is not None
        assert fetched.age == 28
        assert fetched.gender is Gender.F

    # US-26: register sem demografia mantem os campos None
    def test_register_sem_demografia_mantem_none(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        service = UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
        )

        user = service.register(
            first_name="Ana",
            last_name="Souza",
            username="ana.souza",
            email="ana@example.com",
            password="S3nh@Forte!",
        )

        assert user.age is None
        assert user.area is None
        assert user.gender is None
        assert user.city is None

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


class TestUserServiceUpdateProfile:
    """Testes de UserService.update_profile (US-15)."""

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

    @pytest.fixture
    def saved_user(self, fake_repo: FakeUserRepository, valid_user: User) -> User:
        return fake_repo.save(valid_user)

    # CT-15.1: usuário não encontrado lança UserNotFoundError
    def test_usuario_inexistente_lanca_excecao(self, service: UserService) -> None:
        with pytest.raises(UserNotFoundError):
            service.update_profile("id-que-nao-existe", first_name="Ana")

    # CT-15.2: atualização de first_name persiste e retorna usuário atualizado
    def test_atualiza_first_name(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        result = service.update_profile(saved_user.id, first_name="Joana")

        assert result.first_name == "Joana"
        assert result.last_name == saved_user.last_name

    # CT-15.3: atualização de last_name persiste e retorna usuário atualizado
    def test_atualiza_last_name(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        result = service.update_profile(saved_user.id, last_name="Souza")

        assert result.last_name == "Souza"
        assert result.first_name == saved_user.first_name

    # CT-15.4: atualização de email válido persiste o novo email
    def test_atualiza_email(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        result = service.update_profile(saved_user.id, email="novo@example.com")

        assert result.email.value == "novo@example.com"

    # CT-15.5: atualização de username válido persiste o novo username
    def test_atualiza_username(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        result = service.update_profile(saved_user.id, username="novo.username")

        assert result.username.value == "novo.username"

    # CT-15.6 (CA-02): updated_at é atualizado a cada mudança
    def test_updated_at_e_atualizado(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        original_updated_at = saved_user.updated_at

        result = service.update_profile(saved_user.id, first_name="Joana")

        assert result.updated_at > original_updated_at

    # CT-15.7 (CA-03): email duplicado (de outro usuário) lança EmailAlreadyExistsError
    def test_email_duplicado_lanca_excecao(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
        saved_user: User,
    ) -> None:
        outro = User(
            username=Username("outro.usuario"),
            email=Email("outro@example.com"),
            hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
            first_name="Outro",
            last_name="Usuario",
        )
        fake_repo.save(outro)

        with pytest.raises(EmailAlreadyExistsError):
            service.update_profile(saved_user.id, email="outro@example.com")

    # CT-15.8 (CA-04): username duplicado lança UsernameAlreadyExistsError
    def test_username_duplicado_lanca_excecao(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
        saved_user: User,
    ) -> None:
        outro = User(
            username=Username("outro.usuario"),
            email=Email("outro@example.com"),
            hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
            first_name="Outro",
            last_name="Usuario",
        )
        fake_repo.save(outro)

        with pytest.raises(UsernameAlreadyExistsError):
            service.update_profile(saved_user.id, username="outro.usuario")

    # CT-15.9 (CA-05): email inválido lança InvalidEmailError
    def test_email_invalido_lanca_excecao(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        with pytest.raises(InvalidEmailError):
            service.update_profile(saved_user.id, email="nao-e-um-email")

    # CT-15.10 (CA-06): username inválido (curto demais) lança InvalidUsernameError
    def test_username_invalido_lanca_excecao(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        with pytest.raises(InvalidUsernameError):
            service.update_profile(saved_user.id, username="curto")

    # CT-15.11 (CA-10): payload vazio não altera nenhum campo nem updated_at
    def test_payload_vazio_nao_altera_usuario(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        original_updated_at = saved_user.updated_at
        original_email = saved_user.email
        original_username = saved_user.username
        original_first_name = saved_user.first_name
        original_last_name = saved_user.last_name

        result = service.update_profile(saved_user.id)

        assert result.email == original_email
        assert result.username == original_username
        assert result.first_name == original_first_name
        assert result.last_name == original_last_name
        assert result.updated_at == original_updated_at

    # CT-15.12 (CA-10): atualização parcial preserva campos não informados
    def test_atualizacao_parcial_preserva_outros_campos(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        email_original = saved_user.email
        username_original = saved_user.username

        result = service.update_profile(saved_user.id, first_name="Joana")

        assert result.email == email_original
        assert result.username == username_original
        assert result.last_name == saved_user.last_name

    # CT-15.13: usuário pode atualizar para o próprio email sem 409
    def test_mesmo_email_do_proprio_usuario_nao_conflita(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        result = service.update_profile(saved_user.id, email=saved_user.email.value)

        assert result.email == saved_user.email

    # CT-15.14: usuário pode atualizar para o próprio username sem 409
    def test_mesmo_username_do_proprio_usuario_nao_conflita(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        result = service.update_profile(
            saved_user.id, username=saved_user.username.value
        )

        assert result.username == saved_user.username

    # CT-15.15 (CA-09): nome inválido lança InvalidNameError
    def test_first_name_invalido_lanca_excecao(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        with pytest.raises(InvalidNameError):
            service.update_profile(saved_user.id, first_name="   ")

    # CT-15.16: atualização persiste no repositório
    def test_atualizacao_persiste_no_repositorio(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
        saved_user: User,
    ) -> None:
        service.update_profile(saved_user.id, first_name="Persistida")

        fetched = fake_repo.find_by_id(saved_user.id)
        assert fetched is not None
        assert fetched.first_name == "Persistida"

    # US-26: atualização de demografia altera só os campos informados
    def test_update_profile_atualiza_demografia(
        self,
        service: UserService,
        fake_repo: FakeUserRepository,
        saved_user: User,
    ) -> None:
        result = service.update_profile(saved_user.id, age=45, city="Florianópolis")

        assert result.age == 45
        assert result.city == "Florianópolis"
        # campos não informados não são tocados
        assert result.area is None
        assert result.gender is None
        fetched = fake_repo.find_by_id(saved_user.id)
        assert fetched is not None
        assert fetched.age == 45

    # US-26: demografia inválida no update lança exceção de domínio
    def test_update_profile_demografia_invalida_lanca_excecao(
        self,
        service: UserService,
        saved_user: User,
    ) -> None:
        with pytest.raises(InvalidAgeError):
            service.update_profile(saved_user.id, age=999)


class TestUserServiceChangePassword:
    """Testes de UserService.change_password (US-16)."""

    CURRENT_HASH = "$2b$12$currenthash"
    CURRENT_PLAIN = "S3nh@Atual!"
    NEW_PLAIN = "N0v@Senha!"
    NEW_HASH = "$2b$12$newhash"

    def _make_spy(self, verify_returns: list[bool]) -> PasswordHasher:
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.verify.side_effect = verify_returns
        spy.hash.return_value = self.NEW_HASH
        return spy

    def _make_service(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
        spy: PasswordHasher,
    ) -> UserService:
        return UserService(
            user_repo=fake_repo,
            access_level_repo=fake_access_level_repo,
            password_hasher=spy,
        )

    def _saved_user(self, fake_repo: FakeUserRepository) -> User:
        user = User(
            username=Username("maria.silva"),
            email=Email("maria@example.com"),
            hashed_password=HashedPassword(self.CURRENT_HASH),
            first_name="Maria",
            last_name="Silva",
        )
        return fake_repo.save(user)

    # CT-16.1 (CA-01): senha atual correta + nova válida → sucesso
    def test_senha_atual_correta_e_nova_valida_retorna_usuario(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        result = service.change_password(user.id, self.CURRENT_PLAIN, self.NEW_PLAIN)

        assert result.hashed_password.value == self.NEW_HASH

    # CT-16.2: spy — hash chamado exatamente 1 vez com a nova senha
    def test_hash_chamado_exatamente_uma_vez(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        service.change_password(user.id, self.CURRENT_PLAIN, self.NEW_PLAIN)

        spy.hash.assert_called_once_with(self.NEW_PLAIN)

    # CT-16.3 (CA-02): updated_at é atualizado após troca
    def test_updated_at_e_atualizado(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)
        original_updated_at = user.updated_at

        result = service.change_password(user.id, self.CURRENT_PLAIN, self.NEW_PLAIN)

        assert result.updated_at > original_updated_at

    # CT-16.4 (CA-03): senha atual incorreta → InvalidCredentialsError
    def test_senha_atual_incorreta_lanca_excecao(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        with pytest.raises(InvalidCredentialsError):
            service.change_password(user.id, "senha-errada", self.NEW_PLAIN)

    # CT-16.5 (CA-04): nova senha igual à atual → SamePasswordError
    def test_nova_senha_igual_a_atual_lanca_excecao(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, True])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        with pytest.raises(SamePasswordError):
            service.change_password(user.id, self.CURRENT_PLAIN, self.CURRENT_PLAIN)

    # CT-16.6 (CA-05): nova senha fraca → WeakPasswordError
    def test_nova_senha_fraca_lanca_excecao(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        with pytest.raises(WeakPasswordError):
            service.change_password(user.id, self.CURRENT_PLAIN, "fraca")

    # CT-16.7: usuário não encontrado → UserNotFoundError
    def test_usuario_inexistente_lanca_excecao(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)

        with pytest.raises(UserNotFoundError):
            service.change_password(
                "id-inexistente", self.CURRENT_PLAIN, self.NEW_PLAIN
            )

    # CT-16.8: hash não é chamado se senha atual for incorreta
    def test_hash_nao_chamado_se_senha_atual_incorreta(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        with pytest.raises(InvalidCredentialsError):
            service.change_password(user.id, "errada", self.NEW_PLAIN)

        spy.hash.assert_not_called()

    # CT-16.9: troca persiste nova senha no repositório
    def test_nova_senha_persiste_no_repositorio(
        self,
        fake_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        spy = self._make_spy([True, False])
        service = self._make_service(fake_repo, fake_access_level_repo, spy)
        user = self._saved_user(fake_repo)

        service.change_password(user.id, self.CURRENT_PLAIN, self.NEW_PLAIN)

        fetched = fake_repo.find_by_id(user.id)
        assert fetched is not None
        assert fetched.hashed_password.value == self.NEW_HASH
