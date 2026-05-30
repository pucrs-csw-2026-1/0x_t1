from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceClient:
    """Identidade de máquina (principal de serviço) para o fluxo OAuth2
    client_credentials.

    Diferente de um usuário, não tem perfil/senha: autentica por
    `client_id` + `client_secret` e recebe um token com `principal_type=service`
    e os scopes concedidos ao cliente.
    """

    client_id: str
    secret: str
    scopes: list[str] = field(default_factory=list)
