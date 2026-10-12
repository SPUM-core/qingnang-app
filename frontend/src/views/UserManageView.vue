<template>
  <section class="page friends" data-page-id="P17">
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

    <!-- ════ Tab 3: 家庭健康看板（后端 family-aggregate 合并推算） ════ -->
    <div v-else-if="activeTab === 'family'" class="content family-dashboard">
      <!-- 空状态 -->
      <div v-if="!familyData.members || familyData.members.length < 2" class="empty-state">
        <div class="empty-emoji">🏠</div>
        <h3>添加家人，开启家庭健康看板</h3>
        <p class="muted">青囊会合并全家的五形向量，自动发现共同短板、相克关系和联合调理方案</p>
        <button class="btn" @click="showAdd = true">+ 添加家人</button>
        <div class="empty-hint">
          <h4>📋 看板会展示：</h4>
          <ul>
            <li>👨‍👩‍👧‍👦 全家成员网格 + 代际标识</li>
            <li>📊 全家向量并集 / 交集弱项雷达</li>
            <li>⚠️ 相克告警（长辈木极旺 × 晚辈土枯竭）</li>
            <li>🎯 联合调理建议（饮食 / 作息 / 运动）</li>
          </ul>
        </div>
      </div>

      <!-- 有家人数据 -->
      <template v-else>
        <!-- ① 全家成员网格 -->
        <div class="fd-section">
          <div class="section-head">
            <h2>👨‍👩‍👧‍👦 全家 · {{ familyData.members.length }} 人</h2>
            <span v-if="familyData.generation_span" class="hint">
              代际跨度：{{ familyGenLabel(familyData.generation_span[0]) }} ~ {{ familyGenLabel(familyData.generation_span[1]) }}
            </span>
          </div>
          <div class="family-grid-v2">
            <div v-for="m in familyData.members" :key="m.qingnang_id"
                 class="family-member-card" :class="{ 'is-me': m.is_me, [`gen-${m.generation_level}`]: true }">
              <div class="fc-avatar" :style="{ background: memberGradient(m) }">{{ memberEmoji(m) }}</div>
              <p class="fc-name">{{ m.nickname }}{{ m.is_me ? '（我）' : '' }}</p>
              <p class="fc-kinship">{{ kinshipLabel(m.kinship_type, m.generation_level) }}</p>
              <!-- 迷你五形条 -->
              <div class="fc-wuxing-bars">
                <div v-for="(label, k) in wuxingLabels" :key="k" class="fwb-bar">
                  <span class="fwb-label">{{ label }}</span>
                  <div class="fwb-track">
                    <div class="fwb-fill" :style="{ width: `${m.v_base?.[k] ?? 50}%`, background: wuxingColors[k] }"></div>
                  </div>
                  <span class="fwb-val">{{ Math.round(m.v_base?.[k] ?? 50) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ② 全家向量合并 -->
        <div class="fd-section">
          <div class="section-head">
            <h2>📊 全家合并体质</h2>
            <span class="hint">并集（max）+ 交集弱项（全家共同短板）</span>
          </div>
          <div class="union-vs-intersection">
            <!-- 全家并集 -->
            <div class="uvi-card union">
              <h4>全家并集（谁最高算谁）</h4>
              <div class="uvi-bars">
                <div v-for="(label, k) in wuxingLabels" :key="k" class="uvi-bar">
                  <span class="uvi-label">{{ label }}</span>
                  <div class="uvi-track">
                    <div class="uvi-fill" :style="{ width: `${familyData.union?.[k] ?? 50}%`, background: wuxingColors[k] }"></div>
                  </div>
                  <span class="uvi-val">{{ Math.round(familyData.union?.[k] ?? 50) }}</span>
                </div>
              </div>
            </div>
            <!-- 全家交集弱项 -->
            <div class="uvi-card intersection" :class="{ has_weak: Object.keys(familyData.intersection_weak || {}).length }">
              <h4>全家共同短板</h4>
              <template v-if="Object.keys(familyData.intersection_weak || {}).length">
                <div class="weak-chips">
                  <span v-for="(v, k) in familyData.intersection_weak" :key="k" class="weak-chip">
                    {{ k }}形 · 全家最低 {{ Math.round(v) }}
                  </span>
                </div>
                <p class="weak-hint">这是全家人共同需要调理的方向 — 一起做效果翻倍</p>
              </template>
              <p v-else class="muted">暂无全家共同短板 ✓</p>
            </div>
          </div>
        </div>

        <!-- ③ 相克告警 -->
        <div v-if="familyData.tensions?.length" class="fd-section tensions">
          <div class="section-head">
            <h2>⚠️ 家庭相克检测</h2>
            <span class="hint">根据五行生克：木克土 · 土克水 · 水克火 · 火克金 · 金克木</span>
          </div>
          <div class="tension-list">
            <div v-for="(t, i) in familyData.tensions" :key="i" class="tension-card">
              <div class="tension-label">{{ t.label }}</div>
              <div class="tension-detail">
                <p><b>攻方</b>：{{ t.attacker.map(x => `${x[0]}(${Math.round(x[1])})`).join('、') }}</p>
                <p><b>受方</b>：{{ t.victim.map(x => `${x[0]}(${Math.round(x[1])})`).join('、') }}</p>
              </div>
              <p class="tension-suggest">💡 建议：攻方成员避免在金/木旺的时辰与受方高强度对话，可各自选时辰调理</p>
            </div>
          </div>
        </div>

        <!-- ④ 联合调理建议 -->
        <div v-if="familyData.guidance?.length" class="fd-section">
          <div class="section-head">
            <h2>🎯 联合调理建议</h2>
            <span class="hint">后端 SPUM 引擎根据全家合并数据生成</span>
          </div>
          <div class="guidance-list-v2">
            <div v-for="(g, i) in familyData.guidance" :key="i"
                 class="guidance-card" :class="`cat-${g.cat}`">
              <div class="gc-icon">{{ guidanceIcon(g.cat) }}</div>
              <p class="gc-text">{{ g.text }}</p>
            </div>
          </div>
        </div>
      </template>
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
import { computed, ref, onMounted, watch } from 'vue'
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
  gradient: 'linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light))',
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
    avatarGradient: 'linear-gradient(135deg, var(--qn-emerald), #0D2F2A)',
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
    avatarGradient: 'linear-gradient(135deg, var(--qn-water), #01579B)',
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
    avatarGradient: 'linear-gradient(135deg, var(--qn-fire), #8B2500)',
    model_summary: '木↑ 火↓ 土↔ 金↑ 水↑↑',
    weakPoints: ['火形弱', '木形活跃'],
    vBase: { wood: 60, fire: 35, earth: 50, metal: 65, water: 75 } },
  { id: 'QN-MOM-001', name: '胡妈妈', relation: 'family', avatar: '🧓',
    avatarGradient: 'linear-gradient(135deg, var(--qn-earth), #8A6A10)',
    model_summary: '木↓ 火↓ 土↑↑ 金↑↑ 水↓',
    weakPoints: ['木形弱', '水形枯'],
    vBase: { wood: 35, fire: 30, earth: 70, metal: 72, water: 35 } },
  { id: 'QN-SON-001', name: '胡小明', relation: 'family', avatar: '🧒',
    avatarGradient: 'linear-gradient(135deg, var(--qn-wood), #1B5E20)',
    model_summary: '木↑↑ 火↑↑↑ 土↓↓ 金↓ 水↔',
    weakPoints: ['火形过旺', '土形储备不足'],
    vBase: { wood: 72, fire: 85, earth: 28, metal: 40, water: 52 } },

  // 好友
  { id: 'QN-FRIEND-ZC', name: '张晨', relation: 'friend', avatar: '🏃',
    avatarGradient: 'linear-gradient(135deg, var(--qn-water), #01579B)',
    model_summary: '木↓↓ 火↔ 土↑ 金↑↑ 水↑↑',
    weakPoints: ['木形空转', '肝胆弱'],
    vBase: { wood: 30, fire: 50, earth: 58, metal: 68, water: 72 } },
  { id: 'QN-FRIEND-LN', name: '李娜', relation: 'friend', avatar: '☕',
    avatarGradient: 'linear-gradient(135deg, var(--qn-fire), #8B2500)',
    model_summary: '木↑↑ 火↑↑ 土↓↓ 金↓↓ 水↔',
    weakPoints: ['土形三重枯竭', '脾虚'],
    vBase: { wood: 75, fire: 70, earth: 32, metal: 38, water: 52 } },
  { id: 'QN-FRIEND-WW', name: '王武', relation: 'friend', avatar: '🎸',
    avatarGradient: 'linear-gradient(135deg, var(--qn-metal), #546E7A)',
    model_summary: '木↓ 火↓ 土↑ 金↑↑↑ 水↑↑',
    weakPoints: ['金形极旺', '水形流失'],
    vBase: { wood: 40, fire: 32, earth: 55, metal: 82, water: 68 } },

  // 同事
  { id: 'QN-COLLEAGUE-CX', name: '陈曦', relation: 'other', avatar: '💻',
    avatarGradient: 'linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light))',
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

// ═══════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════
// 家庭看板数据源：后端 family-aggregate API
// ═══════════════════════════════════════════════════════════
const familyData = ref({ members: [], union: {}, intersection_weak: {}, tensions: [], guidance: [], generation_span: null })
const wuxingLabels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
const wuxingColors = {
  wood: 'var(--qn-wood)', fire: 'var(--qn-fire)', earth: 'var(--qn-earth)', metal: 'var(--qn-metal)', water: 'var(--qn-water)',
}

async function loadFamilyAggregate() {
  try {
    const r = await friendsApi.familyAggregate()
    if (r.data) familyData.value = r.data
  } catch (e) {
    console.warn('[Family] load failed:', e.message)
  }
}

// 切到 family tab 才加载（不浪费请求）
watch(activeTab, (tab) => {
  if (tab === 'family' && (!familyData.value.members?.length || familyData.value.members.length <= 1)) {
    loadFamilyAggregate()
  }
})

function memberGradient(m) {
  if (m.is_me) return me.value.gradient
  return pickGradient(m.nickname || m.qingnang_id || 'fam')
}
function memberEmoji(m) {
  if (m.is_me) return '🌿'
  if (m.kinship_type === 'spouse') return '💚'
  if (m.kinship_type === 'parent' || m.generation_level > 0) return '🧓'
  if (m.kinship_type === 'child' || m.generation_level < 0) return '🧒'
  if (m.kinship_type === 'sibling') return '👫'
  return '👤'
}
function kinshipLabel(kt, gl) {
  if (!kt && !gl) return ''
  if (kt === 'self') return '我'
  const map = { spouse: '夫妻', parent: '父/母', child: '子/女', sibling: '兄/弟/姐/妹', grandparent: '祖辈', grandchild: '孙辈', other: '亲属' }
  return map[kt] || ''
}
function familyGenLabel(gl) {
  if (gl === 2) return '祖辈'
  if (gl === 1) return '上一代'
  if (gl === 0) return '同代'
  if (gl === -1) return '下一代'
  if (gl === -2) return '孙辈'
  return '—'
}
function guidanceIcon(cat) {
  return { family: '🍜', tension: '⚠️', lifestyle: '⏰', food: '🥗', exercise: '🏃', sleep: '🌙' }[cat] || '💡'
}

// 好友数据源：后端真实数据（后端返回数组，不是 { friends: [...] } 包一层）
// 空就空，不做 mock fallback —— 避免用户看到假数据
// ═══════════════════════════════════════════════════════════
const friends = ref([])
const pendingRequests = ref([])
const loadingFriends = ref(true)

// 头像 emoji 映射（后端只返回昵称/关系，前端按 relation 决定 emoji）
const RELATION_AVATAR = {
  doctor: '🩺', family: '🏠', friend: '🤝', other: '👤',
}
const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light))',
  'linear-gradient(135deg, var(--qn-wood), #1B5E20)',
  'linear-gradient(135deg, var(--qn-water), #01579B)',
  'linear-gradient(135deg, var(--qn-fire), #8B2500)',
  'linear-gradient(135deg, var(--qn-earth), #8A6A10)',
  'linear-gradient(135deg, var(--qn-metal), #546E7A)',
]

