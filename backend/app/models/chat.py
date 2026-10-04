"""chat — 青囊管家对话持久化

青囊生活管家的核心：对话不能聊完就丢。
每条 user message + AI reply 都落库，
同时从 user message 里提取结构化信号（LifeSignal）供 SPUM 引擎联动。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from ..database import Base


class ChatMessage(Base):
    """单条对话记录（user 或 assistant）"""
    __tablename__ = "chat_messages"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id     = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), index=True)

    role        = Column(String(10), nullable=False)    # 'user' | 'assistant'
    content     = Column(Text, nullable=False)

    # ── 执行元数据 ──
    provider    = Column(String(20))       # 'deepseek' | 'qingmeng' | 'local_fallback' | 'engine_direct'
    latency_ms  = Column(Integer)
    llm_online  = Column(JSON)             # bool + 可能的 brief_context 截断引用

    # ── 结构化副产物（chat 端点自动抽取后写入）──
    signals     = Column(JSON)             # 从这条 user message 里抽出的 LifeSignal 快照

    created_at  = Column(DateTime, server_default=func.now(), index=True)


class LifeSignal(Base):
    """生活信号 — 用户日常自述/AI 对话中发现的结构化健康信号

    一条记录 = 一个维度的一个观测。
    维度 tag 来自以下枚举：
      bowel    二便（便秘/便稀/无便意/便血/腹泻）
      sweat    汗液（汗多/盗汗/自汗/动则多汗）
      sleep    睡眠（难入睡/易醒/多梦/早醒/失眠）
      appetite 食欲（食欲不振/易饿/反酸/腹胀）
      menses   月经（量少/推迟/提前/痛经/闭经/淋漓）
      mood     情绪（焦虑/易怒/低落/紧张/叹气）
      energy   体力（易疲乏/精力充沛/腰膝酸软）
      thirst   饮水（口渴/不渴/喜热饮/喜冷饮）
      skin     皮肤（干燥/脱屑/过敏/长痘/发黄）
      breath   呼吸（气短/咳嗽/鼻塞/皮肤痒）
      other    其他（用户自己说但不在上面维度里的）
    """
    __tablename__ = "life_signals"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id     = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), index=True)

    # ── 信号维度（枚举 tag，见上方注释）──
    tag         = Column(String(20), nullable=False, index=True)

    # ── 信号内容 ──
    label       = Column(String(100), nullable=False)   # 归一化标签，如 "动则多汗"
    raw_text    = Column(Text)                           # 从哪段原始文本抽出来的
    confidence  = Column(JSON)                           # {"rule": "keywords", "match": ["汗多","一动就出汗"]}

    # ── 来源 ──
    source      = Column(String(20), default='chat')    # 'chat' | 'inquiry' | 'checkin' | 'manual'
    source_id   = Column(Integer)                        # 关联 ChatMessage.id / InquirySession.id

    created_at  = Column(DateTime, server_default=func.now(), index=True)
