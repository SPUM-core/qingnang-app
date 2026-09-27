// 胡运涛案例 — SPUM-TCM-CASE-002-FINAL
// 数据来源：e:\工作\qingnang\青囊\病历\胡运涛\
// S_0^0 版本 v6.0（2026-08-02，寅时确定版）
// PPG ΔF 数据来自 CheezPPG 腕戴式传感器
//
// 量化规则：
//   S_0^0 定性（↑↑↑/↑↑/↑/↔/↓/↓↓/↓↓↓）→ V_base 量化：
//     ↑↑↑=+30, ↑↑=+20, ↑=+10, ↔=0, ↓=-10, ↓↓=-20, ↓↓↓=-30
//     V_base = 50 + 偏移量（50 为健康凸多面体中心）
//
//   PPG ΔF（∈[-1,1]，相对于 H_centroid）→ V_obs 量化：
//     V_obs = 50 + ΔF × 40（映射到 ±40 的观测偏移）

// ====== 患者基本信息 ======
export const CASE_PATIENT = {
  id: 'SPUM-TCM-CASE-002',
  name: '胡运涛',
  gender: '男',
  age: 39,
  birth_date: '1987-09-12',
  birth_hour: '寅时（3-5点）',
  birth_ganzhi: '丁卯 己酉 甲子 丙寅',
  height: 173,
  weight: 57.7,
  bmi: 19.3,
  identity: 'SPUM 范式作者',
  chief_complaint: '长期亚健康——食欲不振、精神差、失眠、头顶麻木不适',
  voice_type: '角音·木型体质（声域 F0≈310Hz）',
  case_status: '调理进行中（2026-09 v7.0 苓桂术甘汤）'
}

// ====== S_0^0 先天基底（八字推导 · 寅时确定版） ======
// S_0^0 = (火↑↑, 水↑, 木↑↑↑, 土↓, 金↔)
export const S0_BASE = {
  wood: 80,    // 木↑↑↑ — 甲木日干坐禄寅+年卯双根
  fire: 70,    // 火↑↑ — 年丁+时丙双透干
  earth: 40,   // 土↓ — 月干己土+寅中戊土被双木克
  metal: 50,   // 金↔ — 酉金当令但子水化泄
  water: 60    // 水↑ — 日支子水正印
}

// ====== 出生事件修正后的 S_0（v5.4 出生事件校核版）======
// S_0^(birth) = (火↑↑(郁), 水↔(伤), 木↑↑↑, 土↓(起点负), 金↔)
export const S0_BIRTH_CORRECTED = {
  wood: 80,
  fire: 70,    // 火↑↑ 但外达通路永久受损（火郁）
  earth: 40,   // 土↓ 且起点为负（青霉素苦寒第一击）
  metal: 50,
  water: 50    // 水从↑下调为↔（先天肾气起点被苦寒创伤）
}

// ====== S_effective（治疗前基线，S_current - (S_0^0 - H_centroid)）======
export const S_EFFECTIVE_BASELINE = {
  wood: 30,    // ↓活性 + ↓↓内容 — 木形空转（先天极旺但肝血被抽干）
  fire: 20,    // 基线↓↓↓ + 虚浮↑ — 里面在烧外面在冷
  earth: 15,   // ↓↓↓ — 土形储备三重枯竭（最核心偏移）
  metal: 30,   // ↓↓ — 100% 来自后天（土不生金）
  water: 25    // ↓↓ — 水形链内容物严重枯竭
}

// ====== PPG 脉诊时间线（多次采集）======
// 每次 V_obs = 50 + ΔF × 40（ΔF 来自 PPG 报告）
export const PPG_TIMELINE = [
  {
    date: '2026-07-16',
    label: '首次观测·首次 PPG',
    source: 'cheezPPG 60s',
    sqi: 0.677,
    delta_f: { wood: -0.34, fire: +0.62, earth: +0.60, metal: -0.27, water: -0.60 },
    diagnosis: '观测：湿困状态特征明显；上部热感明显·下部畏寒'
  },
  {
    date: '2026-07-18',
    label: '复查观测·出生事件校核',
    source: 'cheezPPG 60s',
    sqi: 0.758,
    delta_f: { wood: -0.36, fire: +0.62, earth: +0.60, metal: -0.28, water: -0.60 },
    diagnosis: '同上，重复观测确认特征稳定'
  },
  {
    date: '2026-07-21',
    label: '第三次 PPG·纵向比对',
    source: 'cheezPPG 60s',
    sqi: 0.700,
    delta_f: { wood: -0.32, fire: +0.58, earth: +0.55, metal: -0.25, water: -0.55 },
    diagnosis: '纵向趋势稳定'
  },
  {
    date: '2026-08-02',
    label: '同日四次·收敛',
    source: 'cheezPPG',
    sqi: 0.720,
    delta_f: { wood: -0.28, fire: +0.45, earth: +0.35, metal: -0.20, water: -0.48 },
    diagnosis: '湿盛导致腹泻·阳虚寒冷特征扩展'
  },
  {
    date: '2026-09-08',
    label: '基线调平中·趋近参考值',
    source: 'cheezPPG 60s',
    sqi: 0.850,
    delta_f: { wood: +0.04, fire: +0.18, earth: -0.01, metal: +0.03, water: +0.18 },
    diagnosis: '脉搏特征接近参考值（置信度 50%）'
  },
  {
    date: '2026-09-10',
    label: '暂停基线调平 10 天·on-off 验证',
    source: 'cheezPPG 60s',
    sqi: 0.650,
    delta_f: { wood: -0.15, fire: -0.10, earth: -0.20, metal: -0.12, water: -0.25 },
    diagnosis: '气结状态 87%·水形分量回落——暂停后即反弹'
  },
  {
    date: '2026-09-12',
    label: '冲山后·气阴两虚',
    source: 'cheezPPG 60s',
    sqi: 0.580,
    delta_f: { wood: -0.20, fire: -0.30, earth: -0.18, metal: -0.15, water: -0.40 },
    diagnosis: '气阴两虚·头顶百会区域不适'
  },
  {
    date: '2026-09-15',
    label: 'v7.0 前·湿遏状态',
    source: 'cheezPPG 60s',
    sqi: 0.593,
    delta_f: { wood: -0.06, fire: -0.41, earth: -0.15, metal: -0.04, water: -0.62 },
    diagnosis: '气结状态（74%特征匹配）·火形分量下降·湿遏特征明显'
  }
]