function pickGradient(str) {
  let h = 0
  for (const c of str) h = (h * 31 + c.charCodeAt(0)) | 0
  return AVATAR_GRADIENTS[Math.abs(h) % AVATAR_GRADIENTS.length]
}

onMounted(async () => {
  loadingFriends.value = true
  try {
    // ✅ 后端直接返回数组（r.data 就是 [friend, friend, ...]）
    const r = await friendsApi.list()
    const arr = Array.isArray(r.data) ? r.data : []
    friends.value = arr.map((f, i) => ({
      id: f.friend_id || f.qingnang_id || `bk-${i}`,
      friend_id: f.friend_id,
      qingnang_id: f.qingnang_id,
      name: f.nickname || f.name || '好友',
      relation: f.relation || 'friend',
      kinship_type: f.kinship_type,
      kinship_label: f.kinship_label || '',
      is_doctor: f.is_doctor || f.is_doctor_bind,
      is_doctor_bind: f.is_doctor_bind,
      permissions: f.permissions,
      vBase: f.v_base || {},
      model_summary: f.v_base_summary || '',
      avatar: RELATION_AVATAR[f.relation] || '👤',
      avatarGradient: pickGradient(f.nickname || f.qingnang_id || `f${i}`),
      doctor: f.doctor_info ? {
        hospital: f.doctor_info.hospital,
        title: f.doctor_info.title,
        bindDate: f.bind_date,
        verified: f.doctor_info.verified,
        lastPlan: '医生方案',
        lastPlanDate: f.bind_date,
        nextVisit: null,
      } : null,
    }))

    // 同时加载待处理请求
    try {
      const pr = await friendsApi.pendingRequests()
      pendingRequests.value = Array.isArray(pr.data) ? pr.data : []
    } catch {}
  } catch (e) {
    console.warn('[Friends] load failed:', e.message)
    friends.value = []
  } finally {
    loadingFriends.value = false
  }
})

