// 极简 CDP 客户端：连接手机 WebView，执行一段 JS 并打印返回值
// 用法: node cdp.mjs <port> <base64-expression>
//       node cdp.mjs <port> @/path/to/expr.js   ← 从文件读（避免命令行长度限制）
import { readFileSync } from 'node:fs'
const [,, port, b64] = process.argv;
const expr = b64.startsWith('@')
  ? readFileSync(b64.slice(1), 'utf8')
  : Buffer.from(b64, 'base64').toString('utf8');

// 1) 先从 /json 拿 page 的 webSocketDebuggerUrl
const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = list.find(p => p.type === 'page');
if (!page) { console.error('未找到 page'); process.exit(1); }

const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((res) => {
    const i = ++id;
    pending.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
}
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
ws.onopen = async () => {
  try {
    const r = await send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    if (r.result?.exceptionDetails) {
      console.error('JS 异常:', JSON.stringify(r.result.exceptionDetails, null, 2).slice(0, 800));
    } else {
      console.log(JSON.stringify(r.result?.result?.value ?? r.result, null, 2));
    }
  } catch (err) {
    console.error('失败:', err.message);
  }
  ws.close();
  process.exit(0);
};
ws.onerror = () => { console.error('WebSocket 连接失败'); process.exit(1); };
