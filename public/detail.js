function getQuery(k){
  const u = new URL(location.href);
  return u.searchParams.get(k);
}

const TV_SYMBOL_MAP = {
  // US indices
  '^GSPC': 'SP:SPX',    // S&P 500 index symbol on TV
  '^NDX': 'NASDAQ:NDX', // Nasdaq 100 index (or NASDAQ:NDX)
  // HK indices
  '^HSI': 'HSI',        // HSI composite
  '^HSTECH': 'HSI:TECH', // alt: TV sometimes uses HKEX:HSTECH index symbols; fallback via ETF
  // CN indices
  '000001.SS': 'SSE:000001', // 上证指数
  '000300.SH': 'SSE:000300'  // 沪深300（有时为 CSI:000300 / SZSE:399300 视TV路由）
};

async function load(){
  const code = getQuery('code');
  if(!code){
    document.getElementById('current-stats').innerHTML = '缺少代码参数';
    return;
  }
  const resp = await fetch('/data/data.json', {cache:'no-store'});
  const data = await resp.json();
  const item = (data.indexes||[]).find(x=>x.code===code);
  document.getElementById('index-title').textContent = item?`${item.name}（${item.code}）`:`指数详情`;
  if(!item){
    document.getElementById('current-stats').innerHTML = '未找到该指数的数据';
    return;
  }
  renderStats(item);
  renderChart(item);
  renderInsights(item);
  renderTV(code, item);
}

function renderStats(it){
  const el = document.getElementById('current-stats');
  const pePct = it.pe_percentile!=null?Math.round(it.pe_percentile*100)+'%':'-';
  const pbPct = it.pb_percentile!=null?Math.round(it.pb_percentile*100)+'%':'-';
  el.innerHTML = `
    <p>点位：<strong>${it.price ?? '-'}</strong></p>
    <p>PE(TTM)：${it.pe_ttm ?? '-'}，历史分位：${pePct}</p>
    <p>PB：${it.pb ?? '-'}，历史分位：${pbPct}</p>
  `;
}

function renderChart(it){
  const ctx = document.getElementById('valuationChart').getContext('2d');
  const labels = (it.history||[]).map(d=>d.date);
  const pe = (it.history||[]).map(d=>d.pe_percentile);
  const pb = (it.history||[]).map(d=>d.pb_percentile);
  new Chart(ctx,{
    type:'line',
    data:{
      labels,
      datasets:[
        {label:'PE分位', data:pe, borderColor:'#4cc9f0', tension:.2},
        {label:'PB分位', data:pb, borderColor:'#2ecc71', tension:.2}
      ]
    },
    options:{
      plugins:{legend:{labels:{color:'#e6edf3'}}},
      scales:{
        x:{ticks:{color:'#9fb0c0'}},
        y:{min:0,max:1,ticks:{color:'#9fb0c0', callback:(v)=>Math.round(v*100)+'%'}}
      }
    }
  });
}

function renderInsights(it){
  const el = document.getElementById('trend-insights');
  const t = it.trend_text || '趋势分析待更新。';
  el.innerHTML = `<p>${t}</p>`;
}

function renderTV(code, item){
  const container = document.getElementById('tv-chart');
  if(!window.TradingView || !container) return;
  const tvSym = TV_SYMBOL_MAP[code] || fallbackTVSymbol(code);
  if(!tvSym){
    container.innerHTML = '<p class="muted">暂不支持该指数的TradingView图表。</p>';
    return;
  }
  /* global TradingView */
  new TradingView.widget({
    symbol: tvSym,
    container_id: 'tv-chart',
    autosize: true,
    interval: 'D',
    timezone: 'Etc/UTC',
    theme: 'dark',
    style: '1',
    locale: 'zh_CN',
    enable_publishing: false,
    allow_symbol_change: false,
    hide_side_toolbar: false,
    withdateranges: true,
    studies: ['RSI@tv-basicstudies','MAExp@tv-basicstudies'],
  });
}

function fallbackTVSymbol(code){
  // 常见替代：使用 ETF 作为图表展示
  switch(code){
    case '^GSPC': return 'AMEX:SPY';
    case '^NDX': return 'NASDAQ:QQQ';
    case '^HSI': return 'HKEX:2800';
    case '^HSTECH': return 'HKEX:3067';
    case '000001.SS': return 'SSE:000001';
    case '000300.SH': return 'SZSE:399300';
    default: return null;
  }
}

load();