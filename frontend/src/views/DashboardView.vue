<template>
  <section class="page home"
           @touchstart="onPullStart"
           @touchmove="onPullMove"
           @touchend="onPullEnd">
    <!-- ══ 下拉刷新指示器 ══ -->
    <div class="pull-refresh"
         :style="{ height: pullDistance + 'px', opacity: pullDistance > 0 ? 1 : 0 }">
      <!-- 下拉阶段：箭头 + 阻尼拉伸 -->
      <template v-if="!pullRefreshing">
        <div class="pr-arrow" :class="{ spin: pullDistance > 80 }">↓</div>
      </template>
      <!-- 刷新阶段：青囊主题加载动画 -->
      <template v-else>
        <div class="pr-loader">
          <div class="pr-ring pr-ring-outer"></div>
          <div class="pr-ring pr-ring-inner"></div>
          <div class="pr-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </template>
      <span class="pr-text">
        {{ pullRefreshing ? '青囊正在更新…' : (pullDistance > 80 ? '释放刷新' : '下拉刷新') }}
      </span>
    </div>
    <!-- 问候头部 -->
    <div class="home-header">
      <div>
        <h1 class="home-greeting">{{ greeting }}，{{ userStore.displayName }}</h1>
        <p class="home-date">{{ today }} · {{ weekday }} · {{ caseStatusLabel }}</p>
      </div>
      <div class="home-quick">
        <div class="quick-stat">
          <span class="qs-val">{{ vectorStore.driftSeries?.length || 0 }}</span>
          <span class="qs-label">次观测</span>
        </div>
        <div class="quick-stat">
          <span class="qs-val">{{ archivedDays }}</span>
          <span class="qs-label">天归档</span>
        </div>
      </div>
    </div>

    <!-- 🎖️ 数字模型成熟度进度卡（4 阶段节点 + 总进度 + next_target）
         2026-10-04 隐藏：成熟度是后台隐形设定，AI 用它引导用户完善采集，不需要给用户看
         如需恢复：把 v-if="false" 改成 v-if="maturity" -->
    <div v-if="false && maturity" :class="['maturity-card', `stage-${maturity.stage}`]">
      <!-- 4 阶段节点横向进度 -->
      <div class="mc-track">
        <div class="mc-line">
          <div class="mc-fill" :style="{ width: maturityPercent + '%' }"></div>
        </div>
        <div v-for="(node, idx) in STAGE_NODES" :key="idx"
             :class="['mc-node', { done: idx + 1 < maturity.stage, current: idx + 1 === maturity.stage, locked: idx + 1 > maturity.stage }]">
          <span class="mc-node-ico">{{ node.icon }}</span>
          <span class="mc-node-label">{{ node.name }}</span>
          <span v-if="idx + 1 === maturity.stage" class="mc-node-cur">当前</span>
        </div>
      </div>
      <!-- 分数 + 分项进度 -->
      <div class="mc-body">
        <div class="mc-score">
          <span class="mc-score-num">{{ maturity.score }}</span>
          <span class="mc-score-max">/ {{ maturity.max_score || 11 }}</span>
          <span class="mc-score-pct">({{ maturityPercent }}%)</span>
        </div>
        <!-- 分项进度条（数据源：后端 /maturity 端点返回的 progress 字段） -->
        <div class="mc-items">
          <div class="mc-item" :class="{ done: maturity.progress?.profile_complete >= 4 }">
            <span class="mc-item-lbl">基本资料</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: (maturity.progress?.profile_complete / 4 * 100) + '%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.profile_complete || 0 }}/4</span>
          </div>
          <div class="mc-item" :class="{ done: maturity.progress?.has_baseline }">
            <span class="mc-item-lbl">建档 + 基线</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: maturity.progress?.has_baseline ? '100%' : '0%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.has_baseline ? '✅' : '—' }}</span>
          </div>
          <div class="mc-item" :class="{ done: (maturity.progress?.observation_count || 0) >= 3 }">
            <span class="mc-item-lbl">脉搏采集</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: Math.min(100, (maturity.progress?.observation_count || 0) / 3 * 100) + '%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.observation_count || 0 }}/3</span>
          </div>
          <div class="mc-item" :class="{ done: maturity.progress?.inquiry_done }">
            <span class="mc-item-lbl">深度问诊</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: maturity.progress?.inquiry_done ? '100%' : '0%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.inquiry_done ? '✅' : '—' }}</span>
          </div>
          <div class="mc-item" :class="{ done: (maturity.progress?.signal_tag_count || 0) >= 3 }">
            <span class="mc-item-lbl">生活信号</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: Math.min(100, (maturity.progress?.signal_tag_count || 0) / 3 * 100) + '%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.signal_tag_count || 0 }}/3</span>
          </div>
        </div>
      </div>
      <!-- next_target 引导 -->
      <p v-if="maturity.next_target" class="mc-next">
        🎯 下一站：{{ maturity.next_target }}
      </p>
      <p v-if="maturity.missing_signals?.length" class="mc-missing">
        还差：{{ maturity.missing_signals.join(' · ') }}
      </p>
    </div>

    <!-- 注：问诊报告已迁移到「体质 → 报告时间线」统一展示，这里不再重复 -->

    <!-- ════ 英雄卡组：今日最重要的事 + 今日宜忌（独立两卡） ════ -->
    <div class="hero-row">
      <!-- 英雄卡 1：今日最重要的事 -->
      <div class="hero-card">
        <div class="hero-main">
          <p class="hero-tag">今日 · 时空锚点</p>
          <h2 class="hero-title">今日最重要的事</h2>
          <p class="hero-item"><span class="hero-dot"></span>{{ heroTodo?.title || '暂无待办 · 好好休息' }}</p>
          <p class="hero-sub">{{ anchorSafe.yi }} · 当前状态 {{ anchorSafe.state }}</p>
          <p class="hero-sub">忌 {{ anchorSafe.ji }} · 顺当日节律</p>
          <button class="hero-btn" @click="goPending">开始调理</button>
        </div>
      </div>

      <!-- 英雄卡 2：今日宜忌（独立卡） -->
      <div class="hero-yi-card">
        <div class="hero-yi-head">
          <div class="hero-yi-head-left">
            <p class="hero-tag">今日 · 宜忌速览</p>
            <h2 class="hero-title">今日宜忌</h2>
          </div>
          <!-- ⭐ 2026-10-05 新增：右上角天气 -->
          <div v-if="anchorSafe.weather" class="hero-weather">
            <span class="hw-icon" :class="'hw-' + anchorSafe.weather.icon">
              <span v-if="anchorSafe.weather.icon === 'sun'">☀️</span>
              <span v-else-if="anchorSafe.weather.icon === 'cloud'">⛅</span>
              <span v-else-if="anchorSafe.weather.icon === 'rain'">🌧️</span>
              <span v-else-if="anchorSafe.weather.icon === 'thunder'">⛈️</span>
              <span v-else-if="anchorSafe.weather.icon === 'snow'">🌨️</span>
              <span v-else-if="anchorSafe.weather.icon === 'fog'">🌫️</span>
              <span v-else>🌤️</span>
            </span>
            <div class="hw-info">
              <span class="hw-temp">{{ anchorSafe.weather.temp_high }}° / {{ anchorSafe.weather.temp_low }}°</span>
              <span class="hw-desc">{{ anchorSafe.weather.desc }} · {{ anchorSafe.weather.qihou }}</span>
            </div>
          </div>
        </div>
        <div class="yj-pair">
          <div class="yj-block yi">
            <span class="yj-ico good"><QIcon name="check" :size="13" /></span>
            <div class="yj-text">
              <span class="yj-k">宜</span>
              <span class="yj-v">{{ anchorSafe.yi }}</span>
            </div>
          </div>
          <div class="yj-block ji">
            <span class="yj-ico bad"><QIcon name="forbid" :size="13" /></span>
            <div class="yj-text">
              <span class="yj-k">忌</span>
              <span class="yj-v">{{ anchorSafe.ji }}</span>
            </div>
          </div>
        </div>
        <p class="hero-yi-more" @click="openReminders">展开全部宜忌 →</p>
      </div>
    </div>

    <!-- ════ 第二行：体质调理曲线 + 今日时空锚点（横屏并列） ════ -->
    <div class="top-row">
      <!-- 左：体质调理曲线（仅当前用户数据） -->
      <div class="card chart-card">
        <div class="card-head">
          <h2>体质曲线</h2>
          <div style="display:flex;gap:6px;align-items:center;">
            <span class="chip-dv">
              {{ driftTrajectory ? '综合健康得分' : ('ΔV ' + vectorStore.trendStateLabel) }}
            </span>
          </div>
        </div>
        <DriftChart
          v-if="driftTrajectory || driftSeries.length"
          :trajectory="driftTrajectory"
          :series="driftSeries"
          height="260px"
          class="curve-chart"
        />
        <p v-else class="placeholder curve-empty">暂无观测数据 · 完成一次数据采集后生成调理曲线</p>
      </div>

      <!-- 右：时空锚点（可点 → AI 大白话解读） -->
      <div class="card chart-card anchor-card clickable" @click="openAnchorExplain">
        <div class="card-head">
          <h2><QIcon name="anchor" :size="15" /> 今日时空锚点</h2>
          <span class="anchor-sub">{{ anchorSafe.ganzhi }} · <span class="ai-hint">点我 AI 解读</span></span>
        </div>
        <div class="anchor-grid">
          <div class="ag-cell">
            <span class="ag-label">当令时辰</span>
            <span class="ag-val">{{ anchorSafe.dangling }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">流飞星</span>
            <span class="ag-val">{{ anchorSafe.feixing }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">十二建除</span>
            <span class="ag-val">{{ anchorSafe.jianchu }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">冲煞</span>
            <span class="ag-val warn">{{ anchorSafe.chong }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">煞方</span>
            <span class="ag-val">{{ anchorSafe.shaxiang }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">值日星辰</span>
            <span class="ag-val">{{ anchorSafe.richuxing }}</span>
          </div>
        </div>

        <!-- 彭祖百忌 + 二十八宿 -->
        <div class="anchor-extras">
          <div class="ae-row" v-if="anchorSafe.pengzu">
            <span class="ae-label">彭祖百忌</span>
            <span class="ae-val">{{ anchorSafe.pengzu }}</span>
          </div>
          <div class="ae-row" v-if="anchorSafe.su">
            <span class="ae-label">二十八宿</span>
            <span class="ae-val">{{ anchorSafe.su }}宿</span>
          </div>
        </div>

        <!-- ⭐ 2026-10-05 新增：玉匣记摘录条 -->
        <div v-if="anchorSafe.yuxiaji" class="anchor-yuxiaji">
          <span class="yxj-quote">{{ anchorSafe.yuxiaji }}</span>
        </div>

        <!-- 时辰节律线：三段式 -->
        <div class="anchor-timeline">
          <div class="tl-seg" v-for="s in rhythmSegments" :key="s.range" :class="s.color">
            <span class="tl-bar"></span>
            <span class="tl-text">{{ s.range }} {{ s.label }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ════ 生活提醒：Stage 2+ 才显示（Stage 1 只有先天基底，无基线数据） ════ -->
    <div v-if="maturity?.stage >= 2" class="card reminders-mini">
      <button class="rem-collapse" @click="remExpanded = !remExpanded">
        <span class="rem-collapse-text">展开全部提醒与禁忌（{{ remTotal }} 条 · 含绝对禁忌与矿物避忌）</span>
        <span class="rem-chevron" :class="{ open: remExpanded }">›</span>
      </button>

      <div v-if="remExpanded" class="rem-body">
        <!-- 分段器 -->
        <div class="rem-head">
          <div class="rem-tabs">
            <button v-for="t in remTabs" :key="t.key" class="rem-tab"
                    :class="{ active: activeRem === t.key }" @click="activeRem = t.key">
              {{ t.label }}
            </button>
          </div>
        </div>

        <!-- 流式生成中：骨架屏 + 渐进 token 预览 -->
        <div v-if="lifestyleLoading" class="lifestyle-loading">
          <div class="lifestyle-loading-header">
            <span class="spinner"><QIcon name="spark" :size="16" /></span>
            <span>青檬引擎正在生成今日提醒…（约 15-20s）</span>
          </div>
          <pre v-if="lifestylePreview" class="lifestyle-preview">{{ lifestylePreview.slice(-500) }}</pre>
          <div v-else class="lifestyle-preview-placeholder">正在连接青檬引擎…</div>
        </div>

        <!-- 宜 -->
        <div v-if="!lifestyleLoading && activeRem === 'good'" class="rem-lists">
          <div class="rem-col">
            <h4 class="rem-col-title good"><QIcon name="check" :size="13" /> 今日宜（{{ clothGoodSelect.length + foodGoodSelect.length }}）</h4>
            <div v-for="r in [...clothGoodSelect, ...foodGoodSelect]" :key="r.id" class="rem-item rem-good">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }}</span>
            </div>
          </div>
          <div class="rem-col">
            <h4 class="rem-col-title bad"><QIcon name="warn" :size="13" /> 今日忌（{{ clothBadSelect.length + foodBadSelect.length }}）</h4>
            <div v-for="r in [...clothBadSelect, ...foodBadSelect]" :key="r.id" class="rem-item rem-bad">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }}</span>
            </div>
          </div>
        </div>
        <!-- 住 -->
        <div v-else-if="!lifestyleLoading && activeRem === 'home'" class="rem-lists">
          <div v-for="r in homeSelect" :key="r.id" class="rem-item" :class="{ 'rem-urgent': r.urgent }">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }}</span>
          </div>
        </div>
        <!-- 禁忌：绝对禁忌 / 矿物避忌默认收起 -->
        <div v-else-if="!lifestyleLoading" class="rem-fold-zone">
          <h4 class="rem-col-title warn"><QIcon name="warn" :size="13" /> 慎用（{{ relativeSelect.length }}）</h4>
          <div v-for="r in relativeSelect" :key="r.id" class="rem-item">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }} · {{ r.reason }}</span>
          </div>

          <details class="rem-fold">
            <summary class="rem-fold-summary danger"><QIcon name="forbid" :size="13" /> 绝对禁忌（{{ absoluteSelect.length }}）</summary>
            <div v-for="r in absoluteSelect" :key="r.id" class="rem-item rem-danger">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }} · {{ r.reason }}</span>
            </div>
          </details>

          <details class="rem-fold">
            <summary class="rem-fold-summary"><QIcon name="gem" :size="13" /> 矿物避忌（{{ stoneSelect.length }}）</summary>
            <div v-for="r in stoneSelect" :key="r.id" class="rem-item rem-stone">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }}</span>
            </div>
          </details>
        </div>
      </div>
    </div>

    <!-- ════ 第二行：待办卡片网格 ════ -->
    <template v-if="maturity?.stage >= 2">
    <div class="section-head">
      <h2 class="section-title"><QIcon name="doc" :size="15" /> 今日生活建议</h2>
      <div class="seg-control">
        <button v-for="t in segTabs" :key="t.key" class="seg-btn"
                :class="{ active: activeFilter === t.key }" @click="activeFilter = t.key">
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 待办卡片网格 -->
    <div v-if="activeFilter !== 'archived'" class="todo-grid">
      <TodoCard
        v-for="todo in filteredTodos"
        :key="todo.id"
        :todo="todo"
        :feedbacks="getFeedbacks(todo.id)"
        @open-detail="openDetailModal"
        @open-punch="openPunchModal"
      />
      <div v-if="!filteredTodos.length" class="todo-empty">
        没有匹配的待办
      </div>
    </div>

    <!-- 归档视图 -->
    <div v-else class="archive-view">
      <div class="archive-summary" v-if="archivedDays > 0">
        <p>共 <strong>{{ archivedDays }}</strong> 天归档 · <strong>{{ totalFeedbacks }}</strong> 条反馈 · 用作复诊诊断数据</p>
      </div>
      <div v-if="archives.length" class="archive-list">
        <details v-for="arc in archives" :key="arc.date" class="archive-day">
          <summary class="archive-day-head">
            <span class="archive-date">{{ arc.date }}</span>
            <span class="archive-todo-count">{{ arc.todos.length }} 项</span>
            <span class="archive-fb-count"><QIcon name="chat" :size="11" /> {{ arc.totalFeedbacks }} 条反馈</span>
          </summary>
          <div class="archive-day-body">
            <div v-for="t in arc.todos" :key="t.id" class="archive-todo">
              <span class="archive-todo-title">{{ t.title }}</span>
              <span class="archive-exec" :class="'exec-' + t.exec_status">{{ execLabel(t.exec_status) }}</span>
              <span v-if="t.feedbacks?.length" class="archive-fb">{{ t.feedbacks.length }}条反馈</span>
            </div>
          </div>
        </details>
      </div>
      <p v-else class="placeholder">暂无归档 · 完成今日待办后，每日自动归档</p>
    </div>
    </template>

    <!-- ════ 打卡弹窗（v-if/v-else 链之外，独立渲染） ════ -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="punchModal.todo" class="punch-modal-backdrop" @click.self="closePunchModal">
          <div class="punch-modal">
            <div class="pm-head">
              <div class="pm-title-wrap">
                <span class="pm-tag">{{ punchModal.isEdit ? '修改执行反馈' : '今日打卡' }}</span>
                <h3 class="pm-title">{{ punchModal.todo.title }}</h3>
                <p v-if="punchModal.todo.due" class="pm-due">🕐 {{ punchModal.todo.due }}</p>
              </div>
              <button class="pm-close" @click="closePunchModal" aria-label="关闭">✕</button>
            </div>

            <div class="pm-section">
              <label class="pm-label">执行状态</label>
              <div class="pm-exec-btns">
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'done' }"
                        @click="punchModal.execStatus = 'done'">已完成</button>
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'partial' }"
                        @click="punchModal.execStatus = 'partial'">部分执行</button>
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'skipped' }"
                        @click="punchModal.execStatus = 'skipped'">跳过</button>
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'failed' }"
                        @click="punchModal.execStatus = 'failed'">未执行</button>
              </div>
            </div>

            <div v-if="punchModal.feedbacks?.length" class="pm-section">
              <label class="pm-label">历史反馈（{{ punchModal.feedbacks.length }}）</label>
              <div v-for="(fb, i) in punchModal.feedbacks" :key="i" class="pm-fb-item">
                <span class="pm-fb-date">{{ fb.date }}</span>
                <span class="pm-fb-status" :class="'pm-fb-' + fb.status">{{ execLabel(fb.status) }}</span>
                <span v-if="fb.note" class="pm-fb-note">{{ fb.note }}</span>
              </div>
            </div>

            <div class="pm-section">
              <label class="pm-label">反馈（可选）</label>
              <textarea v-model="punchModal.note" placeholder="执行细节、感受或遇到的问题…" rows="3"></textarea>
            </div>

            <div class="pm-foot">
              <button class="pm-cancel" @click="closePunchModal">取消</button>
              <button class="pm-submit" @click="submitPunch" :disabled="punchModal.submitting">
                <span v-if="punchModal.submitting">提交中…</span>
                <span v-else>提交</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ════ 详情弹窗（替代手风琴展开） ════ -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="detailModal" class="punch-modal-backdrop" @click.self="closeDetailModal">
          <div class="punch-modal">
            <div class="pm-head">
              <div class="pm-title-wrap">
                <span class="pm-tag">今日建议</span>
                <h3 class="pm-title">{{ detailModal.title }}</h3>
                <p v-if="detailModal.remind" class="pm-desc">{{ detailModal.remind }}</p>
              </div>
              <button class="pm-close" @click="closeDetailModal" aria-label="关闭">✕</button>
            </div>

            <div v-if="dmDetail" class="pm-section">
              <label class="pm-label">📋 做法</label>
              <p class="pm-text">{{ dmDetail }}</p>
            </div>

            <div class="pm-section">
              <label class="pm-label">💡 推荐原因</label>
              <p class="pm-text">{{ dmReason }}</p>
            </div>

            <div v-if="detailModal.source_ref" class="pm-section">
              <label class="pm-label">📚 出处</label>
              <p class="pm-text source-text">{{ detailModal.source_ref }}</p>
            </div>

            <div class="pm-foot">
              <button class="pm-cancel" @click="closeDetailModal">关闭</button>
              <button class="pm-submit" @click="askDetailQA">💬 问问青囊管家</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ════ 第三行：体质趋势（雷达图，恢复） ════ -->
    <div class="card chart-card trend-card">
      <div class="card-head">
        <h2>体质趋势</h2>
        <span class="chip-dv">ΔV {{ vectorStore.trendStateLabel }}</span>
      </div>
      <div class="trend-body">
        <RadarChart v-if="vBase || latestObs" :v-base="vBase" :v-obs="latestObs" hide-legend height="220px" class="trend-radar" />
        <p v-else class="placeholder trend-radar">暂无数据</p>
        <div class="trend-side">
          <div class="legend-row"><span class="lg-swatch base"></span>先天基底</div>
          <div class="legend-row"><span class="lg-swatch obs"></span>当前观测</div>
          <p class="trend-delta">{{ deltaSummary }}</p>
          <button class="btn-ghost-sm" @click="goCase">查看档案</button>
        </div>
      </div>
    </div>

    <!-- ════ 第四行：漂移矢量一览 ════ -->
    <div class="card table-card">
      <h2>漂移矢量一览</h2>
      <table class="table">
        <thead><tr><th>维度</th><th>先天基底</th><th>最新观测</th><th>ΔV</th></tr></thead>
        <tbody>
          <tr v-for="row in deltaTable" :key="row.k">
            <td>{{ row.label }}</td>
            <td>{{ fmt(row.base) }}</td>
            <td>{{ fmt(row.obs) }}</td>
            <td :class="{ delta: true, up: row.delta > 0, down: row.delta < 0 }">{{ fmt(row.delta) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ════ AI 大白话解读 Modal ════ -->
    <div v-if="anchorModal.show" class="modal-backdrop" @click.self="anchorModal.show = false">
      <div class="modal-card anchor-explain-modal">
        <div class="modal-head">
          <h3>🌿 今日时空锚点 · 大白话解读</h3>
          <button class="modal-close" @click="anchorModal.show = false">✕</button>
        </div>
        <div class="modal-body">
          <!-- 加载中 -->
          <div v-if="anchorModal.loading" class="ae-loading">
            <div class="ae-spinner"></div>
            <p>青檬引擎正在翻译术语…</p>
            <p class="muted small">（先解读每个术语是什么意思，再结合你的体质给建议）</p>
          </div>
          <!-- 错误 -->
          <div v-else-if="anchorModal.error" class="ae-error">
            <p>抱歉，AI 解读暂时不可用</p>
            <p class="muted small">{{ anchorModal.error }}</p>
          </div>
          <!-- 结果：用 markdown-like 渲染 -->
          <div v-else class="ae-content">
            <!-- 引擎标记 -->
            <div class="ae-engine-tag" v-if="anchorModal.engine">
              {{ anchorModal.engine === 'qingmeng' ? '⚡ 青檬引擎生成' : anchorModal.engine === 'deepseek' ? '⚡ DeepSeek 生成' : '📖 本地术语词典' }}
            </div>
            <div class="ae-markdown" v-html="renderMarkdown(anchorModal.text)"></div>

            <!-- ⭐ 和管家继续聊 -->
            <div class="ae-footer">
              <div class="ae-footer-hint">想继续深入？把这段解读交给青囊管家，基于此展开对话</div>
              <button class="ae-chat-btn" @click="continueWithAssistant">
                <span class="ae-chat-icon">💬</span>
                <span>和青囊管家继续聊</span>
                <span class="ae-chat-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onActivated, ref, watch, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useVectorStore } from '../stores/vector'
import { useUserStore } from '../stores/user'
import * as storage from '../utils/storage'
import { healthCheck, api, assistant as assistantApi, notifications as notifApi, lifestyleStream } from '../api/client'
import RadarChart from '../components/charts/RadarChart.vue'
import DriftChart from '../components/charts/DriftChart.vue'
import TodoCard from '../components/TodoCard.vue'
import QIcon from '../components/ui/QIcon.vue'
// mock 数据已移除——所有内容从后端 API / reasoning 端点实时获取
// 后端不可达时为空占位，不展示任何其他用户的病历数据

const router = useRouter()

// ═══════════════════════════════════════════════════════════
// 生活提醒数据源（全部从后端拉取，无任何用户特定硬编码）
// 后端不可达时显示"加载中"占位，不展示他人病历内容
// ═══════════════════════════════════════════════════════════
const anchor = reactive({
  ganzhi: '', dangling: '', dangling_elem: '',
  feixing: '', chong: '',
  jianchu: '', pengzu: '', shaxiang: '', richuxing: '', su: '',
  yi: '', ji: '',
  state: '',
  yuxiaji: '',     // ⭐ 玉匣记摘录
  weather: null,
})
const todayTimeline = ref([])
const clothReminders = ref([])
const foodGood = ref([])
const foodBad = ref([])
const homeReminders = ref([])
const absoluteAvoid = ref([])
const relativeAvoid = ref([])
const stoneReminders = ref([])

// ── Lifestyle 流式状态 ──
const lifestyleLoading = ref(false)
const lifestylePreview = ref('')   // 渐进 token 预览文本

// ── 时空锚点 AI 解读 Modal ──
const anchorModal = reactive({
  show: false, loading: false, error: '', text: '', engine: '',
})

async function openAnchorExplain() {
  // 把当前 anchorSafe 整包发给后端
  const payload = Object.fromEntries(
    Object.entries(anchorSafe.value).filter(([k, v]) =>
      v && k !== 'state' && k !== 'weather'    // state 是 UI 字段；weather 另一个接口
    )
  )
  if (!payload.ganzhi && !payload.yi) {
    anchorModal.error = '今日时空锚点数据还在加载，请稍等'
    anchorModal.show = true
    return
  }

  anchorModal.show = true
  anchorModal.loading = true
  anchorModal.error = ''
  anchorModal.text = ''
  anchorModal.engine = ''

  try {
    const r = await fetch('/api/v1/assistant/reasoning/anchor-explain', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + storage.getToken(),
      },
      body: JSON.stringify(payload),
    })
    const data = await r.json()
    if (data.ok && data.explain) {
      anchorModal.text = data.explain
      anchorModal.engine = data.engine || ''
    } else {
      anchorModal.error = data.message || '返回数据异常'
    }
  } catch (e) {
    anchorModal.error = e.message || '网络请求失败'
  } finally {
    anchorModal.loading = false
  }
}

