"""chat_compress - 对话历史容量阈值压缩：超 512K 触发 LLM 提炼成记忆节点后删除原消息"""
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ....models import ChatMessage, LifeSignal
from ....config import settings


# ═══════════════════════════════════════════════════════
# 历史容量阈值压缩（512K 触发 → LLM 提炼 → 删原消息）
# ═══════════════════════════════════════════════════════

CHAT_HISTORY_MAX_BYTES = 512 * 1024      # 512K
CHAT_HISTORY_BATCH_PAIRS = 8             # 每轮压缩 8 对 user+assistant
CHAT_HISTORY_KEEP_RECENT = 20            # 永远保留最近 20 条（10 对）不压缩
EPISODIC_TTL_DAYS = 30                   # episodic 记忆默认过期天数
PERMANENT_PER_USER_LIMIT = 50            # 单用户 permanent 节点上限（防无限增长）

# 进程内锁：防止同一用户并发压缩
_compressing_users: set = set()


async def _compress_old_messages(user_id: int):
    """历史容量阈值压缩（异步，chat 端点 commit 后后台触发）

    逻辑：
      1. 算总容量 SUM(OCTET_LENGTH(content))
      2. 超限 → 取最早 N 轮 → LLM 压缩提炼 → 写 ChatMemoryNode → 删原消息
      3. 循环直到低于阈值
    """
    global _compressing_users
    if user_id in _compressing_users:
        return  # 已在压缩，跳过
    _compressing_users.add(user_id)

    try:
        from datetime import datetime, timedelta
        from ....database import SessionLocal
        from ....models.chat import ChatMemoryNode

        db = SessionLocal()
        try:
            # 0. 清理过期 episodic 节点（顺便降低 prompt 注入噪音）
            db.query(ChatMemoryNode).filter(
                ChatMemoryNode.user_id == user_id,
                ChatMemoryNode.tier == "episodic",
                ChatMemoryNode.expires_at < datetime.utcnow(),
            ).delete(synchronize_session=False)
            db.commit()

            # 1. 算总容量
            total_bytes = db.query(
                func.coalesce(func.sum(func.length(ChatMessage.content)), 0)
            ).filter(ChatMessage.user_id == user_id).scalar()

            if total_bytes <= CHAT_HISTORY_MAX_BYTES:
                return  # 没超限

            # 2. 排除最近 KEEP_RECENT 条
            recent_ids = [r[0] for r in db.query(ChatMessage.id)
                          .filter(ChatMessage.user_id == user_id)
                          .order_by(ChatMessage.id.desc())
                          .limit(CHAT_HISTORY_KEEP_RECENT).all()]
            if not recent_ids:
                return

            # 3. 取最早消息（压缩对象）
            oldest_msgs = db.query(ChatMessage).filter(
                ChatMessage.user_id == user_id,
                ChatMessage.id.notin_(recent_ids),
            ).order_by(ChatMessage.id.asc()).limit(CHAT_HISTORY_BATCH_PAIRS * 2).all()

            if len(oldest_msgs) < 4:
                return

            # 4. 拼对话文本
            dialogue_lines = []
            for m in oldest_msgs:
                role_label = "用户" if m.role == "user" else "青囊管家"
                dialogue_lines.append(f"[{role_label}] {m.content}")
            dialogue_text = "\n".join(dialogue_lines)

            first_ts = str(oldest_msgs[0].created_at)[:19]
            last_ts = str(oldest_msgs[-1].created_at)[:19]
            source_ids = [m.id for m in oldest_msgs]
            source_range = {"from": first_ts, "to": last_ts, "count": len(source_ids)}

            # 5. 调 LLM 压缩 → list[dict]
            nodes_data = await _llm_compress_dialogue(dialogue_text, first_ts, last_ts)
            permanent_count = sum(1 for n in nodes_data if n["tier"] == "permanent")

            # 6. 安全检查：如果 LLM 完全没识别到 permanent，补跑一次只抓 permanent 的检查
            if permanent_count == 0 and any(kw in dialogue_text for kw in ["年", "长期", "一直", "30岁", "岁以"]):
                try:
                    extra = await _llm_safety_check_permanent(dialogue_text, first_ts, last_ts)
                    if extra:
                        nodes_data.extend(extra)
                        permanent_count += len(extra)
                except Exception:
                    pass  # 安全检查失败不阻塞主流程

            # 7. 写节点（每条事实一个 ChatMemoryNode）
            now = datetime.utcnow()
            for n in nodes_data:
                tier = n["tier"]
                node = ChatMemoryNode(
                    user_id=user_id,
                    summary=n["summary"],
                    category=n.get("category", "other"),
                    tier=tier,
                    source_msg_ids=source_ids,
                    source_range=source_range,
                    expires_at=(now + timedelta(days=EPISODIC_TTL_DAYS)) if tier == "episodic" else None,
                )
                db.add(node)

            # 8. 删除原消息
            db.query(ChatMessage).filter(ChatMessage.id.in_(source_ids)).delete(synchronize_session=False)
            db.query(LifeSignal).filter(
                LifeSignal.source_id.in_(source_ids),
                LifeSignal.source.in_(["chat", "chat_llm"]),
            ).update({LifeSignal.source_id: None}, synchronize_session=False)

            db.commit()

            # 9. 递归（如果还超限）
            await _compress_old_messages(user_id)

        finally:
            db.close()

    except Exception as e:
        print(f"[compress] user={user_id} error: {e}")
    finally:
        _compressing_users.discard(user_id)


