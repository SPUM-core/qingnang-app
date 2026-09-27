"""测试 assistant — 合规词表过滤器 + chat 端点"""
import sys
import pytest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.v1.assistant import compliance_filter, PROHIBITED_WORDS, STRIP_WORDS


class TestComplianceFilter:
    """合规词表单元测试 — 不依赖 DB / LLM"""

    def test_diagnostic_words_replaced(self):
        """诊断类词汇必须被替换"""
        raw = "这是一个中医诊断：湿遏证，需要辨证施治"
        filtered = compliance_filter(raw)
        assert "诊断" not in filtered, f"'诊断' 未被替换: {filtered}"
        assert "辨证" not in filtered, f"'辨证' 未被替换: {filtered}"
        assert "生活观察" in filtered
        assert "梳理" in filtered

    def test_treatment_words_replaced(self):
        """治疗类词汇必须被替换"""
        raw = "这个治疗方案的疗效很好，能治愈你的问题，根治困扰"
        filtered = compliance_filter(raw)
        for bad in ["治疗", "疗效", "治愈", "根治"]:
            assert bad not in filtered, f"'{bad}' 未被替换: {filtered}"

    def test_prescription_words_replaced(self):
        """处方/药疗类词汇必须被替换"""
        raw = "处方是苓桂术甘汤加黄连附子肉桂"
        filtered = compliance_filter(raw)
        for bad in ["处方", "黄连", "附子", "肉桂"]:
            assert bad not in filtered, f"'{bad}' 未被替换: {filtered}"

    def test_strip_words_removed(self):
        """STRIP_WORDS 必须直接剔除"""
        raw = "需要药物治疗，有医学建议支持，中医诊断明确"
        filtered = compliance_filter(raw)
        for bad in ["医学建议", "中医诊断"]:
            assert bad not in filtered, f"'{bad}' 未被剔除: {filtered}"

    def test_safe_words_pass_through(self):
        """正常生活词汇不受影响"""
        raw = "晚上22:30前睡觉，泡脚40度15分钟"
        filtered = compliance_filter(raw)
        assert filtered == raw  # 完全一致

    def test_empty_input(self):
        assert compliance_filter("") == ""
        assert compliance_filter(None) is None  # None 保护

    def test_all_prohibited_words_have_mapping(self):
        """每个禁用词都有非空替换"""
        for bad, good in PROHIBITED_WORDS.items():
            assert good, f"'{bad}' 的替换词为空"
            assert bad != good, f"'{bad}' 替换后还是自己"


class TestAssistantChat:
    """assistant/chat 集成测试"""

    def test_chat_returns_reply(self, client, onboarded_user):
        """chat 端点必须返回 reply 字段"""
        r = client.post("/api/v1/assistant/chat",
                        json={"message": "你好"}, headers=onboarded_user)
        assert r.status_code == 200
        d = r.json()
        assert "reply" in d
        assert len(d["reply"]) > 0
        assert "engine" in d

    def test_chat_reply_compliant(self, client, onboarded_user):
        """LLM fallback 回复也必须过合规过滤器"""
        r = client.post("/api/v1/assistant/chat",
                        json={"message": "我该怎么治疗"}, headers=onboarded_user)
        assert r.status_code == 200
        reply = r.json()["reply"]
        # fallback 里用的 "调理" 不是禁用词，但要确保没有残留禁用词
        for bad in ["治疗", "处方", "脉诊", "问诊"]:
            assert bad not in reply, f"回复含禁用词 '{bad}': {reply}"

    def test_chat_unauthorized(self, client):
        r = client.post("/api/v1/assistant/chat", json={"message": "hi"})
        # get_current_user 缺少 Authorization header 可能返回 401/422
        assert r.status_code in (401, 403, 422), f"期望拒绝访问，实际 {r.status_code}"

    def test_chat_message_too_long(self, client, onboarded_user):
        long_msg = "啊" * 2500
        r = client.post("/api/v1/assistant/chat",
                        json={"message": long_msg}, headers=onboarded_user)
        assert r.status_code == 422

    def test_chat_empty_message(self, client, onboarded_user):
        r = client.post("/api/v1/assistant/chat",
                        json={"message": ""}, headers=onboarded_user)
        assert r.status_code == 422


class TestAssistantHealth:
    def test_health_endpoint(self, client):
        r = client.get("/api/v1/assistant/health")
        assert r.status_code == 200
        assert "qingmeng_online" in r.json()
        # 测试环境 QINGMENG_URL 指向 localhost:1 → 应该是 False
        assert r.json()["qingmeng_online"] is False
