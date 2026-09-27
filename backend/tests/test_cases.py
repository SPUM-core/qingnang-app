"""测试 cases — onboarding / mine / reports"""
import pytest


class TestOnboarding:
    def test_onboarding_ok(self, client, auth_headers):
        r = client.post("/api/v1/cases/onboarding", json={
            "nickname": "测试", "gender": "male",
            "birth_date": "1992-03-15", "birth_hour": "午时",
            "birthplace": "上海", "engine": "spum_bazi",
            "v_innate": {"wood": 55, "fire": 30, "earth": 60, "metal": 45, "water": 50},
            "bazi_result": {"bazi": "壬申/癸卯/庚寅/壬午",
                            "pillars": ["壬申","癸卯","庚寅","壬午"],
                            "true_solar_time": "1992-03-15 11:52:00"},
        }, headers=auth_headers)
        assert r.status_code == 200, f"onboarding {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "bazi" in d
        assert "engine" in d

    def test_onboarding_unauthorized(self, client):
        r = client.post("/api/v1/cases/onboarding", json={"nickname": "x"})
        assert r.status_code in (401, 403, 422)


class TestCasesMine:
    def test_mine_no_onboarding(self, client, auth_headers):
        """只有注册没建档 — 返回 onboarded=False 或 need_onboarding"""
        r = client.get("/api/v1/cases/mine", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        # 实际格式：{'onboarded': False, 'message': '未初始化建档'}
        assert "onboarded" in d or "case" in d or "need_onboarding" in d

    def test_mine_after_onboarding(self, client, onboarded_user):
        r = client.get("/api/v1/cases/mine", headers=onboarded_user)
        assert r.status_code == 200


class TestReports:
    def test_reports_no_onboarding(self, client, auth_headers):
        """没建档 — 返回 reports 为空或 need_onboarding"""
        r = client.get("/api/v1/cases/reports", headers=auth_headers)
        assert r.status_code == 200

    def test_reports_after_onboarding(self, client, onboarded_user):
        r = client.get("/api/v1/cases/reports", headers=onboarded_user)
        assert r.status_code == 200
