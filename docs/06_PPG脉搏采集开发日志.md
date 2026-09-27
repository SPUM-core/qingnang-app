# PPG 脉搏采集开发日志

> 会话日期：2026-09-27
> 涉及仓库：qingnang-APP（前端 + 后端）
> 参考仓库：qingnang/青囊/脉诊/采集（硬件固件 + Python 采集脚本）

---

## 一、背景与问题

### 1.1 原始状态

CollectView.vue 的脉搏采集卡片存在**三层伪代码**：

| 项 | 伪代码现状 |
|---|---|
| 硬件检测 | `HARDWARE_CONNECTED = false` 硬编码常量，永远不检测 |
| 后端检测 | 把青囊主后端 `/health` 说成"硬件后端在线" |
| 采集流程 | `startRealCollect()` 调已废弃的 SSE 硬件 API（8766 端口根本不存在），失败后 fallback 离线 mock |
| 波形 | RAF 实时滚动动画（Canvas buffer shift），不是静态真实曲线 |
| 网格 | 浅灰色均匀线（非 ECG 标准） |

### 1.2 用户反馈

> "硬件设备依然显示未连接。脉象可以采集，示波并未展示。"
> "将波形动画，改成心电图标准页面，带网格那种，示波曲线要素真实数据曲线，不要动画演示。"
> "参考 `e:\工作\qingnang\青囊\脉诊\采集`"

---

## 二、硬件环境确认

### 2.1 用户硬件

```
Arduino UNO (FTDI FT232R USB 转串口)
  ↓
CheezPPG 腕戴式 PPG 模块 (XH2.54-4P)
  ↓
固件：ppg_wrist_cheez.ino
  采样率：125 Hz
  波特率：115200
  输出格式：CSV 6 通道（raw, smooth, filtered, peak, HR, HRV）
  端口：COM3
```

### 2.2 自检结果（ppg_acquisition.py --selftest）

```
[OK] 检测到 2 个串口：
  1. COM1  未知设备
  2. COM3  FTDI FT232R（原装 Arduino / 部分 STM32 板）
[OK] 自动检测默认端口：COM3
[OK] 连接测试通过：COM3 @ 115200 baud
[OK] 数据流正常（6通道 CheezPPG 模式，≈125 Hz）
```

### 2.3 固件输出格式

```
2874,2620,2590,1,72,45
 ↑raw  ↑smooth ↑filtered ↑peak ↑HR ↑HRV(SDNN)
```

Python 采集脚本路径：`e:\工作\qingnang\青囊\脉诊\采集\ppg_acquisition.py`
- `CheezPPGStreamer`：6 通道 @ 125Hz
- `PPGStreamer`：单通道 Pulsesensor @ 250Hz
- `resolve_port()`：自动检测默认串口（三段 fallback）
- `detect_format()`：嗅探数据格式（1.5s）

---

## 三、改动路线图

### 阶段 1：诚实化硬件状态（已完成）
- 删硬编码 `HARDWARE_CONNECTED = false`
- 状态条分层：后端服务 / 硬件设备
- 离线模式合成真实 PPG 波形

### 阶段 2：ECG 标准网格 + 静态真实波形（已完成）
- 删 RAF 滚动动画 → 一次性合成 20s PPG
- ECG 双层网格（小格 4px + 大格 20px）
- Heusden PPG 模型（上升支陡 → 主峰 → 降中峡 → 重搏波）

### 阶段 3：硬件联机（多次迭代）

#### 3a 第一次尝试：Web Serial API（前端直连）❌ 失败

| 操作 | 结果 |
|---|---|
| `navigator.serial.requestPort()` | 浏览器代理模拟点击 → **不算用户手势** → 弹窗不出现 |
| Console 里调用 | 同上 |
| 手动点击按钮 | 用户报"点击没反应" |

**根因**：Web Serial API 要求 `requestPort()` 必须在**真实鼠标点击事件的同步调用栈**里触发。浏览器代理、Console、Vite HMR 都无法满足。

#### 3b 第二次尝试：加 debug 信号

加 `hardwareInfo.value = '⏳ 正在请求串口权限...'` 作为点击事件触发验证。
结果：按钮点击后状态条确实变了 → **Vue @click 绑定没问题**，就是 `requestPort()` 不弹窗。

#### 3c 第三次尝试：后端 SSE 桥接 ✅ 最终方案

