<!--
  QMarkdown — 青囊统一 Markdown 渲染器
  用途：AI 回复、诊断报告、知识库等所有需要 Markdown 渲染的地方
  功能：表格 / 标题 / 列表 / 代码块 / 引用 / KaTeX 公式 ($ 行内 $$ 块级) / **加粗**
  安全：DOMPurify 过滤 HTML，防 XSS
-->
<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import katex from '@traptitech/markdown-it-katex'
import DOMPurify from 'dompurify'

// ── 一次性初始化 MarkdownIt（只在模块加载时跑一次）──
const md = new MarkdownIt({
  html: false,          // Markdown 里的 HTML 标签先当文本，DOMPurify 后会清掉
  linkify: true,        // 自动识别 URL 为链接
  breaks: true,         // 单个换行 → <br>（AI 回复里换行吗很重要）
  typographer: true,    // 智能引号、破折号等替换
})

// ⭐ 显式开启 Markdown 表格（commonmark preset 默认没有）
md.enable('table')
// 启用所有可选规则（确保 heading/list/blockquote/code fence 都生效）
md.enable('heading')
md.enable('list')
md.enable('blockquote')
md.enable('code')
md.enable('fence')

// KaTeX 公式支持 —— 需要 katex.css 在 main.js 全局引入
md.use(katex, {
  throwOnError: false,
  output: 'html',
})

// 可选：代码高亮（如果以后装 highlight.js）
// md.use(require('markdown-it-highlightjs'))

const props = defineProps({
  content: { type: String, default: '' },
})

// ⭐ 核心：Markdown 渲染 → DOMPurify 清洗 → 安全 HTML
const safeHtml = computed(() => {
  if (!props.content) return ''
  // 1. Markdown → HTML
  const rawHtml = md.render(props.content)
  // 2. DOMPurify XSS 过滤 —— ⚠️ 默认白名单不含 <table>，必须显式给完整白名单
  const clean = DOMPurify.sanitize(rawHtml, {
    // 允许所有标准 Markdown 会输出的标签 + KaTeX MathML 标签
    ADD_TAGS: [
      // ── KaTeX MathML（markdown-it-katex 输出）──
      'katex', 'katex-display', 'semantics', 'annotation', 'annotation-xml',
      'mrow', 'mn', 'mi', 'mo', 'msup', 'msub', 'msubsup', 'mfrac', 'mroot',
      'mpadded', 'mphantom', 'mstyle', 'mspace', 'msub', 'msup',
      'merror', 'menclose', 'mmultiscripts', 'mprescripts', 'none',
      'maction', 'maligngroup', 'malignmark', 'mpostfix', 'munder', 'mover', 'munderover',
      // ── 表格（DOMPurify 默认白名单没有！）──
      'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption', 'colgroup', 'col',
    ],
    ADD_ATTR: ['class', 'data-expr', 'style', 'width', 'height', 'viewBox',
               'xmlns', 'xlink:href', 'alt', 'title', 'role', 'aria-label'],
  })
  return clean
})
</script>

<template>
  <div class="q-md" v-html="safeHtml" />
</template>

<style>
/* ⚠️ 非 scoped —— v-html 生成的 DOM 没有 scope 属性，必须全局写。
   但所有选择器都加了 .q-md 前缀，不会污染全局 */

.q-md * { box-sizing: border-box; }

/* ── 标题 ── */
.q-md h1, .q-md h2, .q-md h3, .q-md h4 {
  font-weight: 600;
  line-height: 1.4;
  margin: 14px 0 8px;
  color: var(--qn-ink);
}
.q-md h1 { font-size: 1.15em; border-left: 3px solid var(--qn-emerald); padding-left: 8px; }
.q-md h2 { font-size: 1.08em; border-left: 2px solid var(--qn-emerald); padding-left: 7px; }
.q-md h3 { font-size: 1.02em; color: var(--qn-emerald-dark); }
.q-md h4 { font-size: 0.96em; }

/* ── 段落 ── */
.q-md p { margin: 6px 0; line-height: 1.7; }
.q-md br { display: block; content: ''; margin-top: 2px; }

/* ── 加粗 / 斜体 ── */
.q-md strong { color: var(--qn-emerald-dark); font-weight: 600; }
.q-md em { color: var(--qn-ink-2); }

/* ── 表格（重点！截图里的问题）── */
.q-md table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0 12px;
  font-size: calc(12px * var(--qn-fs-scale));
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--qn-line);
}
.q-md thead { background: rgba(var(--qn-emerald-rgb), 0.08); }
.q-md th {
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  color: var(--qn-emerald-dark);
  border-bottom: 2px solid var(--qn-emerald);
  white-space: nowrap;
}
.q-md td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--qn-line);
  line-height: 1.5;
  vertical-align: top;
}
.q-md tbody tr:last-child td { border-bottom: none; }
.q-md tbody tr:nth-child(even) { background: rgba(var(--qn-emerald-rgb), 0.03); }
.q-md tbody tr:hover td { background: rgba(var(--qn-emerald-rgb), 0.06); }

/* ── 列表 ── */
.q-md ul, .q-md ol { padding-left: 20px; margin: 6px 0; }
.q-md li { margin: 3px 0; line-height: 1.6; }
.q-md ul li::marker { color: var(--qn-emerald); }

/* ── 引用 ── */
.q-md blockquote {
  margin: 8px 0;
  padding: 6px 12px;
  border-left: 3px solid var(--qn-emerald-accent);
  background: rgba(var(--qn-emerald-rgb), 0.04);
  color: var(--qn-ink-2);
  border-radius: 0 6px 6px 0;
}

/* ── 行内代码 ── */
.q-md code:not(pre code) {
  background: rgba(var(--qn-emerald-rgb), 0.1);
  color: var(--qn-emerald-dark);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.92em;
  font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
}

/* ── 代码块 ── */
.q-md pre {
  background: #1e2422;
  color: #e0e0e0;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: calc(12px * var(--qn-fs-scale));
  line-height: 1.5;
}
.q-md pre code {
  background: none;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

/* ── 分隔线 ── */
.q-md hr {
  border: none;
  border-top: 1px solid var(--qn-line);
  margin: 14px 0;
}

/* ── 链接 ── */
.q-md a {
  color: var(--qn-emerald);
  text-decoration: none;
  border-bottom: 1px dashed var(--qn-emerald);
}
.q-md a:hover {
  color: var(--qn-emerald-dark);
  border-bottom-style: solid;
}

/* ── KaTeX 公式对齐 ── */
.q-md .katex {
  font-size: 1.05em;
}
.q-md .katex-display {
  margin: 10px 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 0;
}
.q-md .katex-display > .katex {
  display: inline-block;
  white-space: normal;
}
</style>
