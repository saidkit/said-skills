// said:board, the shared client of the backlog and todo boards: the filter bars, the cursor and its keys, the side
// panel (the page's drawer) and the header status line. Each board's own script loads its fragment and calls in.
// Every string shown comes from the server's fragment; this script only moves, hides and focuses what is there.
(function(){
  var B=window.saidBoard;if(!B)return;
  var L=B.lists={},doc=window.document;
  function $(id){return doc.getElementById(id);}
  function list(){return B.board()==='backlog'||B.board()==='todo';}
  function pane(){var p=$('boardpane');return p&&list()&&p.getAttribute('data-board')===B.board()?p:null;}
  // the boards' stylesheet, linked once (the shell's own stylesheet stays as it is)
  L.css=function(){if($('lists-css'))return;var l=doc.createElement('link');l.id='lists-css';l.rel='stylesheet';l.href='/boards/lists.css';doc.head.appendChild(l);};
  L.css();

  // ---------- the header status line: the shown board's own; the features stamp comes back with features ----------
  var saved=null;
  L.status=function(p){var s=p&&p.querySelector('[data-status]'),u=$('updated');if(!s||!u)return;
    var d=new Date(),t=('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2)+':'+('0'+d.getSeconds()).slice(-2);
    u.textContent=s.getAttribute('data-status')+', read '+t;};
  var last=B.board();
  new MutationObserver(function(){var b=B.board();if(b===last)return;var u=$('updated');
    if(last==='features'&&u)saved=u.innerHTML;
    if(b==='features'&&u&&saved!==null){u.innerHTML=saved;}
    if(b!=='features'&&u&&last==='features')u.textContent='reading the '+b+' files';
    last=b;if(B.drawerOpen())B.closeDrawer();}).observe(doc.body,{attributes:true,attributeFilter:['data-board']});

  // ---------- filters (backlog: chips, search, show closed; todo: search) ----------
  var F={};  // per board: {sets:{area,stage,rec,prio}, q, closed}
  function st(b){if(!F[b])F[b]={sets:{area:{},stage:{},rec:{},prio:{}},q:'',closed:false};return F[b];}
  function empty(o){for(var k in o)return false;return true;}
  function cardPass(li,S){
    if(!S.closed&&li.getAttribute('data-closed')==='1')return false;
    var m={area:li.getAttribute('data-area'),stage:li.getAttribute('data-stage'),rec:li.getAttribute('data-rec'),prio:li.getAttribute('data-priority')||'none'};
    for(var k in S.sets){if(!empty(S.sets[k])&&!S.sets[k][m[k]])return false;}
    return !S.q||(li.getAttribute('data-q')||'').indexOf(S.q)>=0;}
  L.apply=function(p){if(!p)return;var S=st(B.board());
    var q=p.querySelector('.lb-q');if(q&&q.value!==S.q)q.value=S.q;
    var c=p.querySelector('.lb-closed');if(c)c.checked=S.closed;
    p.querySelectorAll('.lb-chip[data-f]').forEach(function(b){var set=S.sets[b.getAttribute('data-f')];
      b.setAttribute('aria-pressed',empty(set)||set[b.getAttribute('data-v')]?'true':'false');});
    var shown=0,total=0;
    p.querySelectorAll('.lb-group').forEach(function(g){var n=0,all=g.querySelectorAll('li.bl-row');
      all.forEach(function(li){var ok=cardPass(li,S);li.hidden=!ok;if(ok)n++;});
      total+=all.length;shown+=n;var cn=g.querySelector('.lb-count');if(cn)cn.textContent=n+' of '+cn.getAttribute('data-of');g.hidden=!n;});
    if(p.querySelector('.td-list')){var rows=p.querySelectorAll('li.td-row');total=0;shown=0;
      rows.forEach(function(li){var ok=!S.q||(li.getAttribute('data-q')||'').indexOf(S.q)>=0;li.hidden=!ok;
        if(!li.classList.contains('td-context')){total++;if(ok)shown++;}});
      p.querySelectorAll('.td-group').forEach(function(d){var any=d.querySelector('li.td-row:not([hidden])');d.hidden=!any;if(S.q&&any)d.open=true;});}
    var e=p.querySelector('.lb-empty');if(e)e.hidden=!!shown;
    var f=p.querySelector('.lb-foot');if(f&&p.querySelector('.lb-group'))f.textContent=shown+' of '+total+' entries shown.';
    else if(f&&S.q)f.textContent=shown+' of '+total+' lines match the filter.';};
  doc.addEventListener('click',function(e){var p=pane();if(!p||!e.target.closest)return;
    var b=e.target.closest('.lb-chip[data-f]');var S=st(B.board());
    if(b&&p.contains(b)){var set=S.sets[b.getAttribute('data-f')],v=b.getAttribute('data-v');if(set[v])delete set[v];else set[v]=1;L.apply(p);return;}
    if(e.target.closest('.lb-reset')&&p.contains(e.target)){S.sets={area:{},stage:{},rec:{},prio:{}};S.q='';S.closed=false;L.apply(p);return;}});
  doc.addEventListener('input',function(e){var p=pane();if(!p||!e.target.classList)return;
    if(e.target.classList.contains('lb-q')){st(B.board()).q=e.target.value.toLowerCase();L.apply(p);}});
  doc.addEventListener('change',function(e){var p=pane();if(!p||!e.target.classList)return;
    if(e.target.classList.contains('lb-closed')){st(B.board()).closed=e.target.checked;L.apply(p);}});

  // ---------- the cursor and the side panel ----------
  var CUR=null;
  function items(){var p=pane();if(!p)return [];
    return Array.prototype.filter.call(p.querySelectorAll('li.bl-row,li.td-row:not(.td-context)'),function(li){return !li.hidden&&!li.closest('details:not([open]),[hidden]')&&li.getClientRects().length>0;});}
  function byKey(k){var p=pane();if(!p||!k)return null;var all=p.querySelectorAll('li[data-key]');
    for(var i=0;i<all.length;i++)if(all[i].getAttribute('data-key')===k)return all[i];return null;}
  function paint(){var p=pane();if(!p)return null;p.querySelectorAll('li.cursor').forEach(function(x){x.classList.remove('cursor');});
    var li=byKey(CUR);if(li)li.classList.add('cursor');return li;}
  function cursor(k,focus){CUR=k;var li=paint();if(li){li.scrollIntoView({block:'nearest'});if(focus!==false)li.focus({preventScroll:true});}return li;}
  L.repaint=function(){var p=pane();if(!p)return;var sel=p.querySelectorAll('li.sel');sel.forEach(function(x){x.classList.remove('sel');});
    if(CUR&&byKey(CUR)){paint();}else CUR=null;};
  L.open=function(li){var t=li&&li.querySelector('template.lb-detail'),dc=$('drawer-content');if(!t||!dc)return;
    var p=pane();if(p)p.querySelectorAll('li.sel').forEach(function(x){x.classList.remove('sel');});li.classList.add('sel');cursor(li.getAttribute('data-key'),false);
    var w=doc.createElement('div');w.className='lb-side';w.setAttribute('data-key',li.getAttribute('data-key'));w.setAttribute('data-line',li.getAttribute('data-line'));
    w.appendChild(t.content.cloneNode(true));dc.innerHTML='';dc.appendChild(w);
    doc.body.classList.add('drawer-open');dc.setAttribute('tabindex','-1');dc.focus({preventScroll:true});};
  function move(d){var it=items();if(!it.length)return;var i=-1;
    for(var x=0;x<it.length;x++)if(it[x].getAttribute('data-key')===CUR){i=x;break;}
    i=i<0?0:Math.max(0,Math.min(it.length-1,i+d));cursor(it[i].getAttribute('data-key'));}
  doc.addEventListener('click',function(e){var p=pane();if(!p||!e.target.closest)return;
    var r=e.target.closest('[data-open]');if(r&&$('drawer').contains(r)){var li=byKey(r.getAttribute('data-open'));if(li){var S=st(B.board());if(li.hidden){S.sets={area:{},stage:{},rec:{},prio:{}};S.q='';S.closed=true;L.apply(p);}L.open(li);}return;}
    if(e.target.closest('button,a,input,label,summary,details.td-subs'))return;
    var li=e.target.closest('li.bl-row,li.td-row');if(li&&p.contains(li))L.open(li);});
  function typing(t){var n=(t&&t.tagName||'').toLowerCase();return n==='input'||n==='textarea'||n==='select'||(t&&t.isContentEditable);}
  doc.addEventListener('keydown',function(e){if(!list()||e.defaultPrevented||e.metaKey||e.ctrlKey||e.altKey||typing(e.target))return;
    var k=e.key,h=$('help');
    if(k==='?'){window.toggleHelp();e.preventDefault();return;}
    if(k==='Escape'){if(h&&h.classList.contains('open')){window.toggleHelp(false);e.preventDefault();return;}
      if(B.drawerOpen()){B.closeDrawer();var li=byKey(CUR);if(li)li.focus({preventScroll:true});e.preventDefault();return;}
      if(CUR){CUR=null;paint();if(doc.activeElement&&doc.activeElement.blur)doc.activeElement.blur();e.preventDefault();}return;}
    if(B.drawerOpen()&&$('drawer').contains(doc.activeElement)){if(k==='ArrowLeft'||k==='h'){B.closeDrawer();var c=byKey(CUR);if(c)c.focus({preventScroll:true});e.preventDefault();}return;}
    var a=doc.activeElement,onList=!a||a===doc.body||(a.matches&&a.matches('li.bl-row,li.td-row'));
    if(k==='ArrowDown'||k==='j'){e.preventDefault();move(1);return;}
    if(k==='ArrowUp'||k==='k'){e.preventDefault();move(-1);return;}
    if(k==='Home'||k==='End'){var it=items();if(it.length){e.preventDefault();cursor(it[k==='End'?it.length-1:0].getAttribute('data-key'));}return;}
    if((k==='Enter'||k===' '||k==='ArrowRight'||k==='l')&&onList){var li2=byKey(CUR)||items()[0];if(li2){e.preventDefault();L.open(li2);}}});

  // ---------- the row writes: the same two posts from a card or from the side panel ----------
  L.post=function(path,holder,extra,done){var m=doc.querySelector('meta[name="said-board-csrf"]'),
      body={key:holder.getAttribute('data-key'),line:+holder.getAttribute('data-line')},msg=holder.querySelector('.row-msg');
    for(var k in extra)body[k]=extra[k];
    fetch(path,{method:'POST',credentials:'same-origin',body:JSON.stringify(body),
      headers:{'Content-Type':'application/json','X-Said-Board':'1','X-Said-Board-Csrf':m?m.content:''}})
      .then(function(r){return r.json().catch(function(){return {ok:false,error:'HTTP '+r.status};});})
      .then(function(j){if(j&&j.ok)done();else if(msg)msg.textContent=(j&&j.error)||'refused';})
      .catch(function(){if(msg)msg.textContent='the board did not answer';});};
  L.wclick=function(e,base,lane,reload){var b=e.target.closest&&e.target.closest('[data-w]');if(!b)return false;
    var p=pane(),side=$('drawer');if(!(p&&p.contains(b))&&!(side&&side.contains(b)))return false;
    var h=b.closest('[data-key]');if(!h)return true;var x=lane?{lane:lane}:{};
    if(b.getAttribute('data-w')==='priority')x.letter=b.getAttribute('data-letter');else x.to=+b.getAttribute('data-to');
    e.stopPropagation();L.post(base+b.getAttribute('data-w'),h,x,function(){if(side&&side.contains(b))B.closeDrawer();reload();});return true;};
})();
