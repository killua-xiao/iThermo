async function loadData(){
  try{
    const resp = await fetch('/data/data.json', {cache:'no-store'});
    const data = await resp.json();
    renderList(data.indexes||[]);
  }catch(e){
    console.error(e);
    document.getElementById('index-list').innerHTML = '<div class="card">数据加载失败，请稍后重试。</div>';
  }
}

function statusBadge(status){
  const map = { low:'ok', neutral:'warn', high:'bad' };
  const cls = map[status]||'warn';
  const text = status==='low'?'低估':status==='high'?'高估':'中性';
  return `<span class="badge ${cls}">${text}</span>`;
}

function renderList(indexes){
  const container = document.getElementById('index-list');
  if(!indexes.length){
    container.innerHTML = '<div class="card">暂无数据</div>';
    return;
  }
  container.innerHTML = indexes.map(it=>{
    const link = `/detail.html?code=${encodeURIComponent(it.code)}`;
    return `
      <a class="card index-card" href="${link}">
        <h3>${it.name}</h3>
        <div class="muted">代码：${it.code}</div>
        <p>点位：<strong>${it.price ?? '-'}</strong></p>
        <p>估值：${statusBadge(it.valuation_status)} <span class="muted">(PE分位 ${it.pe_percentile!=null?Math.round(it.pe_percentile*100):'-'}% / PB分位 ${it.pb_percentile!=null?Math.round(it.pb_percentile*100):'-'}%)</span></p>
      </a>
    `;
  }).join('');
}

loadData();