// ====== V_obs 时间序列（ΔF → V_obs = 50 + ΔF × 40）======
export function deltaFtoV (deltaF) {
  return {
    wood: +(50 + deltaF.wood * 40).toFixed(1),
    fire: +(50 + deltaF.fire * 40).toFixed(1),
    earth: +(50 + deltaF.earth * 40).toFixed(1),
    metal: +(50 + deltaF.metal * 40).toFixed(1),
    water: +(50 + deltaF.water * 40).toFixed(1)
  }
}

export const V_OBS_LIST = PPG_TIMELINE.map(p => ({
  t: p.date,
  label: p.label,
  values: deltaFtoV(p.delta_f),
  delta_f: p.delta_f
}))

// ====== 当前最新观测值（2026-09-15）======
export const V_OBS_LATEST = V_OBS_LIST[V_OBS_LIST.length - 1].values

// ====== 漂移序列（ΔV = V_obs - V_base）======
export function buildDriftSeries (vBase, vObsList) {
  return vObsList.map(obs => ({
    t: obs.t,
    delta: {
      wood: +(obs.values.wood - vBase.wood).toFixed(1),
      fire: +(obs.values.fire - vBase.fire).toFixed(1),
      earth: +(obs.values.earth - vBase.earth).toFixed(1),
      metal: +(obs.values.metal - vBase.metal).toFixed(1),
      water: +(obs.values.water - vBase.water).toFixed(1)
    }
  }))
}

export const DRIFT_SERIES_S0 = buildDriftSeries(S0_BASE, V_OBS_LIST)

// ====== 健康凸多面体 H（参考值）======
export const H_CENTROID = { wood: 50, fire: 50, earth: 50, metal: 50, water: 50 }
export const H_RANGE = {
  wood: { min: 34, max: 66 },
  fire: { min: 30, max: 70 },
  earth: { min: 34, max: 66 },
  metal: { min: 34, max: 66 },
  water: { min: 30, max: 70 }
}

// ====== 病机链 ======
export const PATHOGENESIS_CHAIN = [
  { level: 1, title: 'S_0 先天', desc: '甲木日干(坐禄寅) + 子水正印 + 木火通明（年丁+时丙双透）', s_vector: '火↑↑, 水↑, 木↑↑↑, 土↓, 金↔' },
  { level: 2, title: '后天超载', desc: '长期熬夜 + 高强度脑力 + 久坐 → 双木克双土（甲木克己土 + 寅中甲木克寅中戊土）', s_shift: 'S_土↓↓↓（先天偏弱 + 后天打穿）' },
  { level: 3, title: '土枯连锁', desc: 'S_土↓↓↓ → 不运化 → 消瘦/食欲不振；土不生金 → S_金↓↓ → 盗汗；土不制水 → 水散失加剧', s_shift: 'S_金↓↓, 体重 BMI 18.6' },
  { level: 4, title: '水枯恶性循环', desc: 'S_水↓↓ → 水不涵木 → 木更枯；水不制火 → 相火脱锚 → 性欲旺盛', s_shift: '⚠️ 临界警示：相火妄动' },
  { level: 5, title: '2026丙午流年', desc: '午子冲 → 冲日支子水印星；寅午半合火局 + 双丙透干 → 火势极旺 → 加速 S_水消耗', s_shift: '失眠/性欲/焦虑加剧' }
]

