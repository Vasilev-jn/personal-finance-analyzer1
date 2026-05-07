from finance_app.services import auth_service


def test_password_record_roundtrip():
    record = auth_service.create_password_record("secret-123")
    assert record["algo"] == "pbkdf2_sha256"
    assert auth_service.verify_password("secret-123", record) is True
    assert auth_service.verify_password("wrong", record) is False
    assert auth_service.record_secret(record)
