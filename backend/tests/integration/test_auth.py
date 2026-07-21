import pytest

from app.application.auth.login_use_case import LoginUseCase, LogoutUseCase, RefreshTokenUseCase
from app.application.auth.register_use_case import RegisterUserUseCase
from app.domain.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.infrastructure.db.models.enums import UserRole
from app.infrastructure.repositories.user_repository import UserRepository


async def test_register_and_login_flow(db_session):
    repo = UserRepository(db_session)
    register = RegisterUserUseCase(repo)

    user = await register.execute(
        username="grid_op_delhi",
        email="grid_op_delhi@example.in",
        password="S3curePass!23",
        full_name="Delhi Grid Operator",
        role=UserRole.GRID_OPERATOR,
    )
    await db_session.commit()
    assert user.username == "grid_op_delhi"
    assert user.role == UserRole.GRID_OPERATOR

    login = LoginUseCase(repo)
    logged_in_user, access_token, refresh_token = await login.execute(
        username="grid_op_delhi", password="S3curePass!23"
    )
    await db_session.commit()
    assert logged_in_user.id == user.id
    assert access_token
    assert refresh_token


async def test_duplicate_username_rejected(db_session):
    repo = UserRepository(db_session)
    register = RegisterUserUseCase(repo)
    await register.execute(
        username="engineer1", email="e1@example.in", password="password123",
        full_name="Engineer One", role=UserRole.ENGINEER,
    )
    await db_session.commit()

    with pytest.raises(UserAlreadyExistsError):
        await register.execute(
            username="engineer1", email="different@example.in", password="password123",
            full_name="Duplicate", role=UserRole.ENGINEER,
        )


async def test_login_with_wrong_password_rejected(db_session):
    repo = UserRepository(db_session)
    register = RegisterUserUseCase(repo)
    await register.execute(
        username="researcher1", email="r1@example.in", password="correct-password",
        full_name="Researcher One", role=UserRole.RESEARCHER,
    )
    await db_session.commit()

    login = LoginUseCase(repo)
    with pytest.raises(InvalidCredentialsError):
        await login.execute(username="researcher1", password="wrong-password")


async def test_refresh_and_logout_flow(db_session):
    repo = UserRepository(db_session)
    register = RegisterUserUseCase(repo)
    await register.execute(
        username="admin1", email="admin1@example.in", password="adminpass1",
        full_name="Admin One", role=UserRole.ADMIN,
    )
    await db_session.commit()

    login = LoginUseCase(repo)
    _, access_token, refresh_token = await login.execute(username="admin1", password="adminpass1")
    await db_session.commit()

    refresh = RefreshTokenUseCase(repo)
    new_access_token = await refresh.execute(refresh_token=refresh_token)
    assert new_access_token

    logout = LogoutUseCase(repo)
    await logout.execute(refresh_token=refresh_token)
    await db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        await refresh.execute(refresh_token=refresh_token)