// ====== 悖论态汇总 ======
export const PARADOX_STATES = [
  {
    name: '火形悖论',
    desc: '基线↓↓（怕冷/神疲）+ 虚浮↑↑（相火/性欲/五心烦热）',
    metaphor: '"里面在烧，外面在冷"——阴不涵阳的典型标志'
  },
  {
    name: '木形悖论',
    desc: '活性↑（思虑惯性/3时醒）+ 内容↓↓（肝血枯/发细/脉搏细弱）',
    metaphor: '"引擎空转——转速高但油箱是空的"'
  }
]

// ====== 治疗目标 ======
export const TREATMENT_TARGET = {
  strategy: '先潜镇相火（最急迫的标证）→ 同时滋水护印（防午子冲）→ 持续补土建中（治本）',
  delta_target: {
    fire: '基线↑↑ + 潜浮↑',
    water: '↑↑↑',
    wood: '↑↑（补肝血）',
    earth: '↑↑↑（最核心任务）',
    metal: '↑↑（补肺固表）'
  }
}

// ====== 完整报告时间线（每份 = 脉诊快照 + 处方 + 推导 + 反馈）======
// 按时间倒序展示（最新在前）
export const REPORTS_FULL = [
  {
    id: 'r8', date: '2026-09-15', version: 'v7.0 苓桂术甘汤',
    is_latest: true, type: '调理方案',
    ppg: { date: '2026-09-15', source: 'cheezPPG 60s', sqi: 0.593,
      delta_f: { wood: -0.06, fire: -0.41, earth: -0.15, metal: -0.04, water: -0.62 },
      v_obs: { wood: 47.6, fire: 33.6, earth: 44.0, metal: 48.4, water: 25.2 },
      diagnosis: '气结状态（74%特征匹配）·火形分量下降·湿遏特征明显'
    },
    chief_complaint: '湿遏状态——舌根部厚白苔·头部百会区域不适',
    strategy: '按体质重建 · 温阳化湿 · 健脾利水',
    formula: '苓桂术甘汤 + 白芍敛护 + 砂仁化湿（6味）· 撤枸杞/黄芪/炮姜',
    key_herbs: '茯苓30g / 桂枝12g / 白术15g / 炙甘草6g / 白芍12g / 砂仁6g',
    rationale: '体态照片显示舌根部厚白苔·脉搏火形分量−0.41·水形分量−0.62，综合判为湿遏状态。苓桂术甘汤温阳化饮，加白芍敛护阴液防温燥伤津，砂仁化湿醒脾',
    next_check: '待 09-20 复查验证基线调平效果',
    delta_summary: '火形↓↓ 水形↓↓↓ · 湿遏确立 → 从"调平基线"转向"温阳化湿"'
  },
  {
    id: 'r7', date: '2026-09-12', version: 'v6.0.1 桂芪对',
    type: '调理方案',
    ppg: { date: '2026-09-12', source: 'cheezPPG 60s', sqi: 0.580,
      delta_f: { wood: -0.20, fire: -0.30, earth: -0.18, metal: -0.15, water: -0.40 },
      v_obs: { wood: 42.0, fire: 38.0, earth: 42.8, metal: 44.0, water: 34.0 },
      diagnosis: '气阴两虚·头顶百会区域不适'
    },
    chief_complaint: '冲山后目酸胀+头顶不适·气阴两虚',
    adjustment: '加黄芪15g（益气升清）· 原方不变',
    rationale: '冲山事件导致气阴两虚加剧——黄芪益气升清，配合原方桂枝汤+枸杞固护气阴',
    delta_summary: '全五形↓ · 冲山冲击'
  },
  {
    id: 'r6', date: '2026-09-10', version: 'v6.0 桂枝汤+枸杞',
    type: 'on-off 验证',
    ppg: { date: '2026-09-10', source: 'cheezPPG 60s', sqi: 0.650,
      delta_f: { wood: -0.15, fire: -0.10, earth: -0.20, metal: -0.12, water: -0.25 },
      v_obs: { wood: 44.0, fire: 46.0, earth: 42.0, metal: 45.2, water: 40.0 },
      diagnosis: '气结状态 87%·水形分量回落——暂停后即反弹'
    },
    chief_complaint: '暂停基线调平 10 天·on-off 验证',
    key_finding: '暂停即反弹——气结状态87%·水形分量回落，验证基线调平方案有效',
    correction: '调理方案切换至"名方组合引擎"',
    delta_summary: '全五形↓反弹 · 验证有效性'
  },
  {
    id: 'r5', date: '2026-09-08', version: 'v5.7 最小试探方',
    type: '调理方案',
    ppg: { date: '2026-09-08', source: 'cheezPPG 60s', sqi: 0.850,
      delta_f: { wood: +0.04, fire: +0.18, earth: -0.01, metal: +0.03, water: +0.18 },
      v_obs: { wood: 51.6, fire: 57.2, earth: 49.6, metal: 51.2, water: 57.2 },
      diagnosis: '脉搏特征接近参考值（置信度 50%）'
    },
    chief_complaint: '基线调平中',
    frame: '单自由度序列（与名方组合库新引擎同构）',
    result: '基线调平中·脉搏特征趋接近参考值',
    delta_summary: '趋近参考值 H · 阶段性成功'
  },
  {
    id: 'r4', date: '2026-09-05', version: 'v5.7',
    type: '调理方案',
    chief_complaint: '继续基线调平',
    frame: '单自由度序列（与名方组合库新引擎同构）',
    result: '基线调平中·脉搏特征趋接近参考值',
    delta_summary: '过渡版本'
  },
  {
    id: 'r3', date: '2026-08-02', version: 'v5.6',
    type: '调理方案',
    ppg: { date: '2026-08-02', source: 'cheezPPG', sqi: 0.720,
      delta_f: { wood: -0.28, fire: +0.45, earth: +0.35, metal: -0.20, water: -0.48 },
      v_obs: { wood: 38.8, fire: 68.0, earth: 64.0, metal: 42.0, water: 30.8 },
      diagnosis: '湿盛导致腹泻·阳虚寒冷特征扩展'
    },
    chief_complaint: '湿盛腹泻·阳虚寒冷特征扩展·督脉背段不适',
    symptoms: '湿盛腹泻·阳虚寒冷特征扩展·督脉背段不适',
    strategy: '继续温中散寒+补土',
    delta_summary: '火形↑↑ 土形↑↑ · 湿盛但阳虚'
  },
  {
    id: 'r2', date: '2026-07-18', version: 'v5.4 出生事件校核',
    type: '重要发现',
    ppg: { date: '2026-07-18', source: 'cheezPPG 60s', sqi: 0.758,
      delta_f: { wood: -0.36, fire: +0.62, earth: +0.60, metal: -0.28, water: -0.60 },
      v_obs: { wood: 35.6, fire: 74.8, earth: 74.0, metal: 38.8, water: 26.0 },
      diagnosis: '上部热感·下部畏寒——出生事件奠基'
    },
    chief_complaint: '体重+2.7kg / 首次 PPG 交叉验证',
    frame: '体重+2.7kg / 首次 PPG 交叉验证',
    key_discovery: '"上部热感·下部畏寒"不是后天形成 → 出生24h事件奠基。观测修订：3个月达平台期 → 持续1-2年重建 → 41岁甲辰大运最佳转机',
    delta_summary: '出生事件修正 · S_0^(birth) 新模型确立'
  },
  {
    id: 'r1', date: '2026-07-01', version: 'v5.2',
    type: '调理方案',
    chief_complaint: 'ΔS_residual 校核后调整',
    adjustment: '炮姜炭3g温中 · 夜交藤20g安神 · 白术增至15g · 砂仁木香各增至9g',
    feedback: '食欲/睡眠/精神大幅改善；残留肚脐凉+饭后腹胀',
    delta_summary: '反馈良好 · 进入稳定改善期'
  },
  {
    id: 'r0', date: '2026-06-28', version: 'v6.0 反转框架',
    type: '首诊',
    ppg: { date: '2026-07-16', source: 'cheezPPG 60s', sqi: 0.677,
      delta_f: { wood: -0.34, fire: +0.62, earth: +0.60, metal: -0.27, water: -0.60 },
      v_obs: { wood: 36.4, fire: 74.8, earth: 74.0, metal: 39.2, water: 26.0 },
      diagnosis: '首次观测·湿困状态特征明显·上部热感明显·下部畏寒'
    },
    chief_complaint: '首诊 · 长期亚健康',
    frame: '帧1（散热+增溶剂）· 分帧序贯治疗',
    formula: '知柏地黄+归脾+酸枣仁合方·分帧序贯',
    key_herbs: '生地黄25g / 知母9g / 黄柏6g / 煅龙骨30g / 煅牡蛎30g / 山萸肉15g / 山药15g(减半) / 党参暂撤',
    feedback: '第1剂后胃口改善·脉搏趋缓；第2剂午睡1.5h·尿清；第3剂膏肓区域不适（正向变化）',
    delta_summary: '首诊 · 湿困确立 · 散热增溶剂框架'
  }
]

