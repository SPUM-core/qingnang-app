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
      <!-- ⭐ 待处理请求面板 -->
      <div v-if="pendingRequests.length" class="pending-panel">
        <h3>📨 待处理请求 · {{ pendingRequests.length }}</h3>
        <div class="pending-list">
          <div v-for="r in pendingRequests" :key="r.friend_id" class="pending-card">
            <div class="mini-avatar" :style="{ background: pickGradient(r.from_nickname) }">👤</div>
            <div class="pending-info">
              <p class="pending-name">{{ r.from_nickname }}</p>
              <p class="pending-meta">青囊 ID: {{ r.from_qingnang_id }} · {{ r.relation === 'family' ? '家人' : '好友' }}</p>
            </div>
            <div class="pending-actions">
              <button class="btn btn-small" @click="acceptRequest(r.friend_id)">接受</button>
              <button class="btn btn-ghost btn-small" @click="rejectRequest(r.friend_id)">拒绝</button>
            </div>
          </div>
        </div>
      </div>

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

    <!-- ════ Tab 2: 联合建议 + 体质匹配度报告 ════ -->
    <div v-else-if="activeTab === 'together'" class="content">
      <div class="section-head">
        <h2>🤝 一起玩 · 一起吃 · 一起养</h2>
        <span class="hint">选择好友查看联合建议 · 青囊自动计算体质匹配度</span>
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
        <span v-if="matchReport?._fallback" class="fallback-tag">纯前端计算</span>
      </div>

      <p v-if="!partner" class="placeholder">选择好友，青囊会为你们生成联合建议 + 体质匹配度报告</p>

      <template v-else>
        <!-- ⭐ 匹配度总览 -->
        <div v-if="matchReport" class="match-header">
          <div class="match-score">
            <div class="score-ring" :style="{ '--score': matchReport.similarity }">
              <span class="score-val">{{ Math.round(matchReport.similarity * 100) }}</span>
              <span class="score-unit">%</span>
            </div>
            <p class="score-label">体质相似度</p>
          </div>
          <div class="match-tags">
            <span v-if="matchReport.intersection?.length" class="tag-intersection">🔗 共同弱项：{{ matchReport.intersection.join('、') }}</span>
            <span v-if="matchReport.complement?.length" class="tag-complement">✨ 互补：{{ matchReport.complement.join('、') }}</span>
          </div>
        </div>

        <!-- 五形对比 + 交集/互补标记 -->
        <div class="joint-compare">
          <div class="compare-card compare-me">
            <h4>你的五形向量</h4>
            <div class="vector-bars">
              <div v-for="d in matchReport.wuxing" :key="d.k" class="vector-bar" :class="{ 'bar-intersection': d.intersection, 'bar-complement': d.complement }">
                <span class="vb-label">{{ d.label }}{{ d.intersection ? '🔗' : '' }}{{ d.complement ? '✨' : '' }}</span>
                <div class="vb-track"><div class="vb-fill vb-me" :style="{ width: d.me + '%' }"></div></div>
                <span class="vb-val">{{ d.me }}</span>
              </div>
            </div>
          </div>
          <div class="compare-card compare-partner">
            <h4>{{ partner.name }}的五形向量</h4>
            <div class="vector-bars">
              <div v-for="d in matchReport.wuxing" :key="d.k" class="vector-bar" :class="{ 'bar-intersection': d.intersection, 'bar-complement': d.complement }">
                <span class="vb-label">{{ d.label }}{{ d.intersection ? '🔗' : '' }}{{ d.complement ? '✨' : '' }}</span>
                <div class="vb-track"><div class="vb-fill vb-partner" :style="{ width: d.friend + '%' }"></div></div>
                <span class="vb-val">{{ d.friend }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ⚠️ 相忌检测 -->
        <div v-if="matchReport.clash?.length" class="clash-warn">
          <h4>⚠️ 体质相忌（建议错开时辰）</h4>
          <p v-for="(c, i) in matchReport.clash" :key="i" class="clash-item">
            {{ c.label }} · {{ c.direction === 'me→friend' ? '你旺对方弱' : '对方旺你弱' }}
          </p>
        </div>

        <!-- 一句话总结 -->
        <div v-if="matchReport.conclusion" class="conclusion-card">
          <span class="conclusion-icon">🧭</span>
          <p class="conclusion-text">{{ matchReport.conclusion }}</p>
        </div>

        <!-- 🍜 联合饮食 -->
        <div class="advice-section">
          <h3>✨ 联合建议</h3>
          <div class="advice-block">
            <div class="advice-head"><span class="advice-emoji">🍜</span><span>适合双方的饮食</span></div>
            <div class="chips">
              <span v-for="t in jointAdvice" :key="t" class="chip">{{ t }}</span>
            </div>
          </div>
          <div class="advice-block">
            <div class="advice-head"><span class="advice-emoji">🎯</span><span>一起做什么</span></div>
            <ul class="activity-list">
              <li v-for="(a, i) in jointActivities" :key="i">{{ a }}</li>
            </ul>
          </div>
        </div>

        <!-- ⭐⭐ 时辰重叠提醒 -->
        <div v-if="shichenData.length" class="shichen-section">
          <div class="section-head">
            <h3>📅 时辰重叠机会</h3>
            <span class="hint">基于双方五形向量推算 · 推荐最佳互动时段</span>
          </div>
          <div class="shichen-grid">
            <div v-for="sc in shichenData" :key="sc.key" class="shichen-card" :class="`sc-${sc.status}`">
              <div class="sc-head">
                <span class="sc-emoji">{{ sc.emoji }}</span>
                <span class="sc-name">{{ sc.name }}</span>
                <span class="sc-range">{{ sc.range }}</span>
              </div>
              <p class="sc-action">{{ sc.action }}</p>
              <p class="sc-detail">{{ WUXING_NAMES[sc.wuxing] }}形 · 你{{ sc.meVal }} · 他{{ sc.friendVal }}</p>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ════ Tab 3: 🏆 挑战打卡 ════ -->
    <div v-else-if="activeTab === 'challenge'" class="content">
      <div class="section-head">
        <h2>🏆 挑战打卡 · 一起坚持</h2>
        <span class="hint">选择挑战模板 → 每日打卡 → 连续天数排行榜（本地存储）</span>
      </div>

      <!-- 已参加的挑战 -->
      <div v-if="myChallenges.length" class="my-challenges">
        <h3>我在参加（{{ myChallenges.length }} 个）</h3>
        <div class="challenge-grid">
          <div v-for="c in myChallenges" :key="c.id" class="challenge-card active">
            <div class="cc-icon">{{ c.icon }}</div>
            <div class="cc-info">
              <p class="cc-title">{{ c.title }}</p>
              <p class="cc-rule">{{ c.rule }}</p>
              <div class="cc-progress">
                <div class="cc-bar">
                  <div class="cc-fill" :style="{ width: Math.min(c.checkins.length / c.duration * 100, 100) + '%' }"></div>
                </div>
                <span class="cc-count">{{ c.checkins.length }} / {{ c.duration }} 天</span>
              </div>
              <p class="cc-streak">🔥 连续 {{ c.streak }} 天 · 开始于 {{ c.start_date }}</p>
            </div>
            <div class="cc-actions">
              <button class="btn btn-small" :disabled="c.checkins.includes(new Date().toISOString().slice(0,10))" @click="checkinChallenge(c.id)">
                {{ c.checkins.includes(new Date().toISOString().slice(0,10)) ? '✅ 今日已打卡' : '打卡' }}
              </button>
              <button class="btn btn-ghost btn-small" @click="leaveChallenge(c.id)">退出</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 可加入的模板 -->
      <div class="challenge-templates">
        <h3>🎯 推荐挑战</h3>
        <div class="challenge-grid">
          <div v-for="tpl in CHALLENGE_TEMPLATES" :key="tpl.id" class="challenge-card template" :class="{ joined: myChallenges.find(c => c.id === tpl.id) }">
            <div class="cc-icon">{{ tpl.icon }}</div>
            <div class="cc-info">
              <p class="cc-title">{{ tpl.title }}</p>
              <p class="cc-rule">{{ tpl.rule }} · {{ tpl.duration }} 天</p>
              <p class="cc-target">适合：{{ tpl.target_user }}</p>
            </div>
            <button v-if="!myChallenges.find(c => c.id === tpl.id)" class="btn btn-small" @click="joinChallenge(tpl)">参加</button>
            <span v-else class="joined-badge">已参加</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ════ Tab 4: 家庭健康看板（后端 family-aggregate 合并推算） ════ -->
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
import {
  cosineSimilarity, intersectionWeak, complementPairs, clashPairs,
  matchConclusion, shichenOverlap, WUXING_NAMES, SHICHEN_ORDER, SHICHEN_WUXING,
} from '../utils/friend-match'

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
  { k: 'wood', label: '木' }, { k: 'fire', label: '火' },
  { k: 'earth', label: '土' }, { k: 'metal', label: '金' }, { k: 'water', label: '水' }
]

