"""测试 auth — 注册 / 登录 / me / 错误码"""
import random
import pytest


class TestRegister:
    def test_register_ok(self, client):
        phone = f"139{random.randint(10000000, 99999999)}"
        r = client.post("/api/v1/auth/register", json={
            "phone": phone, "password": "test2026", "nickname": "测试用户"
        })
        assert r.status_code == 200
        d = r.json()
        assert "token" in d
        assert "qingnang_id" in d
        assert d["qingnang_id"].startswith("QN-")

    def test_register_short_password(self, client):
        phone = f"139{random.randint(10000000, 99999999)}"
        r = client.post("/api/v1/auth/register", json={
            "phone": phone, "password": "123", "nickname": "短密码"
        })
        assert r.status_code in (422, 400), f"期望 422/400 实际 {r.status_code}"


class TestLogin:
    def test_login_ok(self, client, auth_headers):
        phone = f"139{random.randint(10000000, 99999999)}"
        client.post("/api/v1/auth/register", json={
            "phone": phone, "password": "mypass123", "nickname": "登录测试"
        })
        r = client.post("/api/v1/auth/login", json={
            "phone": phone, "password": "mypass123"
        })
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_wrong_password(self, client, auth_headers):
        phone = f"139{random.randint(10000000, 99999999)}"
        client.post("/api/v1/auth/register", json={
            "phone": phone, "password": "correct", "nickname": "登录测试"
        })
        r = client.post("/api/v1/auth/login", json={
            "phone": phone, "password": "wrongpass"
        })
        assert r.status_code == 401

    def test_login_nonexistent_phone(self, client):
        r = client.post("/api/v1/auth/login", json={
            "phone": "13900000000", "password": "whatever"
        })
        assert r.status_code == 401


class TestMe:
    def test_me_ok(self, client, auth_headers):
        r = client.get("/api/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        # me 端点返回用户基本信息（不含 password_hash）
        assert "qingnang_id" in d
        assert "nickname" in d

    def test_me_no_token(self, client):
        """不带 token — 依赖注入拒绝（422 或 401 都算正常拒绝）"""
        r = client.get("/api/v1/auth/me")
        assert r.status_code in (401, 403, 422)

    def test_me_bad_token(self, client):
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": "Bearer garbage.token.here"})
        assert r.status_code in (401, 403, 422)