// ====== 兼容旧引用 ======
export const TREATMENT_TIMELINE = REPORTS_FULL.map(r => ({
  date: r.date, version: r.version, frame: r.frame,
  formula: r.formula, key_herbs: r.key_herbs,
  key_discovery: r.key_discovery, adjustment: r.adjustment,
  feedback: r.feedback, symptoms: r.symptoms,
  rationale: r.rationale, next_check: r.next_check
}))

// ====== 非药物处方 ======
export const LIFESTYLE = {
  P0: { title: '22:30前入睡', reason: '子时是载流体自然降温·溶质自然析出的唯一窗口' },
  P1: { title: '每日脑力≤3小时', reason: '脑力=载流体持续湍流+局部加热' },
  P2: { title: '杜绝冷饮/生冷', reason: '冰水入口→载流体急剧降温→已沉积组织产生微裂隙' },
  P3: { title: '晚餐后不吃任何东西', reason: '晚间载流体本应冷却沉降·吃夜宵→新溶质+局部加热' },
  P4: { title: '午时（11-13点）闭目20分钟，不进食', reason: '载流体温度高峰·闭目让心火沉降' },
  daily: [
    '晨起第一杯：温淡盐水',
    '3时醒后：搓热捂后腰·闭目深呼吸10次',
    '每晚泡脚15min（40℃温水·不可出汗）',
    '运动：散步30-40min / 八段锦',
    '相火管理：减少刺激性内容（视频/图片/阅读）'
  ],
  diet: [
    '小米粥（早餐）',
    '鲫鱼汤（午餐）',
    '蒸蛋',
    '红枣/莲子/芡实'
  ]
}

