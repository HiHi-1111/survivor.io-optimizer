(()=>{
  const BUILD='item-editor-live-v3';
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>Array.from(r.querySelectorAll(s));

  function mark(){
    window.ASCENDANT_BUILD=BUILD;
    if(document.querySelector('.live-build-badge'))return;
    const top=document.querySelector('.topbar-actions')||document.body;
    const b=document.createElement('span');
    b.className='live-build-badge';
    b.textContent=BUILD;
    b.style.cssText='display:inline-flex;align-items:center;border:1px solid #37d6c4;background:#12302c;color:#c9fff7;border-radius:999px;padding:7px 10px;font-size:11px;font-weight:900;letter-spacing:.04em';
    top.prepend(b);
  }

  function fire(input){
    if(!input)return;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
  }

  function valueOf(input,max){return Math.max(0,Math.min(max,parseInt(input?.value||'0',10)||0));}

  function setValue(input,v,max){
    input.value=Math.max(0,Math.min(max,v));
    fire(input);
  }

  function makeStars(input,max,redrawAll){
    const row=document.createElement('div');
    row.className='forge-stars';
    const redraw=()=>{
      const v=valueOf(input,max);
      row.innerHTML='';
      for(let i=0;i<=max;i++){
        const b=document.createElement('button');
        b.type='button';
        b.className='forge-star'+(i>0&&i<=v?' filled':'')+(i===v?' current':'');
        b.textContent=i===0?'0':'★';
        b.title='Set '+i;
        b.onclick=()=>{setValue(input,i,max);redrawAll();};
        row.appendChild(b);
      }
    };
    input.addEventListener('change',redraw);
    redraw();
    return row;
  }

  function makeStepper(input,max,label,redrawAll){
    const box=document.createElement('div');
    box.className='forge-box';
    const labelEl=document.createElement('div');
    labelEl.className='forge-label';
    labelEl.textContent=label;
    const step=document.createElement('div');
    step.className='forge-stepper';
    const minus=document.createElement('button');
    minus.type='button'; minus.className='forge-btn'; minus.textContent='-';
    const val=document.createElement('div');
    val.className='forge-value';
    const plus=document.createElement('button');
    plus.type='button'; plus.className='forge-btn'; plus.textContent='+';
    const stars=makeStars(input,max,redrawAll);
    function redraw(){val.textContent=valueOf(input,max)+' / '+max;}
    minus.onclick=()=>{setValue(input,valueOf(input,max)-1,max);redrawAll();};
    plus.onclick=()=>{setValue(input,valueOf(input,max)+1,max);redrawAll();};
    input.addEventListener('change',redraw);
    redraw();
    step.append(minus,val,plus);
    box.append(labelEl,step,stars);
    return box;
  }

  function pathMax(key){
    key=(key||'').toLowerCase();
    if(key==='x')return 13;
    if(key==='base')return 3;
    return 10;
  }

  function enhanceItemCard(card){
    if(card.dataset.realItemEditor==='1')return;
    const rows=$$('.path-row',card);
    if(!rows.length)return;
    card.dataset.realItemEditor='1';
    card.classList.add('item-editor-on');
    const panel=document.createElement('div');
    panel.className='item-control-panel';

    rows.forEach(row=>{
      const key=row.querySelector('.path-key')?.textContent?.trim()||'?';
      const inputs=$$('input',row);
      if(inputs.length<2)return;
      const max=pathMax(key);
      const control=document.createElement('div');
      control.className='forge-control';
      const head=document.createElement('div');
      head.className='forge-control-head';
      head.innerHTML='<span class="forge-key">'+key.toUpperCase()+'</span><span class="forge-gain">current → target</span>';
      const cols=document.createElement('div');
      cols.className='forge-two-cols';
      const redrawAll=()=>{
        const cur=valueOf(inputs[0],max);
        const tar=valueOf(inputs[1],max);
        if(tar<cur)setValue(inputs[1],cur,max);
        cols.innerHTML='';
        cols.append(makeStepper(inputs[0],max,'current',redrawAll),makeStepper(inputs[1],max,'target',redrawAll));
      };
      const actions=document.createElement('div');
      actions.className='forge-actions';
      const clear=document.createElement('button');clear.type='button';clear.className='forge-mini';clear.textContent='clear';clear.onclick=()=>{setValue(inputs[0],0,max);setValue(inputs[1],0,max);redrawAll();};
      const owned=document.createElement('button');owned.type='button';owned.className='forge-mini';owned.textContent='owned';owned.onclick=()=>{setValue(inputs[0],max,max);setValue(inputs[1],max,max);redrawAll();};
      const target=document.createElement('button');target.type='button';target.className='forge-mini';target.textContent='target max';target.onclick=()=>{setValue(inputs[1],max,max);redrawAll();};
      actions.append(clear,owned,target);
      control.append(head,cols,actions);
      panel.append(control);
      redrawAll();
    });
    card.appendChild(panel);
  }

  function enhanceItemOptimizer(){
    const grid=$('#itemOptimizerGrid');
    if(!grid)return;
    if(!grid.dataset.realHelp){
      grid.dataset.realHelp='1';
      const help=document.createElement('div');
      help.className='upgrade-help';
      help.textContent='LIVE ITEM EDITOR: use + / - or stars to set current and target forge levels. Optimize reads these values.';
      grid.parentElement?.insertBefore(help,grid);
    }
    $$('.item-card',grid).forEach(enhanceItemCard);
  }

  function simpleDots(input,max,label){
    const wrap=document.createElement('div');wrap.className='click-level-wrap';
    const lab=document.createElement('div');lab.className='click-level-label';lab.textContent=label;
    const row=document.createElement('div');row.className='click-level-row';
    const redraw=()=>{const v=valueOf(input,max);row.innerHTML='';for(let i=0;i<=max;i++){const b=document.createElement('button');b.type='button';b.className='level-dot'+(i>0&&i<=v?' filled':'')+(i===v?' current':'');b.textContent=i===0?'0':'★';b.onclick=()=>{setValue(input,i,max);redraw();};row.appendChild(b)}};
    input.addEventListener('change',redraw);redraw();wrap.append(lab,row);return wrap;
  }

  function enhanceLevelItem(item){
    if(item.dataset.enhanced==='1')return;
    const input=$('input',item); if(!input)return;
    item.dataset.enhanced='1'; item.classList.add('enhanced');
    const max=parseInt(input.max||'10',10)||10;
    const box=document.createElement('div'); box.className='quick-level-box';
    box.appendChild(simpleDots(input,max,'level'));
    item.appendChild(box);
  }

  function enhanceLevels(){
    ['#techGrid','#petsGrid','#mountsGrid'].forEach(sel=>$$(sel+' .level-item').forEach(enhanceLevelItem));
  }

  function run(){mark();enhanceItemOptimizer();enhanceLevels();}
  document.addEventListener('DOMContentLoaded',()=>{run();setTimeout(run,150);setTimeout(run,700)});
  document.addEventListener('click',e=>{
    if(e.target.closest('.nav-item')||e.target.closest('#btnLoadSample')||e.target.closest('#btnImport'))setTimeout(run,120);
  });
})();