**完全绕开 Web Serial**：后端 Python 直接开串口 → SSE 推给浏览器。

---

## 四、最终架构（已落地）

```
┌─ 前端 CollectView.vue ──────────────────────────────────┐
│                                                          │
│  onMounted → checkServices()                             │
│              ├── /health → 后端服务状态                   │
│              └── /ppg/hardware-status → 硬件状态          │
│                                                          │
│  状态条：后端服务：在线 · 硬件设备：已连接 · COM3 · CheezPPG 6ch @ 125Hz │
│                                                          │
│  点击「开始采集」                                         │
│    ├── hardwareConnected=true → startSseCollect()        │
│    │     EventSource('/api/v1/ppg/stream?duration=20')  │
│    │     → Canvas ECG 网格滚动示波                       │
│    │                                                     │
│    └── hardwareConnected=false → startOfflineCollect()   │
│          一次性合成 20s PPG → 静态曲线                    │
└──────────────────────────────────────────────────────────┘
           ↕ HTTP / SSE
┌─ 青囊后端 :8767 ─────────────────────────────────────────┐
│                                                          │
│  GET /api/v1/ppg/hardware-status                         │
│    → selfcheck_hardware()                                │
│    → verdict: OK / WARN / FAIL                           │
│                                                          │
│  GET /api/v1/ppg/stream?duration=20&port=COM3            │
│    → resolve_port() → detect_format()                    │
│    → CheezPPGStreamer(COM3, 115200)                      │
│    → 每 33ms 推一帧 SSE                                  │
│      {type:'init', mode:'cheez', fs:125}                 │
│      {type:'data', wave:2590, hr:72, hrv:45}            │
│      {type:'done', total:2500}                            │
└──────────────────────────────────────────────────────────┘
           ↓ PySerial
┌─ COM3 @ 115200 ──────────────────────────────────────────┐
│  Arduino UNO → CheezPPG 6ch CSV @ 125Hz                  │
│  2874,2620,2590,1,72,45                                  │
└──────────────────────────────────────────────────────────┘
```

---

## 五、改动文件清单

### 5.1 前端：CollectView.vue

**路径**：`qingnang-APP/frontend/src/views/CollectView.vue`

| 改动 | 说明 |
|---|---|
| 删 ~200 行废弃代码 | `startRealCollect` / `bindSSEHandlers` / `stopSSE` / 旧 Web Serial 全套 |
| 删硬编码常量 | `HARDWARE_CONNECTED = false` / `PPG_BACKEND` / `serialPort` / `serialReader` |
| ECG 标准网格 | 双层（小格 4px + 大格 20px），基线横中线，1px 实线 |
| 波形合成 | `synthesizePpgWaveform()` — Heusden PPG 模型 + 漂移 + 噪声 |
| 离线采集 | `startOfflineCollect()` — 一次性合成 + 静态 Canvas |
| 硬件状态检测 | `checkHardwareStatus()` — fetch 后端 `/ppg/hardware-status` |
| SSE 硬件采集 | `startSseCollect()` — EventSource 后端 `/ppg/stream` |
| 硬件示波 | `drawPpgHw()` — 滚动窗口 + 归一化 + ECG 网格 |
| 状态条模板 | 动态三态 + 连接/断开按钮 |
| Canvas 尺寸 | 420×120 → **640×180**（更清晰） |
| 覆盖层文案 | 「硬件未连接 · 将生成演示波形」→ 诚实提示 |

**文件行数变化**：~920 行（含删 ~200 行废弃 + 新增 ~300 行）

### 5.2 后端：ppg.py

**路径**：`qingnang-APP/backend/app/api/v1/ppg.py`

新增：
- 硬件桥 sys.path 注入（兄弟目录 `qingnang/青囊/脉诊/采集`）
- `GET /api/v1/ppg/hardware-status` — 复用 `selfcheck_hardware()`
- `GET /api/v1/ppg/stream` — SSE 实时推 PPG

**sys.path 关键修正**：
```python
# 错误路径：parents[4] → qingnang-APP → 拼 /qingnang/... → 不存在
_HW_COLLECT_DIR = Path(__file__).resolve().parents[4] / "qingnang" / ...

# 正确路径：parents[4] → qingnang-APP → .parent → e:\工作 → 拼 qingnang/... → 存在
_root = Path(__file__).resolve().parents[4]
_HW_COLLECT_DIR = _root.parent / "qingnang" / "青囊" / "脉诊" / "采集"
```

