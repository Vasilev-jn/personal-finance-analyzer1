from finance_app.services import auth_service


def test_password_record_roundtrip():
    record = auth_service.create_password_record("secret-123")
    assert record["algo"] == "argon2id"
    assert record["hash"].startswith("$argon2id$")
    assert auth_service.verify_password("secret-123", record) is True
    assert auth_service.verify_password("wrong", record) is False
    assert auth_service.password_needs_rehash(record) is False
    assert auth_service.record_secret(record)


def test_pbkdf2_password_record_is_accepted_but_needs_rehash():
    record = auth_service.create_pbkdf2_password_record("secret-123")
    assert record["algo"] == "pbkdf2_sha256"
    assert auth_service.verify_password("secret-123", record) is True
    assert auth_service.verify_password("wrong", record) is False
    assert auth_service.password_needs_rehash(record) is True
