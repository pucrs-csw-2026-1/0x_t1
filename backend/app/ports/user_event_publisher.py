from abc import ABC, abstractmethod

from app.domain.user import User


class UserEventPublisher(ABC):
    """Port outbound para publicação de eventos de domínio de usuário.

    Mantém o Auth desacoplado do mecanismo de mensageria: a aplicação
    pede a publicação de um evento e o adapter concreto (ex.: SNS) decide
    o transporte.
    """

    @abstractmethod
    def publish_profile_changed(self, user: User) -> None:
        """Publica o evento ``UserProfileChanged`` com a demografia e o papel
        atuais do usuário.

        A implementação pode lançar exceções de infraestrutura; cabe ao
        chamador decidir a política (no Auth, a publicação é best-effort —
        ver ``UserService``).
        """
        ...