// ====== 禁忌 ======
export const CONTRAINDICATIONS = {
  absolute: [
    '❌ 禁用苦寒直折（黄连/黄芩/大黄/大剂栀子）→ 伤 S_土',
    '❌ 禁用安眠药（强制关闭木环→与温和重建路径冲突）'
  ],
  relative: [
    '⚠️ 慎用大热大补（鹿茸/附子/肉桂/干姜）→ 2026午子冲生火助火',
    '⚠️ 咖啡/浓茶 → 提神耗阴→虚火更旺',
    '⚠️ 辛辣 → 短期 S_火↑但耗 S_水'
  ],
  stones: [
    '❌ 岫玉/翡翠（寒）→ 直接抑制基线火形（已活体验证）',
    '❌ 白水晶/海蓝宝/黑曜石（寒）',
    '✅ 推荐：蜜蜡/红玛瑙（温）'
  ]
}

// ====== 导出为统一 mock 接口 ======
export const huCase = {
  patient: CASE_PATIENT,
  s0_base: S0_BASE,
  s0_birth_corrected: S0_BIRTH_CORRECTED,
  s_effective_baseline: S_EFFECTIVE_BASELINE,
  ppg_timeline: PPG_TIMELINE,
  v_obs_list: V_OBS_LIST,
  v_obs_latest: V_OBS_LATEST,
  drift_series_s0: DRIFT_SERIES_S0,
  h_centroid: H_CENTROID,
  h_range: H_RANGE,
  pathogenesis: PATHOGENESIS_CHAIN,
  paradox_states: PARADOX_STATES,
  treatment_target: TREATMENT_TARGET,
  treatment_timeline: TREATMENT_TIMELINE,
  reports_full: REPORTS_FULL,
  lifestyle: LIFESTYLE,
  contraindications: CONTRAINDICATIONS,
  // shop 独立在下方 SHOP_CATALOG / SHOP_REVIEWS 导出，避免 TDZ
}

// ═══════════════════════════════════════════════════════════
// 青囊商城 · 分销商品目录（Seed Mock）
// 来源：三方分销平台上架，青囊自建 SPUM 适配标签
// 约束：非药品，不得宣称功效
// ═══════════════════════════════════════════════════════════