// ═══════════════════════════════════════════════════════════
// 从五形向量自动推导弱项标签（后端不返回 weak_points，纯前端推）
// ═══════════════════════════════════════════════════════════
const WUXING_LABELS = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }

function deriveWeakPoints(vBase = {}) {
  const out = []
  for (const [k, name] of Object.entries(WUXING_LABELS)) {
    const v = vBase[k] ?? 50
    if (v < 45) out.push(`${name}形偏弱`)
    if (v > 70) out.push(`${name}形过旺`)
  }
  return out
}

const weakPoints = computed(() => {
  return friends.value.map(f => ({
    ...f,
    weakPoints: deriveWeakPoints(f.vBase).map(wp => {
      const chip = weakPointChips[wp] || { color: 'rgba(107,114,119,0.1)', text: wp }
      return chip.text
    }),
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
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.06), rgba(var(--qn-emerald-light-rgb),0.06));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.15);
  border-radius: var(--qn-r-lg); padding: 16px 20px;
}
.avatar, .mini-avatar, .fc-avatar, .friend-avatar {
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; color: #fff; font-weight: 600;
}
.avatar { width: 52px; height: 52px; font-size: calc(24px * var(--qn-fs-scale)); background: linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light)); }
.friend-avatar { width: 44px; height: 44px; font-size: calc(20px * var(--qn-fs-scale)); flex-shrink: 0; }
.fc-avatar { width: 56px; height: 56px; font-size: calc(24px * var(--qn-fs-scale)); }
.mini-avatar { width: 28px; height: 28px; font-size: calc(14px * var(--qn-fs-scale)); }

