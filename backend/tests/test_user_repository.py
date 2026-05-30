from app.domain.user import Email, Gender, HashedPassword, User, Username
from app.ports.user_repository import UserRepository


def test_save_returns_user(repo: UserRepository, valid_user: User) -> None:
    saved = repo.save(valid_user)
    assert saved == valid_user


def test_save_then_find_by_id(repo: UserRepository, valid_user: User) -> None:
    repo.save(valid_user)
    found = repo.find_by_id(valid_user.id)
    assert found is not None
    assert found.id == valid_user.id


def test_save_then_find_by_email(repo: UserRepository, valid_user: User) -> None:
    repo.save(valid_user)
    found = repo.find_by_email(valid_user.email)
    assert found is not None
    assert found.email == valid_user.email


def test_save_then_find_by_username(repo: UserRepository, valid_user: User) -> None:
    repo.save(valid_user)
    found = repo.find_by_username(valid_user.username)
    assert found is not None
    assert found.username == valid_user.username


def test_find_by_id_nonexistent(repo: UserRepository) -> None:
    assert repo.find_by_id("inexistente") is None


def test_find_by_email_nonexistent(repo: UserRepository) -> None:
    assert repo.find_by_email(Email("naoexiste@example.com")) is None


def test_find_by_username_nonexistent(repo: UserRepository) -> None:
    assert repo.find_by_username(Username("naoexiste123")) is None


def test_round_trip_preserves_value_objects(
    repo: UserRepository, valid_user: User
) -> None:
    repo.save(valid_user)
    found = repo.find_by_id(valid_user.id)
    assert found is not None
    assert isinstance(found.email, Email)
    assert isinstance(found.username, Username)
    assert isinstance(found.hashed_password, HashedPassword)
    assert found.email == valid_user.email
    assert found.username == valid_user.username
    assert found.hashed_password == valid_user.hashed_password


def test_round_trip_preserves_demographics(repo: UserRepository) -> None:
    """US-26: campos demográficos sobrevivem ao round-trip de persistência."""
    user = User(
        username=Username("demo.user"),
        email=Email("demo@example.com"),
        hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        first_name="Demo",
        last_name="User",
        age=30,
        area="Engenharia",
        gender=Gender.OUTRO,
        city="Porto Alegre",
    )
    repo.save(user)
    found = repo.find_by_id(user.id)
    assert found is not None
    assert found.age == 30
    assert isinstance(found.age, int)
    assert found.area == "Engenharia"
    assert found.gender is Gender.OUTRO
    assert found.city == "Porto Alegre"


def test_round_trip_demographics_ausentes_continuam_none(
    repo: UserRepository, valid_user: User
) -> None:
    """US-26: usuário sem demografia round-trips com os campos em None."""
    repo.save(valid_user)
    found = repo.find_by_id(valid_user.id)
    assert found is not None
    assert found.age is None
    assert found.area is None
    assert found.gender is None
    assert found.city is None


def test_save_overwrites_existing(repo: UserRepository, valid_user: User) -> None:
    repo.save(valid_user)
    valid_user.deactivate()
    repo.save(valid_user)
    found = repo.find_by_id(valid_user.id)
    assert found is not None
    assert found.is_active is False


def test_find_all_repo_vazio(repo: UserRepository) -> None:
    """US-14: lista vazia retorna pagina vazia sem cursor."""
    page = repo.find_all(limit=10)
    assert page.items == []
    assert page.next_cursor is None


def test_find_all_paginates(repo: UserRepository) -> None:
    """US-14: 5 users paginados de 2 em 2 retornam todos exatamente uma vez.

    Testa a propriedade de paginacao sem assumir ordem especifica
    (Dynamo Scan nao garante ordem; o teste so exige cobertura completa
    sem repeticao). Cobre fake e dynamo (parametrizado pela fixture repo).
    """
    ids_criados: list[str] = []
    for i in range(1, 6):
        u = User(
            id=f"user-{i:04d}",
            username=Username(f"user.{i:04d}"),
            email=Email(f"u{i}@example.com"),
            hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
            first_name="Test",
            last_name=f"User{i}",
        )
        repo.save(u)
        ids_criados.append(u.id)

    coletados: list[str] = []
    cursor: str | None = None
    while True:
        page = repo.find_all(limit=2, cursor=cursor)
        coletados.extend(u.id for u in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert sorted(coletados) == sorted(ids_criados)