// 极简 markdown → HTML：支持 **粗体**、✅/⚠️/💡 emoji、--- 分隔线、换行
// 先 escape 所有 HTML 再做 markdown 替换 —— 防 XSS
function renderMarkdown(md) {
  if (!md) return ''
  const escape = (s) => s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
  let html = escape(md)
    .replace(/---/g, '<hr class="ae-hr">')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
  return `<p>${html}</p>`
}

// ⭐ 和青囊管家继续聊：直接调用 window.__qingnangAssistant（QingnangAssistant onMounted 挂载）
function continueWithAssistant() {
  const assistant = window.__qingnangAssistant
  if (!assistant?.openWithContext) {
    // 管家组件还没挂载 —— 提示用户
    anchorModal.error = '青囊管家还在初始化，请稍后再试'
    return
  }
  const payload = {
    anchor: Object.fromEntries(
      Object.entries(anchorSafe.value).filter(([k, v]) => v && k !== 'state' && k !== 'weather')
    ),
    explain: anchorModal.text,
    followup: '关于今天的时空锚点解读，我还有一些问题想深入聊聊 —— 比如哪些建议我可以马上开始做？',
  }
  // 关掉 anchor modal → 让管家抽屉接管
  anchorModal.show = false
  // 等一帧让 DOM 清理完，再调 openWithContext
  requestAnimationFrame(() => {
    assistant.openWithContext(payload)
  })
}