.me-info { flex: 1; min-width: 0; }
.me-name { font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); margin: 0; }
.me-model { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 2px 0; }
.me-id { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }
.me-id code { background: var(--qn-paper); padding: 1px 6px; border-radius: 3px; font-size: calc(11px * var(--qn-fs-scale)); }

/* Tab */
.tabs { display: flex; gap: 6px; margin-bottom: 16px; }
.tab-btn {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 7px 16px; border-radius: 20px;
  border: 1px solid var(--qn-line); background: var(--qn-surface); color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
}
.tab-btn:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.tab-btn.active { background: var(--qn-emerald); border-color: var(--qn-emerald); color: #fff; }
.tab-count { background: var(--qn-paper); color: var(--qn-ink-3); padding: 0 6px; border-radius: 10px; font-size: calc(11px * var(--qn-fs-scale)); }
.tab-btn.active .tab-count { background: rgba(255,255,255,0.2); color: #fff; }

.section-head { display: flex; justify-content: space-between; align-items: center; margin: 8px 0 12px; }
.section-head h2 { font-size: calc(16px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0; }
.hint { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* 好友分组 */
.friend-group { margin-bottom: 20px; }
.group-title { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0 0 10px; font-weight: 500; }
.friend-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.friend-card {
  display: flex; align-items: center; gap: 12px;
  /* ⚠️ border 已删，让全局 .card 纯 shadow 接管 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg);
  padding: 12px 14px; cursor: pointer; transition: all 0.15s;
}
.friend-card:hover { box-shadow: var(--qn-shadow-2); border-color: rgba(var(--qn-emerald-rgb),0.25); transform: translateY(-1px); }
.friend-info { flex: 1; min-width: 0; }
.friend-name { font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0; }
.friend-model { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 2px 0; }
.friend-labels { display: flex; gap: 4px; flex-wrap: wrap; }
.friend-label {
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-emerald);
  background: rgba(var(--qn-emerald-rgb),0.06); padding: 1px 6px; border-radius: 3px; font-weight: 500;
}
.chat-btn {
  font-size: calc(18px * var(--qn-fs-scale)); background: transparent; border: none;
  cursor: pointer; padding: 4px 6px; border-radius: 6px; transition: all 0.15s;
}
.chat-btn:hover { background: var(--qn-paper); }
.chat-btn.doctor-btn { font-size: calc(16px * var(--qn-fs-scale)); }

.doctor-badge {
  font-size: calc(10px * var(--qn-fs-scale)); background: linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light));
  color: #fff; padding: 1px 7px; border-radius: 10px; font-weight: 500;
  margin-left: 6px; vertical-align: middle;
}
.friend-doctor-hint {
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qingnang-spirit); margin: 2px 0 0;
}

.empty-group { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); padding: 14px; text-align: center; }

/* 联合建议 */
.together-picker {
  display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 16px 20px;
}
.picker-me { display: flex; align-items: center; gap: 8px; font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-ink); }
.picker-select {
  flex: 1; max-width: 360px; padding: 8px 12px;
  border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); font-size: calc(13px * var(--qn-fs-scale));
}
.plus { font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

.joint-compare {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;
}
/* ⚠️ border 已删 */
.compare-card { background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 14px 16px; }
.compare-card h4 { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0 0 10px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; }
.compare-partner h4 { color: var(--qn-emerald); }

.vector-bars { display: flex; flex-direction: column; gap: 6px; }
.vector-bar { display: grid; grid-template-columns: 20px 1fr 32px; align-items: center; gap: 8px; font-size: calc(12px * var(--qn-fs-scale)); }
.vb-label { color: var(--qn-ink-3); font-weight: 600; }
.vb-track { height: 8px; background: var(--qn-paper); border-radius: 4px; overflow: hidden; }
.vb-fill { height: 100%; border-radius: 4px; transition: width 0.4s; }
.vb-me { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-light)); }
.vb-partner { background: linear-gradient(90deg, var(--qn-emerald-accent), var(--qn-emerald-light)); }
.vb-val { color: var(--qn-ink-2); font-family: var(--font-mono); font-size: calc(11px * var(--qn-fs-scale)); text-align: right; }

.advice-section { display: flex; flex-direction: column; gap: 14px; }
.advice-section h3 { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 4px 0; font-weight: 600; }
.advice-block {
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 14px 18px;
}
.advice-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-ink); }
.advice-emoji { font-size: calc(18px * var(--qn-fs-scale)); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: rgba(var(--qn-emerald-rgb),0.06); border: 1px solid rgba(var(--qn-emerald-rgb),0.2); color: var(--qn-emerald);
  padding: 4px 12px; border-radius: 20px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500;
}
.advice-reasons p, .activity-list li { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.7; }
.activity-list { padding-left: 20px; margin: 0; }

