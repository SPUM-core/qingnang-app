"""测试 ppg — upload / history"""
import pytest


class TestPPGUpload:
    def test_upload_ok(self, client, onboarded_user):
        r = client.post("/api/v1/ppg/upload", headers=onboarded_user, json={
            "sqi": 78.5,
            "delta_f": {"wood": 0.02, "fire": -0.03, "earth": 0.01, "metal": 0, "water": -0.02},
            "v_obs": {"wood": 57, "fire": 28, "earth": 62, "metal": 44, "water": 49},
            "syndrome_hint": "五形基本调和，火形略偏弱",
        })
        assert r.status_code == 200, f"upload {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "observation_id" in d

    def test_upload_no_onboarding(self, client, auth_headers):
        """没建档 — 可能 400/404/422 各种拒绝，不应该 200"""
        r = client.post("/api/v1/ppg/upload", headers=auth_headers, json={
            "sqi": 70.0,
            "delta_f": {"wood": 0.0},
            "v_obs": {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50},
        })
        assert r.status_code != 200, "没建档不应该 upload 成功"

    def test_upload_missing_sqi(self, client, onboarded_user):
        r = client.post("/api/v1/ppg/upload", headers=onboarded_user, json={
            "delta_f": {"wood": 0.0},
            "v_obs": {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50},
        })
        # Pydantic 校验 → 422
        assert r.status_code == 422

    def test_upload_multiple(self, client, onboarded_user):
        """连续上传 3 次"""
        for i in range(3):
            r = client.post("/api/v1/ppg/upload", headers=onboarded_user, json={
                "sqi": 70.0 + i * 5,
                "delta_f": {"wood": i * 0.01},
                "v_obs": {"wood": 50 + i, "fire": 50, "earth": 50, "metal": 50, "water": 50},
            })
            assert r.status_code == 200, f"第{i+1}次 upload 失败: {r.status_code}"


class TestPPGHistory:
    def test_history_empty(self, client, onboarded_user):
        r = client.get("/api/v1/ppg/history", headers=onboarded_user)
        assert r.status_code == 200