// ═══════════════════════════════════════════════════════════
// 好友数据源：后端真实数据
// ═══════════════════════════════════════════════════════════
const friends = ref([])
const pendingRequests = ref([])
const loadingFriends = ref(true)

const RELATION_AVATAR = { doctor: '🩺', family: '🏠', friend: '🤝', other: '👤' }
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
        lastPlan: '医生方案', lastPlanDate: f.bind_date, nextVisit: null,
      } : null,
    }))
    // 待处理请求
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

// 待处理请求操作
async function acceptRequest(friendId) {
  try {
    await friendsApi.accept(friendId)
    pendingRequests.value = pendingRequests.value.filter(r => r.friend_id !== friendId)
    // 刷新好友列表
    const r = await friendsApi.list()
    friends.value = (Array.isArray(r.data) ? r.data : []).map((f, i) => ({
      id: f.friend_id || `bk-${i}`, friend_id: f.friend_id,
      qingnang_id: f.qingnang_id, name: f.nickname || '好友',
      relation: f.relation || 'friend', kinship_type: f.kinship_type,
      vBase: f.v_base || {}, model_summary: f.v_base_summary || '',
      avatar: RELATION_AVATAR[f.relation] || '👤',
      avatarGradient: pickGradient(f.nickname || f.qingnang_id || `f${i}`),
    }))
  } catch (e) { alert('接受失败：' + e.message) }
}
async function rejectRequest(friendId) {
  try {
    await friendsApi.reject(friendId)
    pendingRequests.value = pendingRequests.value.filter(r => r.friend_id !== friendId)
  } catch (e) { alert('拒绝失败：' + e.message) }
}