/* ═══════════════════════════════════════════════════════
   家庭健康看板（后端 family-aggregate）
═══ */
.fd-section { margin-bottom: 28px; }

/* 空状态 */
.empty-state { text-align: center; padding: 48px 24px; }
.empty-emoji { font-size: 56px; margin-bottom: 12px; }
.empty-state h3 { font-size: calc(17px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0 0 8px; }
.empty-state .muted { margin: 0 0 24px; max-width: 420px; margin-left: auto; margin-right: auto; }
.empty-hint { margin-top: 28px; padding: 16px 20px; background: var(--qn-paper); border-radius: var(--qn-r-sm); text-align: left; max-width: 480px; margin-left: auto; margin-right: auto; }
.empty-hint h4 { font-size: calc(13px * var(--qn-fs-scale)); margin: 0 0 8px; color: var(--qn-ink-2); }
.empty-hint ul { margin: 0; padding-left: 18px; }
.empty-hint li { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.9; }

/* 成员网格 */
.family-grid-v2 {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px;
}
.family-member-card {
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg);
  padding: 18px 16px; text-align: center; transition: all 0.2s;
}
.family-member-card:hover { box-shadow: var(--qn-shadow-2); transform: translateY(-2px); }
.family-member-card.is-me { border-color: var(--qn-emerald); box-shadow: 0 0 0 2px rgba(var(--qn-emerald-rgb),0.12); }
.family-member-card.gen-1, .family-member-card.gen-2 { border-left: 3px solid var(--qn-earth); }     /* 长辈 */
.family-member-card.gen--1, .family-member-card.gen--2 { border-left: 3px solid var(--qn-wood); }   /* 晚辈 */