### 5.3 未改动文件

| 文件 | 原因 |
|---|---|
| 固件 .ino | 用户已烧录，无需改 |
| ppg_acquisition.py | 作为后端桥接库 import，无需改 |
| 前端 API client | 没动 |
| Docker / 部署 | 本地开发阶段 |

---

## 六、关键踩坑记录

### 坑 1：Web Serial `requestPort()` 必须用户手势

| 事实 | 说明 |
|---|---|
| 浏览器代理模拟点击 | ❌ 不算用户手势 |
| Console 里执行 `navigator.serial.requestPort()` | ❌ 不算用户手势 |
| 真实鼠标亲手点按钮 ✅ | 算用户手势 |

**教训**：前端硬件方案必须预留给"物理点击"场景。浏览器自动化测试无法覆盖这一步。

### 坑 2：FTDI 驱动 COM3 被占 PermissionError(13)

| 操作 | 结果 |
|---|---|
| Python 脚本独占 COM3 后再开后端 | PermissionError |
| 后端开了再开采集脚本 | 同样 PermissionError |
| 拔插 USB 线 | ✅ 释放 |
| `stream_lock` threading.Lock 全局单例 | ✅ 防止后端内部并发 |

**教训**：Windows USB 转串口芯片驱动会独占 COM 口，多进程/多线程必须串行访问。

### 坑 3：sys.path 兄弟目录计算

```
qingnang-APP/backend/app/api/v1/ppg.py
  → parents[4] = qingnang-APP
  → 目标目录 = qingnang-APP 同级的 qingnang/青囊/脉诊/采集
  → parents[4].parent / "qingnang" → 正确
```

**教训**：跨项目 import 用 `.parent` 回退到兄弟，别猜相对路径。

### 坑 4：FastAPI StreamingResponse + Pylance

StreamingResponse 生成器内部的 `time.sleep()` / `streamer.stop()` 等阻塞调用在 SSE 场景下是可以的——因为是独立生成器线程，不阻塞 FastAPI 主循环。但要加 `finally` 块确保串口关闭。

### 坑 5：Serial 嗅探 2s 等待

Arduino 在 DTR 复位后需要 ~2s 启动 + 2s 进入稳定数据流。自检脚本 `selfcheck_hardware()` 里有明确的 `time.sleep(2.0)` + `timeout=0.5` + 1.5s 嗅探窗口。少了任何一步都会误判"无数据流"。

---

## 七、SSE 协议规格

### 7.1 /api/v1/ppg/stream

**Query 参数**：
| 参数 | 默认 | 说明 |
|---|---|---|
| duration | 20.0 | 采集时长（秒） |
| port | null | 串口（不传则自动检测） |
| baud | 115200 | 波特率 |

**事件格式**：

**握手帧**（第一帧）
```json
{
  "type": "init",
  "port": "COM3",
  "baud": 115200,
  "mode": "cheez",
  "fs": 125,
  "channels": ["raw", "smooth", "filtered", "peak", "HR", "HRV"]
}
```

**数据帧**（每 ~33ms，约 30fps）
```json
{
  "type": "data",
  "wave": 2590,
  "hr": 72,
  "hrv": 45,
  "peak": 1,
  "sample": 1847
}
```

**结束帧**
```json
{ "type": "done", "total": 2500 }
```

**错误帧**
```json
{ "error": "could not open port 'COM3': PermissionError" }
```

### 7.2 /api/v1/ppg/hardware-status

```json
{
  "ok": true,
  "verdict": "OK",
  "port_count": 2,
  "default_port": "COM3",
  "connect_ok": true,
  "stream_ok": true,
  "stream_rate": 125.0,
  "stream_mode": "cheez",
  "report": ["[OK] 检测到 2 个串口", "[OK] 连接测试通过..."]
}
```

---

## 八、前端 UI 状态机

