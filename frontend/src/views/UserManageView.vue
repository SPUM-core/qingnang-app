<template>
  <section class="page friends">
    <!-- 头部：自己的数字模型 + 邀请入口 -->
    <div class="friends-head">
      <div class="me-card">
        <div class="avatar">🌿</div>
        <div class="me-info">
          <p class="me-name">{{ me.name }} · {{ me.age }}岁</p>
          <p class="me-model">数字模型：{{ me.model_summary }}</p>
          <p class="me-id">青囊 ID：<code>{{ me.id }}</code></p>
        </div>
        <button class="btn btn-ghost btn-small" @click="showInvite = true">📤 邀请朋友</button>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" class="tab-btn"
              :class="{ active: activeTab === t.key }"
              @click="activeTab = t.key">
        {{ t.icon }} {{ t.label }}
        <span v-if="t.count" class="tab-count">{{ t.count }}</span>
      </button>
    </div>

    <!-- ════ Tab 1: 好友列表 ════ -->
    <div v-if="activeTab === 'list'" class="content">
      <div class="section-head">
        <h2>👥 我的好友</h2>
        <button class="btn btn-ghost btn-small" @click="showAdd = true">+ 添加好友</button>
      </div>

      <!-- 分组 -->
      <div v-for="group in groups" :key="group.key" class="friend-group">
        <h3 class="group-title">{{ group.label }} · {{ group.friends.length }} 人</h3>
        <div class="friend-cards">
          <div v-for="f in group.friends" :key="f.id" class="friend-card" @click="selectFriend(f)">
            <div class="friend-avatar" :style="{ background: f.avatarGradient }">{{ f.avatar }}</div>
            <div class="friend-info">
              <p class="friend-name">
                {{ f.name }}
                <span v-if="f.isDoctor" class="doctor-badge">🩺 青囊中医</span>
              </p>
              <p class="friend-model">{{ f.model_summary }}</p>
              <p class="friend-labels">
                <span v-for="w in f.weakPoints" :key="w" class="friend-label">{{ w }}</span>
              </p>
              <p v-if="f.isDoctor" class="friend-doctor-hint">
                📅 {{ f.doctor.lastPlanDate }} · {{ f.doctor.lastPlan }}
              </p>
            </div>
            <button v-if="!f.isDoctor" class="chat-btn" @click.stop="openTogether(f)">🤝</button>
            <button v-else class="chat-btn doctor-btn" @click.stop="showDoctor(f)">👤</button>
          </div>
          <p v-if="!group.friends.length" class="empty-group">暂无{{ group.label }}好友</p>
        </div>
      </div>
    </div>

    <!-- ════ Tab 2: 互动建议（双人/多人联合） ════ -->
    <div v-else-if="activeTab === 'together'" class="content">
      <div class="section-head">
        <h2>🤝 一起玩 · 一起吃 · 一起养</h2>
        <span class="hint">选择好友查看联合建议 · 双方向量取交集</span>
      </div>

      <div class="together-picker">
        <div class="picker-me">
          <div class="mini-avatar" :style="{ background: me.gradient }">🌿</div>
          <span>{{ me.name }}（我）</span>
        </div>
        <span class="plus">+</span>
        <select v-model="partnerId" class="picker-select" @change="computeJoint">
          <option value="">选择一位好友...</option>
          <option v-for="f in allFriends" :key="f.id" :value="f.id">{{ f.name }} · {{ f.model_summary }}</option>
        </select>
      </div>

      <!-- 对比雷达图预览 -->
      <div v-if="partner" class="joint-compare">
        <div class="compare-card compare-me">
          <h4>你的五形向量</h4>
          <div class="vector-bars">
            <div v-for="d in dims" :key="d.k" class="vector-bar">
              <span class="vb-label">{{ d.label }}</span>
              <div class="vb-track"><div class="vb-fill vb-me" :style="{ width: meVector[d.k] + '%' }"></div></div>
              <span class="vb-val">{{ meVector[d.k] }}</span>
            </div>
          </div>
        </div>
        <div class="compare-card compare-partner">
          <h4>{{ partner.name }}的五形向量</h4>
          <div class="vector-bars">
            <div v-for="d in dims" :key="d.k" class="vector-bar">
              <span class="vb-label">{{ d.label }}</span>
              <div class="vb-track"><div class="vb-fill vb-partner" :style="{ width: partnerVector[d.k] + '%' }"></div></div>
              <span class="vb-val">{{ partnerVector[d.k] }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 交集共识 → 联合建议 -->
      <div v-if="partner && jointAdvice.length" class="advice-section">
        <h3>✨ 联合建议（基于 {{ me.name }} × {{ partner.name }} 的向量交集）</h3>

        <!-- 饮食 -->
        <div class="advice-block">
          <div class="advice-head"><span class="advice-emoji">🍜</span><span>适合双方的饮食</span></div>
          <div class="chips">
            <span v-for="t in jointAdvice" :key="t" class="chip">{{ t }}</span>
          </div>
        </div>

        <!-- 推荐理由 -->
        <div class="advice-block">
          <div class="advice-head"><span class="advice-emoji">🧭</span><span>联合推荐理由</span></div>
          <div class="advice-reasons">
            <p v-for="(r, i) in jointReasons" :key="i">{{ r }}</p>
          </div>
        </div>

        <!-- 共同适合的活动 -->
        <div class="advice-block">
          <div class="advice-head"><span class="advice-emoji">🎯</span><span>一起做什么</span></div>
          <ul class="activity-list">
            <li v-for="(a, i) in jointActivities" :key="i">{{ a }}</li>
          </ul>
        </div>
      </div>

      <p v-else-if="!partner" class="placeholder">选择好友，青囊会为你们生成联合建议</p>
    </div>

    <!-- ════ Tab 3: 家庭综合指导 ════ -->
    <div v-else-if="activeTab === 'family'" class="content">
      <div class="section-head">
        <h2>🏠 家庭综合指导</h2>
        <span class="hint">多位家庭成员的数字模型联合分析</span>
      </div>

      <div v-if="familyMembers.length >= 2" class="family-grid">
        <div v-for="(m, i) in familyMembers" :key="m.id"
             class="family-cell" :class="{ 'is-me': i === 0 }">
          <div class="fc-avatar" :style="{ background: m.gradient }">{{ m.avatar }}</div>
          <p class="fc-name">{{ m.name }}{{ i === 0 ? '（我）' : '' }}</p>
          <p class="fc-model">{{ m.model_summary }}</p>
        </div>
      </div>

      <div v-if="familyGuidance.length" class="family-guidance">
        <h3>📋 家庭综合建议</h3>
        <div class="fg-list">
          <div v-for="(g, i) in familyGuidance" :key="i" class="fg-item">
            <span class="fg-icon">{{ g.icon }}</span>
            <div class="fg-body">
              <p class="fg-title">{{ g.title }}</p>
              <p class="fg-desc">{{ g.desc }}</p>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="placeholder">添加至少 2 位家人以生成综合指导</p>
    </div>

    <!-- ════ Tab 4: 邀请推荐 ════ -->
    <div v-else class="content">
      <div class="invite-card">
        <h2>📤 邀请朋友使用青囊</h2>
        <p class="invite-desc">每邀请一位朋友完成初始化，你和朋友都将获得一次免费的深度联合分析机会</p>

        <div class="invite-code">
          <div class="ic-label">你的邀请码</div>
          <div class="ic-value">QN-{{ me.id.slice(-6) }}-2026</div>
          <button class="btn btn-small" @click="copyCode">复制</button>
        </div>

        <div class="invite-link">
          <div class="ic-label">邀请链接</div>
          <input :value="inviteLink" readonly class="ic-link-input" />
          <button class="btn btn-ghost btn-small" @click="copyLink">复制</button>
        </div>

        <div class="invite-share">
          <button class="share-btn" @click="shareVia('wechat')">💬 微信</button>
          <button class="share-btn" @click="shareVia('moments')">📱 朋友圈</button>
          <button class="share-btn" @click="shareVia('sms')">✉️ 短信</button>
        </div>

        <p class="invite-terms">* 被邀请者通过链接注册并完成初始化建档流程，即视为有效邀请</p>
      </div>
    </div>

    <!-- 添加好友弹窗 -->
    <div v-if="showAdd" class="modal" @click.self="showAdd = false">
      <div class="modal-card">
        <h3>添加好友</h3>
        <input v-model="addQuery" placeholder="输入青囊 ID 或手机号" class="modal-input" />
        <div v-if="addResults.length" class="add-results">
          <div v-for="r in addResults" :key="r.id" class="result-row">
            <div class="mini-avatar" :style="{ background: r.avatarGradient }">{{ r.avatar }}</div>
            <div class="result-info">
              <p>{{ r.name }}</p>
              <p class="result-id">青囊 ID: {{ r.id }}</p>
            </div>
            <button class="btn btn-small" @click="addFriend(r)">+ 发送</button>
          </div>
        </div>
        <p v-else-if="addQuery" class="placeholder">未找到匹配用户</p>
        <button class="btn btn-ghost" style="width:100%;margin-top:10px" @click="showAdd = false">取消</button>
      </div>
    </div>

    <!-- 医生详情弹窗 -->
    <div v-if="showDoctorModal" class="modal" @click.self="showDoctorModal = false">
      <div class="modal-card doctor-modal">
        <div class="doctor-modal-head">
          <div class="friend-avatar big" :style="{ background: activeDoctor?.avatarGradient }">{{ activeDoctor?.avatar }}</div>
          <div>
            <h3>{{ activeDoctor?.name }}</h3>
            <p class="doctor-tagline">🩺 青囊中医临床智能体 · 已绑定</p>
          </div>
        </div>

        <div class="doctor-section">
          <h4>🏥 医院 & 资质</h4>
          <p><b>{{ activeDoctor?.doctor?.hospital }}</b></p>
          <p class="muted">{{ activeDoctor?.doctor?.title }}</p>
          <p class="muted">执业医师资格证：{{ activeDoctor?.doctor?.license }}</p>
        </div>

        <div class="doctor-section">
          <h4>🔗 绑定信息</h4>
          <p>绑定日期：<b>{{ activeDoctor?.doctor?.bindDate }}</b></p>
          <p class="muted">{{ activeDoctor?.doctor?.notes }}</p>
        </div>

        <div class="doctor-section">
          <h4>📋 方案推送记录</h4>
          <div class="plan-card">
            <p class="plan-title"><b>{{ activeDoctor?.doctor?.lastPlan }}</b></p>
            <p class="plan-date">{{ activeDoctor?.doctor?.lastPlanDate }} · 医生审核签字后推送给你</p>
          </div>
          <p class="muted next-plan">下次随访：{{ activeDoctor?.doctor?.nextVisit }}</p>
        </div>

        <div class="doctor-section doctor-actions">
          <button class="btn btn-ghost">📤 分享我的身体报告给医生</button>
          <button class="btn btn-primary">💬 给医生发消息</button>
        </div>

        <p class="doctor-disclaimer">* 医生端使用青囊中医（专业版），所有方案需经医生审核签字后才会推送给你。你可以随时解绑。</p>
        <button class="btn btn-ghost btn-danger ghost-danger" style="width:100%;margin-top:10px" @click="showDoctorModal = false">关闭</button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { friends as friendsApi } from '../api/client'
import { useUserStore } from '../stores/user'
import { toModelSummary } from '../stores/vector'

// ═══════════════════════════════════════════════════════════
// 我（当前登录用户）的五形向量 — 从 userStore 动态取
// ═══════════════════════════════════════════════════════════
const userStore = useUserStore()
const caseData = computed(() => userStore.caseData || {})
const me = computed(() => ({
  id: userStore.qingnangId || 'me',
  name: userStore.displayName || '我',
  age: '',
  model_summary: toModelSummary(caseData.value?.v_baseline || caseData.value?.v_current),
  gradient: 'linear-gradient(135deg, #1A4D45, #2A6B62)',
  vBase: caseData.value?.v_baseline || { wood: 50, fire: 50, earth: 50, metal: 50, water: 50 }
}))
const meVector = computed(() => me.value.vBase)

const dims = [
  { k: 'wood', label: '木' },
  { k: 'fire', label: '火' },
  { k: 'earth', label: '土' },
  { k: 'metal', label: '金' },
  { k: 'water', label: '水' }
]

// ═══════════════════════════════════════════════════════════
// 模拟好友数据（默认值，后端种子没注入好友时 fallback 用）
// ═══════════════════════════════════════════════════════════
const DEFAULT_FRIENDS = [
  // ═══ 医生（青囊中医 B 端绑定）
  { id: 'QD-ZYY-ZC', name: '张 医生', relation: 'doctor', avatar: '🩺',
    avatarGradient: 'linear-gradient(135deg, #1A4D45, #0D2F2A)',
    model_summary: '木↔ 火↑ 土↓ 金↔ 水↓',
    weakPoints: ['脾胃偏弱', '水形精'],
    vBase: { wood: 52, fire: 62, earth: 40, metal: 55, water: 38 },
    isDoctor: true,
    doctor: {
      hospital: '北京中医药大学东直门医院',
      title: '主任医师 · 中医内科',
      license: '110xxxxxxxxxxxxx',
      bindDate: '2026-09-10',
      lastPlan: 'v7.0 苓桂术甘汤 + 白芍 + 砂仁',
      lastPlanDate: '2026-09-15',
      nextVisit: '2026-10-15',
      notes: '你的主治医生 · 已绑定青囊中医'
    } },
  { id: 'QD-ZYY-LN', name: '李 医生', relation: 'doctor', avatar: '⚕️',
    avatarGradient: 'linear-gradient(135deg, #0288D1, #01579B)',
    model_summary: '木↑ 火↑↑ 土↓ 金↓ 水↑',
    weakPoints: ['火形极旺', '土形储备不足'],
    vBase: { wood: 65, fire: 82, earth: 35, metal: 38, water: 60 },
    isDoctor: true,
    doctor: {
      hospital: '广州中医药大学第一附属医院',
      title: '副主任医师 · 针灸科',
      license: '144xxxxxxxxxxxxx',
      bindDate: '2026-08-05',
      lastPlan: 'v6.0.1 桂芪对（已停用）',
      lastPlanDate: '2026-09-12',
      nextVisit: '—',
      notes: '远程咨询医生 · 已解绑（方案迭代到张医生）'
    } },

  // 家人
  { id: 'QN-WIFE-001', name: '林慕青', relation: 'family', avatar: '🌸',
    avatarGradient: 'linear-gradient(135deg, #D84315, #8B2500)',
    model_summary: '木↑ 火↓ 土↔ 金↑ 水↑↑',
    weakPoints: ['火形弱', '木形活跃'],
    vBase: { wood: 60, fire: 35, earth: 50, metal: 65, water: 75 } },
  { id: 'QN-MOM-001', name: '胡妈妈', relation: 'family', avatar: '🧓',
    avatarGradient: 'linear-gradient(135deg, #D4A017, #8A6A10)',
    model_summary: '木↓ 火↓ 土↑↑ 金↑↑ 水↓',
    weakPoints: ['木形弱', '水形枯'],
    vBase: { wood: 35, fire: 30, earth: 70, metal: 72, water: 35 } },
  { id: 'QN-SON-001', name: '胡小明', relation: 'family', avatar: '🧒',
    avatarGradient: 'linear-gradient(135deg, #43A047, #1B5E20)',
    model_summary: '木↑↑ 火↑↑↑ 土↓↓ 金↓ 水↔',
    weakPoints: ['火形过旺', '土形储备不足'],
    vBase: { wood: 72, fire: 85, earth: 28, metal: 40, water: 52 } },

  // 好友
  { id: 'QN-FRIEND-ZC', name: '张晨', relation: 'friend', avatar: '🏃',
    avatarGradient: 'linear-gradient(135deg, #0288D1, #01579B)',
    model_summary: '木↓↓ 火↔ 土↑ 金↑↑ 水↑↑',
    weakPoints: ['木形空转', '肝胆弱'],
    vBase: { wood: 30, fire: 50, earth: 58, metal: 68, water: 72 } },
  { id: 'QN-FRIEND-LN', name: '李娜', relation: 'friend', avatar: '☕',
    avatarGradient: 'linear-gradient(135deg, #D84315, #8B2500)',
    model_summary: '木↑↑ 火↑↑ 土↓↓ 金↓↓ 水↔',
    weakPoints: ['土形三重枯竭', '脾虚'],
    vBase: { wood: 75, fire: 70, earth: 32, metal: 38, water: 52 } },
  { id: 'QN-FRIEND-WW', name: '王武', relation: 'friend', avatar: '🎸',
    avatarGradient: 'linear-gradient(135deg, #90A4AE, #546E7A)',
    model_summary: '木↓ 火↓ 土↑ 金↑↑↑ 水↑↑',
    weakPoints: ['金形极旺', '水形流失'],
    vBase: { wood: 40, fire: 32, earth: 55, metal: 82, water: 68 } },

  // 同事
  { id: 'QN-COLLEAGUE-CX', name: '陈曦', relation: 'other', avatar: '💻',
    avatarGradient: 'linear-gradient(135deg, #1A4D45, #2A6B62)',
    model_summary: '木↑↑ 火↑ 土↓ 金↑ 水↓↓',
    weakPoints: ['水形枯竭', '熬夜'],
    vBase: { wood: 72, fire: 62, earth: 38, metal: 58, water: 32 } }
]

// 标签
const weakPointChips = {
  '火形弱': { color: 'rgba(216,67,21,0.1)', text: '补火' },
  '火形过旺': { color: 'rgba(216,67,21,0.1)', text: '清火' },
  '火形空转': { color: 'rgba(216,67,21,0.1)', text: '潜火' },
  '木形弱': { color: 'rgba(67,160,71,0.1)', text: '补肝' },
  '木形过旺': { color: 'rgba(67,160,71,0.1)', text: '疏木' },
  '木形空转': { color: 'rgba(67,160,71,0.1)', text: '补木' },
  '木形活跃': { color: 'rgba(67,160,71,0.1)', text: '养血' },
  '土形三重枯竭': { color: 'rgba(212,160,23,0.1)', text: '补土' },
  '土形储备不足': { color: 'rgba(212,160,23,0.1)', text: '建中' },
  '土形弱': { color: 'rgba(212,160,23,0.1)', text: '健脾' },
  '脾虚': { color: 'rgba(212,160,23,0.1)', text: '健脾' },
  '金形弱': { color: 'rgba(144,164,174,0.15)', text: '补肺' },
  '金形极旺': { color: 'rgba(144,164,174,0.15)', text: '泻金' },
  '水形枯': { color: 'rgba(2,136,209,0.1)', text: '滋水' },
  '水形流失': { color: 'rgba(2,136,209,0.1)', text: '固水' },
  '水形枯竭': { color: 'rgba(2,136,209,0.1)', text: '补肾' },
  '肝胆弱': { color: 'rgba(67,160,71,0.1)', text: '疏肝胆' },
  '熬夜': { color: 'rgba(2,136,209,0.1)', text: '早卧' }
}

// 好友数据源：后端真实数据，空则显示"暂无好友"
const friends = ref([])
onMounted(async () => {
  try {
    const r = await friendsApi.list()
    friends.value = (r.data?.friends || []).map((f, i) => ({
      id: f.friend_qingnang_id || `bk-${i}`,
      name: f.nickname || f.name || '好友',
      relation: f.relation || 'friend',
      avatar: f.avatar || '👤',
      vBase: f.v_base || { wood: 50, fire: 50, earth: 50, metal: 50, water: 50 },
      model_summary: f.model_summary || '',
      weakPoints: f.weak_points || [],
      isDoctor: f.is_doctor || f.relation === 'doctor',
    }))
  } catch (e) {
    console.warn('[Friends] load failed:', e.message)
    friends.value = []
  }
})

const weakPoints = computed(() => {
  return friends.value.map(f => ({
    ...f,
    weakPoints: f.weakPoints.map(wp => {
      const chip = weakPointChips[wp] || { color: 'rgba(107,114,119,0.1)', text: wp }
      return chip.text
    })
  }))
})

const groups = computed(() => [
  { key: 'doctor', label: '🏥 我的医生', friends: weakPoints.value.filter(f => f.relation === 'doctor') },
  { key: 'family', label: '家人', friends: weakPoints.value.filter(f => f.relation === 'family') },
  { key: 'friend', label: '好友', friends: weakPoints.value.filter(f => f.relation === 'friend') },
  { key: 'other', label: '其他', friends: weakPoints.value.filter(f => f.relation === 'other') }
])
const familyMembers = computed(() => [me, ...weakPoints.value.filter(f => f.relation === 'family')])

const allFriends = computed(() => weakPoints.value)

// Tab
const tabs = computed(() => [
  { key: 'list', icon: '👥', label: '好友列表', count: weakPoints.value.length },
  { key: 'together', icon: '🤝', label: '联合建议' },
  { key: 'family', icon: '🏠', label: '家庭指导' },
  { key: 'invite', icon: '📤', label: '邀请朋友' }
])
const activeTab = ref('list')

// ═══════════════════════════════════════════════════════════
// 联合建议引擎：双方五形向量取交集 → 推荐共同适合的
// ═══════════════════════════════════════════════════════════
const partnerId = ref('')
const partner = computed(() => allFriends.value.find(f => f.id === partnerId.value) || null)
const partnerVector = computed(() => partner.value?.vBase || null)

function computeJoint() {
  // 联合饮食推荐逻辑：根据双方弱项推导
}

const jointAdvice = computed(() => {
  if (!partner.value) return []
  const myWk = me.weakPoints?.map(p => ({ wp: p, name: me.name })) || []
  const pWk = partner.value.weakPoints || []

  // 交集弱项 → 联合推荐
  const common = []
  if (partner.value.vBase.earth < 45 && meVector.earth < 45) common.push('小米粥', '山药', '茯苓饼')
  if (partner.value.vBase.fire < 45 && meVector.fire > 65) common.push('鲫鱼豆腐汤', '莲子百合粥')
  if (partner.value.vBase.wood > 65 && meVector.wood > 65) common.push('菊花茶', '乌梅饮')
  if (partner.value.vBase.water < 45) common.push('银耳雪梨', '温淡盐水')
  if (partner.value.vBase.metal > 60) common.push('百合莲子', '白萝卜')
  if (meVector.wood > 70 && partner.value.vBase.wood < 45) common.push('绿叶菜', '绿色食物')
  return [...new Set(common)]
})

const jointReasons = computed(() => {
  if (!partner.value) return []
  const reasons = []
  const p = partner.value
  if (meVector.earth < 45 && p.vBase.earth < 45)
    reasons.push(`你和${p.name}的土形都偏弱（你的${meVector.earth} · 他的${p.vBase.earth}），健脾是共同目标`)
  if (meVector.fire > 65 && p.vBase.fire < 45)
    reasons.push(`你火形偏旺需要潜镇，而${p.name}火形偏弱需要温养——联合饮食需兼顾`)
  if (meVector.water < 50 && p.vBase.water < 45)
    reasons.push(`双方水形都有流失风险，滋水保阴是共同任务`)
  if (meVector.wood > 70 && p.vBase.wood < 45)
    reasons.push(`你肝血偏旺，${p.name}肝胆偏虚——推荐的饮食能同时养护双方`)
  return reasons
})

const jointActivities = computed(() => {
  if (!partner.value) return []
  const acts = ['✅ 温和散步 30 分钟（推荐时段：申时 15-17 点）',
                '🧘 八段锦（联合练习，节奏可以更慢）',
                '🍵 睡前温淡盐水（双方同步，建立习惯仪式感）',
                '💡 约定 22:30 同时入睡，互相打卡监督']
  return acts
})

// 家庭综合指导
const familyGuidance = computed(() => {
  if (familyMembers.value.length < 2) return []
  const items = []
  const hasWeakEarth = familyMembers.value.some(m => m.vBase.earth < 45)
  const hasWeakWater = familyMembers.value.some(m => m.vBase.water < 45)
  const hasStrongFire = familyMembers.value.some(m => m.vBase.fire > 70)

  items.push({
    icon: '🏠', title: '家庭晚餐方案',
    desc: '小米粥 + 鲫鱼汤 作为每周 2-3 次的联合晚餐，兼顾全家土形调理'
  })
  items.push({
    icon: '⏰', title: '家庭作息约定',
    desc: '统一约定 22:30 熄灯（木形活跃成员需在 22:00 前关闭屏幕，避免相火妄动）'
  })
  if (hasWeakEarth) items.push({
    icon: '🍜', title: '健脾家庭食谱',
    desc: '山药炖排骨、茯苓粥、蒸蛋——避免冷饮/生冷作为全家共识'
  })
  if (hasStrongFire) items.push({
    icon: '🌙', title: '睡前仪式',
    desc: '每晚睡前温水泡脚（不可大汗），火形活跃成员可加少量艾叶'
  })
  items.push({
    icon: '🤝', title: '家庭周运动',
    desc: '每周联合散步 2 次 + 八段锦 1 次，作为家庭习惯建立'
  })
  return items
})

// 邀请
const inviteLink = computed(() => `https://qingnang.app/invite?code=QN-${me.id.slice(-6)}-2026`)
function copyCode() { navigator.clipboard?.writeText(inviteLink.value) }
function copyLink() { navigator.clipboard?.writeText(inviteLink.value) }
function shareVia(channel) {
  const msgs = { wechat: '已生成微信分享', moments: '已生成朋友圈', sms: '已生成短信' }
  alert(`${msgs[channel]}：${inviteLink.value}`)
}

// 添加好友
const showAdd = ref(false)
const showInvite = ref(false)
const addQuery = ref('')
const addResults = computed(() => {
  if (!addQuery.value) return []
  const q = addQuery.value.toLowerCase()
  return allFriends.value.filter(f =>
    f.id.toLowerCase().includes(q) || f.name.includes(addQuery.value)
  ).slice(0, 3)
})
async function addFriend(r) {
  try {
    await friendsApi.add(r.qingnang_id || r.id, 'friend')
    showAdd.value = false
    // 刷新
    const r2 = await friendsApi.list()
    friends.value = (r2.data?.friends || []).map((f, i) => ({
      id: f.friend_qingnang_id || `bk-${i}`,
      name: f.nickname || f.name || '好友',
      relation: f.relation || 'friend',
      avatar: f.avatar || '👤',
      vBase: f.v_base || { wood: 50, fire: 50, earth: 50, metal: 50, water: 50 },
      model_summary: f.model_summary || '',
      weakPoints: f.weak_points || [],
    }))
  } catch (e) {
    alert('添加好友失败：' + (e.response?.data?.detail || e.message))
  }
}
function selectFriend(f) { partnerId.value = f.id }
function openTogether(f) { partnerId.value = f.id; activeTab.value = 'together' }

// 医生弹窗
const showDoctorModal = ref(false)
const activeDoctor = ref(null)
function showDoctor(f) { activeDoctor.value = f; showDoctorModal.value = true }
</script>

<style scoped>
.friends { max-width: 1400px; }

/* 头部我卡片 */
.friends-head { margin-bottom: 18px; }
.me-card {
  display: flex; align-items: center; gap: 14px;
  background: linear-gradient(135deg, rgba(26,77,69,0.06), rgba(46,125,106,0.06));
  border: 1px solid rgba(26,77,69,0.15);
  border-radius: var(--radius-md); padding: 16px 20px;
}
.avatar, .mini-avatar, .fc-avatar, .friend-avatar {
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; color: #fff; font-weight: 600;
}
.avatar { width: 52px; height: 52px; font-size: 24px; background: linear-gradient(135deg, #1A4D45, #2A6B62); }
.friend-avatar { width: 44px; height: 44px; font-size: 20px; flex-shrink: 0; }
.fc-avatar { width: 56px; height: 56px; font-size: 24px; }
.mini-avatar { width: 28px; height: 28px; font-size: 14px; }

.me-info { flex: 1; min-width: 0; }
.me-name { font-size: 16px; font-weight: 600; color: var(--qingnang-emerald); margin: 0; }
.me-model { font-size: 12px; color: var(--ink-secondary); margin: 2px 0; }
.me-id { font-size: 11px; color: var(--ink-tertiary); margin: 0; }
.me-id code { background: var(--qingnang-paper); padding: 1px 6px; border-radius: 3px; font-size: 11px; }

/* Tab */
.tabs { display: flex; gap: 6px; margin-bottom: 16px; }
.tab-btn {
  font-size: 13px; padding: 7px 16px; border-radius: 20px;
  border: 1px solid var(--ink-line); background: #fff; color: var(--ink-secondary);
  cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
}
.tab-btn:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }
.tab-btn.active { background: var(--qingnang-emerald); border-color: var(--qingnang-emerald); color: #fff; }
.tab-count { background: var(--qingnang-paper); color: var(--ink-tertiary); padding: 0 6px; border-radius: 10px; font-size: 11px; }
.tab-btn.active .tab-count { background: rgba(255,255,255,0.2); color: #fff; }

.section-head { display: flex; justify-content: space-between; align-items: center; margin: 8px 0 12px; }
.section-head h2 { font-size: 16px; color: var(--qingnang-emerald); margin: 0; }
.hint { font-size: 12px; color: var(--ink-tertiary); }

/* 好友分组 */
.friend-group { margin-bottom: 20px; }
.group-title { font-size: 13px; color: var(--ink-tertiary); margin: 0 0 10px; font-weight: 500; }
.friend-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.friend-card {
  display: flex; align-items: center; gap: 12px;
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md);
  padding: 12px 14px; cursor: pointer; transition: all 0.15s;
}
.friend-card:hover { box-shadow: var(--shadow-card-hover); border-color: rgba(26,77,69,0.25); transform: translateY(-1px); }
.friend-info { flex: 1; min-width: 0; }
.friend-name { font-size: 14px; font-weight: 600; color: var(--ink-primary); margin: 0; }
.friend-model { font-size: 12px; color: var(--ink-secondary); margin: 2px 0; }
.friend-labels { display: flex; gap: 4px; flex-wrap: wrap; }
.friend-label {
  font-size: 10px; color: var(--qingnang-emerald);
  background: rgba(26,77,69,0.06); padding: 1px 6px; border-radius: 3px; font-weight: 500;
}
.chat-btn {
  font-size: 18px; background: transparent; border: none;
  cursor: pointer; padding: 4px 6px; border-radius: 6px; transition: all 0.15s;
}
.chat-btn:hover { background: var(--qingnang-paper); }
.chat-btn.doctor-btn { font-size: 16px; }

.doctor-badge {
  font-size: 10px; background: linear-gradient(135deg, #1A4D45, #2A6B62);
  color: #fff; padding: 1px 7px; border-radius: 10px; font-weight: 500;
  margin-left: 6px; vertical-align: middle;
}
.friend-doctor-hint {
  font-size: 11px; color: var(--qingnang-spirit); margin: 2px 0 0;
}

.empty-group { font-size: 12px; color: var(--ink-tertiary); padding: 14px; text-align: center; }

/* 联合建议 */
.together-picker {
  display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 16px 20px;
}
.picker-me { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500; color: var(--ink-primary); }
.picker-select {
  flex: 1; max-width: 360px; padding: 8px 12px;
  border: 1px solid var(--ink-line); border-radius: var(--radius-sm); font-size: 13px;
}
.plus { font-size: 18px; color: var(--ink-tertiary); }

.joint-compare {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;
}
.compare-card { background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 14px 16px; }
.compare-card h4 { font-size: 12px; color: var(--ink-tertiary); margin: 0 0 10px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; }
.compare-partner h4 { color: var(--qingnang-emerald); }

.vector-bars { display: flex; flex-direction: column; gap: 6px; }
.vector-bar { display: grid; grid-template-columns: 20px 1fr 32px; align-items: center; gap: 8px; font-size: 12px; }
.vb-label { color: var(--ink-tertiary); font-weight: 600; }
.vb-track { height: 8px; background: var(--qingnang-paper); border-radius: 4px; overflow: hidden; }
.vb-fill { height: 100%; border-radius: 4px; transition: width 0.4s; }
.vb-me { background: linear-gradient(90deg, #1A4D45, #2A6B62); }
.vb-partner { background: linear-gradient(90deg, #45C4A8, #2A6B62); }
.vb-val { color: var(--ink-secondary); font-family: var(--font-mono); font-size: 11px; text-align: right; }

.advice-section { display: flex; flex-direction: column; gap: 14px; }
.advice-section h3 { font-size: 14px; color: var(--qingnang-emerald); margin: 4px 0; font-weight: 600; }
.advice-block {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 14px 18px;
}
.advice-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 13px; font-weight: 500; color: var(--ink-primary); }
.advice-emoji { font-size: 18px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: rgba(26,77,69,0.06); border: 1px solid rgba(26,77,69,0.2); color: var(--qingnang-emerald);
  padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;
}
.advice-reasons p, .activity-list li { font-size: 13px; color: var(--ink-secondary); line-height: 1.7; }
.activity-list { padding-left: 20px; margin: 0; }

/* 家庭综合指导 */
.family-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }
.family-cell {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 16px;
  text-align: center;
}
.family-cell.is-me { border-color: var(--qingnang-emerald); box-shadow: var(--shadow-card); }
.fc-name { font-size: 13px; font-weight: 600; color: var(--ink-primary); margin: 8px 0 4px; }
.fc-model { font-size: 11px; color: var(--ink-tertiary); margin: 0; }
.family-guidance h3 { font-size: 14px; color: var(--qingnang-emerald); margin: 10px 0; font-weight: 600; }
.fg-list { display: flex; flex-direction: column; gap: 8px; }
.fg-item {
  display: flex; gap: 12px; align-items: flex-start;
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-sm); padding: 12px 14px;
}
.fg-icon { font-size: 20px; flex-shrink: 0; }
.fg-title { font-size: 13px; font-weight: 600; color: var(--ink-primary); margin: 0 0 3px; }
.fg-desc { font-size: 12px; color: var(--ink-secondary); margin: 0; line-height: 1.5; }

/* 邀请 */
.invite-card {
  max-width: 520px; margin: 0 auto;
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 24px 28px;
}
.invite-card h2 { font-size: 18px; color: var(--qingnang-emerald); margin: 0 0 6px; }
.invite-desc { font-size: 13px; color: var(--ink-secondary); margin: 0 0 20px; line-height: 1.6; }
.invite-code, .invite-link {
  display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 10px;
  background: var(--qingnang-paper); border: 1px solid var(--ink-line); border-radius: var(--radius-sm); padding: 10px 14px; margin-bottom: 10px;
}
.ic-label { grid-column: 1 / -1; font-size: 11px; color: var(--ink-tertiary); font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 4px; }
.ic-value { font-family: var(--font-mono); font-size: 16px; font-weight: 600; color: var(--qingnang-emerald); }
.ic-link-input { border: none; background: transparent; font-family: var(--font-mono); font-size: 12px; color: var(--ink-secondary); width: 100%; outline: none; }
.invite-share { display: flex; gap: 8px; margin: 16px 0 12px; }
.share-btn {
  flex: 1; font-size: 13px; padding: 10px; border-radius: var(--radius-sm);
  border: 1px solid var(--ink-line); background: #fff; cursor: pointer; transition: all 0.15s;
}
.share-btn:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }
.invite-terms { font-size: 11px; color: var(--ink-tertiary); text-align: center; line-height: 1.6; }

/* 弹窗 */
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-card { background: #fff; border-radius: var(--radius-md); padding: 20px; width: 380px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal-card h3 { margin: 0 0 14px; color: var(--qingnang-emerald); font-size: 16px; }
.modal-input { width: 100%; padding: 9px 12px; border: 1px solid var(--ink-line); border-radius: var(--radius-sm); font-size: 14px; margin-bottom: 12px; }
.modal-input:focus { outline: none; border-color: var(--qingnang-emerald); }
.add-results { display: flex; flex-direction: column; gap: 6px; }
.result-row {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px; background: var(--qingnang-paper); border-radius: var(--radius-sm);
}
.result-info { flex: 1; min-width: 0; }
.result-info p { margin: 0; font-size: 13px; color: var(--ink-primary); }
.result-id { font-size: 11px; color: var(--ink-tertiary); }

/* 按钮 */
.btn { padding: 8px 16px; border: none; border-radius: var(--radius-sm); background: var(--qingnang-emerald); color: #fff; cursor: pointer; font-size: 13px; transition: all 0.15s; font-family: var(--font-body); font-weight: 500; }
.btn:hover { background: var(--qingnang-emerald-light); }
.btn-ghost { background: transparent; color: var(--qingnang-emerald); border: 1px solid var(--qingnang-emerald); }
.btn-ghost:hover { background: var(--qingnang-paper); }
.btn-small { padding: 5px 12px; font-size: 12px; }

/* 医生弹窗 */
.doctor-modal { width: 480px; max-height: 85vh; overflow-y: auto; }
.doctor-modal-head { display: flex; gap: 14px; align-items: center; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--ink-line); }
.doctor-modal-head .friend-avatar.big { width: 56px; height: 56px; font-size: 26px; }
.doctor-modal-head h3 { margin: 0 0 4px; font-size: 18px; color: var(--qingnang-emerald); }
.doctor-tagline { font-size: 12px; color: var(--ink-tertiary); margin: 0; }

.doctor-section { margin-bottom: 14px; }
.doctor-section h4 { font-size: 12px; color: var(--ink-tertiary); font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 6px; }
.doctor-section p { font-size: 13px; color: var(--ink-primary); margin: 3px 0; line-height: 1.5; }
.doctor-section .muted { font-size: 12px; color: var(--ink-tertiary); }

.plan-card {
  background: var(--qingnang-paper); border: 1px solid var(--ink-line);
  border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 6px;
}
.plan-title { font-size: 14px; color: var(--qingnang-emerald); margin: 0 0 3px; }
.plan-date { font-size: 11px; color: var(--ink-tertiary); margin: 0; }
.next-plan { font-size: 12px; margin-top: 6px; }

.doctor-actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.doctor-actions .btn { flex: 1; min-width: 160px; text-align: center; }

.btn-primary { background: var(--qingnang-spirit); }
.btn-primary:hover { background: #36A88F; }

.doctor-disclaimer {
  font-size: 11px; color: var(--ink-tertiary); line-height: 1.6; text-align: center;
  padding: 10px; background: var(--qingnang-paper); border-radius: var(--radius-sm); margin-top: 14px;
}

/* 响应式 */
@media (max-width: 720px) {
  .joint-compare { grid-template-columns: 1fr; }
  .family-grid { grid-template-columns: repeat(2, 1fr); }
  .friends-head .me-card { flex-wrap: wrap; }
}
</style>
