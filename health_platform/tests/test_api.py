"""FastAPI 合同、OpenAPI、Probe 与敏感信息测试。"""

from fastapi.testclient import TestClient

from health_platform.platform.web.app import create_app


def test_probe_lifecycle_and_openapi() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").json() == {"status": "ready"}
        schema = client.get("/openapi.json").json()
        assert "/api/v1/identity/register" in schema["paths"]


def test_register_login_me_and_no_password_leak() -> None:
    app = create_app()
    with TestClient(app) as client:
        body = {
            "email": "alice@example.com",
            "username": "alice",
            "display_name": "Alice",
            "password": "correct horse battery staple",
        }
        registered = client.post("/api/v1/identity/register", json=body)
        assert registered.status_code == 201
        assert "password" not in registered.text
        login = client.post(
            "/api/v1/identity/login",
            json={
                "identifier": "ALICE",
                "password": body["password"],
                "client_id": "flutter",
                "device_name": "phone",
                "client_type": "flutter",
            },
        )
        assert login.status_code == 200
        access = login.json()["access_token"]
        me = client.get("/api/v1/identity/me", headers={"Authorization": f"Bearer {access}"})
        assert me.json()["username"] == "alice"
        assert access not in me.text


def test_login_enumeration_error_model_is_stable() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/identity/login",
            json={
                "identifier": "unknown",
                "password": "wrong password",
                "client_id": "app",
                "device_name": "phone",
                "client_type": "flutter",
            },
        )
        assert response.status_code == 401
        assert response.json()["error_code"] == "IDENTITY_INVALID_CREDENTIALS"
        assert "trace_id" in response.json()


def test_discovery_jwks_fixed_rs256() -> None:
    with TestClient(create_app()) as client:
        discovery = client.get("/api/v1/.well-known/openid-configuration").json()
        assert discovery["code_challenge_methods_supported"] == ["S256"]
        assert discovery["id_token_signing_alg_values_supported"] == ["RS256"]
        keys = client.get("/api/v1/.well-known/jwks.json").json()["keys"]
        assert keys and keys[0]["alg"] == "RS256"
        assert "d" not in keys[0]
