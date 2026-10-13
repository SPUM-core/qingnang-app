/**
 * friend-match — 好友体质匹配度纯函数
 *
 * 不依赖后端、不依赖 Pinia、只吃两个五形向量
 * 后端 /match/{friend_id} API 返回的数据结构与此一致
 *
 *   五形向量 vBase = { wood: 60, fire: 35, earth: 50, metal: 65, water: 75 }
 *   值域 0-100，50 是健康基准线
 */

const WUXING_KEYS = ['wood', 'fire', 'earth', 'metal', 'water']
const WUXING_NAMES = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }

// 相克关系（用于相忌检测）：攻 → 受
const KE_MAP = [
  { attacker: 'wood',  victim: 'earth',  label: '木克土' },
  { attacker: 'earth', victim: 'water',  label: '土克水' },
  { attacker: 'water', victim: 'fire',   label: '水克火' },
  { attacker: 'fire',  victim: 'metal', label: '火克金' },
  { attacker: 'metal', victim: 'wood',   label: '金克木' },
]

// 时辰与五形对应（SPUM 体系）
const SHICHEN_WUXING = {
  zi:    { name: '子时', range: '23-01', wuxing: 'water',  hint: '胆经当令，宜入睡' },
  chou:  { name: '丑时', range: '01-03', wuxing: 'earth',  hint: '肝经当令，深睡养精' },
  yin:   { name: '寅时', range: '03-05', wuxing: 'wood',   hint: '肺经当令，宜早起' },
  mao:   { name: '卯时', range: '05-07', wuxing: 'wood',   hint: '大肠经，晨起先动' },
  chen:  { name: '辰时', range: '07-09', wuxing: 'earth',  hint: '胃经当令，吃好早餐' },
  si:    { name: '巳时', range: '09-11', wuxing: 'fire',   hint: '脾经当令，工作高峰' },
  wu:    { name: '午时', range: '11-13', wuxing: 'fire',   hint: '心经当令，宜小憩' },
  wei:   { name: '未时', range: '13-15', wuxing: 'earth',  hint: '小肠经，温和运动' },
  shen:  { name: '申时', range: '15-17', wuxing: 'metal',  hint: '膀胱经，疏木好时段' },
  you:   { name: '酉时', range: '17-19', wuxing: 'metal',  hint: '肾经当令，酉时金旺' },
  xu:    { name: '戌时', range: '19-21', wuxing: 'earth',  hint: '心包经，泡脚养身' },
  hai:   { name: '亥时', range: '21-23', wuxing: 'water',  hint: '三焦经，准备入睡' },
}

const SHICHEN_ORDER = ['zi','chou','yin','mao','chen','si','wu','wei','shen','you','xu','hai']

/**
 * 余弦相似度 —— 两个五形向量的方向一致性
 * 返回 0-1，1 = 完全同方向（体质相似），0 = 正交
 */
export function cosineSimilarity(a, b) {
  let dot = 0, normA = 0, normB = 0
  for (const k of WUXING_KEYS) {
    const va = a[k] ?? 50, vb = b[k] ?? 50
    dot += va * vb
    normA += va * va
    normB += vb * vb
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB)
  if (denom === 0) return 0
  // 归一化到 0-1（余弦原始值域 -1~1，但五形向量都是正数）
  return (dot / denom + 1) / 2
}

/**
 * 交集弱项 —— 双方都偏低的形（都 < 45）
 */
export function intersectionWeak(a, b, threshold = 45) {
  const out = []
  for (const k of WUXING_KEYS) {
    const va = a[k] ?? 50, vb = b[k] ?? 50
    if (va < threshold && vb < threshold) {
      out.push({ k, label: WUXING_NAMES[k], me: va, friend: vb })
    }
  }
  return out
}

/**
 * 互补 —— 一方高、另一方低的形（差值 >= 20）
 * 你高我低 = 你能帮我；我高你低 = 我能帮你
 */
export function complementPairs(a, b, diff = 20) {
  const out = []
  for (const k of WUXING_KEYS) {
    const va = a[k] ?? 50, vb = b[k] ?? 50
    if (va - vb >= diff) out.push({ k, label: WUXING_NAMES[k], direction: 'me→friend', me: va, friend: vb })
    else if (vb - va >= diff) out.push({ k, label: WUXING_NAMES[k], direction: 'friend→me', me: va, friend: vb })
  }
  return out
}

/**
 * 相忌 —— 一方的旺形克对方的弱形
 * 攻方 >= 70 且受方 <= 45
 */
