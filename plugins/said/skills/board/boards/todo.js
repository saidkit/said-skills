// said:board, the todo board: one tab per lane with a todo file, its own route and refresh.
// The first show after a page load re-reads the files; a later response never overwrites a newer one.
// The filter row, the folds, the cursor, the sheet, the picker, the drags and the header status are the shared list
// client (boards/lists.js). A priority or an order write posts at once (no confirm) and the board re-reads. In the line's sheet
// a state step or the Next button posts the state at once, and the text and the sub-items are edited in place by the shared
// line editor (boards/lists.js): Enter saves, Esc discards, a refusal keeps the field and offers a reload.
(function(){
  var B=window.saidBoard;if(!B||!B.lists)return;var L=B.lists;
  var st={lane:''};
  function valid(v){return typeof v==='string'&&/^[A-Za-z0-9_-]{0,40}$/.test(v);}
  try{var k=JSON.parse(localStorage.getItem('sb-todo')||'{}');if(valid(k.lane))st.lane=k.lane;}catch(e){}
  var seq=0,first=true;
  function pane(){var p=document.getElementById('boardpane');return p&&p.getAttribute('data-board')==='todo'?p:null;}
  function lane(p){var l=p&&p.querySelector('.td-list');return l?l.getAttribute('data-lane'):'';}
  function load(p,fresh){
    var my=++seq,q=new URLSearchParams({lane:st.lane});if(fresh)q.set('fresh','1');
    function put(h){if(my===seq&&B.board()==='todo'&&p.getAttribute('data-board')==='todo'){p.innerHTML=h;L.apply(p);L.repaint();L.status(p);ed.settle();}}
    fetch('/todo/board?'+q.toString(),{credentials:'same-origin'})
      .then(function(r){if(!r.ok)throw new Error(r.status);return r.text();})
      .then(put)
      .catch(function(){put('<div class="empty-state">The todo files could not be loaded.</div>');L.failed();});
  }
  var ed=L.editor({board:'todo',route:'/todo/edit',pane:pane,extra:function(){return {lane:lane(pane())};},reload:function(){var p=pane();if(p)load(p,true);},
    label:'Reload line',notes:'Sub-items',noun:'Sub-item',ops:{add:'sub-add',del:'sub-del',restore:'restore-sub'},depth:false,tags:false,hint:'new sub-item: in PROJ-01, adr: ..., or ref: path'});
  document.addEventListener('click',function(e){
    var b=e.target.closest&&e.target.closest('#drawer-content [data-set-state]');if(!b||b.disabled||B.board()!=='todo'||!pane())return;
    ed.act('/todo/state',{lane:lane(pane()),line:+b.getAttribute('data-line'),expected:b.getAttribute('data-raw'),state:b.getAttribute('data-set-state')},b.closest('.lb-side').querySelector('.d-next'));});
  function show(p){p.innerHTML='<div class="empty-state td-loading">Loading the todo files.</div>';load(p,first);first=false;}
  L.cfg.todo={base:'/todo/',extra:function(){return {lane:lane(pane())};},reload:function(){var p=pane();if(p)load(p,true);}};
  B.boards.todo={show:show,refresh:function(fresh){var p=pane();if(p)load(p,!!fresh);}};
  document.addEventListener('click',function(e){
    var p=pane();if(!p||!e.target.closest)return;
    if(L.wclick(e,'/todo/',lane(p),function(){load(p,true);}))return;
    var t=e.target.closest('[data-td-lane]');if(!t||!p.contains(t))return;
    var v=t.getAttribute('data-td-lane');if(!valid(v))return;st.lane=v;
    try{localStorage.setItem('sb-todo',JSON.stringify(st));}catch(x){}
    load(p,false);
  },true);
  if(B.board()==='todo'){var p=pane();if(p)show(p);}
})();
