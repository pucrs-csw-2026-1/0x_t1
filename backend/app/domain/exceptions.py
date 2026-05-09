class DomainError(Exception):
    """Classe base para todas as exceções de domínio."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidEmailError(DomainError):
    """Exceção para email inválido."""

    def __init__(self, email: str) -> None:
        super().__init__(f"Email inválido: {email}")


class WeakPasswordError(DomainError):
    """Exceção para senha fraca."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Senha fraca: {reason}")


class InvalidUsernameError(DomainError):
    """Exceção para nome de usuário inválido."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Nome de usuário inválido: {reason}")


class InvalidNameError(DomainError):
    """Exceção para nome inválido."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Nome inválido: {reason}")


class EmailAlreadyExistsError(DomainError):
    """Exceção para email já existente."""

    def __init__(self, email: str) -> None:
        super().__init__(f"Email já cadastrado: {email}")


class UsernameAlreadyExistsError(DomainError):
    """Exceção para nome de usuário já existente."""

    def __init__(self, username: str) -> None:
        super().__init__(f"Nome de usuário já cadastrado: {username}")


class InvalidCredentialsError(DomainError):
    """Exceção para credenciais inválidas."""

    def __init__(self) -> None:
        super().__init__("Credenciais inválidas.")


class InvalidTokenError(DomainError):
    """Exceção para token inválido."""

    def __init__(self) -> None:
        super().__init__("Token inválido.")


class TokenExpiredError(DomainError):
    """Exceção para token expirado."""

    def __init__(self) -> None:
        super().__init__("Token expirado.")


class TokenRevokedError(DomainError):
    """Exceção para token revogado."""

    def __init__(self) -> None:
        super().__init__("Token revogado.")


class InsufficientScopeError(DomainError):
    """Exceção para escopo insuficiente."""

    def __init__(self, required: str) -> None:
        super().__init__(f"Permissão insuficiente: requer '{required}'.")


class UserNotFoundError(DomainError):
    """Exceção para usuário não encontrado."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"Usuário não encontrado: {user_id}")


class AccessLevelNotFoundError(DomainError):
    """Exceção para nível de acesso não encontrado."""

    def __init__(self, title: str) -> None:
        super().__init__(f"Nível de acesso não encontrado: {title}")


class InvalidPaginationError(DomainError):
    """Exceção para parâmetros de paginação inválidos."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Parâmetros de paginação inválidos: {reason}")
