// said:board, the backlog board: by stage or by priority (its tabs), its own fragment route, cache and refresh.
// The first show after a page load re-reads the file; a later response never overwrites a newer one.
// The filter bars, the cursor, the side panel and the header status are the shared list client (boards/lists.js).
// A row's priority and order buttons post at once (no confirm) and the board re-reads.
(function(){
  var B=window.saidBoard;if(!B||!B.lists)return;var L=B.lists;
  var by='stage';try{if(localStorage.getItem('sb-backlog-by')==='priority')by='priority';}catch(e){}
  var seq=0,first=true;
  function load(p,fresh){
    var body=p.querySelector('.bl-body'),my=++seq;if(!body)return;
    function put(h){if(my===seq&&B.board()==='backlog'&&p.getAttribute('data-board')==='backlog'){body.innerHTML=h;L.apply(p);L.repaint();L.status(p);}}
    fetch('/backlog/'+by+(fresh?'?fresh=1':''),{credentials:'same-origin'})
      .then(function(r){if(!r.ok)throw new Error(r.status);return r.text();})
      .then(put)
      .catch(function(){put('<div class="empty-state">The backlog could not be loaded.</div>');});
  }
  function show(p){p.innerHTML='<div class="bl-body"><div class="empty-state">Loading the backlog.</div></div>';load(p,first);first=false;}
  function pane(){var p=document.getElementById('boardpane');return p&&p.getAttribute('data-board')==='backlog'?p:null;}
  B.boards.backlog={show:show,refresh:function(fresh){var p=pane();if(p)load(p,!!fresh);}};
  document.addEventListener('click',function(e){
    var p=pane();if(!p)return;
    if(L.wclick(e,'/backlog/','',function(){load(p,true);}))return;
    var t=e.target.closest&&e.target.closest('[data-bl-by]');if(!t||!p.contains(t))return;
    by=t.getAttribute('data-bl-by')==='priority'?'priority':'stage';
    try{localStorage.setItem('sb-backlog-by',by);}catch(x){}
    load(p,false);
  },true);
  if(B.board()==='backlog'){var p=pane();if(p)show(p);}
})();
