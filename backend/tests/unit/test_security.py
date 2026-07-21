import uuid

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domain.exceptions import InvalidTokenError


def test_password_hash_roundtrip():
    plain = "S3curePass!23"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id, role="engineer")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "engineer"


def test_refresh_token_roundtrip():
    user_id = uuid.uuid4()
    token, expires_at = create_refresh_token(subject=user_id)
    payload = decode_token(token, expected_type="refresh")
    assert payload["sub"] == str(user_id)
    assert expires_at is not None


def test_token_type_mismatch_rejected():
    user_id = uuid.uuid4()
    access_token = create_access_token(subject=user_id, role="admin")
    with pytest.raises(InvalidTokenError):
        decode_token(access_token, expected_type="refresh")


def test_garbage_token_rejected():
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-real-token", expected_type="access")