export function clashPairs(a, b) {
  const out = []
  for (const ke of KE_MAP) {
    const myAttacker = a[ke.attacker] ?? 50
    const myVictim = a[ke.victim] ?? 50
    const friendAttacker = b[ke.attacker] ?? 50
    const friendVictim = b[ke.victim] ?? 50

    // 我旺 × 他弱 = 我克他
    if (myAttacker >= 70 && friendVictim <= 45) {
      out.push({ label: ke.label, direction: 'me→friend',
        attacker: { k: ke.attacker, val: myAttacker },
        victim: { k: ke.victim, val: friendVictim } })
    }
    // 他旺 × 我弱 = 他克我
    if (friendAttacker >= 70 && myVictim <= 45) {
      out.push({ label: ke.label, direction: 'friend→me',
        attacker: { k: ke.attacker, val: friendAttacker },
        victim: { k: ke.victim, val: myVictim } })
    }
  }
  return out
}

/**
 * 一句话总结 —— 给匹配报告生成自然语言结论
 */
export function matchConclusion(meName, friendName, intersection, complement, clash, similarity) {
  const parts = []

  if (intersection.length) {
    const names = intersection.map(x => x.label).join('、')
    parts.push(`你们${names}形都偏弱，一起调理效果加倍`)
  }

  if (complement.length) {
    // 只取前 2 个互补
    const top = complement.slice(0, 2)
    const lines = top.map(c =>
      c.direction === 'me→friend'
        ? `你${c.label}形旺能帮到${friendName}的${c.label}形弱`
        : `${friendName}${c.label}形旺能帮到你的${c.label}形弱`
    )
    parts.push(lines.join('；'))
  }

  if (clash.length) {
    const top = clash.slice(0, 1)[0]
    parts.push(`⚠️ 你们存在${top.label}关系，建议避开${top.direction === 'me→friend' ? '你旺他弱' : '他旺你弱'}的时辰高强度对话`)
  }

  if (similarity > 0.7) parts.push('总体相似度高，适合互相参考调理经验')
  else if (similarity < 0.4) parts.push('体质差异较大，建议各自独立调理')

  return parts.join('。') + '。'
}

/**
 * ⭐ 时辰重叠提醒 —— 双方在每个时辰的状态评估 + 推荐/避开
 *
 * 逻辑：
 *   - 每个人的 vBase 决定了每个时辰的五形强弱
 *   - 时辰五形 = 个人该形的 vBase 值
 *   - 双方同时 → 交集状态
 *
 * 返回 12 个时辰的评估 + 推荐动作
 */
export function shichenOverlap(meVec, friendVec) {
  const out = []
  for (const key of SHICHEN_ORDER) {
    const sc = SHICHEN_WUXING[key]
    const wuxing = sc.wuxing

    const meVal = meVec[wuxing] ?? 50
    const friendVal = friendVec[wuxing] ?? 50
    const avg = (meVal + friendVal) / 2
    const diff = Math.abs(meVal - friendVal)

    let status, emoji, action
    if (avg >= 60 && diff <= 15) {
      // 双方该形都活跃 → 最佳重叠
      status = 'good'
      emoji = '✅'
      action = `一起${recommendActivity(wuxing, 'active')}`
    } else if (meVal < 45 && friendVal < 45) {
      // 双方该形都弱 → 避开高强度
      status = 'avoid'
      emoji = '❌'
      action = '避免高强度互动，各自安静养身'
    } else if (diff >= 25) {
      // 双方该形差异大 → 相忌
      status = 'caution'
      emoji = '⚠️'
      action = '错开时段调理，避免同一任务'
    } else {
      status = 'neutral'
      emoji = '·'
      action = sc.hint
    }

    out.push({
      key, name: sc.name, range: sc.range,
      wuxing, meVal, friendVal, avg, diff,
      status, emoji, action,
    })
  }
  return out
}

function recommendActivity(wuxing, state) {
  const map = {
    wood:   state === 'active' ? '散步疏木气结（推荐申时）' : '避免久坐，适当伸展',
    fire:   state === 'active' ? '温和运动助火宣通' : '避免辛辣温补，宜清润',
    earth:  state === 'active' ? '一起吃饭健脾养胃' : '饮食清淡，忌生冷',
    metal:  state === 'active' ? '深呼吸/扩胸补肺' : '避免吸烟，润肺为先',
    water:  state === 'active' ? '泡脚/温淡盐水滋水' : '避免熬夜，固水保阴',
  }
  return map[wuxing] || '温和互动'
}

/**
 * 全家并集弱项 —— 全家成员某形都偏弱
 */
export function familyUnionWeak(members, threshold = 45) {
  const keys = WUXING_KEYS
  const weak = {}
  for (const k of keys) {
    const vals = members.map(m => m.v_base?.[k] ?? 50)
    const min = Math.min(...vals)
    if (min < threshold) {
      weak[WUXING_NAMES[k]] = { min: Math.round(min), max: Math.max(...vals), count: members.filter(m => (m.v_base?.[k] ?? 50) < threshold).length }
    }
  }
  return weak
}

export { WUXING_NAMES, SHICHEN_WUXING, SHICHEN_ORDER }