```
页面加载
  │
  ├─ checkHardwareStatus()
  │     │
  │     ├─ ok=true, connect=true, stream=true
  │     │     → 状态条：🟢 已连接 · COM3 · CheezPPG 6ch @ 125Hz
  │     │     → 覆盖层：「硬件已就绪 · 点击开始采集」
  │     │
  │     ├─ ok=true, port_count>0 但 stream=false
  │     │     → 状态条：🟡 检测中（请确保硬件已戴好）
  │     │     → 覆盖层：「硬件未连接 · 将生成演示波形」
  │     │
  │     └─ 其他
  │           → 状态条：🟠 未连接 · 点击右侧按钮选择串口
  │           → 覆盖层：同上
  │
  ├─ 点「开始采集」
  │     │
  │     ├─ hardwareConnected=true
  │     │     → startSseCollect()
  │     │     → EventSource → Canvas 实时滚动示波
  │     │     → HR/HRV 固件直出
  │     │
  │     └─ hardwareConnected=false
  │           → startOfflineCollect()
  │           → 一次性合成 20s PPG
  │           → 静态 Canvas 曲线
  │
  └─ 倒计时 20s → stopPpg() → 「分析波形」按钮
```

---

## 九、ECG 标准网格参数

```
画布尺寸：640 × 180 px
网格：
  小格：4px × 4px    颜色 #E8E4DA  线宽 0.5
  大格：20px × 20px  颜色 #C8C3B7  线宽 0.8（每 5 小格一条）
基线：横中线 h*0.5   颜色 rgba(26,77,69,0.25) 线宽 1
波形线宽：1.8        圆头圆尾
波形范围：h*0.38（上下各留 12% 边界）
```

---

## 十、后续 TODO

### P0 — 当前阻塞
- [ ] **COM3 PermissionError**（拔插 USB 线可解）— 这是 Windows FTDI 驱动独占问题
- [ ] 用户真实环境验证（前端 SSE → 实时示波链路）

### P1 — 功能补全
- [ ] Pulsesensor 指尖固件兼容（嗅探 mode='adc' → 前端峰值检测法算 HR/HRV）
- [ ] SSE 断连重连（EventSource 原生有，但要处理前端状态同步）
- [ ] 波形上传（采集完 `/api/v1/ppg/upload` 带 `ppg_wave` 字段）
- [ ] CSP 放行 SSE 端点（`connect-src` 目前已有 localhost）

### P2 — 优化
- [ ] SSE 推送频率调优（33ms → 可配置，CheezPPG 125Hz 原始输出可 8ms 一帧）
- [ ] ppgBuffer 长度限制 + 内存友好（20s × 125Hz = 2500 点，Float32Array 足够）
- [ ] 自动停止后 EventSource.close() 确保不泄漏
- [ ] 前端 CORS 配置（EventSource 自动同源，无问题；跨源需后端 CORS）

### P3 — 可选项
- [ ] 放弃 Web Serial 代码完全删除（当前已删大部分，残留常量 `HW_MODES` 等）
- [ ] 采集卡片 + 语音采集 + 体态照片卡片的视觉对齐（grid 高度一致性）
- [ ] HRV 时间域 / 频域分析（当前固件只给 SDNN，可扩展）

---

## 十一、构建验证汇总

| 步骤 | 时间 | 状态 |
|---|---|---|
| 删伪代码 + 诚实化状态条 | — | ✅ |
| ECG 网格 + 静态 PPG 合成 | 7.62s | ✅ |
| Web Serial API 实现 | ~7s | ✅（代码编译通过） |
| 固件嗅探 + CheezPPG 协议对齐 | 7.40s | ✅ |
| 后端 sys.path 修正 | — | ✅ |
| 后端 hardware-status 端点 | — | ✅ 200 OK |
| 后端 SSE stream 端点 | — | ✅ 路由注册成功 |
| 前端 SSE EventSource | 7.62s | ✅ |
| **硬件 SSE 实时示波** | — | ⏸ COM3 被占待拔插验证 |

---

## 十二、快速重启命令

```powershell
# 后端 :8767（已含 ppg 硬件桥）
cd e:\工作\qingnang-APP\backend
python -m uvicorn app.main:app --host localhost --port 8767

# 前端 :5173
cd e:\工作\qingnang-APP\frontend
node .\node_modules\vite\bin\vite.js --host --port 5173

# 硬件自检（独立验证 COM3 状态）
cd e:\工作\qingnang\青囊\脉诊\采集
python ppg_acquisition.py --selftest

# 直接测 SSE stream（PowerShell 看几帧）
$r = Invoke-WebRequest -Uri "http://localhost:8767/api/v1/ppg/stream?duration=3" -TimeoutSec 5
$r.Content -split "`n" | Select-Object -First 20
```

---

*日志生成时间：2026-09-27 · 版本 v1.0（后端 SSE 桥接版）*