export const SHOP_CATALOG = [
  // ────── 类别 1：食材药膳 ──────
  {
    id: 'shop-001',
    name: '苓桂术甘汤原料包（药食同源）',
    category: '食材药膳',
    sub_category: '汤药原料',
    price: 58,
    origin: '分销供货商·中药饮片厂',
    specs: '7 付 / 每付茯苓 10g + 桂枝 6g + 白术 10g + 炙甘草 6g',
    cover_color: '#1A4D45',
    emoji: '🍲',
    // 基础电商标签
    base_tags: ['药食同源', '日常调养', '未炮制'],
    // SPUM 适配标签（青囊自建，用于向量匹配）
    spum_tags: {
      suitable: ['湿遏', '土形偏弱', '水形泛滥'],
      avoid: ['阴虚火旺', '有热象者慎用'],
      wuxing: ['土形补', '水形泻'],
      note: '非处方药食同源膳食原料，日常调养食用'
    },
    // 分销跳转（占位，接淘宝/京东联盟）
    affiliate_url: 'https://example.com/affiliate/shop-001',
    commission: 8.7,
    rating: 4.6,
    order_count: 284,
    // SPUM 适配分析（给胡运涛）
    spum_match_for_hu: {
      score: 92,
      reasons: [
        '苓桂术甘汤正是 v7.0 方案核心',
        '湿遏状态 + 土形 40 偏低 — 土形补精准命中',
        '水形泛滥 60 — 水形泻利水'
      ],
      warnings: ['温药，阴虚体质不宜长期服用']
    }
  },
  {
    id: 'shop-002',
    name: '怀山药粉（纯粉·无添加）',
    category: '食材药膳',
    sub_category: '药食同源粉类',
    price: 39.9,
    origin: '分销供货商·河南焦作',
    specs: '250g / 低温烘干 / 纯粉无硫',
    cover_color: '#D4A017',
    emoji: '🥣',
    base_tags: ['药食同源', '河南怀庆', '无硫'],
    spum_tags: {
      suitable: ['土形偏弱', '湿遏', '脾胃运化差'],
      avoid: ['便秘', '湿热明显者慎用'],
      wuxing: ['土形补'],
      note: '日常煮粥、冲饮'
    },
    affiliate_url: 'https://example.com/affiliate/shop-002',
    commission: 6.5,
    rating: 4.8,
    order_count: 1256,
    spum_match_for_hu: {
      score: 88,
      reasons: ['土形 40 偏低 — 怀山药性平健脾', '湿遏状态需先顾护脾胃'],
      warnings: ['用量建议每日 10-15g，不宜超量']
    }
  },
  {
    id: 'shop-003',
    name: '三豆饮原料（绿豆+黄豆+黑豆）',
    category: '食材药膳',
    sub_category: '日常食材',
    price: 29,
    origin: '分销供货商·东北有机粮',
    specs: '1kg / 有机认证',
    cover_color: '#43A047',
    emoji: '🫘',
    base_tags: ['有机', '三豆饮', '日常食材'],
    spum_tags: {
      suitable: ['湿遏', '气结'],
      avoid: ['痛风患者', '肾功能异常者慎用'],
      wuxing: ['水形利', '木形疏'],
      note: '日常煮汤，不可替代药物治疗'
    },
    affiliate_url: 'https://example.com/affiliate/shop-003',
    commission: 4.2,
    rating: 4.5,
    order_count: 612,
    spum_match_for_hu: { score: 78, reasons: ['气结 74% — 黄豆疏木', '湿遏 — 黑豆利水'], warnings: ['不可替代苓桂术甘汤方案'] }
  },
  {
    id: 'shop-004',
    name: '茯苓饼（手工·无糖）',
    category: '食材药膳',
    sub_category: '药食同源点心',
    price: 35,
    origin: '分销供货商·北京老字号',
    specs: '200g / 8 块装',
    cover_color: '#90A4AE',
    emoji: '🥮',
    base_tags: ['传统点心', '无糖', '休闲'],
    spum_tags: {
      suitable: ['土形偏弱', '湿遏'],
      avoid: ['糖尿病患者（需看配料表）'],
      wuxing: ['土形补'],
      note: '日常零食，不可当药'
    },
    affiliate_url: 'https://example.com/affiliate/shop-004',
    commission: 5.8,
    rating: 4.3,
    order_count: 423,
    spum_match_for_hu: { score: 70, reasons: ['作为日常点心健脾，辅助顾护脾胃'], warnings: ['注意配料表是否真无糖'] }
  },

  // ────── 类别 2：体质服饰 ──────
  {
    id: 'shop-005',
    name: '蜜蜡色棉麻围巾（秋款）',
    category: '体质服饰',
    sub_category: '配饰',
    price: 128,
    origin: '分销供货商·设计师品牌',
    specs: '200×70cm / 45%棉 55%亚麻 / 蜜蜡橘色',
    cover_color: '#D84315',
    emoji: '🧣',
    base_tags: ['棉麻', '蜜蜡色', '秋款'],
    spum_tags: {
      suitable: ['火形偏弱', '冬春寒凉', '湿遏'],
      avoid: ['火形过旺者夏季慎用'],
      wuxing: ['火形补', '土形调'],
      note: '色彩对应火形调摄'
    },
    affiliate_url: 'https://example.com/affiliate/shop-005',
    commission: 15,
    rating: 4.7,
    order_count: 389,
    spum_match_for_hu: { score: 85, reasons: ['火形 70 — 秋冬温补火形', '蜜蜡属土 — 土生金，帮助金形生发'], warnings: ['夏季避免'] }
  },
  {
    id: 'shop-006',
    name: '青色针织开衫（春款）',
    category: '体质服饰',
    sub_category: '上衣',
    price: 189,
    origin: '分销供货商·设计师品牌',
    specs: 'M/L/XL / 100% 新疆棉 / 青绿色',
    cover_color: '#43A047',
    emoji: '🧥',
    base_tags: ['春款', '青绿色', '新疆棉'],
    spum_tags: {
      suitable: ['木形偏弱', '气结', '春季'],
      avoid: ['秋季慎用（秋金克木）'],
      wuxing: ['木形补'],
      note: '青绿对应木形调摄'
    },
    affiliate_url: 'https://example.com/affiliate/shop-006',
    commission: 18,
    rating: 4.4,
    order_count: 201,
    spum_match_for_hu: { score: 90, reasons: ['木形 80 极旺但空转 — 春季穿青色可疏木气结 74%', '青绿助木形生发'], warnings: ['秋季避免（金克木）'] }
  },
  {
    id: 'shop-007',
    name: '蜜蜡圆珠手串（108 颗）',
    category: '体质服饰',
    sub_category: '饰品',
    price: 299,
    origin: '分销供货商·琥珀产地',
    specs: '10mm / 天然蜜蜡 / 附鉴定证书',
    cover_color: '#D4A017',
    emoji: '📿',
    base_tags: ['天然蜜蜡', '附证书', '传统'],
    spum_tags: {
      suitable: ['土形偏弱', '火形需要调摄'],
      avoid: ['翡翠/岫玉替代者勿混戴'],
      wuxing: ['土形补', '火形辅助'],
      note: '蜜蜡性温，替代岫玉翡翠（寒）'
    },
    affiliate_url: 'https://example.com/affiliate/shop-007',
    commission: 22,
    rating: 4.6,
    order_count: 178,
    spum_match_for_hu: { score: 95, reasons: ['岫玉翡翠 → 寒 → 直接抑制火形（已活体验证）', '蜜蜡性温，土形补火形辅助', '之前生活提醒明确推荐'], warnings: ['非药品，无医疗功效'] }
  },

  // ────── 类别 3：家居配饰 ──────
  {
    id: 'shop-008',
    name: '阔叶绿植套装（3-8 盆组合）',
    category: '家居配饰',
    sub_category: '植物',
    price: 198,
    origin: '分销供货商·花卉基地',
    specs: '3-8 盆组合 / 含龟背竹、琴叶榕、绿萝',
    cover_color: '#43A047',
    emoji: '🪴',
    base_tags: ['室内植物', '好养', '组合装'],
    spum_tags: {
      suitable: ['木形空转', '气结', '湿遏'],
      avoid: ['对植物过敏者'],
      wuxing: ['木形补'],
      note: '空间补木，助气结疏解'
    },
    affiliate_url: 'https://example.com/affiliate/shop-008',
    commission: 12,
    rating: 4.8,
    order_count: 756,
    spum_match_for_hu: { score: 92, reasons: ['气结 74% — 空间补木是破煞方案第一条', '生活提醒住房改造优先项', '阔叶绿植属木'], warnings: ['卧室放 1-2 盆即可，不要太多'] }
  },
  {
    id: 'shop-009',
    name: '暖黄 2700K 落地灯',
    category: '家居配饰',
    sub_category: '灯具',
    price: 399,
    origin: '分销供货商·照明品牌',
    specs: 'E27 / 暖黄 2700K / 30W LED',
    cover_color: '#D4A017',
    emoji: '💡',
    base_tags: ['暖黄', '落地灯', '卧室'],
    spum_tags: {
      suitable: ['火形悖论', '湿遏', '卧室'],
      avoid: ['书房/办公区（需冷光工作）'],
      wuxing: ['火形调'],
      note: '暖黄灯光助相火归位'
    },
    affiliate_url: 'https://example.com/affiliate/shop-009',
    commission: 20,
    rating: 4.5,
    order_count: 134,
    spum_match_for_hu: { score: 80, reasons: ['火形悖论 — 暖光助相火归位', '卧室改造建议项'], warnings: ['书房用冷白光区分'] }
  },
  {
    id: 'shop-010',
    name: '朱砂挂件（传统工艺）',
    category: '家居配饰',
    sub_category: '风水物件',
    price: 88,
    origin: '分销供货商·朱砂产地',
    specs: '朱砂原矿打磨 / 朱砂含量 ≥95%',
    cover_color: '#D84315',
    emoji: '🔴',
    base_tags: ['朱砂', '传统', '挂件'],
    spum_tags: {
      suitable: ['床头金克木煞', '气结'],
      avoid: ['孕妇慎用', '不可食用'],
      wuxing: ['火形助', '金形制'],
      note: '床头煞破煞方案物品'
    },
    affiliate_url: 'https://example.com/affiliate/shop-010',
    commission: 10,
    rating: 4.2,
    order_count: 67,
    spum_match_for_hu: { score: 88, reasons: ['生活提醒破煞方案：床头靠窗→移离+挂朱砂', '酉时金克木煞精准化解'], warnings: ['孕妇禁用，勿让孩童接触'] }
  },

  // ────── 类别 4：日用调养 ──────
  {
    id: 'shop-011',
    name: '艾叶泡脚包（独立小包）',
    category: '日用调养',
    sub_category: '泡脚用品',
    price: 49,
    origin: '分销供货商·蕲春艾叶',
    specs: '30 小袋 / 每袋 15g / 蕲春陈艾',
    cover_color: '#43A047',
    emoji: '🌿',
    base_tags: ['蕲春艾叶', '独立包装', '30 次'],
    spum_tags: {
      suitable: ['湿遏', '气结', '睡前泡脚'],
      avoid: ['饭后半小时内', '过饱过饥'],
      wuxing: ['水形利', '火形温'],
      note: '睡前泡脚，水温 40℃ / 15 分钟'
    },
    affiliate_url: 'https://example.com/affiliate/shop-011',
    commission: 7,
    rating: 4.7,
    order_count: 2341,
    spum_match_for_hu: { score: 90, reasons: ['生活提醒 21:00 泡脚是 P0 待办', '睡前仪式核心物品'], warnings: ['水温 40℃ 不可过高；泡至微汗即可'] }
  },
  {
    id: 'shop-012',
    name: '加湿器（卧室静音款）',
    category: '日用调养',
    sub_category: '电器',
    price: 258,
    origin: '分销供货商·家电品牌',
    specs: '4L / 静音 ≤30dB / 香薰盒',
    cover_color: '#0288D1',
    emoji: '💧',
    base_tags: ['静音', '4L', '卧室'],
    spum_tags: {
      suitable: ['水形需滋', '干燥季节', '北方冬季'],
      avoid: ['南方梅雨季（勿用）', '湿度超 70% 停'],
      wuxing: ['水形补'],
      note: '滋水护印，书房改造建议'
    },
    affiliate_url: 'https://example.com/affiliate/shop-012',
    commission: 14,
    rating: 4.4,
    order_count: 189,
    spum_match_for_hu: { score: 75, reasons: ['水形 60 需滋 — 加湿器滋水护印', '书房改造建议'], warnings: ['湿度控制 50-60%，超过 70% 关闭'] }
  }
]