async def _llm_compress_dialogue(dialogue_text: str, first_ts: str, last_ts: str) -> list[dict]:
    """调 LLM 把一段历史对话压缩成带 tier 的记忆节点列表

    返回: [{"summary": "...", "category": "...", "tier": "permanent" | "episodic"}, ...]
    """
    import httpx, json as _json

    prompt = f"""你是青囊管家的"长期记忆压缩器"。下面是一段你和用户的早期对话（{first_ts} ~ {last_ts}）。

请从对话里提炼出**有价值的记忆条目**，按置信度/时效性分成两档：

## tier 判定规则

### permanent（永久记忆，高置信度，永不过期）
以下情况归 permanent：
- 用户明确陈述的**长期/慢性**事实（>3个月），如"腰膝酸软30年"、"长期失眠靠安眠药"
- 用户**核心体质倾向**（木形偏旺、土形偏弱等 SPUM 五形判定）
- 用户**强烈的偏好/禁忌**（"不吃辣"、"讨厌运动"、"坚持每天泡脚"）
- 用户**重要的健康事件**（"去年做了手术"、"多次治疗无果"）
- 用户**长期坚持的习惯**（"每天2点睡"、"烟龄20年"）

### episodic（时效记忆，低置信度，默认 30 天过期）
以下情况归 episodic：
- 用户**近期饮食**（"今天吃了火锅"、"这几天没胃口"）
- 用户**一过性情绪/疲劳**（"今早有点累"、"昨天压力大"）
- 用户**短期调理进展**（"上周泡了药浴睡得好"、"这两天睡眠改善了"）
- 用户**近期观测数据**（"昨天测了 PPG"、"今天脉搏快"）
- 用户**临时计划**（"这周要出差"、"下周去体检"）

## category 取值
constitution | symptom | preference | progress | diet | mood | habit | event | other

## 输出格式（严格 JSON）
```json
{{
  "permanent": [
    {{"summary": "腰膝酸软30年，阴雨天加重", "category": "symptom"}},
    {{"summary": "核心体质：土形37.5最高，木形25.0偏弱", "category": "constitution"}}
  ],
  "episodic": [
    {{"summary": "今天吃了火锅后胃有点胀", "category": "diet"}},
    {{"summary": "这三天睡得比之前好", "category": "progress"}}
  ]
}}
```

## 严格约束
- 只输出 JSON，不要任何解释文字
- permanent 条目**必须**满足 >3个月 / 核心体质 / 强烈偏好 其中之一
- 如果对话里没有某一档的内容，那一档就输出空数组
- 每个 summary 不超过 40 字，保留具体数字
- 严禁医疗术语

原始对话：
{dialogue_text[:4000]}"""

    # 优先 deepseek（JSON mode）
    api_key = getattr(settings, 'DEEPSEEK_API_KEY', '') or getattr(settings, 'deepseek_api_key', '')
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 800,
                    },
                )
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"].strip()
                    return _parse_memory_json(raw, dialogue_text[:300])
        except Exception as e:
            print(f"[compress-llm] deepseek error: {e}")

    # 终极兜底：单条 permanent（截断前 150 字）
    return [{"summary": dialogue_text[:150], "category": "other", "tier": "permanent"}]


