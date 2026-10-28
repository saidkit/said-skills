// said:board, the todo board: one tab per lane with a todo file, state and priority filters, its own route and refresh.
// The first show after a page load re-reads the files; a later response never overwrites a newer one.
// The search, the cursor, the side panel and the header status are the shared list client (boards/lists.js).
// A row's priority and order buttons post at once (no confirm) and the board re-reads.
(function(){
  var B=window.saidBoard;if(!B||!B.lists)return;var L=B.lists;
  var st={lane:'',state:'all',priority:'all'};
  var OK={state:['all','open','wip','done'],priority:['all','A','B','C','none']};
  function valid(n,v){return typeof v==='string'&&(n==='lane'?/^[A-Za-z0-9_-]{0,40}$/.test(v):OK[n].indexOf(v)>=0);}
  try{var k=JSON.parse(localStorage.getItem('sb-todo')||'{}');['lane','state','priority'].forEach(function(n){if(valid(n,k[n]))st[n]=k[n];});}catch(e){}
  var seq=0,first=true;
  function pane(){var p=document.getElementById('boardpane');return p&&p.getAttribute('data-board')==='todo'?p:null;}
  function load(p,fresh){
    var my=++seq,q=new URLSearchParams({lane:st.lane,state:st.state,priority:st.priority});if(fresh)q.set('fresh','1');
    function put(h){if(my===seq&&B.board()==='todo'&&p.getAttribute('data-board')==='todo'){p.innerHTML=h;L.apply(p);L.repaint();L.status(p);}}
    fetch('/todo/board?'+q.toString(),{credentials:'same-origin'})
      .then(function(r){if(!r.ok)throw new Error(r.status);return r.text();})
      .then(put)
      .catch(function(){put('<div class="empty-state">The todo files could not be loaded.</div>');});
  }
  function show(p){p.innerHTML='<div class="empty-state td-loading">Loading the todo files.</div>';load(p,first);first=false;}
  B.boards.todo={show:show,refresh:function(fresh){var p=pane();if(p)load(p,!!fresh);}};
  document.addEventListener('click',function(e){
    var p=pane();if(!p||!e.target.closest)return;
    var l=p.querySelector('.td-list');if(L.wclick(e,'/todo/',l?l.getAttribute('data-lane'):'',function(){load(p,true);}))return;
    var t=e.target.closest('[data-td-lane],[data-td-state],[data-td-priority]');if(!t||!p.contains(t))return;
    ['lane','state','priority'].forEach(function(n){var v=t.getAttribute('data-td-'+n);if(v!==null&&valid(n,v))st[n]=v;});
    try{localStorage.setItem('sb-todo',JSON.stringify(st));}catch(x){}
    load(p,false);
  },true);
  if(B.board()==='todo'){var p=pane();if(p)show(p);}
})();
