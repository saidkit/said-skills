// said:board, the backlog board: its four views (Outline, By section, By stage, By priority), its own fragment route,
// cache and refresh. The first show after a page load re-reads the file; a later response never overwrites a newer one.
// The toolbar, the filter row, the folds, the cursor, the sheet, the picker and the drags are the shared list client
// (boards/lists.js). A priority or an order write posts at once (no confirm) and the board re-reads. A topic heading's
// add button, or N at the cursor's topic, opens a field at the end of that topic; Enter posts the entry and keeps the field.
// In the entry sheet the text, a note and a tag are edited in place by the shared line editor (boards/lists.js).
(function(){
  var B=window.saidBoard;if(!B||!B.lists)return;var L=B.lists;
  var VIEWS=['outline','section','stage','priority'],by='outline';
  try{var s=localStorage.getItem('sb-backlog-by');if(VIEWS.indexOf(s)>=0)by=s;}catch(e){}
  var seq=0,first=true;
  function load(p,fresh){
    var body=p.querySelector('.bl-body'),my=++seq;if(!body)return;
    function put(h){if(my===seq&&B.board()==='backlog'&&p.getAttribute('data-board')==='backlog'){body.innerHTML=h;L.apply(p);L.repaint();L.status(p);reopen(p);ed.settle();}}
    fetch('/backlog/'+by+(fresh?'?fresh=1':''),{credentials:'same-origin'})
      .then(function(r){if(!r.ok)throw new Error(r.status);return r.text();})
      .then(put)
      .catch(function(){put('<div class="empty-state">The backlog could not be loaded.</div>');L.failed();});
  }
  function show(p){p.innerHTML='<div class="bl-body"><div class="empty-state">Loading the backlog.</div></div>';load(p,first);first=false;}
  function pane(){var p=document.getElementById('boardpane');return p&&p.getAttribute('data-board')==='backlog'?p:null;}
  // ---------- quick add: a field at the end of a topic; Enter posts and keeps it open, Esc or an empty blur closes it ----------
  var again=null,busy=false;
  function field(p){return p.querySelector('.qa-row');}
  function headOf(p,ck){var all=p.querySelectorAll('.hd[data-ck]');for(var i=0;i<all.length;i++)if(all[i].getAttribute('data-ck')===ck)return all[i];return null;}
  function closeAdd(p){var r=field(p);if(r){r.remove();L.apply(p);}}
  function openAdd(p,hd){
    var q=hd&&hd.querySelector('.qa');if(!q)return;
    closeAdd(p);var ck=hd.getAttribute('data-ck'),topic=hd.parentNode;L.unfold(ck);topic.classList.remove('closed');
    var row=document.createElement('div');row.className='qa-row';
    row.innerHTML='<input type="text" class="input input-bordered input-xs qa-in" maxlength="300" placeholder="new entry, #word makes a tag" aria-label="new entry"><span class="qa-msg" role="status"></span>';
    topic.appendChild(row);L.apply(p);var inp=row.querySelector('input'),msg=row.querySelector('.qa-msg');
    inp.addEventListener('keydown',function(e){
      if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeAdd(p);q.focus({preventScroll:true});return;}
      if(e.key==='Enter'){e.preventDefault();send(p,hd,q,inp,msg,ck);}});
    inp.addEventListener('blur',function(){if(!inp.value.trim()&&!busy)closeAdd(p);});
    inp.focus();}
  function send(p,hd,q,inp,msg,ck){
    var text=inp.value.trim();if(!text||busy)return;
    var m=document.querySelector('meta[name="said-board-csrf"]'),body={section:q.getAttribute('data-qs'),topic:q.getAttribute('data-qt'),text:text};
    if(q.hasAttribute('data-qu'))body.subtopic=q.getAttribute('data-qu');
    busy=true;msg.textContent='';
    fetch('/backlog/add',{method:'POST',credentials:'same-origin',body:JSON.stringify(body),
      headers:{'Content-Type':'application/json','X-Said-Board':'1','X-Said-Board-Csrf':m?m.content:''}})
      .then(function(r){return r.json().catch(function(){return {ok:false,error:'HTTP '+r.status};});})
      .then(function(j){busy=false;
        if(j&&j.ok){if(j.key)L.pin(j.key);again=ck;load(p,true);}else msg.textContent=(j&&j.error)||'refused';})
      .catch(function(){busy=false;msg.textContent='the board did not answer';});}
  function reopen(p){var ck=again;again=null;if(ck)openAdd(p,headOf(p,ck));}
  document.addEventListener('click',function(e){var p=pane(),b=e.target.closest&&e.target.closest('.qa');
    if(p&&b&&p.contains(b)){e.stopPropagation();openAdd(p,b.closest('.hd'));}},true);
  document.addEventListener('keydown',function(e){var p=pane(),t=e.target,n=(t&&t.tagName||'').toLowerCase();
    if(!p||e.defaultPrevented||e.metaKey||e.ctrlKey||e.altKey||(e.key!=='n'&&e.key!=='N')||n==='input'||n==='textarea'||n==='select'||(t&&t.isContentEditable))return;
    var d=document.getElementById('drawer');if(d&&d.contains(t))return;
    var li=L.cursorLi(),topic=li&&li.closest('.topic'),hd=topic&&topic.firstElementChild;
    if(hd&&hd.classList.contains('hd')&&hd.querySelector('.qa')){e.preventDefault();openAdd(p,hd);}});
  // ---------- the entry sheet's edits: the shared line editor, on the backlog's route ----------
  var ed=L.editor({board:'backlog',route:'/backlog/edit',pane:pane,reload:function(){var p=pane();if(p)load(p,true);},label:'Reload entry',notes:'Notes',noun:'Note',
    ops:{add:'note-add',del:'note-del',restore:'restore-note'},depth:true,tags:true,hint:'new note, Tab indents, Shift+Tab outdents'});
  L.cfg.backlog={base:'/backlog/',reload:function(){var p=pane();if(p)load(p,true);}};
  B.boards.backlog={show:show,refresh:function(fresh){var p=pane();if(p)load(p,!!fresh);}};
  document.addEventListener('click',function(e){
    var p=pane();if(!p)return;
    if(L.wclick(e,'/backlog/','',function(){load(p,true);}))return;
    var t=e.target.closest&&e.target.closest('[data-bl-by]');if(!t||!p.contains(t))return;
    var v=t.getAttribute('data-bl-by');if(VIEWS.indexOf(v)<0)return;by=v;
    try{localStorage.setItem('sb-backlog-by',by);}catch(x){}
    load(p,false);
  },true);
  if(B.board()==='backlog'){var p=pane();if(p)show(p);}
})();