.fc-kinship { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 2px 0 10px; }
.fc-wuxing-bars { display: flex; flex-direction: column; gap: 3px; margin-top: 10px; text-align: left; }
.fwb-bar { display: grid; grid-template-columns: 18px 1fr 28px; align-items: center; gap: 6px; }
.fwb-label { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-weight: 500; }
.fwb-track { height: 5px; background: var(--qn-line); border-radius: 3px; overflow: hidden; }
.fwb-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.fwb-val { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-2); text-align: right; font-variant-numeric: tabular-nums; }

/* 全家合并 */
.union-vs-intersection {
  display: grid; grid-template-columns: 1.3fr 1fr; gap: 14px;
}
.uvi-card {
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 18px;
}
.uvi-card h4 { font-size: calc(13px * var(--qn-fs-scale)); margin: 0 0 14px; color: var(--qn-ink-2); font-weight: 600; }
.uvi-card.intersection { background: linear-gradient(180deg, var(--qn-surface) 0%, #FBF8F0 100%); }
.uvi-card.intersection.has_weak { border-color: rgba(212,160,23,0.4); }

.uvi-bars { display: flex; flex-direction: column; gap: 6px; }
.uvi-bar { display: grid; grid-template-columns: 24px 1fr 36px; align-items: center; gap: 10px; }
.uvi-label { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); text-align: center; }
.uvi-track { height: 10px; background: var(--qn-line); border-radius: 5px; overflow: hidden; }
.uvi-fill { height: 100%; border-radius: 5px; transition: width 0.4s ease; }
.uvi-val { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); font-variant-numeric: tabular-nums; }

.weak-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.weak-chip {
  background: rgba(212,160,23,0.1); border: 1px solid rgba(212,160,23,0.35);
  color: #8A6A10; padding: 4px 10px; border-radius: 14px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500;
}
.weak-hint { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 0; line-height: 1.6; }

/* 相克告警 */
.tension-list { display: flex; flex-direction: column; gap: 10px; }
.tension-card {
  background: var(--qn-banner-bad-bg); border: 1px solid var(--qn-bad-bd); border-radius: var(--qn-r-sm); padding: 14px 16px;
}
.tension-label { font-size: calc(14px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-fire); margin-bottom: 8px; }
.tension-detail p { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 2px 0; line-height: 1.7; }
.tension-suggest { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 8px 0 0; font-weight: 500; }

/* 联合调理建议 */
.guidance-list-v2 { display: flex; flex-direction: column; gap: 10px; }
.guidance-card {
  display: flex; align-items: flex-start; gap: 12px;
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-sm); padding: 14px 16px;
}
.guidance-card.cat-family { border-left: 3px solid var(--qn-earth); }
.guidance-card.cat-tension { border-left: 3px solid var(--qn-fire); }
.guidance-card.cat-lifestyle { border-left: 3px solid var(--qn-water); }
.gc-icon { font-size: calc(20px * var(--qn-fs-scale)); flex-shrink: 0; margin-top: 1px; }
.gc-text { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); margin: 0; line-height: 1.7; flex: 1; }

/* 旧 family-grid / family-guidance 样式保留不冲突 —— 已不再使用 */

