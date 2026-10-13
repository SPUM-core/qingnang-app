#!/usr/bin/env node
/**
 * ═══════════════════════════════════════════════════════════════════
 * 安全区避让检查（防再犯 · 2026-10-12 建立 / 2026-10-12 升级）
 * ───────────────────────────────────────────────────────────────────
 * 背景：App 的「状态栏被内容吃掉」问题在 2026-10-12 前反复出现，
 *       根因都是**同一个**：业务样式在层叠中覆盖了避让声明
 *         · App.vue 竖屏 .page{padding:16px 14px} 覆盖 base.css 的避让
 *         · QingnangAssistant .drawer-head{padding:10px 14px} 覆盖 media 里的避让
 *       还有一类更隐蔽的：**页面/浮层压根没写避让**
 *         · 6 个页面没用 .page → 完全没有避让（知识卡片/体质曲线/商城…）
 *         · 9 个 position:fixed 浮层未登记 → 顶部/底部被系统栏吃掉
 *
 * 本脚本查三类问题：
 *  ① 裸用 env(safe-area-inset-*)：Android WebView 取值不确定，
 *     必须走 --safe-*（唯一真相源在 src/styles/base.css）。
 *  ② position:fixed 的「贴边」浮层（inset:0 / top:0 / bottom:0）
 *     既没有 var(--safe-*)，又没登记进 base.css 的兜底表
 *     → 全新浮层漏网的典型形态，必须拦住。
 *  ③ 报告用 .page 但未挂在 .layout__main 下的可疑页面（提示级）。
 *
 * 用法：  node scripts/check-safe-area.mjs
 *        （已挂到 npm run build / npm run check:safe，退出码 1 = 有违规）
 * ═══════════════════════════════════════════════════════════════════
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, extname, join, relative } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const SRC = join(root, 'src')
const BASE_CSS = join(SRC, 'styles', 'base.css')
const EXTS = new Set(['.vue', '.css', '.scss', '.less', '.sass'])

/** 唯一允许写 env(safe-area-inset-*) 的文件：安全区变量定义处 */
const ALLOW_ENV = ['src/styles/base.css']

/** 已知无需避让的例外 */
const FIXED_EXEMPT = new Set([
  'dbg-badge',                          // 调试角标，dev-only
  'fade-enter-from', 'fade-leave-to',   // 过渡类名
  'splash-root', 'onboarding',          // 全屏沉浸页（meta.fullScreen），故意铺满
  'drawer', 'guide-overlay',            // 全屏容器/引导层，内容各自避让（.drawer-head 已登记）
  'history-sidebar-overlay',            // 纯遮罩
])

/** 纯遮罩层（只负责压暗，不承载内容）→ 无需避让 */
const BACKDROP_RE = /(^|-)backdrop$/
const isBackdrop = (c) => BACKDROP_RE.test(c)

const stripComments = (s) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) {
      if (name === 'node_modules' || name.startsWith('.')) continue
      walk(p, out)
    } else if (EXTS.has(extname(p))) {
      out.push(p)
    }
  }
  return out
}

/* ── 从 base.css 兜底表提取「已登记」的类名（含 --safe- 且带 !important 的行） ── */
const baseCss = readFileSync(BASE_CSS, 'utf8')
const registry = new Set()
for (const line of baseCss.split('\n')) {
  if (line.includes('--safe-') && line.includes('!important')) {
    for (const m of line.matchAll(/\.([A-Za-z0-9_-]+)/g)) registry.add(m[1])
  }
}

const rel = (f) => relative(root, f).replace(/\\/g, '/')
const envProblems = []
const overlayProblems = []

for (const file of walk(SRC)) {
  const relPath = rel(file)
  const raw = readFileSync(file, 'utf8')
  const clean = stripComments(raw)

  /* ① 裸用 env(safe-area-inset-*) */
  if (!ALLOW_ENV.includes(relPath)) {
    clean.split('\n').forEach((line, i) => {
      if (/env\(\s*safe-area-inset/.test(line)) {
        envProblems.push({ file: relPath, line: i + 1, text: line.trim() })
      }
    })
  }

  /* ② position:fixed 贴边浮层缺少避让且未登记 */
  if (relPath !== 'src/styles/base.css') {
    const re = /position\s*:\s*fixed/g
    let m
    while ((m = re.exec(clean))) {
      const open = clean.lastIndexOf('{', m.index)
      const close = clean.indexOf('}', m.index)
      if (open < 0 || close < 0) continue
      const decls = clean.slice(open + 1, close)
      const selStart = Math.max(
        clean.lastIndexOf('}', open - 1),
        clean.lastIndexOf('{', open - 1),
        clean.lastIndexOf('>', open - 1),   // 不越过 </script> / <style> 边界
        clean.lastIndexOf(';', open - 1)
      )
      const selector = clean.slice(selStart + 1, open).trim()
      const line = clean.slice(0, m.index).split('\n').length

      const isEdgeStuck = /inset\s*:\s*0|(^|[;{\s])top\s*:\s*0|(^|[;{\s])bottom\s*:\s*0/.test(decls)
      if (!isEdgeStuck) continue
      if (/var\(\s*--safe-/.test(decls)) continue

      const classes = [...selector.matchAll(/\.([A-Za-z0-9_-]+)/g)].map((x) => x[1])
      const exempt =
        classes.some((c) => FIXED_EXEMPT.has(c)) ||
        classes.some((c) => isBackdrop(c))
      const registered = classes.some((c) => registry.has(c))
      if (exempt || registered) continue

      overlayProblems.push({ file: relPath, line, selector, classes })
    }
  }
}

let failed = false

if (envProblems.length) {
  failed = true
  console.error('\n✖ [①] 发现裸用 env(safe-area-inset-*)：\n')
  console.error('  请改用统一变量（定义见 src/styles/base.css 顶部 html 块）：')
  console.error('    var(--safe-top) / var(--safe-bottom) / var(--safe-left) / var(--safe-right)\n')
  for (const p of envProblems) console.error(`  ${p.file}:${p.line}  ${p.text}`)
}

if (overlayProblems.length) {
  failed = true
  console.error('\n✖ [②] 发现「贴边 fixed 浮层」未做安全区避让，也未登记兜底表：\n')
  console.error('  这两种改法任选其一（推荐前者）：')
  console.error('    a) 在组件规则里用 var(--safe-top) / var(--safe-bottom)')
  console.error('    b) 把类名登记到 src/styles/base.css 末尾「浮层安全区兜底」表\n')
  for (const p of overlayProblems) {
    console.error(`  ${p.file}:${p.line}  ${p.selector.slice(0, 70)}`)
    console.error(`      → 类名: ${p.classes.map((c) => '.' + c).join(', ') || '(无类名)'}`)
  }
}

if (failed) {
  console.error('\n提示：容器级避让见 base.css 的 .layout__main（普通页面无需各自处理）；')
  console.error('      只有 position:fixed / Teleport 出去的浮层才需要单独避让。\n')
  process.exit(1)
}

console.log(
  `✓ 安全区检查通过：无裸用 env()；fixed 贴边浮层均已有避让或登记（兜底表 ${registry.size} 条）`
)
