"""测试安全 — 响应头 / CORS / 注入防护"""
import pytest


class TestSecurityHeaders:
    """每个响应都必须带安全头"""

    EXPECTED_HEADERS = [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Permissions-Policy", None),       # 只检查存在
        ("Referrer-Policy", None),          # 只检查存在
        ("Content-Security-Policy", None),  # 只检查存在
    ]

    @pytest.mark.parametrize("path", [
        "/health",
        "/api/v1/knowledge/",
    ])
    def test_public_endpoint_headers(self, client, path):
        r = client.get(path)
        for h, expected in self.EXPECTED_HEADERS:
            val = r.headers.get(h)
            assert val is not None, f"{path} 缺失安全头 {h}"
            if expected is not None:
                assert val == expected, f"{path} {h} 值错误: {val}"

    def test_authenticated_endpoint_headers(self, client, auth_headers):
        r = client.get("/api/v1/auth/me", headers=auth_headers)
        for h, _ in self.EXPECTED_HEADERS:
            assert r.headers.get(h) is not None, f"auth/me 缺失 {h}"

    def test_csp_frame_ancestors_none(self, client):
        r = client.get("/health")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp, f"CSP 缺少 frame-ancestors: {csp}"

    def test_csp_default_self(self, client):
        r = client.get("/health")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp


class TestCORS:
    def test_allowed_origin(self, client):
        r = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"

    def test_disallowed_origin_no_wildcard(self, client):
        r = client.get("/health", headers={"Origin": "https://evil.com"})
        ao = r.headers.get("Access-Control-Allow-Origin", "")
        assert ao != "*"  # 绝对不能通配
        # 可能返回空（白名单外不允许）
        assert ao != "https://evil.com"


class TestInputSanitization:
    """基础的输入校验 — 防止注入"""

    def test_auth_register_rejects_sql_injection_phone(self, client):
        phone = "'; DROP TABLE users; --"
        r = client.post("/api/v1/auth/register", json={
            "phone": phone, "password": "test2026", "nickname": "x"
        })
        # 应该 422（phone 格式校验失败）或 400 — 不能 200
        assert r.status_code != 200, f"SQL 注入 phone 竟然通过了!"

    def test_auth_login_rejects_special_chars_phone(self, client):
        r = client.post("/api/v1/auth/login", json={
            "phone": "xxx<script>alert(1)</script>", "password": "x"
        })
        assert r.status_code != 200

    def test_knowledge_returns_no_html(self, client, auth_headers):
        """knowledge 端点返回的 content 不应有 HTML 标签"""
        r = client.get("/api/v1/knowledge/", headers=auth_headers)
        assert r.status_code == 200, f"knowledge {r.status_code} {r.text[:200]}"
        items = r.json().get("items", [])
        for it in items:
            content = it.get("summary", "") + it.get("title", "")
            assert "<script" not in content.lower(), f"知识卡片含 script 标签: {it['id']}"


class TestHTTPSOnlyInProduction:
    """生产环境必须 HSTS"""
    # 这个在本地 test 环境不触发，留给部署阶段手动验证
    pass