// ═══════════════════════════════════════════════════════════
// 从五形向量自动推导弱项标签
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

const weakPointChips = {
  '火形弱': { color: 'rgba(216,67,21,0.1)', text: '补火' },
  '火形过旺': { color: 'rgba(216,67,21,0.1)', text: '清火' },
  '木形弱': { color: 'rgba(67,160,71,0.1)', text: '补肝' },
  '木形过旺': { color: 'rgba(67,160,71,0.1)', text: '疏木' },
  '土形偏弱': { color: 'rgba(212,160,23,0.1)', text: '健脾' },
  '土形过旺': { color: 'rgba(212,160,23,0.1)', text: '泻土' },
  '金形偏弱': { color: 'rgba(144,164,174,0.15)', text: '补肺' },
  '金形过旺': { color: 'rgba(144,164,174,0.15)', text: '泻金' },
  '水形偏弱': { color: 'rgba(2,136,209,0.1)', text: '滋水' },
  '水形过旺': { color: 'rgba(2,136,209,0.1)', text: '利水' },
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
const familyMembers = computed(() => [me.value, ...weakPoints.value.filter(f => f.relation === 'family')])
const allFriends = computed(() => weakPoints.value)

// Tab
const tabs = computed(() => [
  { key: 'list',      icon: '👥', label: '好友列表', count: weakPoints.value.length },
  { key: 'together',  icon: '🤝', label: '联合建议' },
  { key: 'challenge', icon: '🏆', label: '挑战打卡' },
  { key: 'family',    icon: '🏠', label: '家庭指导' },
  { key: 'invite',    icon: '📤', label: '邀请朋友' }
])
const activeTab = ref('list')

// ═══════════════════════════════════════════════════════════
// ⭐ 体质匹配度报告（调用后端 match API，fallback 纯前端计算）
// ═══════════════════════════════════════════════════════════
const partnerId = ref('')
const partner = computed(() => allFriends.value.find(f => f.id === partnerId.value) || null)
const partnerVector = computed(() => partner.value?.vBase || null)

const matchReport = ref(null)    // 后端 match API 返回的数据
const matchLoading = ref(false)
const shichenData = ref([])      // 时辰重叠数据（纯前端）

async function computeJoint() {
  if (!partner.value) { matchReport.value = null; shichenData.value = []; return }
  matchLoading.value = true
  try {
    // 优先调后端 match API（有 conclusion + 更精确的检测）
    const r = await friendsApi.match(partner.value.friend_id || partner.value.id)
    matchReport.value = r.data
  } catch (e) {
    // fallback：纯前端计算
    console.warn('[Match] backend failed, using frontend fallback:', e.message)
    const a = meVector.value, b = partnerVector.value
    const intersection = intersectionWeak(a, b)
    const complement = complementPairs(a, b)
    const clash = clashPairs(a, b)
    const sim = cosineSimilarity(a, b)
    matchReport.value = {
      similarity: +sim.toFixed(3),
      wuxing: dims.map(d => ({
        k: d.k, label: d.label,
        me: a[d.k] ?? 50, friend: b[d.k] ?? 50,
        intersection: intersection.some(x => x.k === d.k),
        complement: complement.some(x => x.k === d.k),
      })),
      intersection: intersection.map(x => x.label),
      complement: complement.map(x => x.label),
      clash: clash,
      conclusion: matchConclusion(me.value.name, partner.value.name, intersection, complement, clash, sim),
      _fallback: true,
    }
  } finally {
    matchLoading.value = false
  }
  // 时辰重叠（纯前端，不依赖后端）
  shichenData.value = shichenOverlap(meVector.value, partnerVector.value)
}

// partner 变化时自动重新计算
watch(partnerId, computeJoint)

// ═══════════════════════════════════════════════════════════
// 🏆 挑战打卡 MVP（localStorage）
// ═══════════════════════════════════════════════════════════
const CHALLENGES_KEY = 'qn_challenges_v1'

const CHALLENGE_TEMPLATES = [
  { id: 'sleep-30',  title: '早睡 30 天',    rule: '22:30 前入睡打卡', duration: 30, icon: '🌙', wuxing: 'wood',  target_user: '木形空转·熬夜' },
  { id: 'bath-21',   title: '每日泡脚 21 天', rule: '40℃ 15min',        duration: 21, icon: '♨️', wuxing: 'water', target_user: '湿遏·相火妄动' },
  { id: 'nocold-14', title: '忌冷饮 14 天',  rule: '全天不碰冰饮',      duration: 14, icon: '🧊', wuxing: 'earth', target_user: '湿遏·土枯' },
  { id: 'salt-21',   title: '晨起先喝温盐水 21 天', rule: '晨起第一杯',  duration: 21, icon: '💧', wuxing: 'water', target_user: '水形流失·虚胖' },
  { id: 'walk-20',   title: '散步 30min × 20 次', rule: '申时最佳',         duration: 20, icon: '🚶', wuxing: 'wood',  target_user: '气结·土弱' },
]

function loadChallenges() {
  try { return JSON.parse(localStorage.getItem(CHALLENGES_KEY) || '[]') } catch { return [] }
}
function saveChallenges(arr) { localStorage.setItem(CHALLENGES_KEY, JSON.stringify(arr)) }

const myChallenges = ref(loadChallenges())

function joinChallenge(tpl) {
  const existing = myChallenges.value.find(c => c.id === tpl.id)
  if (existing) { alert('你已经参加这个挑战了'); return }
  const c = {
    id: tpl.id, title: tpl.title, rule: tpl.rule, duration: tpl.duration,
    icon: tpl.icon, wuxing: tpl.wuxing, target_user: tpl.target_user,
    start_date: new Date().toISOString().slice(0, 10),
    checkins: [],
    streak: 0,
  }
  myChallenges.value.push(c)
  saveChallenges(myChallenges.value)
}

function checkinChallenge(challengeId) {
  const today = new Date().toISOString().slice(0, 10)
  const c = myChallenges.value.find(x => x.id === challengeId)
  if (!c) return
  if (c.checkins.includes(today)) { alert('今天已经打过卡了'); return }
  c.checkins.push(today)
  // 计算连续天数
  c.checkins.sort()
  c.streak = calcStreak(c.checkins)
  saveChallenges(myChallenges.value)
}

function calcStreak(checkins) {
  if (!checkins.length) return 0
  let streak = 0
  let d = new Date()
  for (let i = checkins.length - 1; i >= 0; i--) {
    const ci = checkins[i]
    const today = d.toISOString().slice(0, 10)
    if (ci === today) { streak++; d.setDate(d.getDate() - 1) }
    else break
  }
  return streak
}

function leaveChallenge(challengeId) {
  if (!confirm('确定退出这个挑战吗？打卡记录会保留')) return
  myChallenges.value = myChallenges.value.filter(c => c.id !== challengeId)
  saveChallenges(myChallenges.value)
}

// ═══════════════════════════════════════════════════════════
// 家庭看板数据源
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

// ═══════════════════════════════════════════════════════════
// 邀请
// ═══════════════════════════════════════════════════════════
const inviteLink = computed(() => `https://qingnang.app/invite?code=QN-${me.value.id.slice(-6)}-2026`)
function copyCode() { navigator.clipboard?.writeText(inviteLink.value) }
function copyLink() { navigator.clipboard?.writeText(inviteLink.value) }
function shareVia(channel) {
  const msgs = { wechat: '已生成微信分享', moments: '已生成朋友圈', sms: '已生成短信' }
  alert(`${msgs[channel]}：${inviteLink.value}`)
}

// ═══════════════════════════════════════════════════════════
// 添加好友
// ═══════════════════════════════════════════════════════════
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
    // 刷新列表
    const r2 = await friendsApi.list()
    friends.value = (Array.isArray(r2.data) ? r2.data : []).map((f, i) => ({
      id: f.friend_id || f.qingnang_id || `bk-${i}`, friend_id: f.friend_id,
      qingnang_id: f.qingnang_id, name: f.nickname || '好友',
      relation: f.relation || 'friend', vBase: f.v_base || {},
      model_summary: f.v_base_summary || '',
      avatar: RELATION_AVATAR[f.relation] || '👤',
      avatarGradient: pickGradient(f.nickname || f.qingnang_id || `f${i}`),
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

/* ═══════════════════════════════════════════════════════════
   📨 待处理请求面板
═══ */
.pending-panel {
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.06), rgba(var(--qn-emerald-light-rgb),0.06));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.2);
  border-radius: var(--qn-r-lg); padding: 14px 18px; margin-bottom: 18px;
}
.pending-panel h3 { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0 0 10px; }
.pending-list { display: flex; flex-direction: column; gap: 8px; }
.pending-card {
  display: flex; align-items: center; gap: 10px;
  background: var(--qn-surface); border-radius: var(--qn-r-sm); padding: 10px 14px;
}
.pending-info { flex: 1; min-width: 0; }
.pending-name { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-ink); margin: 0; }
.pending-meta { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 2px 0 0; }
.pending-actions { display: flex; gap: 6px; flex-shrink: 0; }