def _parse_memory_json(raw: str, fallback_text: str) -> list[dict]:
    """从 LLM 返回里抽 JSON，解析成记忆条目列表"""
    import json as _json, re

    # 去掉 markdown code fence
    text = raw.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        obj = _json.loads(text)
    except Exception:
        # 尝试找第一个 { ... } 片段
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                obj = _json.loads(m.group())
            except Exception:
                return [{"summary": fallback_text, "category": "other", "tier": "permanent"}]
        else:
            return [{"summary": fallback_text, "category": "other", "tier": "permanent"}]

    nodes = []
    for item in obj.get("permanent", []) or []:
        nodes.append({
            "summary": str(item.get("summary", "")).strip(),
            "category": item.get("category", "other"),
            "tier": "permanent",
        })
    for item in obj.get("episodic", []) or []:
        nodes.append({
            "summary": str(item.get("summary", "")).strip(),
            "category": item.get("category", "other"),
            "tier": "episodic",
        })

    # 过滤空 summary
    return [n for n in nodes if n["summary"] and len(n["summary"]) > 3]


async def _llm_safety_check_permanent(dialogue_text: str, first_ts: str, last_ts: str) -> list[dict]:
    """压缩安全检查：如果主压缩没识别到 permanent，但对话里疑似有，二次只抓 permanent 事实"""
    import httpx, json as _json, re

    prompt = f"""你是青囊管家的"永久记忆安全审计器"。下面是一段早期对话（{first_ts} ~ {last_ts}）。

请扫描对话，**只**找出**绝对应该保留的永久事实**（必须满足 >3个月 / 核心体质 / 强烈偏好 之一）。
如果你认为对话里确实没有这些内容，返回空数组即可。

判定标准（满足任一）：
- 有明确时长的长期/慢性事实："腰膝酸软30年"、"长期失眠"、"坚持X年"
- 用户核心体质判定：SPUM 五形明确倾向（"土形最高"、"木形偏旺"）
- 用户强烈表达的偏好/禁忌："不吃辣"、"讨厌运动"、"烟瘾"
- 重要健康事件：手术/重大病史/多次治疗无果

输出（严格 JSON）：
```json
{{"permanent": [
  {{"summary": "...", "category": "symptom"}},
  {{"summary": "...", "category": "constitution"}}
]}}
```
如无：`{{"permanent": []}}`
每个 summary 不超 40 字，保留具体数字。

对话：
{dialogue_text[:3000]}"""

    api_key = getattr(settings, 'DEEPSEEK_API_KEY', '')
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0.1, "max_tokens": 400},
                )
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"].strip()
                    m = re.search(r'\{[\s\S]*\}', raw)
                    if m:
                        obj = _json.loads(m.group())
                        return [{"summary": str(i.get("summary","")).strip(),
                                 "category": i.get("category","other"), "tier": "permanent"}
                                for i in (obj.get("permanent") or [])
                                if i.get("summary") and len(str(i.get("summary","")).strip()) > 3]
        except Exception:
            pass

    return []
