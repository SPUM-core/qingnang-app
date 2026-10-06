"""chat — 青囊管家对话持久化

青囊生活管家的核心：对话不能聊完就丢。
每条 user message + AI reply 都落库，
同时从 user message 里提取结构化信号（LifeSignal）供 SPUM 引擎联动。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float, LargeBinary, Boolean
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


class ChatMemoryNode(Base):
    """LLM 压缩提炼的长期记忆节点

    tier 分层（LLM 压缩时自动判定）：
      'permanent' — 高置信度永久记忆（>3个月长期症状、明确体质倾向、强烈偏好）
                     永不过期，build_system_prompt 始终注入（最多 20 条）
      'episodic'  — 时效性记忆（近期饮食、一过性情绪、短期进展）
                     有 TTL（默认 30 天），过期自动清理
    """
    __tablename__ = "chat_memory_nodes"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    summary     = Column(Text, nullable=False)              # 记忆条目文本
    category    = Column(String(50))                         # 分类: constitution / symptom / preference / progress / diet / mood / other
    tier        = Column(String(20), default="episodic", index=True)  # permanent | episodic
    expires_at  = Column(DateTime, index=True)              # episodic 专用：过期自动清理；permanent = NULL

    source_msg_ids = Column(JSON)                           # 来源 ChatMessage.id 列表
    source_range = Column(JSON)                             # {"from": "...", "to": "..."} 原消息时间范围

    compressed_at = Column(DateTime, server_default=func.now(), index=True)


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


class VoiceSample(Base):
    """语音样本 — 闻诊五音分析的输入素材

    存储策略：单用户最多 5 条（质量分优先保留），
    超过时替换质量最低的；总存储阈值 10MB 循环覆盖。
    """
    __tablename__ = "voice_samples"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # 元数据
    duration    = Column(Float)              # 秒
    sample_rate = Column(Integer)            # Hz
    file_size   = Column(Integer)            # bytes
    file_format = Column(String(20))         # webm / mp3 / wav / m4a

    # 二进制：用 LargeBinary 直接存 DB（简化存储，无需文件系统路径）
    audio_data  = Column(LargeBinary)

    # 质量/排序
    quality_score = Column(Float)            # 0-100（时长 + RMS + 有声段比例综合）

    # 识别出的文本（后端 ASR 自动填充）
    asr_text    = Column(Text)
    asr_provider = Column(String(20))        # 哪家 ASR

    # 关联闻诊分析结果
    voice_analysis_id = Column(Integer, ForeignKey("voice_analyses.id", ondelete="SET NULL"))

    # 来源
    source      = Column(String(20), default="chat")  # chat_upload | voice_sample_view
    source_id   = Column(Integer)                      # ChatMessage.id 等

    created_at  = Column(DateTime, server_default=func.now(), index=True)


class VoiceAnalysis(Base):
    """闻诊分析结果 — 五音频谱分析的结构化输出"""
    __tablename__ = "voice_analyses"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # 输入：可以是单条样本或多条汇总
    sample_ids  = Column(JSON)              # 分析用的 VoiceSample.id 列表
    aggregated  = Column(Boolean, default=False)  # true = 多样本汇总

    # 输出（voice_analyzer.analyze_voice 的返回，JSON 化）
    basic        = Column(JSON)             # basic 字段
    wuyin        = Column(JSON)             # wuyin 五音结果
    virtual_yang = Column(JSON)             # 虚阳外浮检测
    s_vector     = Column(JSON)             # 闻诊 S 向量修正
    confidence   = Column(String(20))       # high / medium / low
    warnings     = Column(JSON)             # 警告列表

    # 系统提示词里要注入的简化版
    summary_text = Column(Text)              # "闻诊摘要（宫35%土形↑↑...虚阳外浮+）"

    # 时间
    analyzed_at  = Column(DateTime, server_default=func.now(), index=True)

    # 下游：是否触发了 Case.v_current 修正
    applied_to_case = Column(Boolean, default=False)
    applied_at      = Column(DateTime)


class TonguePhoto(Base):
    """舌部照片 — 望诊舌象分析输入 + SPUM 舌象结果

    存储策略：每用户最多 3 张（按质量分排序），超出时替换质量最低的。
    照片存储阈值 20MB 单用户循环覆盖。
    """
    __tablename__ = "tongue_photos"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # 图片
    file_format = Column(String(20), default="jpeg")
    file_size   = Column(Integer)            # bytes
    image_data  = Column(LargeBinary)

    # 质量排序
    quality_score = Column(Float)

    # SPUM 分析结果
    confidence   = Column(String(20))        # high / medium / low
    tongue_type  = Column(String(50))        # "淡红（正常）" / "红绛/少苔" / "紫暗" / ...
    s_vector     = Column(JSON)              # {"火": "↑↑", "土": "↓↓", ...}
    bgr_mean     = Column(JSON)              # {B, G, R}
    coating_pct  = Column(JSON)              # {white, yellow, purple, total}
    rationale    = Column(JSON)              # 分析依据 list[str]
    warnings     = Column(JSON)

    # 来源
    source       = Column(String(20), default="collect")
    source_id    = Column(Integer)           # 关联 ChatMessage/InquirySession 等

    created_at   = Column(DateTime, server_default=func.now(), index=True)


class MedicalReport(Base):
    """检查报告 — 用户拍摄上传，LLM 识别归档，随时调取

    存储策略：单用户最多 20 份（按上传时间倒序），总阈值 50MB 循环覆盖。
    识别失败时只存图 + metadata，用户可手动补填。
    """
    __tablename__ = "medical_reports"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # 图片
    file_format = Column(String(20), default="jpeg")
    file_size   = Column(Integer)
    image_data  = Column(LargeBinary)

    # 报告 metadata（LLM 识别 或 用户手动输入）
    report_date = Column(DateTime)           # 报告日期（LLM 从图里识别）
    report_title = Column(String(200))       # 如 "甲状腺功能检查" / "血常规"
    report_type = Column(String(50))         # lab（化验）/ imaging（影像）/ diagnosis（诊断书）/ other

    # LLM 结构化识别结果
    recognized  = Column(Boolean, default=False)     # 是否成功识别
    provider    = Column(String(20))                  # LLM / manual / tesseract
    raw_text    = Column(Text)                        # 原始识别文本
    structured  = Column(JSON)                        # 结构化提取（LLM 输出 JSON）
    summary     = Column(Text)                        # LLM 生成的 1 句话摘要

    # SPUM 翻译（可选：AI 把指标翻译为 S 向量偏移建议）
    spum_note   = Column(Text)

    # 人工修正
    manual_notes = Column(Text)

    # 来源
    source       = Column(String(20), default="collect")
    source_id    = Column(Integer)

    created_at   = Column(DateTime, server_default=func.now(), index=True)
    updated_at   = Column(DateTime)