/* ═══════════════════════════════════════════════════════════
   ⭐ 体质匹配度报告
═══ */
.fallback-tag {
  font-size: calc(10px * var(--qn-fs-scale)); background: rgba(var(--qn-emerald-rgb),0.1);
  color: var(--qn-emerald); padding: 2px 8px; border-radius: 10px; font-weight: 500; flex-shrink: 0;
}

.match-header {
  display: flex; align-items: center; gap: 20px; margin-bottom: 20px;
  background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 18px 22px;
}
.match-score { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.score-ring {
  width: 80px; height: 80px; border-radius: 50%;
  background: conic-gradient(var(--qn-emerald) calc(var(--score) * 1%), var(--qn-line) 0);
  display: flex; align-items: center; justify-content: center; position: relative;
}
.score-ring::before {
  content: ''; position: absolute; inset: 6px; border-radius: 50%; background: var(--qn-surface);
}
.score-val { font-size: calc(22px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-emerald); z-index: 1; }
.score-unit { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald); z-index: 1; }
.score-label { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }

.match-tags { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.tag-intersection {
  font-size: calc(12px * var(--qn-fs-scale)); background: rgba(212,160,23,0.1);
  color: #8A6A10; padding: 4px 12px; border-radius: 14px; font-weight: 500;
}
.tag-complement {
  font-size: calc(12px * var(--qn-fs-scale)); background: rgba(var(--qn-emerald-rgb),0.08);
  color: var(--qn-emerald); padding: 4px 12px; border-radius: 14px; font-weight: 500;
}

.bar-intersection .vb-label, .bar-complement .vb-label { font-weight: 700; }
.bar-intersection { background: rgba(212,160,23,0.05); border-radius: 4px; }
.bar-complement { background: rgba(var(--qn-emerald-rgb),0.05); border-radius: 4px; }

.clash-warn {
  background: var(--qn-banner-bad-bg); border: 1px solid var(--qn-bad-bd); border-radius: var(--qn-r-sm);
  padding: 12px 16px; margin-bottom: 14px;
}
.clash-warn h4 { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-fire); margin: 0 0 6px; font-weight: 600; }
.clash-item { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 2px 0; }

