from app.domain.user import Email, HashedPassword, User, Username
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


def test_save_overwrites_existing(repo: UserRepository, valid_user: User) -> None:
    repo.save(valid_user)
    valid_user.deactivate()
    repo.save(valid_user)
    found = repo.find_by_id(valid_user.id)
    assert found is not None
    assert found.is_active is False
