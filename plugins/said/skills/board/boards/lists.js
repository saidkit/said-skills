// said:board, the shared client of the backlog and todo boards: the toolbar and filter row, the folds, the cursor and
// its keys, the priority picker, the drags, the sheet (the page's drawer) and the header status line. Each board's own
// script loads its fragment and calls in. Every string shown comes from the server's fragment; this script only moves,
// hides and focuses what is there, and posts the two writes the server already has (priority and order); the sheet's line editor is built here for a board to use.
(function(){
  var B=window.saidBoard;if(!B)return;
  var L=B.lists={cfg:{}},doc=window.document;
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
    last=b;closePop();if(B.drawerOpen())B.closeDrawer();}).observe(doc.body,{attributes:true,attributeFilter:['data-board']});

  // ---------- filters: the backlog's toolbar and filter row, the todo's search ----------
  var F={};  // per board: {sec, cs, done, sets:{prio,stage}, q}
  function st(b){if(!F[b])F[b]={sec:'',cs:'all',done:b==='todo',sets:{prio:{},stage:{},state:{}},q:'',pin:{}};return F[b];}  // the todo board shows done lines, its state chips filter them
  function empty(o){for(var k in o)return false;return true;}
  function terms(q){return q.toLowerCase().split(/\s+/).filter(Boolean);}
  function view(p){var g=p.querySelector('.bl-groups');return g?g.getAttribute('data-by'):'';}
  function cardPass(li,S,v){
    if(li.classList.contains('td-context')||S.pin[li.getAttribute('data-key')])return true;  // a card just added shows in place until a filter changes
    if(!S.done&&li.getAttribute('data-done')==='1')return false;
    if(S.cs==='formed'&&li.getAttribute('data-formed')!=='1')return false;
    if(S.sec&&v!=='section'&&li.getAttribute('data-section')!==S.sec)return false;
    if(!empty(S.sets.prio)&&!S.sets.prio[li.getAttribute('data-priority')||'none'])return false;
    if(!empty(S.sets.stage)&&!S.sets.stage[li.getAttribute('data-stage')])return false;
    if(!empty(S.sets.state)&&!S.sets.state[li.getAttribute('data-state')])return false;
    var q=li.getAttribute('data-q')||'';return terms(S.q).every(function(t){return q.indexOf(t)>=0;});}
  function live(li,S){return S.done||li.getAttribute('data-done')!=='1';}
  function each(p,sel,f){Array.prototype.forEach.call(p.querySelectorAll(sel),f);}
  function setCounts(p,S,cards){
    each(p,'.tn[data-n]',function(e){var s=e.getAttribute('data-n'),n=0;cards.forEach(function(li){if(live(li,S)&&(!s||li.getAttribute('data-section')===s))n++;});e.textContent=n;});
    each(p,'.chip[data-set]',function(b){var set=b.getAttribute('data-set'),v=b.getAttribute('data-v'),n=0;
      cards.forEach(function(li){var x=set==='prio'?(li.getAttribute('data-priority')||'none'):li.getAttribute('data-'+set);if(live(li,S)&&x===v)n++;});
      b.querySelector('.n').textContent=n;});}
  var ROW='li.bl-row,li.td-row',ROWV='li.bl-row:not([hidden]),li.td-row:not([hidden])';
  function applyBacklog(p,S){
    var v=view(p),cards=Array.prototype.slice.call(p.querySelectorAll(ROW)),shown=0;
    var q=p.querySelector('.bb-q');if(q&&q.value!==S.q)q.value=S.q;
    var dn=p.querySelector('.bb-done');if(dn)dn.checked=S.done;
    each(p,'[data-sec]',function(b){b.classList.toggle('btn-active',b.getAttribute('data-sec')===S.sec);});
    each(p,'[data-cs]',function(b){b.classList.toggle('btn-active',b.getAttribute('data-cs')===S.cs);});
    each(p,'.chip[data-set]',function(b){var set=S.sets[b.getAttribute('data-set')],on=!!set[b.getAttribute('data-v')];
      b.classList.toggle('sel',on);b.setAttribute('aria-pressed',empty(set)||on?'true':'false');});
    var cl=p.querySelector('.bb-clear');if(cl)cl.disabled=!(S.q||S.sec||!empty(S.sets.prio)||!empty(S.sets.stage)||!empty(S.sets.state));
    cards.forEach(function(li){var ok=cardPass(li,S,v);li.hidden=!ok;if(ok)shown++;});
    each(p,'.pdrop',function(g){g.hidden=!empty(S.sets.prio)&&!S.sets.prio[g.getAttribute('data-drop')];});
    var narrowed=!!(S.q||S.sec||S.cs==='formed'||!empty(S.sets.prio)||!empty(S.sets.stage)||!empty(S.sets.state));
    // a heading stays while nothing narrows the cards, or while its quick-add field is open
    each(p,'.grp,.topic,.sect:not(.pdrop)',function(g){g.hidden=!g.querySelector(ROWV)&&!(!g.classList.contains('sect')&&(!narrowed||g.querySelector('.qa-row')));});
    each(p,'.hd [data-of],.sect>h2 [data-of]',function(c){var blk=c.closest('.grp,.topic,.sect'),n=blk.querySelectorAll(ROWV).length,of=c.getAttribute('data-of');
      c.textContent=c.tagName==='SMALL'?n:n+' of '+of;});
    each(p,'.dzone',function(z){z.hidden=!!z.parentNode.querySelector(ROWV);});
    setCounts(p,S,cards);
    var e=p.querySelector('.bb-empty');if(e)e.hidden=!!shown;
    var n=p.querySelector('.bb-n');if(n)n.textContent=shown;}
  L.apply=function(p){if(!p)return;if(p.querySelector('.bb')){applyFolds(p);applyBacklog(p,st(B.board()));}};

  // ---------- folds: a heading folds its block on a small box; the state outlives a re-read ----------
  var COLL={};
  function applyFolds(p){each(p,'.hd[data-ck]',function(h){var c=!!COLL[h.getAttribute('data-ck')];h.parentNode.classList.toggle('closed',c);
    h.setAttribute('role','button');h.tabIndex=0;h.setAttribute('aria-expanded',c?'false':'true');});}
  L.unfold=function(k){delete COLL[k];};
  function fold(h){var k=h.getAttribute('data-ck');COLL[k]=!COLL[k];applyFolds(h.closest('.bb'));}

  doc.addEventListener('click',function(e){var p=pane(),t=e.target;if(!p||!t.closest||!p.querySelector('.bb')||!p.contains(t))return;
    var S=st(B.board()),b;
    if(t.closest('.qa'))return;
    if(t.closest('[data-sec],[data-cs],.chip[data-set],.bb-clear'))S.pin={};
    if((b=t.closest('[data-sec]'))){S.sec=b.getAttribute('data-sec');L.apply(p);return;}
    if((b=t.closest('[data-cs]'))){S.cs=b.getAttribute('data-cs');L.apply(p);return;}
    if((b=t.closest('.chip[data-set]'))){var set=S.sets[b.getAttribute('data-set')],v=b.getAttribute('data-v');if(set[v])delete set[v];else set[v]=1;L.apply(p);return;}
    if(t.closest('.bb-clear')){S.q='';S.sec='';S.sets={prio:{},stage:{},state:{}};L.apply(p);return;}
    if((b=t.closest('.hd[data-ck]')))fold(b);});
  doc.addEventListener('keydown',function(e){var t=e.target;if((e.key==='Enter'||e.key===' ')&&t.classList&&t.classList.contains('hd')){e.preventDefault();fold(t);}});
  doc.addEventListener('input',function(e){var p=pane(),t=e.target;if(!p||!t.classList)return;
    if(t.classList.contains('bb-q')){st(B.board()).q=t.value;st(B.board()).pin={};L.apply(p);}});
  doc.addEventListener('change',function(e){var p=pane(),t=e.target;if(!p||!t.classList)return;
    if(t.classList.contains('bb-done')){st(B.board()).done=t.checked;st(B.board()).pin={};L.apply(p);}});

  // ---------- the cursor and the sheet ----------
  var CUR=null;
  function items(){var p=pane();if(!p)return [];
    return Array.prototype.filter.call(p.querySelectorAll('li.bl-row,li.td-row:not(.td-context)'),function(li){return !li.hidden&&!li.closest('details:not([open]),[hidden],.closed')&&li.getClientRects().length>0;});}
  function byKey(k){var p=pane();if(!p||!k)return null;var all=p.querySelectorAll('li[data-key]');
    for(var i=0;i<all.length;i++)if(all[i].getAttribute('data-key')===k)return all[i];return null;}
  function byLine(n){var p=pane();if(!p)return null;var all=p.querySelectorAll('li[data-line]');
    for(var i=0;i<all.length;i++)if(all[i].getAttribute('data-line')===String(n))return all[i];return null;}
  function paint(){var p=pane();if(!p)return null;p.querySelectorAll('li.cursor').forEach(function(x){x.classList.remove('cursor');});
    var li=byKey(CUR);if(li)li.classList.add('cursor');return li;}
  function cursor(k,focus){CUR=k;var li=paint();if(li){li.scrollIntoView({block:'nearest'});if(focus!==false)li.focus({preventScroll:true});}return li;}
  // a write keeps the card the operator was on: by line after a priority write, by key after a move
  L.keep=null;
  L.pin=function(k){st(B.board()).pin[k]=1;};
  L.cursorLi=function(){return byKey(CUR);};
  L.repaint=function(){var p=pane();if(!p)return;var sel=p.querySelectorAll('li.sel');sel.forEach(function(x){x.classList.remove('sel');});
    var k=L.keep;L.keep=null;
    if(k){var li=k.line?byLine(k.line):byKey(k.key);if(li){CUR=li.getAttribute('data-key');paint();if(k.sheet)L.open(li);return;}}
    if(CUR&&byKey(CUR)){paint();}else CUR=null;};
  L.open=function(li){var t=li&&li.querySelector('template.lb-detail'),dc=$('drawer-content');if(!t||!dc)return;
    var p=pane();if(p)p.querySelectorAll('li.sel').forEach(function(x){x.classList.remove('sel');});li.classList.add('sel');cursor(li.getAttribute('data-key'),false);
    var w=doc.createElement('div');w.className='lb-side';w.setAttribute('data-key',li.getAttribute('data-key'));w.setAttribute('data-line',li.getAttribute('data-line'));
    w.appendChild(t.content.cloneNode(true));if(w.querySelector('.d-head'))w.classList.add('dd');dc.innerHTML='';dc.appendChild(w);
    doc.body.classList.add('drawer-open');dc.setAttribute('tabindex','-1');dc.focus({preventScroll:true});};
  function move(d){var it=items();if(!it.length)return;var i=-1;
    for(var x=0;x<it.length;x++)if(it[x].getAttribute('data-key')===CUR){i=x;break;}
    i=i<0?0:Math.max(0,Math.min(it.length-1,i+d));cursor(it[i].getAttribute('data-key'));}
  doc.addEventListener('click',function(e){var p=pane();if(!p||!e.target.closest)return;
    if(e.target.closest('button,a,input,label,summary,.grip,.pslot,.hd'))return;
    var li=e.target.closest('li.bl-row,li.td-row');if(li&&p.contains(li))L.open(li);});

  // a link inside a sheet to another line of the same board opens that line's sheet
  doc.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('[data-open-key]');if(!a)return;var li=byKey(a.getAttribute('data-open-key'));if(li){e.preventDefault();L.open(li);}});

  // ---------- the writes: the two posts from a card, the picker, a key, the sheet or a drag ----------
  L.post=function(path,holder,extra,done){var m=doc.querySelector('meta[name="said-board-csrf"]'),p=pane(),
      body={key:holder.getAttribute('data-key'),line:+holder.getAttribute('data-line')},msg=holder.querySelector('.row-msg')||(p&&p.querySelector('.bb-msg'));
    for(var k in extra)body[k]=extra[k];
    if(msg)msg.textContent='';
    fetch(path,{method:'POST',credentials:'same-origin',body:JSON.stringify(body),
      headers:{'Content-Type':'application/json','X-Said-Board':'1','X-Said-Board-Csrf':m?m.content:''}})
      .then(function(r){return r.json().catch(function(){return {ok:false,error:'HTTP '+r.status};});})
      .then(function(j){if(j&&j.ok)done();else if(msg)msg.textContent=(j&&j.error)||'refused';})
      .catch(function(){if(msg)msg.textContent='the board did not answer';});};
  L.wclick=function(e,base,lane,reload){var b=e.target.closest&&e.target.closest('[data-w]');if(!b)return false;
    var p=pane(),side=$('drawer');if(!(p&&p.contains(b))&&!(side&&side.contains(b)))return false;
    var h=b.closest('[data-key]');if(!h)return true;var x=lane?{lane:lane}:{};
    if(b.getAttribute('data-w')==='priority')x.letter=b.getAttribute('data-letter');else x.to=+b.getAttribute('data-to');
    var inSide=!!(side&&side.contains(b));
    var byPrio=b.getAttribute('data-w')==='priority';  // a priority write keeps the line, an order write moves it
    e.stopPropagation();L.post(base+b.getAttribute('data-w'),h,x,function(){if(inSide)L.keep=byPrio?{line:+h.getAttribute('data-line'),sheet:true}:{key:h.getAttribute('data-key'),sheet:true};reload();});return true;};
  // the board that takes the picker, the keys and the drags registers how to post and reload
  function cfg(){return L.cfg[B.board()];}
  function setPrio(li,letter){var c=cfg();if(!c||!li)return;
    L.post(c.base+'priority',li,Object.assign({letter:letter||'none'},c.extra?c.extra():{}),function(){L.keep={line:+li.getAttribute('data-line'),sheet:false};c.reload();});}
  function moveTo(li,to){var c=cfg();if(!c)return;L.post(c.base+'order',li,Object.assign({to:to},c.extra?c.extra():{}),function(){L.keep={key:li.getAttribute('data-key'),sheet:false};c.reload();});}

  // ---------- the priority picker: #A #B #C none in place ----------
  var SLOT=null;
  function toSlot(){var s=SLOT;SLOT=null;if(s&&s.isConnected){s.focus({preventScroll:true});return true;}return false;}
  function pop(){var d=$('ppop');if(!d){d=doc.createElement('div');d.id='ppop';d.setAttribute('role','menu');d.setAttribute('aria-label','set priority');doc.body.appendChild(d);
    doc.addEventListener('click',function(e){if(!d.contains(e.target)&&!(e.target.closest&&e.target.closest('.pslot')))closePop();});
    doc.addEventListener('keydown',function(e){if(e.key==='Escape'&&d.classList.contains('open')){e.stopPropagation();e.preventDefault();closePop();if(!toSlot()){var li=byKey(CUR);if(li)li.focus({preventScroll:true});}}},true);
    // one tab stop: the arrows move among the four boxes, Tab leaves the menu for the slot it came from
    d.addEventListener('keydown',function(e){var bs=Array.prototype.slice.call(d.querySelectorAll('button')),i=bs.indexOf(doc.activeElement);if(i<0)return;
      if(e.key==='Tab'){closePop();toSlot();return;}
      var n=e.key==='ArrowRight'||e.key==='ArrowDown'?i+1:e.key==='ArrowLeft'||e.key==='ArrowUp'?i-1:e.key==='Home'?0:e.key==='End'?bs.length-1:-1;
      if(n<0)return;e.preventDefault();n=(n+bs.length)%bs.length;bs[i].tabIndex=-1;bs[n].tabIndex=0;bs[n].focus();});}return d;}
  function closePop(){var d=$('ppop');if(d)d.classList.remove('open');}
  var BADGE={A:'#A',B:'#B',C:'#C','':'-'};
  // the picker for a box `slot` whose letter is `cur`; a pick calls `apply(letter)` ('' = none). The features board uses it too.
  L.pick=function(slot,cur,apply){var d=pop();
    d.innerHTML=['A','B','C',''].map(function(l){return '<button type="button" role="menuitemradio" aria-checked="'+(cur===l)+'" class="'+(cur===l?'on':'')+'" data-l="'+l+'" title="'+(l?'set #'+l:'no priority')+'">'+
      '<span class="prio'+(l?'':' none')+'" data-p="'+l+'">'+(l?BADGE[l]:'none')+'</span></button>';}).join('');
    d.querySelectorAll('button').forEach(function(b){b.tabIndex=-1;b.onclick=function(e){e.stopPropagation();closePop();toSlot();apply(b.getAttribute('data-l'));};});
    SLOT=slot;
    var r=slot.getBoundingClientRect();d.style.left=(r.left+window.scrollX-5)+'px';d.style.top=(r.bottom+window.scrollY+4)+'px';d.classList.add('open');
    var f=d.querySelector('.on')||d.querySelector('button');f.tabIndex=0;f.focus();};
  function openPop(slot){var li=slot.closest('li[data-key]');L.pick(slot,li.getAttribute('data-priority')||'',function(l){setPrio(li,l);});}
  doc.addEventListener('click',function(e){var p=pane(),s=e.target.closest&&e.target.closest('.pslot');if(!p||!s||!p.contains(s)||!cfg())return;e.stopPropagation();openPop(s);},true);
  doc.addEventListener('keydown',function(e){var s=e.target.classList&&e.target.classList.contains('pslot')&&e.target;
    if(s&&(e.key==='Enter'||e.key===' ')&&cfg()){e.preventDefault();e.stopPropagation();openPop(s);}},true);

  // ---------- drags: reorder among siblings in the outline; a drop in By priority sets the priority ----------
  var DRAG=null;
  function clearDrop(){each(doc,'.drop-a,.drop-b,.over',function(x){x.classList.remove('drop-a','drop-b','over');});}
  doc.addEventListener('dragstart',function(e){var p=pane(),t=e.target;if(!p||!cfg()||!t.closest)return;
    var g=t.closest('.grip'),c=!g&&t.closest&&t.closest('li.bcard[draggable]'),li=g?g.closest('li.dnd'):c;if(!li||!p.contains(li))return;
    closePop();DRAG={key:li.getAttribute('data-key'),cid:g?li.getAttribute('data-cid'):null,li:li};li.classList.add('dragging');
    e.dataTransfer.effectAllowed='move';try{e.dataTransfer.setData('text/plain',DRAG.key);}catch(x){}});
  doc.addEventListener('dragend',function(){if(DRAG)DRAG.li.classList.remove('dragging');DRAG=null;clearDrop();});
  doc.addEventListener('dragover',function(e){if(!DRAG||!e.target.closest)return;
    if(DRAG.cid!==null){var li=e.target.closest('li.dnd');if(!li||li===DRAG.li||li.getAttribute('data-cid')!==DRAG.cid)return;e.preventDefault();
      var r=li.getBoundingClientRect(),after=e.clientY>r.top+r.height/2;clearDrop();li.classList.add(after?'drop-a':'drop-b');return;}
    var z=e.target.closest('.pdrop');if(!z)return;e.preventDefault();clearDrop();z.classList.add('over');});
  doc.addEventListener('drop',function(e){if(!DRAG||!e.target.closest)return;var d=DRAG;
    if(d.cid!==null){var li=e.target.closest('li.dnd');if(!li||li===d.li||li.getAttribute('data-cid')!==d.cid)return;e.preventDefault();
      var after=li.classList.contains('drop-a'),all=Array.prototype.filter.call(pane().querySelectorAll('li.dnd'),function(x){return x.getAttribute('data-cid')===d.cid&&x!==d.li;});
      clearDrop();moveTo(d.li,all.indexOf(li)+(after?1:0)+1);return;}
    var z=e.target.closest('.pdrop');if(!z)return;e.preventDefault();clearDrop();setPrio(d.li,z.getAttribute('data-drop'));});

  // ---------- the sheet's editor, for a board whose sheet edits lines in place ----------
  // Each commit is one write of a line, refused when the file's line changed: Enter or leaving a changed field saves, Esc discards,
  // a removal has a 6-second Undo, a refused write keeps the field, its text and a reload offer. The board names its route and its
  // operations in `o`: board, route, pane(), extra() (the lane), reload(), label, notes (the section title), noun, ops, depth, tags, hint.
  // a board whose reload fails closes its sheet, whose fields no longer answer
  L.failed=function(){if(B.drawerOpen())B.closeDrawer();};
  L.editor=function(o){
    var tick=null,addMore=false,ops=o.ops;
    function dc(){return $('drawer-content');}
    function mine(){return B.board()===o.board;}
    function sheetLine(){var w=dc()&&dc().querySelector('.lb-side');return w?+w.getAttribute('data-line'):0;}
    function lane(b){var x=o.extra?o.extra():{};for(var k in x)b[k]=x[k];return b;}
    function req(el,extra){var b={op:el.getAttribute('data-ed'),line:+el.getAttribute('data-line'),expected:el.getAttribute('data-raw')};
      for(var k in extra)b[k]=extra[k];return lane(b);}
    function post(route,b,ok,fail){
      var m=doc.querySelector('meta[name="said-board-csrf"]');
      fetch(route,{method:'POST',credentials:'same-origin',body:JSON.stringify(b),
        headers:{'Content-Type':'application/json','X-Said-Board':'1','X-Said-Board-Csrf':m?m.content:''}})
        .then(function(r){return r.json().catch(function(){return {ok:false,error:'HTTP '+r.status};});})
        .then(function(j){if(j&&j.ok)ok(j);else fail(((j&&j.error)||'refused').replace(/^refused: /,''));})
        .catch(function(){fail('the board did not answer');});}
    // a field the user has open (or typed in) is never rebuilt away: the reload waits until every field is saved or closed
    function openField(){var d=dc(),a=d?d.querySelectorAll('.ed-in,.tag-in'):[];
      for(var i=0;i<a.length;i++)if(!a[i].hasAttribute('data-saved')&&(a[i].classList.contains('ed-in')||a[i].value.trim()))return true;return false;}
    var late=false;
    function reloadSheet(force){var p=o.pane();if(!p)return;
      if(!force&&openField()){late=true;return;}
      late=false;L.keep={line:sheetLine(),sheet:B.drawerOpen()};o.reload();}
    function flush(){if(late)reloadSheet();}
    function saved(where,more){tick=where;addMore=!!more;reloadSheet();}
    function sec(title){var h=dc()?dc().querySelectorAll('.esec h4'):[];for(var i=0;i<h.length;i++)if(h[i].textContent===title)return h[i];return null;}
    function settle(){var d=dc();if(!d)return;
      if(tick){var host=tick==='name'?d.querySelector('.d-name'):sec(tick);tick=null;
        if(host){var t=doc.createElement('span');t.className='saved-tick';t.textContent='saved';host.appendChild(t);setTimeout(function(){t.remove();},1000);}}
      if(addMore){addMore=false;var b=d.querySelector('.addnote');if(b)openNoteAdd(b);}}
    function clearErr(host){host.removeAttribute('data-err');var m=host.querySelector('.ed-msg');if(m)m.remove();}
    function showErr(host,text){
      clearErr(host);host.setAttribute('data-err','1');
      var m=doc.createElement('span');m.className='ed-msg';m.setAttribute('role','status');
      m.appendChild(doc.createTextNode(text+'. Your text is kept. '));
      var r=doc.createElement('button');r.type='button';r.className='ed-reload';r.textContent=o.label;m.appendChild(r);host.appendChild(m);}
    // each removal keeps its own Undo for 6 seconds, in the lane it was made in
    function drop(r){clearTimeout(r._t);r.remove();var u=$('ed-undo');if(u&&!u.firstChild)u.remove();}
    function arm(text,b,where){
      b=lane(b);var u=$('ed-undo');
      if(!u){u=doc.createElement('div');u.id='ed-undo';u.setAttribute('role','status');doc.body.appendChild(u);}
      var r=doc.createElement('div'),s=doc.createElement('span');s.textContent=text;var k=doc.createElement('button');k.type='button';k.textContent='Undo';
      r.appendChild(s);r.appendChild(k);u.appendChild(r);r._t=setTimeout(function(){drop(r);},6000);
      k.onclick=function(){k.disabled=true;post(o.route,b,function(){drop(r);saved(where,false);},function(err){s.textContent='Could not undo: '+err;});};}
    function after(j,b,where){
      if(b.op===ops.del)arm(o.noun+' removed',{op:ops.restore,line:j.line,expected:j.raw,text:b.expected},o.notes);
      if(b.op==='tag-del')arm('Tag removed',{op:'restore',line:j.line,expected:j.raw,text:b.expected},'Tags');
      saved(where,b.op===ops.add);}
    function bind(inp,host,f){
      var done=false,busy=false;
      function close(){if(!f.reuse)done=true;clearErr(host);f.close();flush();}
      function save(){
        if(done||busy||host.getAttribute('data-err'))return;
        var b=f.build(inp.value.trim());if(!b){close();return;}
        busy=true;post(o.route,b,function(j){done=true;inp.setAttribute('data-saved','1');after(j,b,f.where);},function(err){busy=false;showErr(host,err);});}
      inp.addEventListener('keydown',function(e){
        if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();return;}
        if(e.key==='Enter'){e.preventDefault();host.removeAttribute('data-err');save();return;}
        if(f.key)f.key(e);});
      inp.addEventListener('blur',function(){setTimeout(function(){if(!done&&!busy&&doc.activeElement!==inp)save();},0);});}
    function input(val,max,label,cls){var i=doc.createElement('input');i.type='text';i.className='ed-in input input-bordered '+cls;i.maxLength=max;i.value=val;i.setAttribute('aria-label',label);return i;}
    function openText(host){
      if(host.querySelector('input'))return;
      var orig=host.innerHTML,val=host.getAttribute('data-value')||'',inp=input(val,300,'line text','input-sm');
      host.textContent='';host.appendChild(inp);inp.focus();inp.select();
      bind(inp,host,{where:'name',close:function(){host.innerHTML=orig;},build:function(v){return v===val?null:req(host,{text:v});}});}
    function openNote(li){
      var nt=li.querySelector('.nt');if(!nt||li.querySelector('.ed-in'))return;
      var val=li.getAttribute('data-value')||'',inp=input(val,300,o.noun.toLowerCase(),'input-xs');
      nt.hidden=true;li.insertBefore(inp,nt);inp.focus();inp.select();
      bind(inp,li,{where:o.notes,close:function(){inp.remove();nt.hidden=false;},
        build:function(v){return v===val?null:v?req(li,{text:v}):req(li,{op:ops.del});}});}
    function openNoteAdd(btn){
      var box=btn.parentNode;if(box.querySelector('.ed-add'))return;
      var last=+btn.getAttribute('data-depth'),depth=Math.max(last,0),row=doc.createElement('div');row.className='ed-add';
      var inp=input('',300,'new '+o.noun.toLowerCase(),'input-xs');inp.placeholder=o.hint;row.appendChild(inp);
      function pad(){row.style.paddingLeft=(depth*18)+'px';row.setAttribute('data-depth',depth);}
      if(o.depth)pad();btn.hidden=true;box.insertBefore(row,btn);inp.focus();
      bind(inp,row,{where:o.notes,close:function(){row.remove();btn.hidden=false;},build:function(v){return v?req(btn,o.depth?{text:v,depth:depth}:{text:v}):null;},
        key:function(e){if(!o.depth||e.key!=='Tab')return;e.preventDefault();depth=e.shiftKey?Math.max(0,depth-1):Math.min(last+1,depth+1);pad();}});}
    function remove(x){
      var b=req(x,x.hasAttribute('data-tag')?{text:x.getAttribute('data-tag')}:{});
      post(o.route,b,function(j){after(j,b,b.op==='tag-del'?'Tags':o.notes);},function(err){showErr(x.closest('.esec'),err);});}
    if(o.tags)doc.addEventListener('focusin',function(e){var t=e.target;
      if(!mine()||!t.classList||!t.classList.contains('tag-in')||t._bound||!dc()||!dc().contains(t))return;t._bound=true;
      bind(t,t.parentNode,{where:'Tags',reuse:true,close:function(){t.value='';},build:function(v){v=v.replace(/^#/,'');return v?req(t,{text:v}):null;}});});
    doc.addEventListener('click',function(e){var d=dc(),t=e.target.closest&&e.target.closest('.d-name[data-ed],.nt,.nx,.tagx,.addnote,.ed-reload');
      if(!mine()||!d||!t||!d.contains(t)||(e.target.closest('a')&&t.classList.contains('nt')))return;
      if(t.classList.contains('ed-reload'))reloadSheet(true);
      else if(t.classList.contains('d-name'))openText(t);
      else if(t.classList.contains('nt'))openNote(t.parentNode);
      else if(t.classList.contains('addnote'))openNoteAdd(t);
      else remove(t);});
    doc.addEventListener('keydown',function(e){var t=e.target;
      if(mine()&&(e.key==='Enter'||e.key===' ')&&t.matches&&t.matches('#drawer-content .d-name[data-ed],#drawer-content .nt')){e.preventDefault();t.click();}});
    // a write from the sheet that is not a field (a state step): posts at once, the sheet reloads, a refusal shows on `host`
    function act(route,b,host){clearErr(host);post(route,b,function(){saved(null,false);},function(err){showErr(host,err);});}
    return {settle:settle,act:act};
  };

  // ---------- keys ----------
  function typing(t){var n=(t&&t.tagName||'').toLowerCase();return n==='input'||n==='textarea'||n==='select'||(t&&t.isContentEditable);}
  doc.addEventListener('keydown',function(e){var t=e.target;
    if(list()&&t.classList&&t.classList.contains('bb-q')&&e.key==='Escape'){t.blur();e.preventDefault();}});
  doc.addEventListener('keydown',function(e){if(!list()||e.defaultPrevented||e.metaKey||e.ctrlKey||e.altKey||typing(e.target))return;
    var k=e.key,h=$('help');
    if(k==='?'){window.toggleHelp();e.preventDefault();return;}
    if(k==='Escape'){if(h&&h.classList.contains('open')){window.toggleHelp(false);e.preventDefault();return;}
      if(B.drawerOpen()){B.closeDrawer();var li=byKey(CUR);if(li)li.focus({preventScroll:true});e.preventDefault();return;}
      if(CUR){CUR=null;paint();if(doc.activeElement&&doc.activeElement.blur)doc.activeElement.blur();e.preventDefault();}return;}
    if(B.drawerOpen()&&$('drawer').contains(doc.activeElement)){if(k==='ArrowLeft'||k==='h'){B.closeDrawer();var c=byKey(CUR);if(c)c.focus({preventScroll:true});e.preventDefault();}return;}
    var a=doc.activeElement,onList=!a||a===doc.body||(a.matches&&a.matches('li.bl-row,li.td-row'));
    if(k==='/'){var p=pane(),q=p&&p.querySelector('.bb-q');if(q){e.preventDefault();q.focus();}return;}
    if(k==='ArrowDown'||k==='j'){e.preventDefault();move(1);return;}
    if(k==='ArrowUp'||k==='k'){e.preventDefault();move(-1);return;}
    if(k==='Home'||k==='End'){var it=items();if(it.length){e.preventDefault();cursor(it[k==='End'?it.length-1:0].getAttribute('data-key'));}return;}
    if(onList&&cfg()&&/^[abc0]$/i.test(k)&&byKey(CUR)){e.preventDefault();setPrio(byKey(CUR),k==='0'?'':k.toUpperCase());return;}
    if((k==='Enter'||k===' '||k==='ArrowRight'||k==='l')&&onList){var li2=byKey(CUR)||items()[0];if(li2){e.preventDefault();L.open(li2);}}});
})();
