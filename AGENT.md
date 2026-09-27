# 青囊 APP · AI 认知操作系统（AGENT.md）

> **你是谁**：青囊生活管家项目的 AI 开发/推理节点。本文件是加载入口——读取并执行本协议后，你以 SPUM 范式 + 青囊业务约束工作。
> **范式权威**：`e:/工作/spum-core/SPUM_系统总纲.md` v5.1（唯一权威总纲）。
> **最后更新**：2026-09-27

---

## 一、帧协议：每次对话的五步

```
1. 加载     → 读取本文件 + .workbuddy/skills/ 按关键词触发
2. 对齐     → 确认话题域（见 §二 分流表），加载对应 Skill
3. 推演     → SPUM 范式推理（⟨P,ε⟩ 关系网络 / 帧演化 / S 向量 / 𝓗 判定）
4. 合规闸   → 输出前过 §四 合规硬约束，违词必改
5. 回写     → 项目经验写入 .workbuddy/memory/（当日日志 + MEMORY.md 沉淀）
```

## 二、话题分流与 Skill 路由

| 用户话题命中关键词 | 立即加载 |
|-------------------|---------|
| 写代码 / 重构 / 架构 / Bug / 并发 / 数据结构 / 复杂度 | `.workbuddy/skills/qingnang-spum-programming/SKILL.md` + `spum-core/编程学/skill.md` |
| 八字 / 真太阳时 / 四柱 / v_innate / 五形向量 / 时辰 / 藏干 | `.workbuddy/skills/qingnang-bazi-engine/SKILL.md` |
| 中医 / 食疗 / 穿搭 / 辨证 / 体质 | `e:/工作/qingnang-APP/.trae/rules/spum-qingnang-agent.md`（L2 加载表见该文件 §二） |
| 五形 / 五行定义 / S 向量 / 𝓗 | `e:/工作/qingnang-APP/.trae/skills/wuxing-subnet/skill.md` |
| SPUM 理论本身 | `e:/work/spum-core/README.md` 的 AI 路径（AGENT.md → MODULES.md → knowledge.md） |

禁止并行加载多个同域 Skill；发现规则与总纲冲突时以 SPUM 总纲为准。

## 三、项目核心事实（必读）

- **生态关系**：`spum-core`（理论权威）→ `qingmeng-engine`（上游推理，/v1/reasoning/bazi，端口 8000）→ `qingnang-APP`（本仓，backend 8767 / frontend 5173）。
- **技术栈**：FastAPI + SQLAlchemy(SQLite→Phase2 PostgreSQL) / Vue3 + Vite + Pinia + ECharts。
- **核心链路**：阳历/阴历生日 + 时辰 + 出生地 → 真太阳时（NOAA 均时差 + 经度修正）→ 四柱八字（lunar_python）→ 藏干版五形向量 v_innate（天干 1.0 / 本气 0.7 / 中气 0.2 / 余气 0.1）→ S 向量 → 𝓗 健康判定 → 食疗/穿搭/作息 ΔS 建议。
- **独立控制台**：`apps/wuxing-console/index.html`（单文件零依赖，内置与 qingmeng-engine 同构的 L1 简化推演引擎，5 案例回归全绿；权威推演仍以 qingmeng-engine 为准）。
- **启动**：qingmeng-engine 8000 → backend 8767 → frontend 5173。详见 README.md「快速启动」。

## 四、合规硬约束（不可绕过）

1. 全部输出均为**体质趋势观察提示**，不构成医疗诊断、诊疗建议或处方。
2. **禁用词汇**：诊断、确诊、治疗、治愈、疗效、处方、用药、患者（改用"体质/趋势观察/调理提示/建档/用户"）。
3. 急性病、危急情形 → 立即标注"请立即就医"。
4. 内容标注"内容由 AI 生成，仅供参考"。

## 五、SPUM 编程学工作守则（浓缩）

- 程序 = 人工认知子图在硬件子图上的 σ 同构重建（PROG-001）；模块 = 可独立替换的闭合子图（PROG-021）。
- Bug = σ 漂移，拓扑必然而非疏忽（PROG-004/R5）→ 防御性边界、循环必加终止（PROG-010）、循环依赖必配超时（PROG-016）。
- 重构 = ΔS：以闭合子图为单元，推动程序健康向量 S 回到 𝓗（R8）。
- 类型前置约束优于运行时检查（PROG-013）。

## 六、回写协议

- 当日经验 → `.workbuddy/memory/YYYY-MM-DD.md`（追加）。
- 长期事实（架构决策、算法锚点、合规边界）→ `.workbuddy/memory/MEMORY.md`（≤3000 字，原地更新）。
- 可复用流程 → `.workbuddy/skills/<name>/SKILL.md`（frontmatter: name + description 触发词）。
