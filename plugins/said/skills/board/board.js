(function(){
  function $(id){return document.getElementById(id);}
  // Global loading indicator: the header logo ticks (45° steps, see board.css) while a request is in
  // flight — but ONLY for a genuinely slow load (a fresh derive / manual refresh). Instant cached
  // navigation must not flash: a short delay before showing skips anything that finishes quickly, and a
  // minimum visible span once shown keeps it from blinking off. A pending counter spans concurrent requests.
  (function(){
    // shown starts true when the shell shipped <body class="loading"> (the initial full-load tick).
    var inflight=0, shown=document.body.classList.contains('sb-loading'),
        showT=null, hideT=null, shownAt=shown?Date.now():0, DELAY=160, MIN=520;
    function on(){shown=true;shownAt=Date.now();document.body.classList.add('sb-loading');}
    function off(){shown=false;document.body.classList.remove('sb-loading');}
    document.addEventListener('htmx:beforeRequest',function(){
      if(++inflight===1){ if(hideT){clearTimeout(hideT);hideT=null;}
        if(!shown&&!showT) showT=setTimeout(function(){showT=null; if(inflight>0)on();}, DELAY); }
    });
    document.addEventListener('htmx:afterRequest',function(){
      if((inflight=inflight>0?inflight-1:0)===0){
        window.__fresh=false;                                      // initial full-load fresh flag is spent -> later nav reuses the cache
        if(showT){clearTimeout(showT);showT=null;}                 // finished before DELAY -> never shown -> no flash
        if(shown){var left=MIN-(Date.now()-shownAt); hideT=setTimeout(off, left>0?left:0);}
      }
    });
  })();
  function sysDark(){return window.matchMedia&&matchMedia('(prefers-color-scheme:dark)').matches;}
  function cssEsc(s){return (window.CSS&&CSS.escape)?CSS.escape(String(s)):String(s).replace(/[^a-zA-Z0-9_-]/g,'\\$&');}
  function apply(t){document.documentElement.setAttribute('data-theme',t);
    var b=$('themeBtn');if(b){b.textContent=(t==='dark'?'\u2600\ufe0f':'\ud83c\udf19');b.title='Theme: '+t;}}
  window.cycleTheme=function(){var t=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';
    localStorage.setItem('sb-theme',t);apply(t);};

  // ---------- keyboard cursor (position) vs selection (opened feature) ----------
  var CUR=null,FOC=false,actT=null;
  function vw(){return document.body.getAttribute('data-view')||'list';}
  function box(){return vw()==='kanban'?$('kanban'):$('roster');}
  function itemSel(){return vw()==='kanban'?'.kcard':'.row';}
  function vis(el){return !!el&&el.offsetParent!==null;}
  function byId(id){if(!id)return null;var b=box();return b?b.querySelector('[data-id="'+cssEsc(id)+'"]'):null;}
  function items(){var b=box();if(!b)return [];
    return Array.prototype.slice.call(b.querySelectorAll(itemSel())).filter(vis);}
  function cols(){var out=[],ks=document.querySelectorAll('#kanban .kcol');
    for(var i=0;i<ks.length;i++){if(!vis(ks[i]))continue;
      out.push({el:ks[i],cards:Array.prototype.slice.call(ks[i].querySelectorAll('.kcard')).filter(vis)});}
    return out;}
  function paint(){var old=document.querySelectorAll('.row.cursor,.kcard.cursor');
    for(var i=0;i<old.length;i++)old[i].classList.remove('cursor');
    var el=byId(CUR);if(el)el.classList.add('cursor');return el;}
  function setCursor(id,opt){CUR=id;var el=paint();
    if(el){el.scrollIntoView({block:'nearest'});
      if(!(opt&&opt.noFocus)){el.focus({preventScroll:true});FOC=true;}}
    return el;}
  function focusCursor(){if(!CUR&&window.__sel)CUR=window.__sel;var el=byId(CUR);
    if(el){el.classList.add('cursor');el.focus({preventScroll:true});FOC=true;el.scrollIntoView({block:'nearest'});}return el;}
  function clearCursor(){CUR=null;FOC=false;var old=document.querySelectorAll('.row.cursor,.kcard.cursor');
    for(var i=0;i<old.length;i++)old[i].classList.remove('cursor');
    if(document.activeElement&&document.activeElement.blur)document.activeElement.blur();}
  function firstId(){var it=items();return it.length?it[0].getAttribute('data-id'):null;}
  function ensureCursor(){if(CUR&&byId(CUR))return true;
    var id=(window.__sel&&byId(window.__sel))?window.__sel:firstId();if(id){setCursor(id);return true;}return false;}
  function activate(now){if(actT){clearTimeout(actT);actT=null;}
    if(now){var e=byId(CUR);if(e)e.click();}
    else actT=setTimeout(function(){var e=byId(CUR);if(e)e.click();},110);}

  // ---------- selection (what the detail/drawer shows) ----------
  function markSel(id){window.__sel=id;
    var s=document.querySelectorAll('.row.selected,.kcard.selected');for(var i=0;i<s.length;i++)s[i].classList.remove('selected');
    var el=byId(id);if(el)el.classList.add('selected');}
  window.selectRow=function(el){var id=el.getAttribute('data-id');markSel(id);CUR=id;paint();};
  window.openDrawer=function(card){var id=card.getAttribute('data-id');markSel(id);CUR=id;paint();document.body.classList.add('drawer-open');
    var dc=$('drawer-content');if(dc){dc.setAttribute('tabindex','-1');dc.focus({preventScroll:true});FOC=false;}};  // drawer catches the keyboard

  function drawerOpen(){return document.body.classList.contains('drawer-open');}
  function closeDrawer(){document.body.classList.remove('drawer-open');if(vw()==='kanban')focusCursor();}
  window.closeDrawer=closeDrawer;
  function inDetail(){var d=$('detail');return !!(d&&d.contains(document.activeElement));}
  function focusDetail(){var d=$('detail');if(!d)return;d.setAttribute('tabindex','-1');d.focus({preventScroll:true});FOC=false;}
  function onBoard(){var a=document.activeElement;  // Enter is board-only; never hijack a focused header/drawer control
    if(!a||a===document.body)return true;
    if(a.classList&&(a.classList.contains('row')||a.classList.contains('kcard')))return true;
    var d=$('detail');return !!(d&&d.contains(a));}
  function inDrawer(){var d=$('drawer');return drawerOpen()&&!!(d&&d.contains(document.activeElement));}

  // ---------- movement ----------
  function kpos(cs){for(var x=0;x<cs.length;x++)for(var y=0;y<cs[x].cards.length;y++)
    if(cs[x].cards[y].getAttribute('data-id')===CUR)return {ci:x,ri:y};
    return {ci:-1,ri:-1};}

  window.toggleHelp=function(f){var h=$('help');if(!h)return;
    h.classList.toggle('open',(f===undefined)?!h.classList.contains('open'):!!f);};
  document.addEventListener('click',function(e){var h=$('help');if(!h||!h.classList.contains('open'))return;
    if(h.contains(e.target)||(e.target.closest&&e.target.closest('#kbdBtn')))return;h.classList.remove('open');});

  // the shared namespace each board's own script reads: one cursor, one selection, one view
  var B=window.saidBoard={$:$,vw:vw,items:items,cols:cols,kpos:kpos,cur:function(){return CUR;},setCursor:setCursor,
    activate:activate,ensureCursor:ensureCursor,focusCursor:focusCursor,clearCursor:clearCursor,drawerOpen:drawerOpen,
    closeDrawer:closeDrawer,inDetail:inDetail,focusDetail:focusDetail,onBoard:onBoard,inDrawer:inDrawer,boards:{},
    board:function(){return document.body.getAttribute('data-board')||'features';}};

  // ---------- tasks / detail (unchanged behavior) ----------
  window.copyNext=function(btn){var d=btn.closest('.d-next');var c=d&&d.querySelector('.nextcmd');if(!c)return;
    if(navigator.clipboard)navigator.clipboard.writeText(c.textContent);
    var o=btn.textContent;btn.textContent='copied \u2713';setTimeout(function(){btn.textContent=o;},1200);};
  window.toggleAll=function(btn){var sec=btn.closest('.d-tasks');if(!sec)return;var open=btn.textContent.indexOf('expand')>=0;
    sec.querySelectorAll('details.task').forEach(function(d){d.open=open;});btn.textContent=open?'collapse all':'expand all';};
  window.__tfilter=null;
  function applyTF(sec,mode){if(!sec)return;sec.setAttribute('data-filter',mode);
    sec.querySelectorAll('.tfilter .btn').forEach(function(b){b.classList.toggle('btn-active',b.getAttribute('data-mode')===mode);});
    var c=sec.querySelector('.tcount');if(c)c.textContent=(mode==='todo'?sec.getAttribute('data-todo'):sec.getAttribute('data-all'));}
  window.setTaskFilter=function(btn){var m=btn.getAttribute('data-mode');window.__tfilter=m;applyTF(btn.closest('.d-tasks'),m);};

  function refreshVisible(){if(!window.htmx)return;var v=vw();
    if(v==='kanban'){var kk=$('kanban');if(kk)htmx.trigger(kk,'refresh');}
    else htmx.trigger('#roster','refresh');}
  refreshVisible=(function(f){return function(){var b=B.board(),o=B.boards[b];if(b!=='features'){if(o&&o.refresh)o.refresh(window.__fresh);return;}f();};})(refreshVisible);
  window.refreshVisible=refreshVisible;
  // Manual refresh: force a live derive (busts the server's short-TTL guard). __fresh is read
  // synchronously by the fragment's hx-vals while htmx.trigger issues the request, then reset.
  window.refreshNow=function(){window.__fresh=true;refreshVisible();window.__fresh=false;};
  // One lane at a time, persisted so a full-page-reload refresh keeps the choice.
  window.setLane=function(sel){localStorage.setItem('sb-lane',sel.value);refreshVisible();};
  function restoreLane(){var ls=$('laneSelect');if(!ls)return;var want=localStorage.getItem('sb-lane'),ok=false;
    for(var i=0;i<ls.options.length;i++){if(ls.options[i].value===want){ok=true;break;}}
    if(ok){if(ls.value!==want){ls.value=want;refreshVisible();}}  // htmx already fired load with the default; re-load the stored lane
    else{localStorage.setItem('sb-lane',ls.value);}}              // no/stale stored lane -> keep the first-declared default
  window.setView=function(btn){var m=btn.getAttribute('data-view');document.body.setAttribute('data-view',m);localStorage.setItem('sb-view',m);
    document.querySelectorAll('.vtoggle .btn').forEach(function(b){b.classList.toggle('btn-active',b.getAttribute('data-view')===m);});
    document.body.classList.remove('drawer-open');refreshVisible();
    setTimeout(function(){if(CUR&&byId(CUR))paint();else CUR=null;},80);};
  window.toggleHideClosed=function(cb){var k=$('kanban');if(k)k.classList.toggle('hide-closed',cb.checked);
    if(CUR&&!vis(byId(CUR)))clearCursor();};
  // ---------- the board switch: one board surface at a time; a board the switch does not show opens features ----------
  function boardNames(){return Array.prototype.map.call(document.querySelectorAll('.board-switch a[data-board]'),function(a){return a.getAttribute('data-board');});}
  function setBoard(b){if(boardNames().indexOf(b)<0)b='features';var feat=b==='features',p=$('boardpane');document.body.setAttribute('data-board',b);
    try{localStorage.setItem('sb-board',b);}catch(e){}
    document.querySelectorAll('.board-switch a[data-board]').forEach(function(a){var on=a.getAttribute('data-board')===b;a.classList.toggle('btn-active',on);if(on)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
    ['listwrap','kanbanwrap'].forEach(function(id){var el=$(id);if(el)el.style.display=feat?'':'none';});
    document.querySelectorAll('.vtoggle,.hz-right .switch').forEach(function(el){el.style.display=feat?'':'none';});
    if(!p&&!feat){p=document.createElement('section');p.id='boardpane';p.className='boardpane';$('main').appendChild(p);}
    if(p){p.style.display=feat?'none':'';p.setAttribute('data-board',b);
      if(!feat){var o=B.boards[b];if(o&&o.show)o.show(p);else p.innerHTML='<div class="empty-state">This board has nothing to show yet.</div>';}}
    var u=new URL(location.href);if(feat)u.searchParams.delete('board');else u.searchParams.set('board',b);
    history.replaceState(null,'',u.pathname+u.search+u.hash);}
  document.addEventListener('htmx:beforeRequest',function(e){var t=e.detail&&e.detail.elt;if(B.board()!=='features'&&t&&(t.id==='roster'||t.id==='kanban')){e.preventDefault();B.skipped=true;}});
  setBoard=(function(f){return function(b){f(b);if(B.board()==='features'&&B.skipped){B.skipped=false;window.refreshNow();}};})(setBoard);
  window.setBoard=setBoard;
  document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('.board-switch a[data-board]');
    if(!a||e.button>0||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();setBoard(a.getAttribute('data-board'));});

  document.addEventListener('htmx:afterSwap',function(e){var t=e.target;if(!t)return;
    if(t.id==='roster'||t.id==='kanban'){
      if(window.__sel){var s=t.querySelector('[data-id="'+cssEsc(window.__sel)+'"]');if(s)s.classList.add('selected');}
      if(CUR){var c=t.querySelector('[data-id="'+cssEsc(CUR)+'"]');if(c){c.classList.add('cursor');if(FOC)c.focus({preventScroll:true});}}
    }
    if(t.querySelector){var ds=t.querySelector('.d-tasks');if(ds&&window.__tfilter)applyTF(ds,window.__tfilter);}});

  // ---------- local writes (only present when the board was started connected) ----------
  // No token, no network call: these post to the board's own origin and write local files.
  // The custom header + JSON body force a preflight, which the server answers for nobody.
  function csrf(){var m=document.querySelector('meta[name="said-board-csrf"]');return m?m.content:'';}
  function say(form,msg,err){var s=form.querySelector('.bl-msg');if(!s)return;
    s.textContent=msg;s.classList.toggle('err',!!err);
    if(!err)setTimeout(function(){if(s.textContent===msg)s.textContent='';},2400);}
  function post(path,payload){
    return fetch(path,{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json','X-Said-Board':'1','X-Said-Board-Csrf':csrf()},
      body:JSON.stringify(payload)}).then(function(r){return r.json().catch(function(){return {ok:false,error:'bad response'};});});}
  window.saveConnect=function(form){var v=(form.elements.app.value||'').trim();
    post('/connect',{app:v}).then(function(r){
      say(form,r.ok?'saved, reload to apply':(r.error||'could not save'),!r.ok);
    }).catch(function(){say(form,'could not save',true);});
    return false;};

  // No auto-poll: status refreshes on a full page load and via the header refresh button only.
  apply(localStorage.getItem('sb-theme')||(sysDark()?'dark':'light'));
  // a stored view whose toggle is not on this page (a view the board no longer has) falls back
  var sv=localStorage.getItem('sb-view')||'list';
  if(!document.querySelector('.vtoggle .btn[data-view="'+cssEsc(sv)+'"]'))sv='list';
  document.body.setAttribute('data-view',sv);
  document.querySelectorAll('.vtoggle .btn').forEach(function(b){b.classList.toggle('btn-active',b.getAttribute('data-view')===sv);});
  restoreLane();
  // the board to open: the URL's ?board=, else the stored one; a feature link in the URL fragment opens features
  var wb=null;try{wb=new URLSearchParams(location.search).get('board')||localStorage.getItem('sb-board');}catch(e){}
  setBoard(/^#[A-Za-z]+-\d/.test(location.hash)?'features':(wb||'features'));
  // A feature named in the URL fragment (`#PROJ-01`) opens its deep-dive once the list has loaded:
  // the id regex gates the lookup, the row's own click opens it, and an unknown id does nothing.
  (function(){var id='';try{id=decodeURIComponent((location.hash||'').slice(1));}catch(e){return;}
    if(!/^[A-Za-z]+-\d+(?:-[A-Za-z0-9]+)*$/.test(id))return;
    // on a multi-lane board, select the lane that holds this exact id first (a lane switch re-loads the lists);
    // the selected lane is kept when it holds the id, and an id no lane holds leaves the lane alone
    var ls=$('laneSelect'),holds=function(o){return (o.getAttribute('data-ids')||'').split(',').indexOf(id)>=0;};
    if(ls&&ls.selectedIndex>=0&&!holds(ls.options[ls.selectedIndex]))for(var i=0;i<ls.options.length;i++){var o=ls.options[i];
      if(holds(o)){ls.value=o.value;setLane(ls);break;}}
    // a swap of the hidden view, or of the default lane before the stored one, cannot hold the row yet:
    // keep listening until the row is found, at most a few list swaps; click once htmx has settled the swap
    // (on afterSwap the row's hx-get is not bound yet, so its click selects without loading the deep-dive)
    // the settled swap must be the one holding the row: another list's settle can land before the row's own
    var n=0;function onSwap(e){var t=e.target;if(!t||(t.id!=='roster'&&t.id!=='kanban'))return;
      var el=byId(id);if(el&&t.contains(el)){document.removeEventListener('htmx:afterSettle',onSwap);el.click();return;}
      if(++n>=4)document.removeEventListener('htmx:afterSettle',onSwap);}
    document.addEventListener('htmx:afterSettle',onSwap);})();
})();