// Tab 选择（生活提醒 mini）
const activeRem = ref('good')
const remExpanded = ref(false)   // 折叠行：默认收起
const remTabs = [
  { key: 'good', label: '宜·忌' },
  { key: 'home', label: '住房' },
  { key: 'avoid', label: '禁忌' }
]
const remTotal = computed(() =>
  clothReminders.value.length + foodGood.value.length + foodBad.value.length +
  homeReminders.value.length + absoluteAvoid.value.length +
  relativeAvoid.value.length + stoneReminders.value.length
)

// ── 英雄卡：今日最重要的事（第一件未完成的 P0，否则第一条待办）──
const heroTodo = computed(() => {
  const p0 = todos.value.find(t => t.priority === 'p0' && !t.done)
  return p0 || todos.value.find(t => !t.done) || todos.value[0] || null
})
function goPending() {
  activeFilter.value = 'pending'
  document.querySelector('.section-head')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function goCase() {
  router.push({ name: 'case' })
}
function openReminders() {
  remExpanded.value = true
  nextTick(() => document.querySelector('.reminders-mini')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

// 精选筛选（压缩版：分类选 2 条 + 全部宜 3 条）
const clothGoodSelect = computed(() => clothReminders.value.filter(r => r.level === 'ok').slice(0, 2))
const clothBadSelect = computed(() => clothReminders.value.filter(r => r.level === 'bad').slice(0, 2))
const foodGoodSelect = computed(() => foodGood.value.slice(0, 2))
const foodBadSelect = computed(() => foodBad.value.slice(0, 2))
const homeSelect = computed(() => homeReminders.value)
const absoluteSelect = computed(() => absoluteAvoid.value)
const relativeSelect = computed(() => relativeAvoid.value)
const stoneSelect = computed(() => stoneReminders.value)

const vectorStore = useVectorStore()
const userStore = useUserStore()
const health = ref({ ok: false })

// 三曲线 trajectory：仅显示当前用户真实数据，无硬编码 fallback
const driftTrajectory = computed(() => {
  // 真实数据优先（vectorStore.fetchTrajectory 拉后端 /cases/trajectories）
  if (vectorStore.trajectory?.actual?.length > 0) return vectorStore.trajectory
  // 无观测数据 → null（降级到 ΔV 漂移线模式，展示当前用户 v_base vs 观测）
  return null
})

const vBase = computed(() => vectorStore.vBase)
const latestObs = computed(() => vectorStore.latestObs)
const driftSeries = computed(() => vectorStore.driftSeries)

// 🎖️ 四阶段节点定义（图标 + 短名），与后端 STAGE_DEFS 对齐
const STAGE_NODES = [
  { icon: '🌱', name: '娱乐级' },
  { icon: '🍲', name: '食疗级' },
  { icon: '🏠', name: '调理级' },
  { icon: '🌿', name: '方剂级' },
]

// maturity 数据源：优先 userStore 全局缓存，兜底 fetchMe 后拉
const maturity = computed(() => userStore.maturity)
const maturityPercent = computed(() => {
  if (!maturity.value) return 0
  const max = maturity.value.max_score || 11
  return Math.min(100, Math.round((maturity.value.score || 0) / max * 100))
})

// 注：问诊报告入口已迁移到「体质 → 报告时间线」，相关 fetch / goInquiryDetail 已删除

/** 根据已采集 PPG 观测数量动态判定用户所处阶段 */
const caseStatusLabel = computed(() => {
  const n = driftSeries.value?.length || 0
  if (n === 0) return '数据收集中'
  if (n < 3) return '基线建立中'
  if (n < 8) return '调理进行中'
  return '调理中 · 稳定观察'
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  if (h < 22) return '晚上好'
  return '夜深了'
})
const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`
})
const weekday = computed(() => ['周日','周一','周二','周三','周四','周五','周六'][new Date().getDay()])

// anchor 安全访问：后端不可达时显示中性占位，不展示他人病历内容
const anchorSafe = computed(() => ({
  yi: anchor.yi || '加载中...',
  ji: anchor.ji || '加载中...',
  state: anchor.state || '',
  ganzhi: anchor.ganzhi || '待生成',
  dangling: anchor.dangling || '',
  dangling_elem: anchor.dangling_elem || '',
  feixing: anchor.feixing || '',
  chong: anchor.chong || '',
  jianchu: anchor.jianchu || '',
  pengzu: anchor.pengzu || '',
  shaxiang: anchor.shaxiang || '',
  richuxing: anchor.richuxing || '',
  su: anchor.su || '',
  yuxiaji: anchor.yuxiaji || '',
  weather: anchor.weather || null,
}))

const deltaTable = computed(() => {
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const delta = vectorStore.deltaV || {}
  return ['wood','fire','earth','metal','water'].map(k => ({
    k, label: labels[k],
    base: vBase.value?.[k],
    obs: latestObs.value?.values?.[k],
    delta: delta[k]
  }))
})
const fmt = (v) => v == null ? '—' : Number(v).toFixed(1)

// ═══════════════════════════════════════════════════════════
// 待办系统：种子数据 + 每日更新 + 归档
// ═══════════════════════════════════════════════════════════

const activeFilter = ref('pending')  // 默认落在「待处理」，对齐设计稿

// 🎯 详情弹窗（替代手风琴展开）
const detailModal = ref(null)
function openDetailModal(todo) { detailModal.value = todo }
function closeDetailModal() { detailModal.value = null }

function buildTodayTodos() {
  // 空列表——待办由后端 /cases/today-todos 动态聚合
  // （1）notifications 生活提醒 （2）AI 对话的 analysis.suggestions
  return []
}

// 后端 priority → TodoCard priority 映射
function mapPriority(p) {
  return ({ high: 'p0', medium: 'p1', low: 'p2' })[p] || 'p1'
}

// 后端 todos → TodoCard 格式
function mapBackendTodo(t) {
  // 🎯 source_ref 只显示真正的经典出处（如《本草纲目》）
  // 不再把 "ai·diet" / "lifestyle" 这种来源标识当成出处
  const isLifestyle = t.source_type === 'lifestyle'
  const rawSource = t.source || ''
  const looksLikeSourceTag = rawSource.startsWith('ai·') || rawSource === 'lifestyle' || rawSource.startsWith('ai')
  const source_ref = t.source_ref || (isLifestyle && !looksLikeSourceTag ? rawSource : '')

  // 🎯 双保险：保证每个 todo 有唯一 id
  // 服务器旧版可能用 category（"diet"/"ai"）当 id → 全部重复
  // 用 source_type + source + title hash 出唯一 key
  const rawId = t.id || ''
  const needsFix = !rawId || /^[a-z]+$/.test(rawId)  // 只有单词（diet/ai）→ 太泛
  const uniqueId = needsFix
    ? `${t.source_type || 'x'}|${rawSource || ''}|${t.title || ''}`
    : rawId

  return {
    id: uniqueId,
    title: t.title,
    remind: t.desc || '',
    priority: mapPriority(t.priority),
    done: false,
    source: t.source_type || '',   // 纯来源标识，不显示给用户
    route: t.route,
    icon: t.icon,
    // LLM 详情字段：点击展开时显示
    detail: t.detail || '',
    reason: t.reason || '',
    source_ref,  // 经典出处（如《本草纲目》），空就不显示
  }
}

function getTodayKey() {
  return new Date().toISOString().slice(0, 10) // YYYY-MM-DD
}

function loadToday() {
  try {
    const data = storage.get('qingnang_today', null)
    if (data) {
      // 如果存的不是今天的日期，先归档昨天的再新建
      if (data.date !== getTodayKey()) {
        archiveYesterday(data)
        return buildTodayTodos()
      }
      return data.todos
    }
  } catch {}
  return buildTodayTodos()
}

function archiveYesterday(yesterdayData) {
  try {
    const archive = storage.get('qingnang_archive', [])
    archive.unshift({
      date: yesterdayData.date,
      todos: yesterdayData.todos.map(t => ({
        id: t.id,
        title: t.title,
        exec_status: t.exec_status || null,
        feedbacks: getFeedbacks(t.id)
      })),
      totalFeedbacks: yesterdayData.todos.reduce((s, t) => s + (getFeedbacks(t.id).length), 0)
    })
    // 最多保留 90 天
    storage.set('qingnang_archive', archive.slice(0, 90))
  } catch {}
}

function saveToday() {
  try {
    storage.set('qingnang_today', {
      date: getTodayKey(),
      todos: todos.value
    })
  } catch {}
}

// 反馈存储：{ [todoId]: [{status, note, date}] }
function loadFeedbacks() {
  return storage.get('qingnang_feedbacks', {}) || {}
}
function saveFeedbacks() {
  try { storage.set('qingnang_feedbacks', feedbacks.value) } catch {}
}

const feedbacks = ref(loadFeedbacks())
function getFeedbacks(todoId) { return feedbacks.value[todoId] || [] }

const todos = ref(loadToday())
watch(todos, saveToday, { deep: true })

function toggleTodo(id) {
  const t = todos.value.find(x => x.id === id)
  if (t) { t.done = !t.done }
}

function handleFeedback(fb) {
  if (!feedbacks.value[fb.todo_id]) feedbacks.value[fb.todo_id] = []
  feedbacks.value[fb.todo_id].push(fb)
  saveFeedbacks()
}

/* ──────────────────────────────────────
   打卡弹窗状态 & 方法
   ────────────────────────────────────── */
const punchModal = reactive({
  todo: null,           // 当前待打卡的 todo 对象
  feedbacks: [],        // 该 todo 的历史反馈
  isEdit: false,        // 是否是修改已完成的打卡
  execStatus: 'done',
  note: '',
  submitting: false,
})

function openPunchModal(todo) {
  punchModal.todo = todo
  punchModal.feedbacks = getFeedbacks(todo.id)
  punchModal.isEdit = !!todo.done
  // 默认选中：新打卡→已完成；修改→上次反馈的 status
  if (punchModal.isEdit && punchModal.feedbacks.length) {
    punchModal.execStatus = punchModal.feedbacks[punchModal.feedbacks.length - 1].status || 'done'
  } else {
    punchModal.execStatus = 'done'
  }
  punchModal.note = ''
  punchModal.submitting = false
  // 禁止 body 滚动
  document.body.style.overflow = 'hidden'
}

function closePunchModal() {
  punchModal.todo = null
  punchModal.note = ''
  punchModal.execStatus = 'done'
  document.body.style.overflow = ''
}

function submitPunch() {
  punchModal.submitting = true
  const fb = {
    status: punchModal.execStatus || 'done',
    note: punchModal.note.trim(),
    date: new Date().toISOString().slice(0, 16).replace('T', ' '),
    todo_id: punchModal.todo.id
  }
  // 1) 保存反馈
  handleFeedback(fb)
  // 2) 标记完成（如果还没完成）
  if (!punchModal.todo.done) {
    toggleTodo(punchModal.todo.id)
  }
  punchModal.submitting = false
  closePunchModal()
}

const filteredTodos = computed(() => {
  const t = todos.value
  if (activeFilter.value === 'pending') return t.filter(x => !x.done)
  return t
})

// 🎯 详情弹窗内容：去重 + 兜底推荐原因
const dmDetail = computed(() => {
  const t = detailModal.value
  if (!t?.detail) return ''
  return t.detail.trim() === (t.remind || '').trim() ? '' : t.detail
})
const dmReason = computed(() => {
  const t = detailModal.value
  if (!t) return ''
  if (t.reason) return t.reason
  const catMap = {
    diet: '饮食', exercise: '运动', sleep: '睡眠',
    cloth: '穿衣', home: '住家', avoid: '避忌',
    herb: '方药', lifestyle: '生活方式', ai: 'AI 建议',
  }
  const catName = catMap[t.source_type] || t.source_type || '生活方式'
  return `青囊根据你的当前体质和今日节律，在${catName}方面推荐你「${t.title}」。`
})

// 问问青囊
function askDetailQA() {
  const t = detailModal.value
  if (!t) return
  const parts = [`【${t.title}】`]
  if (t.remind) parts.push(`提醒：${t.remind}`)
  if (dmDetail.value) parts.push(`做法：${dmDetail.value}`)
  parts.push(`推荐原因：${dmReason.value}`)
  if (t.source_ref) parts.push(`出处：${t.source_ref}`)

  const assistant = window.__qingnangAssistant
  if (!assistant?.openWithContext) {
    alert('青囊管家还在初始化，请稍后再试')
    return
  }
  assistant.openWithContext({
    anchor: { topic: '今日待办', title: t.title },
    explain: parts.join('\n\n'),
    followup: `关于「${t.title}」，我想深入聊聊 —— 比如这个建议适合我现在的体质吗？`,
  })
}

// 分段器：待处理 / 全部 / 归档（设计稿三段式）
const segTabs = computed(() => [
  { key: 'pending', label: `待处理 ${pendingCount.value}` },
  { key: 'all', label: `全部 ${todos.value.length}` },
  { key: 'archived', label: `归档 ${archivedDays.value} 天` }
])

const pendingCount = computed(() => todos.value.filter(x => !x.done).length)

// ── 体质趋势卡：ΔV 摘要（图例旁一行小字）──
const deltaSummary = computed(() => {
  const rows = deltaTable.value.filter(r => r.delta != null)
  if (!rows.length) return '暂无漂移数据'
  const parts = rows
    .filter(r => Math.abs(r.delta) >= 0.5)
    .map(r => `${r.label} ${r.delta > 0 ? '▲' : '▼'} ${Math.abs(r.delta).toFixed(0)}`)
  return parts.length ? parts.join(' · ') + ' · 余稳定' : '五行 ΔV 均稳定'
})

// ── 时空锚点：今日避忌一行字（只保留一条）──
const avoidText = computed(() => {
  const chong = String(anchor.chong || '').replace(/（.*$/, '')
  if (!chong) return '待生成'
  return `冲${chong} · 忌远行`
})

// ── 时辰节律线：三段式（平稳 / 宜动 / 宜静）──
const rhythmSegments = computed(() => {
  const tl = todayTimeline.value || []
  const desc = (names) => tl
    .filter(t => names.some(n => String(t.range || '').includes(n)))
    .map(t => t.desc).filter(Boolean).slice(0, 2).join(' · ')
  return [
    { range: '05-11 卯·辰', label: '平稳', color: 'calm', desc: desc(['卯', '辰']) || '温盐水 · 小米粥' },
    { range: '17-21 酉·戌', label: '宜动', color: 'active', desc: desc(['酉', '戌']) || '减工作 · 泡脚' },
    { range: '21-01 亥·子', label: '宜静', color: 'rest', desc: desc(['亥', '子']) || '放下手机 · 必睡' }
  ]
})

function execLabel(s) {
  return ({ done: '已完成', partial: '部分执行', skipped: '跳过', failed: '未执行' })[s] || '待执行'
}

// 归档数据
const archives = computed(() => storage.get('qingnang_archive', []) || [])
const archivedDays = computed(() => archives.value.length)
const totalFeedbacks = computed(() => archives.value.reduce((s, a) => s + a.totalFeedbacks, 0))

// ── 统一清理：防止重新建档/切换账号后旧 ref 残留 ──
function _resetAllLocalState() {
  Object.assign(anchor, { ganzhi:'', dangling:'', dangling_elem:'', feixing:'', chong:'', jianchu:'', pengzu:'', shaxiang:'', richuxing:'', su:'', yi:'', ji:'', state:'', yuxiaji:'', weather: null })
  todayTimeline.value = []
  clothReminders.value = []
  foodGood.value = []
  foodBad.value = []
  homeReminders.value = []
  absoluteAvoid.value = []
  relativeAvoid.value = []
  stoneReminders.value = []
  lifestyleLoading.value = false
  lifestylePreview.value = ''
}

onMounted(async () => {
  _resetAllLocalState()   // 首次进 Dashboard，清旧状态
  await _onBoard()
})

// SPA keep-alive 时路由回来：内存数据完好，不重跑 LLM！
// 只有真正需要刷新（用户点了"刷新"按钮或 vBase 变了）才触发 _invalidateAndReload
onActivated(async () => {
  // 不调 _resetAllLocalState，不清缓存，不重跑 LLM
  // 只做最轻量的：确认 token 还在（登出后 SPA 路由回来需要重定向）
  if (!userStore.loggedIn) {
    router.replace('/login')
  }
})

// ── 主动失效 + 重新生成（给"刷新"按钮 / vBase 变化时调）──
function _invalidateAndReload() {
  storage.remove(_lifestyleCacheKey())
  _resetAllLocalState()
  return _onBoard()
}

// ═══════════════════════════════════════════════════════════
// 📱 移动端下拉刷新（纯手写 Touch 事件，零依赖）
// ═══════════════════════════════════════════════════════════
const PULL_THRESHOLD = 80       // 释放触发刷新的阈值（px）
const PULL_MAX = 140            // 下拉最大高度
const PULL_BACK_DAMPING = 0.5   // 回弹阻尼系数

const pullDistance = ref(0)
const pullRefreshing = ref(false)
let _pullStartY = 0
let _pullActive = false

function onPullStart(e) {
  if (pullRefreshing.value) return
  // 只有滚动条在最顶端才激活下拉
  if ((window.scrollY || document.documentElement.scrollTop) > 0) return
  _pullStartY = e.touches[0].clientY
  _pullActive = true
}

function onPullMove(e) {
  if (!_pullActive || pullRefreshing.value) return
  const dy = e.touches[0].clientY - _pullStartY
  if (dy > 0) {
    // 带阻尼的下拉：越往下越难拉
    const damped = Math.min(PULL_MAX, dy * PULL_BACK_DAMPING)
    pullDistance.value = damped
    // 阻止浏览器橡皮筋/滚动
    if (e.cancelable) e.preventDefault()
  } else {
    pullDistance.value = 0
  }
}

async function onPullEnd() {
  if (!_pullActive) return
  _pullActive = false

  if (pullDistance.value >= PULL_THRESHOLD && !pullRefreshing.value) {
    // 🎯 触发刷新
    pullRefreshing.value = true
    pullDistance.value = 60   // 固定在刷新指示器高度
    try {
      await _invalidateAndReload()
    } finally {
      pullRefreshing.value = false
      pullDistance.value = 0
    }
  } else {
    // 未达阈值 → 回弹
    pullDistance.value = 0
  }
}

// ── 缓存键：按天（同一天干支一样，LLM 结果可复用）──
function _lifestyleCacheKey() {
  const d = new Date()
  const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
  return `lifestyle:v1:${key}`
}

async function _onBoard() {
  // 进主页先拉一遍最新用户信息（nickname 可能在 onboarding 刚更新）
  try { await userStore.fetchMe() } catch {}
  // 🎖️ 成熟度兜底拉取（页面刷新后 store 可能丢失）
  if (userStore.loggedIn && !userStore.maturity) {
    try { await userStore.fetchMaturity() } catch {}
  }
  // 注：问诊报告已迁移到「体质 → 报告时间线」
  health.value = await healthCheck()
  await vectorStore.fetchCase()

  // ── 从后端聚合今日待办（聊天 suggestions + 生活提醒）──
  try {
    const r = await api.get('/api/v1/cases/today-todos')
    const todosFromBackend = (r.data?.todos || []).map(mapBackendTodo)
    // ⚠️ 2026-10-05 修复：无条件覆盖 todos，不要用 length > 0 判断
    // 否则 reset 后后端返回空时，localStorage 残留的旧 todos 不会被清掉
    todos.value = todosFromBackend
    saveToday()
    console.log(`[Dashboard] ✅ 今日待办来自后端聚合：${todosFromBackend.length} 条`)
    // 也存一下 chief_complaint 方便青囊聊天读
    if (r.data?.chief_complaint) {
      storage.set('qingnang_chief_complaint', r.data.chief_complaint)
    }
  } catch (e) {
    console.warn('[Dashboard] 今日待办后端不可达，使用本地缓存', e)
  }

  // Stage 1 跳过生活提醒（后端也会跳过，但前端也不调，省一次请求）
  if (maturity.value?.stage < 2) {
    console.log('[Dashboard] Stage 1 → 跳过生活提醒生成')
  } else {
  // ── 缓存优先：同一天干支一样，LLM 结果可复用 ──
  const _cacheKey = _lifestyleCacheKey()
  const _cached = storage.get(_cacheKey)
  if (_cached && _cached.anchor) {
    _applyLifestyleResult(_cached)
    console.log(`[Dashboard] ✅ 生活提醒命中缓存（key=${_cacheKey}）`)
  } else {
  // 缓存未命中 → 调 LLM
  const _settings = storage.get('qingnang_settings', {}) || {}
  const _lsPayload = {
    city: _settings.city || null,
    provider: _settings.llm_provider || undefined,  // 不传 → 后端默认 auto(=deepseek)
  }
  lifestyleLoading.value = true
  lifestylePreview.value = ''
  lifestyleStream(_lsPayload, {
    onGenerating: (token) => {
      lifestylePreview.value += token
    },
    onComplete: (d) => {
      lifestyleLoading.value = false
      lifestylePreview.value = ''
      if (d?.anchor) {
        _applyLifestyleResult(d)
        storage.set(_cacheKey, d)  // ⭐ 写缓存
        console.log(`[Dashboard] ✅ 生活提醒来自青檬引擎（engine=${d.engine || 'unknown'}，已缓存）`)
      }
    },
    onNote: (text) => {
      console.log('[lifestyle note]', text)
    },
    onError: (err) => {
      lifestyleLoading.value = false
      lifestylePreview.value = ''
      console.warn('[Dashboard] ❌ 流式生活提醒失败，尝试非流式 fallback', err)
      assistantApi.lifestyle(_lsPayload).then((r) => {
        const d = r.data || {}
        if (d.anchor) {
          _applyLifestyleResult(d)
          storage.set(_cacheKey, d)
        }
      }).catch(() => {
        notifApi.today().then((r) => {
          if (r.data?.anchor) Object.assign(anchor, r.data.anchor)
        }).catch(() => { /* 页面里已有的常量会兜底 */ })
      })
    },
  })
  } // 缓存命中/未命中
  } // stage >= 2
}

// ── lifestyle 结果填充（缓存命中 / onComplete / fallback 共用）──
function _applyLifestyleResult(d) {
  if (d.anchor) Object.assign(anchor, d.anchor)
  if (d.timeline) todayTimeline.value = d.timeline
  if (d.cloth_reminders) clothReminders.value = d.cloth_reminders
  if (d.food_good) foodGood.value = d.food_good
  if (d.food_bad) foodBad.value = d.food_bad
  if (d.home_reminders) homeReminders.value = d.home_reminders
  if (d.absolute_avoid) absoluteAvoid.value = d.absolute_avoid
  if (d.relative_avoid) relativeAvoid.value = d.relative_avoid
}
</script>

<style scoped>
/* max-width 由全局 .page 统一管理（1200px） */

/* ═══════════════════════════════════════════════════════════
   📱 下拉刷新指示器 — 青囊主题
   ═══════════════════════════════════════════════════════════ */
.pull-refresh {
  position: relative;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 10px;
  overflow: hidden;
  transition: height 0.25s cubic-bezier(0.34, 1.56, 0.64, 1),
              opacity 0.2s ease;
  pointer-events: none;
  z-index: 10;
}
.pr-arrow {
  font-size: 22px;
  color: var(--qn-emerald);
  line-height: 1;
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.pr-arrow.spin {
  transform: rotate(180deg);
}

/* ── 青囊主题加载器（刷新中）── */
.pr-loader {
  position: relative;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 外环：青色顺时针旋转 */
.pr-ring {
  position: absolute;
  border-radius: 50%;
  border-style: solid;
}
.pr-ring-outer {
  width: 44px; height: 44px;
  border-width: 2.5px;
  border-color: rgba(var(--qn-emerald-rgb), 0.15);
  border-top-color: var(--qn-emerald);
  animation: pr-rotate 1.2s linear infinite;
}
/* 内环：深色逆时针旋转 + 脉冲 */
.pr-ring-inner {
  width: 26px; height: 26px;
  border-width: 2px;
  border-color: transparent;
  border-top-color: var(--qn-emerald-dark);
  border-right-color: rgba(var(--qn-emerald-rgb), 0.5);
  animation: pr-rotate-rev 0.9s linear infinite, pr-pulse 1.8s ease-in-out infinite;
}
@keyframes pr-rotate {
  to { transform: rotate(360deg); }
}
@keyframes pr-rotate-rev {
  to { transform: rotate(-360deg); }
}
@keyframes pr-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 三个脉冲点（青囊精神象征） */
.pr-dots {
  position: absolute;
  display: flex;
  gap: 3px;
}
.pr-dots span {
  width: 4px; height: 4px;
  background: var(--qn-emerald);
  border-radius: 50%;
  animation: pr-dot-bounce 1.4s ease-in-out infinite;
}
.pr-dots span:nth-child(2) { animation-delay: 0.15s; background: var(--qn-emerald-dark); }
.pr-dots span:nth-child(3) { animation-delay: 0.3s; background: rgba(var(--qn-emerald-rgb), 0.7); }
@keyframes pr-dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.6; }
  40% { transform: translateY(-5px); opacity: 1; }
}

.pr-text {
  font-size: 12px;
  color: var(--qn-ink-3);
  letter-spacing: 1px;
  font-weight: 500;
}

/* ── 问候头部 ── */
.home-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; }
.home-greeting { font-size: calc(24px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0; }
.home-date { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: 4px; }
/* 统计：右对齐弱化，纯文本堆叠（去白盒） */
.home-quick { display: flex; gap: 32px; padding-bottom: 4px; }
.quick-stat { display: flex; flex-direction: column; gap: 2px; text-align: left; }
.qs-val { font-size: calc(22px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); font-family: var(--font-mono); line-height: 1.1; }
.qs-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* ═══════════════════════════════════════════════════════════
   🎖️ 数字模型成熟度进度卡
   ═══════════════════════════════════════════════════════════ */
.maturity-card {
  background: var(--qn-surface);
  border: 1px solid rgba(var(--qn-emerald-rgb),0.12);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
  margin-bottom: 16px;
  position: relative; overflow: hidden;
}
.maturity-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent));
  opacity: 0.6;
}
/* 不同阶段主题色 */
.maturity-card.stage-1::before { background: linear-gradient(90deg, #8B7355, #D4A574); }
.maturity-card.stage-2::before { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent)); }
.maturity-card.stage-3::before { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent), #6BE8C9); }
.maturity-card.stage-4::before { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent), #6BE8C9, #FFD700); }

/* —— 4 阶段节点轨道 —— */
.mc-track { position: relative; padding: 12px 0 8px; margin-bottom: 14px; }
.mc-line {
  position: absolute; top: 28px; left: 24px; right: 24px;
  height: 3px; background: rgba(var(--qn-emerald-rgb),0.1); border-radius: 2px;
}
.mc-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent));
  transition: width 0.6s ease;
}
.mc-node {
  position: relative; z-index: 2;
  display: inline-flex; flex-direction: column; align-items: center; gap: 4px;
  width: 25%;
}
.mc-node-ico {
  width: 42px; height: 42px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: calc(20px * var(--qn-fs-scale));
  background: #f5f7f6; border: 2px solid rgba(var(--qn-emerald-rgb),0.15);
  transition: all 0.3s;
}
.mc-node.done .mc-node-ico {
  background: var(--qn-emerald); border-color: var(--qn-emerald);
  box-shadow: 0 0 0 4px rgba(var(--qn-emerald-accent-rgb),0.2);
}
.mc-node.current .mc-node-ico {
  background: var(--qn-surface); border-color: var(--qn-emerald);
  box-shadow: 0 0 0 5px rgba(var(--qn-emerald-accent-rgb),0.3);
  animation: pulse-ring 2s infinite;
}
.mc-node.locked .mc-node-ico {
  background: #f0f0f0; border-color: #d0d0d0; opacity: 0.5;
}
@keyframes pulse-ring {
  0%, 100% { box-shadow: 0 0 0 4px rgba(var(--qn-emerald-accent-rgb),0.3); }
  50% { box-shadow: 0 0 0 8px rgba(var(--qn-emerald-accent-rgb),0.15); }
}
.mc-node-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.mc-node.done .mc-node-label { color: var(--qn-emerald); font-weight: 600; }
.mc-node.current .mc-node-label { color: var(--qn-emerald-dark); font-weight: 700; }
.mc-node.locked .mc-node-label { color: #aaa; }
.mc-node-cur {
  position: absolute; top: -4px;
  font-size: calc(9px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 8px;
  background: var(--qn-emerald); color: #fff;
  letter-spacing: 0.5px;
}

/* —— 主体：分数 + 分项进度 —— */
.mc-body { display: flex; gap: 24px; align-items: flex-start; }
.mc-score {
  flex-shrink: 0; padding: 8px 16px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.08), rgba(var(--qn-emerald-accent-rgb),0.15));
  border-radius: var(--qn-r-lg); text-align: center;
  border: 1px solid rgba(var(--qn-emerald-rgb),0.12);
}
.mc-score-num { font-size: calc(28px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-emerald-dark); }
.mc-score-max { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.mc-score-pct { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-left: 2px; }
.mc-items { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.mc-item {
  display: grid; grid-template-columns: 72px 1fr 48px; gap: 8px;
  align-items: center; font-size: calc(12px * var(--qn-fs-scale));
}
.mc-item-lbl { color: var(--qn-ink-2); }
.mc-item.done .mc-item-lbl { color: var(--qn-emerald); font-weight: 600; }
.mc-item-bar {
  height: 6px; background: #eef1f0; border-radius: 3px; overflow: hidden;
}
.mc-item-fill {
  height: 100%; border-radius: 3px;
  background: linear-gradient(90deg, var(--qn-emerald), var(--qingnang-spirit));
  transition: width 0.5s ease;
}
.mc-item.done .mc-item-fill { background: var(--qn-emerald); }
.mc-item-val { text-align: right; color: var(--qn-ink-3); font-variant-numeric: tabular-nums; }
.mc-item.done .mc-item-val { color: var(--qn-emerald); font-weight: 600; }

/* —— next_target / missing_signals —— */
.mc-next { margin: 12px 0 4px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-emerald-dark); font-weight: 500; }
.mc-missing { margin: 0; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* ════ 注：问诊报告入口 CSS 已删除（迁移到体质页） ════ */

/* —— 移动端适配 —— 归并到 480px 档位（原 640px） */
@media (max-width: 480px) {
  .maturity-card { padding: 14px 14px; }
  .mc-node { width: 24%; }
  .mc-node-ico { width: 34px; height: 34px; font-size: calc(16px * var(--qn-fs-scale)); }
  .mc-line { left: 18px; right: 18px; top: 23px; }
  .mc-node-label { font-size: calc(10px * var(--qn-fs-scale)); }
  .mc-body { flex-direction: column; gap: 14px; }
  .mc-score { padding: 6px 12px; align-self: flex-start; }
  .mc-item { grid-template-columns: 60px 1fr 36px; font-size: calc(11px * var(--qn-fs-scale)); }
}

/* ── 英雄卡组（桌面并排 / 竖屏上下堆叠） ── */
.hero-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px; }

/* 英雄卡 1：今日最重要的事 */
.hero-card {
  border-radius: var(--radius-lg); padding: 26px 28px;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-dark) 100%);
  box-shadow: 0 8px 24px rgba(9, 40, 36, 0.25);
  color: var(--qn-paper);
}
.hero-main { display: flex; flex-direction: column; gap: 8px; }
.hero-tag { font-size: calc(12px * var(--qn-fs-scale)); letter-spacing: 3px; color: rgba(242,239,231,0.65); margin: 0; }
.hero-title { font-size: calc(21px * var(--qn-fs-scale)); font-weight: 600; margin: 0; letter-spacing: 1px; }
.hero-item { display: flex; align-items: center; gap: 10px; font-size: calc(16px * var(--qn-fs-scale)); font-weight: 500; margin: 4px 0 0; }
.hero-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--qingnang-spirit); flex-shrink: 0; }
.hero-sub { font-size: calc(13px * var(--qn-fs-scale)); color: rgba(242,239,231,0.72); margin: 0; }
.hero-btn {
  margin-top: 10px; align-self: flex-start;
  padding: 9px 26px; border: none; border-radius: var(--qn-r-pill);
  background: var(--qn-paper); color: var(--qn-emerald);
  font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600; letter-spacing: 2px; cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.hero-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }

/* 英雄卡 2：今日宜忌（独立卡，同色系略浅） */
.hero-yi-card {
  border-radius: var(--radius-lg); padding: 22px 24px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.88) 0%, rgba(38,105,92,0.88) 100%);
  color: #fff;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 6px 20px rgba(9, 40, 36, 0.2);
}
.hero-yi-card .hero-title { font-size: calc(17px * var(--qn-fs-scale)); margin-bottom: 14px; }

/* ══ 2026-10-05：天气头部 + 右上角天气 ══ */
.hero-yi-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.hero-yi-head-left { display: flex; flex-direction: column; gap: 2px; }
.hero-weather {
  display: flex; align-items: center; gap: 10px;
  background: rgba(242,239,231,0.1);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px;
  padding: 8px 14px;
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.hw-icon { font-size: 24px; line-height: 1; }
.hw-info { display: flex; flex-direction: column; gap: 1px; }
.hw-temp { font-size: calc(15px * var(--qn-fs-scale)); font-weight: 600; color: #fff; letter-spacing: 0.5px; }
.hw-desc { font-size: calc(11px * var(--qn-fs-scale)); color: rgba(255,255,255,0.7); letter-spacing: 0.5px; }
.yj-pair { display: flex; flex-direction: column; gap: 10px; }
.yj-block {
  display: flex; align-items: center; gap: 12px;
  background: rgba(242,239,231,0.08); border-radius: 10px; padding: 12px 14px;
}
.yj-ico {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.yj-ico.good { background: rgba(123,196,169,0.25); color: #7BC4A9; }
.yj-ico.bad { background: rgba(208,138,110,0.25); color: #D08A6E; }
.yj-text { display: flex; flex-direction: column; gap: 2px; }
.yj-k { font-size: calc(11px * var(--qn-fs-scale)); letter-spacing: 2px; font-weight: 600; }
.yj-block.yi .yj-k { color: #7BC4A9; }
.yj-block.ji .yj-k { color: #D08A6E; }
.yj-v { font-size: calc(14px * var(--qn-fs-scale)); color: rgba(242,239,231,0.92); font-weight: 500; }
.hero-yi-more {
  margin: 14px 0 0; font-size: calc(12px * var(--qn-fs-scale)); color: rgba(242,239,231,0.55); cursor: pointer;
  letter-spacing: 1px; text-align: right;
}
.hero-yi-more:hover { color: rgba(242,239,231,0.85); }

/* ── 卡头（体质调理曲线 / 时空锚点共用）── */
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--qn-line); }
.card-head h2 { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; border: none; }
.chip-dv { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-emerald); background: rgba(var(--qn-emerald-rgb),0.08); border-radius: 12px; padding: 3px 10px; }
.anchor-sub { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-weight: 400; }
.anchor-card .anchor-grid { grid-template-columns: repeat(3, 1fr); }

/* 时空锚点可点击 + AI hint */
.anchor-card.clickable { cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.anchor-card.clickable:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
.anchor-card.clickable:active { transform: translateY(0); }
.ai-hint {
  display: inline-block; margin-left: 6px; padding: 2px 8px; border-radius: 10px;
  background: rgba(var(--qn-emerald-rgb),0.1); color: var(--qn-emerald);
  font-size: calc(11px * var(--qn-fs-scale)); font-weight: 500;
}

/* ════ Modal（AI 大白话解读） ════ */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(26,43,26,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 200;
  padding: 20px; animation: fadeIn 0.18s ease;
}
@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
.modal-card {
  background: var(--qn-surface); border-radius: var(--radius-lg);
  max-width: 560px; width: 100%; max-height: 80vh;
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 16px 48px rgba(0,0,0,0.18);
  animation: slideUp 0.22s ease;
}
@keyframes slideUp { from { transform: translateY(20px); opacity: 0 } to { transform: translateY(0); opacity: 1 } }
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px; border-bottom: 1px solid var(--qn-line);
}
.modal-head h3 { font-size: calc(16px * var(--qn-fs-scale)); margin: 0; color: var(--qn-ink); font-weight: 600; }
.modal-close {
  width: 32px; height: 32px; border: none; background: transparent;
  font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-ink-3); cursor: pointer;
  border-radius: 50%; transition: all 0.15s;
}
.modal-close:hover { background: var(--qn-line); color: var(--qn-ink); }
.modal-body { padding: 22px; overflow-y: auto; flex: 1; }

/* Loading */
.ae-loading { text-align: center; padding: 32px 0; }
.ae-spinner {
  width: 36px; height: 36px; border: 3px solid var(--qn-line);
  border-top-color: var(--qn-emerald); border-radius: 50%;
  margin: 0 auto 16px; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg) } }
.ae-loading p { margin: 4px 0; }

/* Error */
.ae-error { text-align: center; padding: 16px; color: var(--qn-fire); }

/* Content */
.ae-engine-tag {
  display: inline-block; margin-bottom: 14px; padding: 3px 10px; border-radius: 12px;
  background: var(--qn-paper); color: var(--qn-ink-2);
  font-size: calc(11px * var(--qn-fs-scale)); font-weight: 500;
}
.ae-markdown {
  font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink); line-height: 1.8;
}
.ae-markdown strong { color: var(--qn-emerald); font-weight: 600; }
.ae-markdown p { margin: 0 0 12px; }
.ae-hr { border: none; border-top: 1px dashed var(--qn-line); margin: 16px 0; }

/* 继续聊按钮 */
.ae-footer {
  margin-top: 20px; padding-top: 18px;
  border-top: 1px dashed var(--qn-line);
}
.ae-footer-hint {
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  margin: 0 0 12px; text-align: center;
}
.ae-chat-btn {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  width: 100%; padding: 14px 18px;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-light) 100%);
  color: #fff; border: none; border-radius: var(--qn-r-lg);
  font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600;
  cursor: pointer; transition: all 0.18s;
  box-shadow: 0 4px 14px rgba(var(--qn-emerald-rgb),0.25);
}
.ae-chat-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(var(--qn-emerald-rgb),0.35); }
.ae-chat-btn:active { transform: translateY(0); }
.ae-chat-icon { font-size: calc(18px * var(--qn-fs-scale)); }
.ae-chat-arrow { opacity: 0.7; font-size: calc(16px * var(--qn-fs-scale)); }

/* 响应式 — 归并到 480px 档位（原 600px） */
@media (max-width: 480px) {
  .modal-card { max-height: 88vh; border-radius: var(--qn-r-lg); }
  .modal-body { padding: 16px 18px; }
}

/* ── 顶部并列 ── */
.top-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; align-items: stretch; }
/* ⚠️ .card 基础样式已统一到 App.vue 全局（无 border、shadow-only、圆角 16）
   Dashboard 独有：只覆盖 h2 的 margin-bottom */
.card h2 { margin-bottom: 12px; }
.chart-card { min-height: 300px; display: flex; flex-direction: column; }
.chart-card :deep(.radar-chart), .chart-card :deep(.drift-chart) { flex: 1; }

/* ── 体质调理曲线（top-row 左侧） ── */
.curve-chart { flex: 1; min-height: 260px; }
.curve-empty { color: var(--qn-ink-3); text-align: center; padding: 50px 16px; font-size: calc(13px * var(--qn-fs-scale)); }

/* ── 体质趋势卡：雷达图左 + 图例右 ── */
.trend-card { margin-top: 28px; }
.trend-body { display: flex; gap: 20px; align-items: center; flex: 1; min-height: 0; }
.trend-radar { flex: 1; min-width: 0; }
.trend-side { flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.legend-row { display: flex; align-items: center; gap: 8px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.lg-swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.lg-swatch.base { background: var(--qn-emerald); }
.lg-swatch.obs { background: var(--wuxing-fire, var(--qn-cinnabar)); }
.trend-delta { margin: 2px 0 0; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); line-height: 1.6; max-width: 200px; }
.btn-ghost-sm {
  align-self: flex-start; margin-top: 4px;
  font-size: calc(13px * var(--qn-fs-scale)); padding: 6px 16px; border-radius: var(--qn-r-pill);
  border: 1px solid var(--qn-emerald); background: transparent; color: var(--qn-emerald);
  cursor: pointer; transition: background 0.15s;
}
.btn-ghost-sm:hover { background: rgba(var(--qn-emerald-rgb),0.06); }

/* ── 分区标题 + 三段分段器 ── */
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 16px 0 12px; gap: 12px; flex-wrap: wrap; }
.section-title { font-size: calc(18px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0; letter-spacing: 0.5px; }
.seg-control { display: flex; background: var(--qn-surface); border: 1px solid var(--qn-line); border-radius: var(--qn-r-pill); overflow: hidden; }
.seg-btn {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 7px 18px; border: none; background: transparent;
  color: var(--qn-ink-3); cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.seg-btn:hover { color: var(--qn-emerald); }
.seg-btn.active { background: var(--qn-emerald); color: var(--qn-paper); font-weight: 500; }

/* ── 待办卡片网格 ── */
.todo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  grid-auto-rows: 1fr;         /* 关键：每行等高，让卡片内部 flex 布局生效 */
  gap: 16px;
}
.todo-grid > * { height: 100%; }  /* 子元素（TodoCard）撑满网格单元格 */
.todo-empty { grid-column: 1 / -1; text-align: center; padding: 30px; color: var(--qn-ink-3); font-size: calc(13px * var(--qn-fs-scale)); }

/* ── 归档 ── */
.archive-summary { background: var(--qn-paper); border-radius: var(--qn-r-sm); padding: 12px 16px; margin-bottom: 12px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.archive-summary strong { color: var(--qn-emerald); font-weight: 600; }
.archive-list { display: flex; flex-direction: column; gap: 8px; }
/* ⚠️ border 已删 */
.archive-day { background: var(--qn-surface); border-radius: var(--qn-r-sm); overflow: hidden; }
.archive-day-head {
  padding: 12px 16px; cursor: pointer;
  display: flex; gap: 14px; align-items: center; font-size: calc(13px * var(--qn-fs-scale));
  transition: background 0.15s;
}
.archive-day-head:hover { background: var(--qn-paper); }
.archive-date { font-weight: 600; color: var(--qn-emerald); font-family: var(--font-mono); }
.archive-todo-count { color: var(--qn-ink-2); }
.archive-fb-count { color: var(--qn-ink-3); margin-left: auto; font-size: calc(12px * var(--qn-fs-scale)); }
.archive-day-body { padding: 8px 16px 16px; border-top: 1px solid var(--qn-line); background: var(--qn-paper); }
.archive-todo {
  display: flex; gap: 10px; align-items: center;
  padding: 6px 8px; font-size: calc(12px * var(--qn-fs-scale));
  border-radius: 4px;
}
.archive-todo-title { flex: 1; color: var(--qn-ink); }
.archive-exec { font-size: calc(11px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 3px; font-weight: 500; }
.archive-exec.exec-done { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.archive-exec.exec-partial { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.archive-exec.exec-skipped { background: rgba(107,114,119,0.1); color: var(--qn-ink-3); }
.archive-exec.exec-failed { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.archive-exec.exec-null { background: var(--qn-paper); color: var(--qn-ink-3); }
.archive-fb { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* ── 表格 ── */
.table-card { margin-top: 16px; }
.placeholder { color: var(--qn-ink-3); text-align: center; padding: 40px 16px; font-size: calc(13px * var(--qn-fs-scale)); }

/* ── 响应式：竖屏 / 窄窗修复 — 归并到 1024px 档位（原 960px） ── */
@media (max-width: 1024px) {
  .top-row { grid-template-columns: 1fr; }
  .chart-card { min-height: 0; }
  .todo-grid { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  /* 英雄卡：桌面并排 → 竖屏上下堆叠 */
  .hero-row { grid-template-columns: 1fr; gap: 12px; }
  .hero-yi-card .hero-title { font-size: calc(16px * var(--qn-fs-scale)); margin-bottom: 10px; }
  /* 体质趋势：图上文下 */
  .trend-body { flex-direction: column; align-items: stretch; }
  .trend-radar { width: 100%; }
  .trend-side { align-items: flex-start; }
  .trend-delta { max-width: none; }
  /* 问候区改上下两行，统计左对齐 */
  .home-header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .home-quick { gap: 24px; }
  .table-card { overflow-x: auto; }
  .table { min-width: 520px; }
}
/* —— 小屏字体再压一下 — 归并到 480px 档位（原 640px） —— */
@media (max-width: 480px) {
  .home-greeting { font-size: calc(19px * var(--qn-fs-scale)); }
  .home-quick { gap: 20px; }
  .qs-val { font-size: calc(18px * var(--qn-fs-scale)); }
  .hero-card { padding: 20px; }
  .hero-yi-card { padding: 18px 20px; }
  .anchor-grid { gap: 8px; }
  .ag-cell { padding: 10px 8px; }
  .ag-val { font-size: calc(13px * var(--qn-fs-scale)); }
  .todo-grid { grid-template-columns: 1fr; }
  .anchor-timeline { flex-direction: column; gap: 10px; }
  .seg-control { width: 100%; }
  .seg-btn { flex: 1; padding: 7px 8px; text-align: center; }
  .rem-lists { grid-template-columns: 1fr; }
}

/* ═══════════════════════════════════════════════════════════
   今日时空锚点：三格指标条 + 三段节律线
   ═══════════════════════════════════════════════════════════ */
.anchor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px; }
.ag-cell { background: var(--qn-paper); border: none; border-radius: 12px; padding: 10px 12px; text-align: left; min-height: 60px; display: flex; flex-direction: column; justify-content: center; }
.ag-label { display: block; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 4px; }
.ag-val { font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); line-height: 1.2; }
.ag-val.warn { color: var(--wuxing-fire, var(--qn-cinnabar)); }
/* ══ 彭祖百忌 + 二十八宿（2026-10-05 新增）══ */
.anchor-extras { border-top: 1px dashed rgba(26,43,26,0.12); padding-top: 8px; margin-bottom: 8px; display: flex; flex-direction: column; gap: 4px; }
.ae-row { display: flex; font-size: calc(12px * var(--qn-fs-scale)); }
.ae-label { color: var(--qn-ink-3); flex-shrink: 0; width: 72px; }
.ae-val { color: var(--qn-ink-2); }
/* ══ 玉匣记摘录条（2026-10-05 新增）══ */
.anchor-yuxiaji {
  background: rgba(168, 68, 47, 0.06);
  border-left: 3px solid var(--qn-cinnabar);
  border-radius: 0 8px 8px 0;
  padding: 8px 12px;
  margin-bottom: 4px;
}
.yxj-quote { font-family: "STKaiti", "KaiTi", serif; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-cinnabar); letter-spacing: 0.5px; }

.anchor-timeline { display: flex; gap: 8px; }
.tl-seg { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.tl-bar { display: block; height: 4px; border-radius: 2px; }
.tl-seg.calm .tl-bar { background: #C9D8D2; }
.tl-seg.active .tl-bar { background: var(--qn-emerald); }
.tl-seg.rest .tl-bar { background: var(--wuxing-earth, var(--qn-earth)); }
.tl-text { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl-seg.active .tl-text { color: var(--qn-emerald); font-weight: 500; }
.tl-seg.rest .tl-text { color: var(--wuxing-earth, #B8860B); }

/* ═══════════════════════════════════════════════════════════
   生活提醒：折叠行 + 展开区
   ═══════════════════════════════════════════════════════════ */
.reminders-mini { margin-bottom: 16px; padding: 0 18px; }
.rem-collapse {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  background: transparent; border: none; padding: 14px 0;
  font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); cursor: pointer; text-align: left;
}
.rem-collapse:hover .rem-collapse-text { color: var(--qn-emerald); }
.rem-collapse-text { transition: color 0.15s; }
.rem-chevron { font-size: calc(16px * var(--qn-fs-scale)); color: var(--qn-ink-3); transition: transform 0.2s; font-weight: 300; }
.rem-chevron.open { transform: rotate(90deg); }
.rem-body { border-top: 1px dashed var(--qn-line); padding: 12px 0 16px; }
.rem-fold-zone { display: flex; flex-direction: column; gap: 10px; }
/* ⚠️ border 已删 */
.rem-fold { border-radius: 8px; background: var(--qn-surface); }
.rem-fold-summary {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 12px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--wuxing-earth);
  cursor: pointer; list-style: none; user-select: none;
}
.rem-fold-summary::-webkit-details-marker { display: none; }
.rem-fold-summary.danger { color: var(--wuxing-fire); }
.rem-fold-summary::after { content: '›'; margin-left: auto; font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-3); transition: transform 0.2s; font-weight: 300; }
.rem-fold[open] .rem-fold-summary::after { transform: rotate(90deg); }
.rem-fold .rem-item { margin: 0 10px 10px; }
.rem-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.rem-head h2 { font-size: calc(15px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0; }

/* ── Lifestyle 流式加载 ── */
.lifestyle-loading { padding: 20px 12px; }
.lifestyle-loading-header { display: flex; align-items: center; gap: 10px; color: var(--qn-emerald); font-size: calc(13px * var(--qn-fs-scale)); margin-bottom: 12px; font-weight: 500; }
.spinner { animation: pulse 1.2s ease-in-out infinite; display: inline-block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.lifestyle-preview { background: #f7f9fa; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); padding: 10px 12px; font-family: var(--font-mono, monospace); font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; margin: 0; line-height: 1.6; }
.lifestyle-preview-placeholder { color: var(--qn-ink-3); font-size: calc(12px * var(--qn-fs-scale)); font-style: italic; padding: 20px 0; text-align: center; }
.rem-tabs { display: flex; gap: 4px; }
.rem-tab {
  font-size: calc(12px * var(--qn-fs-scale)); padding: 5px 12px; border-radius: 14px;
  border: 1px solid var(--qn-line); background: var(--qn-surface); color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s;
}
.rem-tab:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.rem-tab.active { background: var(--qn-emerald); border-color: var(--qn-emerald); color: #fff; }

.rem-lists { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 720px) { .rem-lists { grid-template-columns: 1fr; } }
.rem-col { display: flex; flex-direction: column; gap: 6px; }
.rem-col-title { font-size: calc(12px * var(--qn-fs-scale)); margin: 0 0 4px; padding-bottom: 4px; border-bottom: 1px dashed var(--qn-line); }
.rem-col-title.good { color: var(--wuxing-wood); }
.rem-col-title.bad { color: var(--wuxing-fire); }
.rem-col-title.warn { color: var(--wuxing-earth); }

.rem-item {
  padding: 10px 12px; border-radius: 8px; border: 1px solid var(--qn-line);
  background: var(--qn-surface); display: flex; flex-direction: column; gap: 3px;
}
.rem-item-title { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.rem-item-desc { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.5; }
.rem-item.rem-good { border-left: 3px solid var(--wuxing-wood); }
.rem-item.rem-bad { border-left: 3px solid var(--wuxing-fire); }
.rem-item.rem-danger { border-left: 4px solid var(--wuxing-fire); background: linear-gradient(135deg, var(--qn-surface), rgba(216,67,21,0.03)); }
.rem-item.rem-stone { border-left: 3px solid var(--wuxing-metal); }
.rem-item.rem-urgent { border-left: 3px solid var(--wuxing-fire); background: rgba(216,67,21,0.04); }

/* ═══════════════════════════════════════════
   打卡弹窗（全屏遮罩 + 居中卡片）
   ═══════════════════════════════════════════ */
.punch-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(16, 24, 40, 0.45);
  backdrop-filter: blur(3px);
  z-index: 9999;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.punch-modal {
  background: var(--qn-surface);
  border-radius: 16px;
  width: 100%; max-width: 520px;
  max-height: 92vh;
  overflow-y: auto;
  padding: 24px;
  box-shadow: 0 20px 60px rgba(16, 24, 40, 0.25);
  animation: pm-slide-up 0.25s ease-out;
}
@keyframes pm-slide-up {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 弹窗头部 */
.pm-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px; padding-bottom: 14px;
  border-bottom: 1px solid var(--qn-line);
}
.pm-title-wrap { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.pm-tag {
  display: inline-block; width: fit-content;
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald);
  background: rgba(var(--qn-emerald-rgb),0.08);
  padding: 2px 10px; border-radius: 10px;
  letter-spacing: 1px; font-weight: 500;
}
.pm-title { font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-ink); margin: 0; font-weight: 600; line-height: 1.35; }
.pm-due { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }
.pm-close {
  width: 32px; height: 32px; border-radius: 50%;
  border: 1px solid var(--qn-line); background: var(--qn-surface);
  color: var(--qn-ink-3); font-size: calc(14px * var(--qn-fs-scale)); line-height: 1;
  cursor: pointer; transition: all 0.15s;
  flex-shrink: 0; margin-left: 12px;
}
.pm-close:hover { color: var(--wuxing-fire); border-color: var(--wuxing-fire); }

/* section */
.pm-section { margin-bottom: 18px; }
.pm-label {
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  display: block; margin-bottom: 8px; font-weight: 500;
}

/* 执行状态按钮 */
.pm-exec-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.pm-exec {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 7px 16px;
  border-radius: 20px;
  border: 1px solid var(--qn-line);
  background: var(--qn-surface); color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s;
}
.pm-exec:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.pm-exec.active {
  background: var(--qn-emerald); border-color: var(--qn-emerald);
  color: #fff; box-shadow: 0 2px 6px rgba(var(--qn-emerald-rgb), 0.25);
}

/* 历史反馈 */
.pm-fb-item {
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  font-size: calc(12px * var(--qn-fs-scale)); padding: 8px 10px; background: var(--qn-paper);
  border-radius: 6px; margin-bottom: 6px;
  border-left: 3px solid var(--qn-line);
}
.pm-fb-date { color: var(--qn-ink-3); font-family: var(--font-mono); font-size: calc(11px * var(--qn-fs-scale)); }
.pm-fb-status { font-weight: 600; padding: 1px 8px; border-radius: 3px; font-size: calc(11px * var(--qn-fs-scale)); }
.pm-fb-done { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.pm-fb-partial { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.pm-fb-skipped { background: rgba(107,114,119,0.1); color: var(--qn-ink-3); }
.pm-fb-failed { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.pm-fb-note { flex: 1 0 100%; color: var(--qn-ink-2); line-height: 1.5; margin-top: 3px; }

/* 反馈输入 */
.pm-section textarea {
  width: 100%; border: 1px solid var(--qn-line); border-radius: 10px;
  padding: 12px; font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body);
  resize: vertical; background: var(--qn-surface); color: var(--qn-ink);
  line-height: 1.55; transition: border-color 0.15s;
  box-sizing: border-box;
}
.pm-section textarea:focus { outline: none; border-color: var(--qn-emerald); }

/* 底部按钮 */
.pm-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  margin-top: 22px; padding-top: 16px;
  border-top: 1px solid var(--qn-line);
}
.pm-cancel {
  padding: 9px 22px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-pill);
  background: var(--qn-surface); color: var(--qn-ink-2); font-size: calc(13px * var(--qn-fs-scale)); cursor: pointer;
  transition: all 0.15s;
}
.pm-cancel:hover { color: var(--qn-ink); border-color: var(--qn-ink-3); }
.pm-submit {
  padding: 9px 24px; border: none; border-radius: var(--qn-r-pill);
  background: var(--qn-emerald); color: var(--qn-paper);
  font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500; letter-spacing: 2px; cursor: pointer;
  transition: all 0.15s;
}
.pm-submit:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(var(--qn-emerald-rgb), 0.3); }
.pm-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* 详情弹窗文本 */
.pm-desc {
  font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  margin: 4px 0 0; line-height: 1.55;
}
.pm-text {
  font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-2);
  line-height: 1.7; margin: 0;
}
.pm-text.source-text {
  font-family: 'STKaiti', 'KaiTi', '楷体', serif;
  color: var(--qn-cinnabar);
  border-left: 2px solid #B8392A;
  padding-left: 10px;
  font-size: calc(13px * var(--qn-fs-scale));
}

/* Transition */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-active .punch-modal, .fade-leave-active .punch-modal { transition: transform 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fade-enter-from .punch-modal, .fade-leave-to .punch-modal { transform: translateY(10px) scale(0.97); }

/* 弹窗手机竖屏 */
@media (max-width: 480px) {
  .punch-modal-backdrop { padding: 0; }
  .punch-modal {
    max-width: 100%; max-height: 100vh; border-radius: 0;
    padding: 20px;
    animation: none;
  }
  .pm-title { font-size: calc(16px * var(--qn-fs-scale)); }
  .pm-exec-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .pm-foot { gap: 8px; }
  .pm-cancel, .pm-submit { flex: 1; padding: 11px 0; text-align: center; }
}
</style>
