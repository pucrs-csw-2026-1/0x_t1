from app.domain.exceptions import UserNotFoundError
from app.domain.user import User
from app.ports.user_repository import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def get_user_by_id(self, user_id: str) -> User:
        """Busca e retorna o usuário pelo ID.

        Raises:
            UserNotFoundError: se nenhum usuário for encontrado com o ID fornecido.
        """
        user = self._user_repo.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user
