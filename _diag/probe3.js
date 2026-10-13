(() => {
  const root = document.documentElement;
  const safeTop = getComputedStyle(root).getPropertyValue('--safe-top').trim();
  const statusBar = getComputedStyle(root).getPropertyValue('--status-bar-height').trim();
  const main = document.querySelector('.layout__main');
  if (!main) return JSON.stringify({ error: 'no .layout__main', path: location.pathname });
  const R = (el) => Math.round(el.getBoundingClientRect().top);

  const synth = document.createElement('div');
  synth.className = 'kb-head';
  synth.style.cssText = 'height:6px;background:rgba(255,0,0,.25)';
  main.insertBefore(synth, main.firstChild);
  const first = main.children[1] || null;

  function setTop(v) {
    let st = document.getElementById('qn-override');
    if (!st) { st = document.createElement('style'); st.id = 'qn-override'; document.head.appendChild(st); }
    st.textContent = '.layout__main{padding-top:' + v + '!important}';
  }
  function snap(label) {
    return {
      label,
      mainPadTop: getComputedStyle(main).paddingTop,
      synthTop: R(synth),
      pageTop: first ? R(first) : null,
      pageCls: first ? first.className : null,
    };
  }

  const a = snap('容器生效(线上)');
  setTop('0px');
  const b = snap('容器强制置0');
  setTop('var(--safe-top)');
  const c = snap('恢复');
  document.getElementById('qn-override').remove();
  synth.remove();

  return JSON.stringify({
    path: location.pathname, safeTop, statusBar, a, b, c,
    delta_synth: a.synthTop - b.synthTop,
    delta_page: (a.pageTop ?? 0) - (b.pageTop ?? 0),
  }, null, 1);
})()
