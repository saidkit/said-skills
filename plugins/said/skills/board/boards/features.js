// The features board: its movement model and its keys. The cursor, the selection and the view belong to the
// shared shell (board.js) and are read here through its one namespace, window.saidBoard.
(function(){
  var B=window.saidBoard;if(!B)return;
  var $=B.$,vw=B.vw,items=B.items,cols=B.cols,kpos=B.kpos,setCursor=B.setCursor,activate=B.activate,
      ensureCursor=B.ensureCursor,focusCursor=B.focusCursor,clearCursor=B.clearCursor,drawerOpen=B.drawerOpen,
      closeDrawer=B.closeDrawer,inDetail=B.inDetail,focusDetail=B.focusDetail,onBoard=B.onBoard,inDrawer=B.inDrawer;
  // the key handler below registers through this adapter, so it runs only while the features board is shown, and
  // it reads the shared cursor as CUR, taken from the namespace as each key arrives, before the handler moves it
  // (kpos and every move read the live cursor in board.js)
  var CUR=null,document={addEventListener:function(t,f,o){window.document.addEventListener(t,function(e){
    if(B.board()!=='features')return;CUR=B.cur();f(e);},o);}};
  function moveList(d){var it=items();if(!it.length)return;
    var i=-1;for(var x=0;x<it.length;x++){if(it[x].getAttribute('data-id')===CUR){i=x;break;}}
    if(i<0)i=0;else i=Math.max(0,Math.min(it.length-1,i+d));
    setCursor(it[i].getAttribute('data-id'));activate(false);}
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
      if(inDrawer()){if(left){e.preventDefault();closeDrawer();}return;}  // drawer caught the keyboard: Up/Down scroll its content, Left/Esc return to the board
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
})();
