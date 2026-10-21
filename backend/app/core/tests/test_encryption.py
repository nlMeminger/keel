from app.core.encryption import decrypt, encrypt


def test_encrypt_round_trips() -> None:
    assert decrypt(encrypt("access-sandbox-abc123")) == "access-sandbox-abc123"


def test_encrypt_does_not_return_the_plaintext() -> None:
    ciphertext = encrypt("access-sandbox-abc123")
    assert "access-sandbox-abc123" not in ciphertext