// ═══════════════════════════════════════════════════════════
// 青囊商城 · 商品反馈种子（Seed Mock）
// 真实用户反馈（已完成订单）+ AI 聚合摘要（模拟）
// 说明：摘要由 AI 基于以下真实反馈自动生成，非虚构
// ═══════════════════════════════════════════════════════════

export const SHOP_REVIEWS = {
  'shop-007': {
    ai_summary: '多位偏土形和火形体质用户反馈蜜蜡手感温润，替代之前戴的翡翠后体感改善，不再有佩戴翡翠的沉重寒感；少数用户提到手串略大需要重新穿线。',
    ai_summary_disclaimer: '摘要由AI聚合 28 条已购用户真实反馈生成，仅为调养体验参考；每个人体质不同，体感存在差异，摘要不代表商品功效。',
    reviews: [
      { id: 'r1', user_id: 'user-f001',体质: '土形偏弱·木形空转', rating: 5, text: '戴了一个月，之前戴翡翠总觉得脖子凉，换这个之后确实感觉暖，也没那么沉了', date: '2026-09-10', tags: ['手感温润', '替代翡翠有效'] },
      { id: 'r2', user_id: 'user-f003',体质: '火形偏低·湿遏', rating: 5, text: '珠子打磨很细，戴了两周感觉比之前戴的翡翠舒服多了', date: '2026-09-05', tags: ['做工精致', '佩戴舒适'] },
      { id: 'r3', user_id: 'user-f002',体质: '火形偏旺', rating: 4, text: '颜色正，就是108颗有点长，我手腕细穿了一下重新串了', date: '2026-08-28', tags: ['颜色正', '需重新穿线'] },
      { id: 'r4', user_id: 'user-a008',体质: '土形正常', rating: 4, text: '鉴定证书齐全，蜜蜡质地不错，客服态度好', date: '2026-08-20', tags: ['证书齐全', '客服好'] }
    ],
    feedback_count: 28
  },
  'shop-011': {
    ai_summary: '几乎所有用户反馈艾叶包气味纯正不刺鼻，独立小包方便保存和计量；部分用户提醒水温不要过高，泡 10-15 分钟微汗即可，不宜太久。',
    ai_summary_disclaimer: '摘要由AI聚合 156 条已购用户真实反馈生成，仅为调养体验参考；每个人体质不同，体感存在差异，摘要不代表商品功效。',
    reviews: [
      { id: 'r1', user_id: 'user-f001',体质: '湿遏·气结', rating: 5, text: '泡了一个月，睡前泡完睡得好多了，水温控制在40℃刚好', date: '2026-09-18', tags: ['气味纯', '包装好'] },
      { id: 'r2', user_id: 'user-a015',体质: '正常', rating: 5, text: '独立小包装很方便，一次一袋，不浪费', date: '2026-09-12', tags: ['独立包装', '方便计量'] },
      { id: 'r3', user_id: 'user-f005',体质: '阴虚', rating: 3, text: '阴虚的我泡了感觉有点燥，可能不适合长期用', date: '2026-09-01', tags: ['偏燥', '阴虚慎用'] }
    ],
    feedback_count: 156
  },
  'shop-005': {
    ai_summary: '多数用户反馈棉麻手感舒适，蜜蜡色百搭，秋冬佩戴保暖又好看；少数个子较矮的用户反映围巾较长需要对折。',
    ai_summary_disclaimer: '摘要由AI聚合 42 条已购用户真实反馈生成，仅为调养体验参考；每个人体质不同，体感存在差异，摘要不代表商品功效。',
    reviews: [
      { id: 'r1', user_id: 'user-f003',体质: '火形偏低', rating: 5, text: '颜色很正，蜜蜡橘色特别好看，搭配深色衣服很洋气', date: '2026-09-20', tags: ['颜色正', '手感好'] },
      { id: 'r2', user_id: 'user-f008',体质: '土形偏弱', rating: 5, text: '棉麻料子不扎，保暖效果不错，秋天戴刚好', date: '2026-09-15', tags: ['棉麻舒适', '保暖'] }
    ],
    feedback_count: 42
  }
}

export default huCase