/* 响应式 */
@media (max-width: 720px) {
  .union-vs-intersection { grid-template-columns: 1fr; }
  .family-grid-v2 { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
}

/* 邀请 */
.invite-card {
  max-width: 520px; margin: 0 auto;
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 24px 28px;
}
.invite-card h2 { font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0 0 6px; }
.invite-desc { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 0 0 20px; line-height: 1.6; }
.invite-code, .invite-link {
  display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 10px;
  background: var(--qn-paper); border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); padding: 10px 14px; margin-bottom: 10px;
}
.ic-label { grid-column: 1 / -1; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 4px; }
.ic-value { font-family: var(--font-mono); font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); }
.ic-link-input { border: none; background: transparent; font-family: var(--font-mono); font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); width: 100%; outline: none; }
.invite-share { display: flex; gap: 8px; margin: 16px 0 12px; }
.share-btn {
  flex: 1; font-size: calc(13px * var(--qn-fs-scale)); padding: 10px; border-radius: var(--qn-r-sm);
  border: 1px solid var(--qn-line); background: var(--qn-surface); cursor: pointer; transition: all 0.15s;
}
.share-btn:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.invite-terms { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); text-align: center; line-height: 1.6; }

/* 弹窗 */
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-card { background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 20px; width: 380px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal-card h3 { margin: 0 0 14px; color: var(--qn-emerald); font-size: calc(16px * var(--qn-fs-scale)); }
.modal-input { width: 100%; padding: 9px 12px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); font-size: calc(14px * var(--qn-fs-scale)); margin-bottom: 12px; }
.modal-input:focus { outline: none; border-color: var(--qn-emerald); }
.add-results { display: flex; flex-direction: column; gap: 6px; }
.result-row {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px; background: var(--qn-paper); border-radius: var(--qn-r-sm);
}
.result-info { flex: 1; min-width: 0; }
.result-info p { margin: 0; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); }
.result-id { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* 按钮 */
.btn { padding: 8px 16px; border: none; border-radius: var(--qn-r-sm); background: var(--qn-emerald); color: #fff; cursor: pointer; font-size: calc(13px * var(--qn-fs-scale)); transition: all 0.15s; font-family: var(--qn-font-body); font-weight: 500; }
.btn:hover { background: var(--qn-emerald-light); }
.btn-ghost { background: transparent; color: var(--qn-emerald); border: 1px solid var(--qn-emerald); }
.btn-ghost:hover { background: var(--qn-paper); }
.btn-small { padding: 5px 12px; font-size: calc(12px * var(--qn-fs-scale)); }

/* 医生弹窗 */
.doctor-modal { width: 480px; max-height: 85vh; overflow-y: auto; }
.doctor-modal-head { display: flex; gap: 14px; align-items: center; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--qn-line); }
.doctor-modal-head .friend-avatar.big { width: 56px; height: 56px; font-size: calc(26px * var(--qn-fs-scale)); }
.doctor-modal-head h3 { margin: 0 0 4px; font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-emerald); }
.doctor-tagline { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }

.doctor-section { margin-bottom: 14px; }
.doctor-section h4 { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 6px; }
.doctor-section p { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); margin: 3px 0; line-height: 1.5; }
.doctor-section .muted { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

.plan-card {
  background: var(--qn-paper); border: 1px solid var(--qn-line);
  border-radius: var(--qn-r-sm); padding: 12px 14px; margin-bottom: 6px;
}
.plan-title { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0 0 3px; }
.plan-date { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }
.next-plan { font-size: calc(12px * var(--qn-fs-scale)); margin-top: 6px; }

.doctor-actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.doctor-actions .btn { flex: 1; min-width: 160px; text-align: center; }

.btn-primary { background: var(--qingnang-spirit); }
.btn-primary:hover { background: #36A88F; }

.doctor-disclaimer {
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); line-height: 1.6; text-align: center;
  padding: 10px; background: var(--qn-paper); border-radius: var(--qn-r-sm); margin-top: 14px;
}

/* 响应式 */
@media (max-width: 720px) {
  .joint-compare { grid-template-columns: 1fr; }
  .family-grid { grid-template-columns: repeat(2, 1fr); }
  .friends-head .me-card { flex-wrap: wrap; }
}
</style>