.conclusion-card {
  display: flex; gap: 12px; align-items: flex-start;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.08), rgba(var(--qn-emerald-light-rgb),0.08));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.2); border-radius: var(--qn-r-sm);
  padding: 14px 18px; margin-bottom: 14px;
}
.conclusion-icon { font-size: calc(20px * var(--qn-fs-scale)); flex-shrink: 0; }
.conclusion-text { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); line-height: 1.7; margin: 0; }

/* ═══════════════════════════════════════════════════════════
   📅 时辰重叠提醒
═══ */
.shichen-section { margin-top: 14px; }
.shichen-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px;
}
.shichen-card {
  background: var(--qn-surface); border-radius: var(--qn-r-sm); padding: 12px 14px;
  border-left: 3px solid var(--qn-line); transition: all 0.15s;
}
.shichen-card.sc-good { border-left-color: var(--qn-emerald); }
.shichen-card.sc-avoid { border-left-color: var(--qn-fire); background: var(--qn-banner-bad-bg); }
.shichen-card.sc-caution { border-left-color: #D4A017; }
.shichen-card.sc-neutral { border-left-color: var(--qn-line); }
.sc-head { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.sc-emoji { font-size: calc(14px * var(--qn-fs-scale)); }
.sc-name { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.sc-range { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-left: auto; }
.sc-action { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 0 0 4px; line-height: 1.5; }
.sc-detail { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }

/* ═══════════════════════════════════════════════════════════
   🏆 挑战打卡
═══ */
.my-challenges, .challenge-templates { margin-bottom: 20px; }
.my-challenges h3, .challenge-templates h3 {
  font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0 0 10px; font-weight: 600;
}
.challenge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.challenge-card {
  display: flex; gap: 12px; align-items: center;
  background: var(--qn-surface); border-radius: var(--qn-r-lg); padding: 14px 16px;
  transition: all 0.15s;
}
.challenge-card.active { border-left: 3px solid var(--qn-emerald); }
.challenge-card.template:hover { box-shadow: var(--qn-shadow-2); transform: translateY(-1px); }
.challenge-card.template.joined { opacity: 0.7; }

.cc-icon {
  width: 44px; height: 44px; border-radius: 10px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light));
  display: flex; align-items: center; justify-content: center;
  font-size: calc(22px * var(--qn-fs-scale));
}
.cc-info { flex: 1; min-width: 0; }
.cc-title { font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0; }
.cc-rule { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 2px 0; }
.cc-target { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0; }
.cc-streak { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qingnang-spirit); margin: 4px 0 0; }

.cc-progress { display: flex; align-items: center; gap: 8px; margin: 6px 0 4px; }
.cc-bar { flex: 1; height: 6px; background: var(--qn-line); border-radius: 3px; overflow: hidden; }
.cc-fill { height: 100%; background: var(--qn-emerald); border-radius: 3px; transition: width 0.3s; }
.cc-count { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-variant-numeric: tabular-nums; white-space: nowrap; }

.cc-actions { display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
.cc-actions .btn { white-space: nowrap; }
.joined-badge { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald); font-weight: 500; }

/* 响应式 */
@media (max-width: 720px) {
  .joint-compare { grid-template-columns: 1fr; }
  .family-grid { grid-template-columns: repeat(2, 1fr); }
  .friends-head .me-card { flex-wrap: wrap; }
}
</style>
