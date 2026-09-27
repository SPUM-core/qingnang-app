<template>
  <section class="page reminders">
    <!-- 顶部：今日时空摘要 -->
    <div class="today-card">
      <div class="today-grid">
        <div class="tg-cell">
          <span class="tg-label">今日干支</span>
          <span class="tg-val">{{ today.ganzhi }}</span>
        </div>
        <div class="tg-cell">
          <span class="tg-label">当令时辰</span>
          <span class="tg-val">{{ today.dangling }} · 旺{{ today.dangling_elem }}</span>
        </div>
        <div class="tg-cell">
          <span class="tg-label">流飞星</span>
          <span class="tg-val">{{ today.feixing }}</span>
        </div>
        <div class="tg-cell">
          <span class="tg-label">你的避忌</span>
          <span class="tg-val tg-warn">冲{{ today.chong }}</span>
        </div>
      </div>
      <p class="today-note">
        📅 {{ today.date }} · 丙戌月 · 今天宜<span class="good">{{ today.yi }}</span>，
        忌<span class="bad">{{ today.ji }}</span>
      </p>
    </div>

    <!-- 分类 Tab -->
    <div class="tabs">
      <button v-for="cat in categories" :key="cat.key" class="tab-btn"
              :class="{ active: activeCat === cat.key }" @click="activeCat = cat.key">
        {{ cat.icon }} {{ cat.label }}
        <span class="tab-count">{{ cat.count }}</span>
      </button>
    </div>

    <!-- ════ 衣：穿搭建议 ════ -->
    <div v-if="activeCat === 'cloth'" class="card-grid">
      <article class="rem-card" v-for="r in clothReminders" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: r.iconBg }">{{ r.icon }}</span>
          <div class="rem-level" :class="r.level">{{ r.levelLabel }}</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <div v-if="r.tags?.length" class="rem-tags">
          <span v-for="t in r.tags" :key="t" class="rem-tag">{{ t }}</span>
        </div>
        <p v-if="r.reason" class="rem-reason">📖 原理：{{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 食：饮食宜忌 ════ -->
    <div v-else-if="activeCat === 'food'" class="card-grid">
      <article class="rem-card rem-good" v-for="r in foodGood" :key="'g-' + r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: '#1A4D45' }">✅</span>
          <div class="rem-level pri-ok">宜</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
      <article class="rem-card rem-bad" v-for="r in foodBad" :key="'b-' + r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: '#D84315' }">⚠️</span>
          <div class="rem-level pri-warn">忌</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 住：住房改造 ════ -->
    <div v-else-if="activeCat === 'home'" class="card-grid">
      <article class="rem-card" v-for="r in homeReminders" :key="r.id" :class="{ 'rem-urgent': r.urgent }">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: r.iconBg }">{{ r.icon }}</span>
          <div v-if="r.urgent" class="rem-urgent-badge">⚠️ 优先</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <div v-if="r.steps?.length" class="rem-steps">
          <p v-for="(s, i) in r.steps" :key="i">{{ i + 1 }}. {{ s }}</p>
        </div>
        <p v-if="r.reason" class="rem-reason">📖 {{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 行：出行/时辰 ════ -->
    <div v-else-if="activeCat === 'travel'" class="card-grid">
      <!-- 时辰提醒 -->
      <article class="rem-card rem-timeline">
        <h3>🕐 今日时辰节律</h3>
        <div class="timeline">
          <div v-for="t in todayTimeline" :key="t.period" class="tl-item" :class="t.type">
            <span class="tl-time">{{ t.range }}</span>
            <span class="tl-elem">{{ t.elem }}</span>
            <span class="tl-desc">{{ t.desc }}</span>
          </div>
        </div>
      </article>
      <article class="rem-card" v-for="r in travelReminders" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: r.iconBg }">{{ r.icon }}</span>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p v-if="r.reason" class="rem-reason">📖 {{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 禁忌规避 ════ -->
    <div v-else-if="activeCat === 'avoid'" class="card-grid">
      <article class="rem-card rem-absolute" v-for="r in absoluteAvoid" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" style="background: #D84315">❌</span>
          <div class="rem-level pri-danger">绝对禁忌</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
      <article class="rem-card" v-for="r in relativeAvoid" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" style="background: #D4A017">⚠️</span>
          <div class="rem-level pri-warn">慎用</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
      <article class="rem-card rem-stones" v-for="r in stoneReminders" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" style="background: #90A4AE">💎</span>
          <div class="rem-level pri-warn">矿物避忌</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
      </article>
    </div>

    <!-- ════ 破煞方案 ════ -->
    <div v-else class="card-grid">
      <article class="rem-card rem-solution" v-for="s in solutions" :key="s.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: s.iconBg }">{{ s.icon }}</span>
          <div class="rem-solution-tag">破煞方案</div>
        </div>
        <h3>{{ s.title }}</h3>
        <p class="rem-desc">{{ s.desc }}</p>
        <div class="solution-body">
          <div class="sol-target">
            <span class="sol-label">针对</span>
            <span class="sol-val">{{ s.target }}</span>
          </div>
          <div class="sol-steps">
            <p v-for="(step, i) in s.steps" :key="i" class="sol-step">
              <span class="sol-step-num">{{ i + 1 }}</span>
              {{ step }}
            </p>
          </div>
        </div>
        <p class="rem-reason">📖 原理：{{ s.reason }}</p>
      </article>
    </div>

    <!-- 底部说明 -->
    <p class="footer-notice">
      * 所有建议基于你的数字模型（湿遏状态 · 土枯 · 气结74% · 相火妄动）推导，
      仅供生活参考，不构成医疗诊断
    </p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

// ═══════════════════════════════════════════════════════════
// 今日时空（静态，模拟 2026-09-25）
// ═══════════════════════════════════════════════════════════
const today = {
  date: '2026-09-25',
  ganzhi: '丙午年 丁酉月 癸酉日',
  dangling: '酉时',
  dangling_elem: '金',
  feixing: '4绿入中',
  chong: '兔（卯）',
  yi: '养生·调理·静养',
  ji: '大动·辛辣·冷饮'
}

const activeCat = ref('cloth')

// 分类数量（根据胡运涛案例动态统计）
const clothReminders = [
  { id: 'c1', icon: '👕', iconBg: '#43A047', title: '今日宜穿：绿色/青色',
    desc: '木形补肝 · 绿色属木，对应肝胆系统，今日气结 74% 状态下可疏解肝气郁结',
    level: 'ok', levelLabel: '宜', tags: ['木形', '气结74%'],
    reason: '你木形先天旺但肝血枯（引擎空转），今日酉时金旺克木，木更弱——绿色可助疏解' },
  { id: 'c2', icon: '🧥', iconBg: '#1A4D45', title: '避免：冷色调·深蓝/暗灰',
    desc: '水形今日流飞 4 绿入中，过冷色调会加剧水形沉潜，加重湿遏',
    level: 'bad', levelLabel: '忌', reason: '湿遏状态下，过冷颜色→体内心阳被遏→湿更难化' },
  { id: 'c3', icon: '💎', iconBg: '#D84315', title: '推荐配饰：红玛瑙/蜜蜡',
    desc: '替代岫玉/翡翠（寒），温润红色可助心火潜镇，又不耗阴',
    level: 'ok', levelLabel: '宜', tags: ['配饰', '绝对禁忌替代方案'],
    reason: '你绝对禁忌岫玉/翡翠（寒·直接抑制基线火形），已活体验证有效' },
  { id: 'c4', icon: '🎽', iconBg: '#D4A017', title: '贴身衣物：避免靛蓝染色',
    desc: '靛蓝属木但性寒，贴身会持续给肝胆施寒，加重木形悖论',
    level: 'warn', levelLabel: '慎用', reason: '引擎空转状态下，木形再受寒→肝血更枯' }
]

const foodGood = [
  { id: 'fg1', title: '小米粥（早餐）', desc: '入脾经 · 温养土形 · 易消化', reason: '你 S_土↓↓↓ 三重枯竭，小米是最温和的养土方式' },
  { id: 'fg2', title: '鲫鱼汤（午餐）', desc: '利水而不寒 · 补土不助湿', reason: '湿遏状态下利水是关键，但不可大寒——鲫鱼性平' },
  { id: 'fg3', title: '温淡盐水（晨起第一杯）', desc: '唤醒载流体循环 · 补充津液而不耗阴', reason: '3时醒后第一杯，代替凉茶/咖啡' },
  { id: 'fg4', title: '蒸蛋 · 红枣莲子芡实', desc: '温润补中 · 不加重脾胃负担', reason: '晚餐后不吃任何东西——本应用于早餐或午餐' }
]
const foodBad = [
  { id: 'fb1', title: '冷饮/生冷（绝对禁忌）', desc: '冰水入口 → 载流体急剧降温 → 已沉积组织产生微裂隙', reason: '湿遏+土枯双状态下，冷饮是雪上加霜' },
  { id: 'fb2', title: '浓茶/咖啡', desc: '提神耗阴 → 虚火更旺', reason: '你火形悖论状态下，咖啡短期提神但相火更妄动' },
  { id: 'fb3', title: '晚餐后进食', desc: '晚间载流体本应冷却沉降 · 吃夜宵→新溶质+局部加热', reason: '子时自然降温窗口被破坏' },
  { id: 'fb4', title: '辛辣·生姜过量', desc: '短期 S_火↑ 但耗 S_水', reason: '你水形分量偏低，辛辣耗阴→水更枯' }
]

const homeReminders = [
  { id: 'h1', icon: '🛏️', iconBg: '#1A4D45', title: '床头调整：移离窗户 2 米以上',
    desc: '当前床头靠窗（子午流注酉时金旺克木），调整到房间中央偏东', urgent: true,
    steps: ['测量床头到窗户距离 < 2 米', '调整床头方向，背靠实墙', '床头上方悬挂红色小饰物（朱砂/红绳）'],
    reason: '酉时金旺克木，木形再弱会加重气结状态——红色破金气' },
  { id: 'h2', icon: '🪴', iconBg: '#43A047', title: '客厅增加绿色植物（3-5盆）',
    desc: '激活空间木形能量，对应你气结 74% 的疏解需要',
    steps: ['选阔叶常绿植物（绿萝/龟背竹）', '放在客厅东南角（木位）', '数量 3 或 8 盆（木数）'],
    reason: '形峦配五行——绿色植物是最温和的空间补木方式' },
  { id: 'h3', icon: '💡', iconBg: '#D4A017', title: '卧室灯光：暖黄 2700K · 睡前调暗',
    desc: '你火形悖论状态下，卧室不宜冷光（抑制相火归位）',
    reason: '冷白光→心火外浮→入睡困难；暖黄光→心火沉降→入眠快' },
  { id: 'h4', icon: '🧘', iconBg: '#0288D1', title: '书房增加水元素（鱼缸/加湿器）',
    desc: '脑力消耗大的空间需要水形调节，同时助滋水护印',
    reason: '脑力=持续湍流+局部加热，水形可降温稳流' },
  { id: 'h5', icon: '🚪', iconBg: '#90A4AE', title: '厨房炉灶与冰箱对角（不要相对）',
    desc: '火水相克煞，你当前湿遏状态不宜再加水火对冲',
    reason: '炉灶属火、冰箱属水，正对冲克→湿遏更甚' }
]

const todayTimeline = [
  { period: '23:00-01:00', range: '子时', elem: '水', desc: '😴 必睡 · 载流体自然降温', type: 'critical' },
  { period: '01:00-03:00', range: '丑时', elem: '土', desc: '熟睡中 · 脾经修复', type: 'good' },
  { period: '03:00-05:00', range: '寅时', elem: '木', desc: '搓热捂后腰 · 闭目深呼吸', type: 'personal' },
  { period: '05:00-07:00', range: '卯时', elem: '木', desc: '温淡盐水 · 散步准备', type: 'good' },
  { period: '07:00-09:00', range: '辰时', elem: '土', desc: '小米粥早餐 · 不赶时间', type: 'good' },
  { period: '11:00-13:00', range: '午时', elem: '火', desc: '闭目 20 分钟 · 不进食', type: 'good' },
  { period: '13:00-15:00', range: '未时', elem: '土', desc: '轻度活动 · 八段锦', type: 'personal' },
  { period: '17:00-19:00', range: '酉时', elem: '金', desc: '⚠️ 金旺克木 · 减少高强度工作', type: 'warn' },
  { period: '19:00-21:00', range: '戌时', elem: '土', desc: '泡脚 15min （40℃ · 不大汗）', type: 'good' },
  { period: '21:00-23:00', range: '亥时', elem: '水', desc: '放下手机 · 准备入睡', type: 'good' }
]

const travelReminders = [
  { id: 't1', icon: '🚶', iconBg: '#43A047', title: '散步时段：申时 15-17 点最佳',
    desc: '此时秋金当令，空气最清爽，同时避开酉时金旺克木的时段', reason: '你气结状态下，申时散步疏解最有效' },
  { id: 't2', icon: '🚗', iconBg: '#90A4AE', title: '长途出行：随身带蜜蜡手串',
    desc: '替代岫玉（绝对禁忌），蜜蜡温而不燥，可在途中持续护持心阳', reason: '长途=久坐→载流体湍流加剧' },
  { id: 't3', icon: '✈️', iconBg: '#0288D1', title: '避免：子时（23-1点）长途飞行',
    desc: '你水形分量偏低，高空+子时叠加水形流失', reason: '高空=气压变化→水形失稳；子时=水形当令但你水形虚' }
]

const absoluteAvoid = [
  { id: 'aa1', title: '苦寒直折（黄连/黄芩/大黄/大剂栀子）', desc: '绝对禁止', reason: '直接伤 S_土 形，与湿遏状态治疗路径完全冲突' },
  { id: 'aa2', title: '安眠药（强制关闭木环）', desc: '绝对禁止', reason: '强制关闭木环 → 与温和重建路径冲突；用睡前温热水替代' },
  { id: 'aa3', title: '岫玉/翡翠/黑曜石（寒色矿物）', desc: '绝对禁止穿戴', reason: '寒→直接抑制基线火形，已活体验证：戴岫玉当天脉搏火形分量 ↓0.22' }
]
const relativeAvoid = [
  { id: 'ra1', title: '大热大补（鹿茸/附子/肉桂/干姜）', desc: '慎用 · 2026 午子冲生火助火', reason: '午子冲+双丙透干+寅午半合火局，火势极旺' },
  { id: 'ra2', title: '咖啡/浓茶', desc: '慎用 · 提神耗阴→虚火更旺', reason: '你火形悖论：外面在冷，里面在烧' },
  { id: 'ra3', title: '辛辣过量', desc: '慎用 · 短期 S_火↑ 但耗 S_水', reason: '短期效果但长期加重水形枯竭' }
]
const stoneReminders = [
  { id: 's1', title: '⛔ 岫玉/翡翠（寒）', desc: '直接抑制基线火形，已活体验证' },
  { id: 's2', title: '⛔ 白水晶/海蓝宝/黑曜石（寒）', desc: '同属寒性，会让火形分量进一步下降' },
  { id: 's3', title: '✅ 推荐：蜜蜡/红玛瑙（温）', desc: '温润而不燥，不破坏当前调理节奏' }
]

const solutions = [
  { id: 'sol1', icon: '🔥', iconBg: '#D84315', title: '破：床头靠窗金克木煞',
    target: '气结 74% · 湿遏状态 · 卧室床头',
    steps: ['床头从窗边移开 2 米以上', '调整床头方向，背靠实墙', '床头上方悬挂朱砂或红色中国结（朱砂 3-5g 即可）', '窗帘加厚，减少晨间酉时金气直接入内'],
    reason: '酉时当令金旺克木，你木形先天极旺但肝血空转（引擎空转），金克木→肝血更枯。朱砂属火，火能克金，同时暖木——一举双得' },
  { id: 'sol2', icon: '🌿', iconBg: '#43A047', title: '破：气结 74% 木形空转煞',
    target: '木形悖论 · 思虑惯性 · 3时醒',
    steps: ['书房增加 3-8 盆阔叶常绿植物（绿萝/龟背竹）', '3时醒后不要看手机', '搓热双手捂后腰 · 闭目深呼吸 10 次', '上午脑力任务 ≤ 1 小时即起身活动 5 分钟'],
    reason: '木形空转=转速高但油箱空——疏木（绿色植物·空间补木）+ 养血（搓腰·保护肾阳·滋水涵木）双管齐下' },
  { id: 'sol3', icon: '💧', iconBg: '#0288D1', title: '破：湿遏状态水形沉潜煞',
    target: '湿遏 · 水形分量 ↓0.62 · 脉搏沉缓',
    steps: ['每日早起温淡盐水 1 杯（200ml，不加糖不加蜜）', '晚上 21:00 前泡脚 15min（水温 40℃，不可出汗）', '卧室增加小型加湿器（湿度 55-60%）', '饮食优先鲫鱼汤/小米粥，避免生冷水果'],
    reason: '湿遏=水形被湿困住→沉潜→不流动。温淡盐水唤醒水形循环，泡脚推动水形上行，加湿器滋水而不助湿' },
  { id: 'sol4', icon: '🌙', iconBg: '#90A4AE', title: '破：厨房水火对冲煞',
    target: '湿遏加剧 · 家宅破煞',
    steps: ['确认炉灶与冰箱不在正对冲位置（>1.5 米距离）', '如无法调整：炉灶上方悬挂葫芦（木，泄火生土·不克水）', '或冰箱门上贴红色装饰贴纸（3×3cm 即可）'],
    reason: '炉灶属火、冰箱属水，正对冲克→水形被火煎熬→湿更难化。葫芦属木，木能通关——泄火生土，土能制水（不直接冲克）' }
]

const categories = computed(() => [
  { key: 'cloth', icon: '👕', label: '穿衣配饰', count: clothReminders.length },
  { key: 'food', icon: '🍜', label: '饮食宜忌', count: foodGood.length + foodBad.length },
  { key: 'home', icon: '🏠', label: '住房改造', count: homeReminders.length },
  { key: 'travel', icon: '🕐', label: '时辰出行', count: todayTimeline.length + travelReminders.length },
  { key: 'avoid', icon: '⚠️', label: '禁忌规避', count: absoluteAvoid.length + relativeAvoid.length + stoneReminders.length },
  { key: 'solution', icon: '💡', label: '破煞方案', count: solutions.length }
])
</script>

<style scoped>
.reminders { max-width: 1400px; }

/* 今日时空卡片 */
.today-card {
  background: linear-gradient(135deg, rgba(26,77,69,0.06), rgba(212,160,23,0.05));
  border: 1px solid rgba(26,77,69,0.15); border-radius: var(--radius-md);
  padding: 16px 20px; margin-bottom: 18px;
}
.today-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 10px; }
.tg-cell { text-align: center; }
.tg-label { display: block; font-size: 11px; color: var(--ink-tertiary); font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 4px; }
.tg-val { font-size: 14px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); }
.tg-warn { color: var(--wuxing-fire); }
.today-note { font-size: 12px; color: var(--ink-secondary); margin: 0; padding-top: 10px; border-top: 1px dashed rgba(26,77,69,0.15); }
.today-note .good { color: var(--wuxing-wood); font-weight: 600; }
.today-note .bad { color: var(--wuxing-fire); font-weight: 600; }

