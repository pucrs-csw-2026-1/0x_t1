from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.application.user_service import UserService
from app.domain.exceptions import (
    AccessLevelNotFoundError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidNameError,
    InvalidUsernameError,
    SamePasswordError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: str = Field(
        ...,
        description="ID único do usuário.",
        examples=["bd0babc3-bd93-443d-aefb-5193f5e1f08c"],
    )
    first_name: str = Field(..., description="Nome do usuário.", examples=["Juca"])
    last_name: str = Field(..., description="Sobrenome do usuário.", examples=["Bala"])
    username: str = Field(..., description="Nome de usuário.", examples=["juca.bala"])
    email: str = Field(
        ..., description="Endereço de email do usuário.", examples=["juca@email.com"]
    )
    access_level: list[str] = Field(
        ...,
        description="Níveis de acesso do usuário.",
        examples=[["9e556479-7003-5916-9cd6-33f4227cec9b"]],
    )
    is_active: bool = Field(
        ..., description="Indica se o usuário está ativo.", examples=[True]
    )
    created_at: datetime = Field(
        ...,
        description="Data de criação do usuário.",
        examples=["2026-05-08T04:55:07.913746Z"],
    )


class UserUpdate(BaseModel):
    first_name: str | None = Field(
        None, description="Novo primeiro nome.", examples=["Juca"]
    )
    last_name: str | None = Field(
        None, description="Novo sobrenome.", examples=["Bala"]
    )
    email: str | None = Field(
        None, description="Novo email.", examples=["juca@email.com"]
    )
    username: str | None = Field(
        None, description="Novo username.", examples=["juca.bala"]
    )


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(
        ..., description="Senha atual do usuário.", examples=["Senha@123"]
    )
    new_password: str = Field(
        ...,
        description=(
            "Nova senha. Deve ter ao menos 8 caracteres com "
            "maiúscula, minúscula, número e caractere especial."
        ),
        examples=["NovaSenha@456"],
    )


class UserCreate(BaseModel):
    first_name: str = Field(
        ...,
        description="Nome do usuário. Deve conter pelo menos 2 caracteres.",
        examples=["Juca"],
    )
    last_name: str = Field(
        ...,
        description="Sobrenome do usuário. Deve conter pelo menos 2 caracteres.",
        examples=["Bala"],
    )
    username: str = Field(
        ...,
        description="Nome de usuário. Deve conter entre 3 e 20 caracteres.",
        examples=["juca.bala"],
    )
    email: str = Field(
        ..., description="Endereço de email do usuário.", examples=["juca@email.com"]
    )
    password: str = Field(
        ...,
        description=(
            "Senha do usuário. Deve conter pelo menos 8 caracteres "
            "com pelo menos uma letra maiúscula, uma letra minúscula, "
            "um número e um caractere especial."
        ),
        examples=["Senha@123"],
    )
    access_level: list[str] | None = Field(
        default=None,
        deprecated=True,
        description="Ignorado. Cadastro público sempre cria perfil 'user'.",
    )


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username.value,
        email=user.email.value,
        access_level=user.access_level,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=200,
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        404: {"description": "Usuário não encontrado."},
    },
    description=(
        "Retorna os dados do usuário autenticado.\n\n"
        "Requer `Authorization: Bearer <access_token>` no header. "
        "Para testar via Swagger UI, clique em **Authorize** (cadeado) "
        "antes de executar."
    ),
)
def get_me(
    user_id: Annotated[str, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Retorna os dados do usuário autenticado."""
    try:
        user = user_service.get_user_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_user_response(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=200,
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        404: {"description": "Usuário não encontrado."},
        409: {"description": "Email ou username já cadastrado."},
        422: {"description": "Dados inválidos (email, username ou nome)."},
    },
    description=(
        "Atualiza o perfil do usuário autenticado.\n\n"
        "Requer `Authorization: Bearer <access_token>` no header. "
        "Todos os campos são opcionais — apenas os informados são alterados."
    ),
)
def update_me(
    payload: UserUpdate,
    user_id: Annotated[str, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Atualiza campos do perfil do usuário autenticado."""
    try:
        user = user_service.update_profile(
            user_id=user_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            username=payload.username,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (EmailAlreadyExistsError, UsernameAlreadyExistsError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (InvalidEmailError, InvalidUsernameError, InvalidNameError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return to_user_response(user)


@router.put(
    "/me/password",
    status_code=204,
    responses={
        400: {"description": "Nova senha igual à senha atual."},
        401: {"description": "Token inválido ou senha atual incorreta."},
        422: {"description": "Nova senha fraca."},
    },
    description=(
        "Troca a senha do usuário autenticado.\n\n"
        "Requer `Authorization: Bearer <access_token>` no header."
    ),
)
def change_password(
    payload: PasswordChangeRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Troca a senha do usuário autenticado."""
    try:
        user_service.change_password(
            user_id=user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except SamePasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    responses={
        201: {"description": "Usuário criado com sucesso."},
        400: {"description": "Dados inválidos (email, senha, username ou nome)."},
        409: {"description": "Email já cadastrado."},
        500: {"description": "Catálogo de níveis de acesso não provisionado."},
    },
)
def register_user(
    payload: UserCreate, user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """Cria uma nova conta de usuário."""
    try:
        user = user_service.register(
            first_name=payload.first_name,
            last_name=payload.last_name,
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (
        InvalidEmailError,
        WeakPasswordError,
        InvalidUsernameError,
        InvalidNameError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AccessLevelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Catálogo de níveis de acesso não provisionado. "
                "Verifique a infraestrutura (terraform apply)."
            ),
        ) from exc
    return to_user_response(user)


@router.delete(
    "/me",
    status_code=204,
    responses={
        204: {"description": "Conta desativada com sucesso."},
        401: {"description": "Token ausente, inválido ou expirado."},
    },
    description=(
        "Desativa a conta do usuário autenticado (soft delete).\n\n"
        "Requer `Authorization: Bearer <access_token>` no header. "
        "Para testar via Swagger UI, clique em **Authorize** (cadeado) "
        "antes de executar."
    ),
)
def deactivate_me(
    user_id: Annotated[str, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Desativa a conta do usuário autenticado (soft delete).

    Marca is_active=False, revoga todos os refresh tokens ativos e preserva o histórico.
    """
    try:
        user_service.deactivate(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
