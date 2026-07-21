from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.application.auth.login_use_case import LoginUseCase, LogoutUseCase, RefreshTokenUseCase
from app.application.auth.register_use_case import RegisterUserUseCase
from app.core.config import get_settings
from app.core.rbac import require_admin
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.user_repository import UserRepository
from app.schemas.auth_schemas import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> UserOut:
    """Create a new user. Restricted to admins — roles are assigned deliberately, not self-selected."""
    use_case = RegisterUserUseCase(UserRepository(session))
    user = await use_case.execute(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    use_case = LoginUseCase(UserRepository(session))
    user, access_token, refresh_token = await use_case.execute(
        username=payload.username, password=payload.password
    )
    # The refresh token is returned in the body for API-client simplicity here;
    # the frontend (Phase 5) is expected to store it as an httpOnly cookie rather
    # than in JS-accessible storage.
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(payload: RefreshRequest, session: AsyncSession = Depends(get_session)) -> AccessTokenResponse:
    use_case = RefreshTokenUseCase(UserRepository(session))
    access_token = await use_case.execute(refresh_token=payload.refresh_token)
    return AccessTokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, session: AsyncSession = Depends(get_session)) -> None:
    use_case = LogoutUseCase(UserRepository(session))
    await use_case.execute(refresh_token=payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