/* Tab */
.tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }
.tab-btn {
  font-size: 13px; padding: 7px 16px; border-radius: 20px;
  border: 1px solid var(--ink-line); background: #fff; color: var(--ink-secondary);
  cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
}
.tab-btn:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }
.tab-btn.active { background: var(--qingnang-emerald); border-color: var(--qingnang-emerald); color: #fff; }
.tab-count { background: var(--qingnang-paper); color: var(--ink-tertiary); padding: 0 6px; border-radius: 10px; font-size: 11px; }
.tab-btn.active .tab-count { background: rgba(255,255,255,0.2); color: #fff; }

/* 卡片网格 */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }

.rem-card {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md);
  padding: 16px 18px; transition: all 0.15s; display: flex; flex-direction: column;
}
.rem-card:hover { box-shadow: var(--shadow-card-hover); border-color: rgba(26,77,69,0.2); }
.rem-card.rem-urgent { border-left: 3px solid var(--wuxing-fire); }
.rem-card.rem-good { border-left: 3px solid var(--wuxing-wood); }
.rem-card.rem-bad { border-left: 3px solid var(--wuxing-fire); }
.rem-card.rem-absolute { border-left: 4px solid var(--wuxing-fire); background: linear-gradient(135deg, #fff, rgba(216,67,21,0.02)); }
.rem-card.rem-stones { border-left: 3px solid var(--wuxing-metal); }

.rem-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.rem-icon {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 16px;
}
.rem-level, .rem-solution-tag, .rem-urgent-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.5px;
}
.rem-level.pri-ok, .rem-level.ok { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.rem-level.pri-warn, .rem-level.warn { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.rem-level.pri-danger, .rem-level.bad { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.rem-urgent-badge { background: var(--wuxing-fire); color: #fff; }
.rem-solution-tag { background: var(--qingnang-emerald); color: #fff; }

.rem-card h3 { font-size: 14px; font-weight: 600; color: var(--ink-primary); margin: 0 0 4px; line-height: 1.4; }
.rem-desc { font-size: 12px; color: var(--ink-secondary); margin: 0 0 8px; line-height: 1.6; }
.rem-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.rem-tag {
  font-size: 10px; color: var(--qingnang-emerald);
  background: rgba(26,77,69,0.06); padding: 1px 6px; border-radius: 3px; font-weight: 500;
}
.rem-reason { font-size: 11px; color: var(--ink-tertiary); margin: 8px 0 0; line-height: 1.5; font-style: italic; }
.rem-steps { margin: 6px 0; padding-left: 14px; }
.rem-steps p { font-size: 12px; color: var(--ink-secondary); margin: 2px 0; line-height: 1.5; }

/* 时辰时间线 */
.rem-timeline { grid-column: 1 / -1; }
.timeline { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.tl-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 12px;
  border-radius: var(--radius-sm); border: 1px solid var(--ink-line);
  font-size: 12px;
}
.tl-time { font-family: var(--font-mono); font-weight: 600; color: var(--ink-primary); font-size: 11px; }
.tl-elem { font-size: 10px; color: var(--ink-tertiary); padding: 1px 6px; background: var(--qingnang-paper); border-radius: 3px; }
.tl-desc { flex: 1; margin-left: 4px; color: var(--ink-secondary); line-height: 1.4; }
.tl-item.critical { border-color: var(--wuxing-fire); background: rgba(216,67,21,0.03); }
.tl-item.good { border-color: var(--wuxing-wood); background: rgba(67,160,71,0.03); }
.tl-item.personal { border-color: var(--qingnang-emerald); background: rgba(26,77,69,0.03); }
.tl-item.warn { border-color: var(--wuxing-earth); background: rgba(212,160,23,0.04); }

/* 破煞方案 */
.rem-solution { background: linear-gradient(135deg, rgba(26,77,69,0.03), rgba(46,125,106,0.03)); border-color: rgba(26,77,69,0.2); }
.solution-body { margin: 8px 0; background: var(--qingnang-paper); border-radius: var(--radius-sm); padding: 10px 12px; }
.sol-target { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px dashed var(--ink-line); }
.sol-label { font-size: 11px; color: var(--ink-tertiary); font-weight: 600; letter-spacing: 0.5px; }
.sol-val { font-size: 12px; color: var(--qingnang-emerald); font-weight: 500; }
.sol-steps { display: flex; flex-direction: column; gap: 5px; }
.sol-step { font-size: 12px; color: var(--ink-primary); display: flex; gap: 8px; align-items: flex-start; line-height: 1.5; }
.sol-step-num {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--qingnang-emerald); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; flex-shrink: 0; margin-top: 1px;
}

.footer-notice { font-size: 11px; color: var(--ink-tertiary); margin-top: 20px; text-align: center; line-height: 1.6; padding: 0 10px; }

@media (max-width: 720px) {
  .today-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
