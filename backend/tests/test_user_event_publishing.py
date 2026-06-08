"""Testes de publicação de UserProfileChanged a partir do UserService (US-29).

Verificam, com um spy do port UserEventPublisher, em quais ganchos o evento é
publicado (register, update_profile com demografia, admin_update com papel) e a
política best-effort (falha de publicação não quebra o fluxo).
"""

import pytest

from app.application.user_service import UserService
from app.domain.access_level import Role
from app.domain.user import Email, Gender, HashedPassword, User, Username
from tests.fakes.user_event_publisher import (
    FailingUserEventPublisher,
    SpyUserEventPublisher,
)
from tests.fakes.user_repository import FakeUserRepository


def _saved_user(repo: FakeUserRepository) -> User:
    user = User(
        username=Username("maria.silva"),
        email=Email("maria@example.com"),
        hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        first_name="Maria",
        last_name="Silva",
    )
    return repo.save(user)


class TestRegisterPublishes:
    # CT: cadastro publica exatamente um evento com o usuário recém-criado
    def test_register_publica_uma_vez(self, fake_repo: FakeUserRepository) -> None:
        spy = SpyUserEventPublisher()
        service = UserService(user_repo=fake_repo, event_publisher=spy)

        user = service.register(
            first_name="Ana",
            last_name="Souza",
            username="ana.souza",
            email="ana@example.com",
            password="S3nh@Forte!",
            age=28,
            gender=Gender.F,
        )

        assert len(spy.published) == 1
        assert spy.published[0].id == user.id
        assert spy.published[0].gender is Gender.F

    # CT (best-effort): falha ao publicar não quebra o cadastro
    def test_register_best_effort_nao_propaga_falha(
        self, fake_repo: FakeUserRepository
    ) -> None:
        service = UserService(
            user_repo=fake_repo,
            event_publisher=FailingUserEventPublisher(),
        )

        user = service.register(
            first_name="Ana",
            last_name="Souza",
            username="ana.souza",
            email="ana@example.com",
            password="S3nh@Forte!",
        )

        # cadastro concluiu e persistiu mesmo com o publisher falhando
        assert fake_repo.find_by_id(user.id) is not None

    # CT: sem publisher injetado, register é no-op de publicação (não falha)
    def test_register_sem_publisher_nao_falha(
        self, fake_repo: FakeUserRepository
    ) -> None:
        service = UserService(user_repo=fake_repo)

        user = service.register(
            first_name="Ana",
            last_name="Souza",
            username="ana.souza",
            email="ana@example.com",
            password="S3nh@Forte!",
        )

        assert fake_repo.find_by_id(user.id) is not None


class TestUpdateProfilePublishes:
    # CT: update com demografia publica o evento
    def test_update_com_demografia_publica(self, fake_repo: FakeUserRepository) -> None:
        spy = SpyUserEventPublisher()
        service = UserService(user_repo=fake_repo, event_publisher=spy)
        user = _saved_user(fake_repo)

        service.update_profile(user.id, age=40, city="Curitiba")

        assert len(spy.published) == 1
        assert spy.published[0].age == 40
        assert spy.published[0].city == "Curitiba"

    # CT (decisão/branch): update só de nome NÃO publica (não é demografia)
    def test_update_apenas_nome_nao_publica(
        self, fake_repo: FakeUserRepository
    ) -> None:
        spy = SpyUserEventPublisher()
        service = UserService(user_repo=fake_repo, event_publisher=spy)
        user = _saved_user(fake_repo)

        service.update_profile(user.id, first_name="Joana")

        assert spy.published == []

    # CT (decisão/branch): payload vazio não publica
    def test_update_vazio_nao_publica(self, fake_repo: FakeUserRepository) -> None:
        spy = SpyUserEventPublisher()
        service = UserService(user_repo=fake_repo, event_publisher=spy)
        user = _saved_user(fake_repo)

        service.update_profile(user.id)

        assert spy.published == []


class TestAdminUpdatePublishes:
    # CT: mudança de papel publica o evento com o novo access_level
    def test_admin_update_papel_publica(self, fake_repo: FakeUserRepository) -> None:
        spy = SpyUserEventPublisher()
        service = UserService(user_repo=fake_repo, event_publisher=spy)
        user = _saved_user(fake_repo)

        service.admin_update(
            admin_id="admin-1",
            target_user_id=user.id,
            access_level=Role.MANAGER,
        )

        assert len(spy.published) == 1
        assert spy.published[0].access_level is Role.MANAGER

    # CT (decisão/branch): mudar só is_active NÃO publica (papel inalterado)
    def test_admin_update_apenas_is_active_nao_publica(
        self, fake_repo: FakeUserRepository
    ) -> None:
        spy = SpyUserEventPublisher()
        service = UserService(user_repo=fake_repo, event_publisher=spy)
        user = _saved_user(fake_repo)

        service.admin_update(
            admin_id="admin-1",
            target_user_id=user.id,
            is_active=False,
        )

        assert spy.published == []

    # CT: best-effort também no admin_update
    def test_admin_update_best_effort(self, fake_repo: FakeUserRepository) -> None:
        service = UserService(
            user_repo=fake_repo,
            event_publisher=FailingUserEventPublisher(),
        )
        user = _saved_user(fake_repo)

        result = service.admin_update(
            admin_id="admin-1",
            target_user_id=user.id,
            access_level=Role.ADMIN,
        )

        assert result.access_level is Role.ADMIN


# CT: admin não pode alterar a si mesmo — regra mantida (não publica)
def test_admin_update_self_raises(fake_repo: FakeUserRepository) -> None:
    spy = SpyUserEventPublisher()
    service = UserService(user_repo=fake_repo, event_publisher=spy)
    user = _saved_user(fake_repo)

    with pytest.raises(ValueError):
        service.admin_update(
            admin_id=user.id,
            target_user_id=user.id,
            access_level=Role.ADMIN,
        )

    assert spy.published == []
