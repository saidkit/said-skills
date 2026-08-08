(function(){
  function $(id){return document.getElementById(id);}
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
  function moveList(d){var it=items();if(!it.length)return;
    var i=-1;for(var x=0;x<it.length;x++){if(it[x].getAttribute('data-id')===CUR){i=x;break;}}
    if(i<0)i=0;else i=Math.max(0,Math.min(it.length-1,i+d));
    setCursor(it[i].getAttribute('data-id'));activate(false);}
  function kpos(cs){for(var x=0;x<cs.length;x++)for(var y=0;y<cs[x].cards.length;y++)
    if(cs[x].cards[y].getAttribute('data-id')===CUR)return {ci:x,ri:y};
    return {ci:-1,ri:-1};}
  function moveKanban(dx,dy){var cs=cols();if(!cs.length)return;var p=kpos(cs);
    if(p.ci<0){for(var x=0;x<cs.length;x++)if(cs[x].cards.length){setCursor(cs[x].cards[0].getAttribute('data-id'));break;}
      return;}
    var ci=p.ci,ri=p.ri;
    if(dx){var nx=ci;while(true){nx+=dx;if(nx<0||nx>=cs.length){nx=ci;break;}if(cs[nx].cards.length)break;}
      ci=nx;ri=Math.min(ri,cs[ci].cards.length-1);}
    if(dy)ri=Math.max(0,Math.min(cs[ci].cards.length-1,ri+dy));
    var c=cs[ci].cards[ri];if(c)setCursor(c.getAttribute('data-id'));}
  function homeEnd(end){if(vw()==='kanban'){var cs=cols();var ci=kpos(cs).ci;
      if(ci<0){for(var x=0;x<cs.length;x++)if(cs[x].cards.length){ci=x;break;}if(ci<0)return;}
      var col=cs[ci];if(!col.cards.length)return;var c=end?col.cards[col.cards.length-1]:col.cards[0];
      setCursor(c.getAttribute('data-id'));}
    else{var it=items();if(!it.length)return;var el=end?it[it.length-1]:it[0];
      setCursor(el.getAttribute('data-id'));activate(false);}}

  window.toggleHelp=function(f){var h=$('help');if(!h)return;
    h.classList.toggle('open',(f===undefined)?!h.classList.contains('open'):!!f);};
  document.addEventListener('click',function(e){var h=$('help');if(!h||!h.classList.contains('open'))return;
    if(h.contains(e.target)||(e.target.closest&&e.target.closest('#kbdBtn')))return;h.classList.remove('open');});

  function isType(e){var t=e.target;if(!t)return false;var n=(t.tagName||'').toLowerCase();
    return n==='input'||n==='textarea'||n==='select'||t.isContentEditable;}

  document.addEventListener('keydown',function(e){
    if(e.defaultPrevented||e.metaKey||e.ctrlKey||e.altKey)return;
    if(isType(e))return;
    var k=e.key;
    if(k==='?'){window.toggleHelp();e.preventDefault();return;}
    if(k==='Escape'){
      var h=$('help');if(h&&h.classList.contains('open')){window.toggleHelp(false);e.preventDefault();return;}
      if(drawerOpen()){closeDrawer();e.preventDefault();return;}
      if(inDetail()){focusCursor();e.preventDefault();return;}
      if(CUR){clearCursor();e.preventDefault();return;}
      return;}
    var down=(k==='ArrowDown'||k==='j'),up=(k==='ArrowUp'||k==='k'),
        left=(k==='ArrowLeft'||k==='h'),right=(k==='ArrowRight'||k==='l');
    if(vw()==='kanban'){
      if(inDrawer()){if(left){e.preventDefault();closeDrawer();}return;}  // drawer caught the keyboard: ↑↓ scroll its content, ←/Esc return to the board
      if(up||down){e.preventDefault();moveKanban(0,down?1:-1);return;}  // moveKanban self-lands on first card when no cursor (no double-jump)
      if(left||right){e.preventDefault();moveKanban(right?1:-1,0);return;}
      if(k==='Home'||k==='End'){e.preventDefault();if(!ensureCursor())return;homeEnd(k==='End');return;}
      if(k==='Enter'){if(!onBoard())return;e.preventDefault();if(!ensureCursor())return;activate(true);return;}
    }else{
      if(inDetail()){if(left){e.preventDefault();focusCursor();}return;}
      if(up||down){e.preventDefault();moveList(down?1:-1);return;}
      if(k==='Home'||k==='End'){e.preventDefault();homeEnd(k==='End');return;}
      if(right||k==='Enter'){if(k==='Enter'&&!onBoard())return;e.preventDefault();if(!ensureCursor())return;activate(true);focusDetail();return;}
    }
  });

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
    if(v==='kanban'){var kk=$('kanban');if(kk)htmx.trigger(kk,'refresh');}else htmx.trigger('#roster','refresh');}
  window.refreshVisible=refreshVisible;
  window.setView=function(btn){var m=btn.getAttribute('data-view');document.body.setAttribute('data-view',m);localStorage.setItem('sb-view',m);
    document.querySelectorAll('.vtoggle .btn').forEach(function(b){b.classList.toggle('btn-active',b.getAttribute('data-view')===m);});
    document.body.classList.remove('drawer-open');refreshVisible();
    setTimeout(function(){if(CUR&&byId(CUR))paint();else CUR=null;},80);};
  window.toggleHideClosed=function(cb){var k=$('kanban');if(k)k.classList.toggle('hide-closed',cb.checked);
    if(CUR&&!vis(byId(CUR)))clearCursor();};

  document.addEventListener('htmx:afterSwap',function(e){var t=e.target;if(!t)return;
    if(t.id==='roster'||t.id==='kanban'){
      if(window.__sel){var s=t.querySelector('[data-id="'+cssEsc(window.__sel)+'"]');if(s)s.classList.add('selected');}
      if(CUR){var c=t.querySelector('[data-id="'+cssEsc(CUR)+'"]');if(c){c.classList.add('cursor');if(FOC)c.focus({preventScroll:true});}}
    }
    if(t.querySelector){var ds=t.querySelector('.d-tasks');if(ds&&window.__tfilter)applyTF(ds,window.__tfilter);}});

  setInterval(refreshVisible,5000);
  apply(localStorage.getItem('sb-theme')||(sysDark()?'dark':'light'));
  var sv=localStorage.getItem('sb-view')||'list';document.body.setAttribute('data-view',sv);
  document.querySelectorAll('.vtoggle .btn').forEach(function(b){b.classList.toggle('btn-active',b.getAttribute('data-view')===sv);});
})();
