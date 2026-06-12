"""Person router: idempotent sync and ui_prefs."""

from .conftest import client


def test_person_sync_creates_and_is_idempotent(make_auth_token) -> None:
    """POST /person/sync creates Person on first call, idempotent on repeat."""
    token = make_auth_token(email="sync_test@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/api/v1/person/sync", headers=headers)
    assert first.status_code == 200
    data = first.json()
    assert data["email"] == "sync_test@example.com"
    assert data["display_name"] == "sync_test"

    second = client.post("/api/v1/person/sync", headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == data["id"]


def test_person_prefs_accepts_valid_keys(make_user) -> None:
    """PATCH /person/prefs updates ui_prefs and returns updated object."""
    headers = make_user("prefs_test@example.com")

    response = client.patch(
        "/api/v1/person/prefs",
        headers=headers,
        json={"text_size": "large", "contrast": "high"},
    )
    assert response.status_code == 200
    prefs = response.json()
    assert prefs["text_size"] == "large"
    assert prefs["contrast"] == "high"
