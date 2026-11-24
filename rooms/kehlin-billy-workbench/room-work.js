/* room-work.js · BilloTech · one saved working state per project + tool, with full undo/redo history.
   Online: Supabase RPCs room_work_open / room_work_commit / room_work_move (BILLO BINDER, member-checked).
   Offline or signed out: same model kept on this device, and pushed up the next time it can reach the binder. */
(function(){
const SB_URL='https://hnzekejoaamsnmtqtwie.supabase.co', SB_KEY='sb_publishable_51ybFNizblfWMqL_qdekcg_kZT7nXHy';
function client(){
  if(window.sb&&window.sb.rpc) return window.sb;
  if(window.__rwsb) return window.__rwsb;
  if(window.supabase&&window.supabase.createClient) return (window.__rwsb=window.supabase.createClient(SB_URL,SB_KEY,{auth:{persistSession:true,autoRefreshToken:true}}));
  return null;
}
const clone=o=>JSON.parse(JSON.stringify(o));
function RoomWork(opt){
  const key=`rw:${opt.project}:${opt.kind}`;
  const me={project:opt.project,kind:opt.kind,state:null,head:0,history:[],online:false,session:null,busy:false,
    onchange:opt.onchange||(()=>{}),onstatus:opt.onstatus||(()=>{})};
  let local=null;
  const loadLocal=()=>{try{local=JSON.parse(localStorage.getItem(key)||'null')}catch(e){local=null}
    if(!local){local={head:0,edits:[{seq:0,label:'Start',state:clone(opt.seed),at:new Date().toISOString(),pending:false}]}}};
  const saveLocal=()=>{try{localStorage.setItem(key,JSON.stringify(local))}catch(e){}};
  const liveHist=()=>local.edits.filter(e=>!e.discarded);
  function syncFromLocal(){me.head=local.head;me.state=clone(local.edits.find(e=>e.seq===local.head).state);
    me.history=liveHist().map(e=>({seq:e.seq,label:e.label,author:e.author||'',at:e.at,pending:!!e.pending}));}
  me.open=async function(){
    loadLocal();
    const sb=client();
    if(sb){try{
      const {data:{session:auth}}=await sb.auth.getSession();
      if(auth){
        const {data,error}=await sb.rpc('room_work_open',{p_project:opt.project,p_kind:opt.kind,p_seed:opt.seed,p_title:opt.title||null});
        if(!error&&data){
          me.online=true;me.session=data.session;
          const pend=local.edits.filter(e=>e.pending&&!e.discarded&&e.seq>0);
          if(pend.length){ // push device-only steps up first
            for(const e of pend){await sb.rpc('room_work_commit',{p_session:me.session,p_label:e.label,p_state:e.state});}
            const r=await sb.rpc('room_work_open',{p_project:opt.project,p_kind:opt.kind,p_seed:opt.seed});
            Object.assign(data,r.data||{});
          }
          local={head:data.head,edits:(data.history||[]).map(h=>({seq:h.seq,label:h.label,author:h.author,at:h.at,state:null}))};
          const cur=local.edits.find(e=>e.seq===data.head)||(local.edits.push({seq:data.head,label:'Current',at:''}),local.edits[local.edits.length-1]);
          cur.state=data.state;saveLocal();
        }
      }
    }catch(e){me.online=false}}
    syncFromLocal();me.onstatus(me.online?'saved':'device');me.onchange(me.state,'open');return me.state;
  };
  me.commit=async function(label,state){
    const s=clone(state);
    local.edits.forEach(e=>{if(e.seq>local.head)e.discarded=true});
    const seq=Math.max(...local.edits.map(e=>e.seq))+1;
    local.edits.push({seq,label,state:s,at:new Date().toISOString(),pending:!me.online});local.head=seq;saveLocal();syncFromLocal();
    me.onchange(me.state,'commit');
    if(me.online){me.onstatus('saving');
      try{const {data,error}=await client().rpc('room_work_commit',{p_session:me.session,p_label:label,p_state:s});
        if(error)throw error;const e=local.edits.find(x=>x.seq===seq);e.seq=data;local.head=data;saveLocal();syncFromLocal();me.onstatus('saved');}
      catch(err){const e=local.edits.find(x=>x.seq===seq);if(e)e.pending=true;saveLocal();me.online=false;me.onstatus('device');}}
    else me.onstatus('device');
  };
  async function moveTo(seq,why){
    const e=local.edits.find(x=>x.seq===seq&&!x.discarded);if(!e)return;
    if(me.online&&!e.pending){me.onstatus('saving');
      try{const {data,error}=await client().rpc('room_work_move',{p_session:me.session,p_seq:seq});if(error)throw error;e.state=data;me.onstatus('saved')}
      catch(err){me.onstatus('device')}}
    if(!e.state)return;local.head=seq;saveLocal();syncFromLocal();me.onchange(me.state,why);
  }
  me.undo=()=>{const h=liveHist().map(e=>e.seq).filter(s=>s<local.head);if(h.length)return moveTo(Math.max(...h),'undo')};
  me.redo=()=>{const h=liveHist().map(e=>e.seq).filter(s=>s>local.head);if(h.length)return moveTo(Math.min(...h),'redo')};
  me.jump=seq=>moveTo(seq,'jump');
  me.canUndo=()=>liveHist().some(e=>e.seq<local.head);
  me.canRedo=()=>liveHist().some(e=>e.seq>local.head);
  return me;
}
window.RoomWork=RoomWork;
/* keyboard: Cmd/Ctrl+Z undo, Shift+Cmd/Ctrl+Z or Ctrl+Y redo, for whichever RoomWork is active */
window.addEventListener('keydown',e=>{const w=window.__rwActive;if(!w)return;const t=e.target;if(t&&/INPUT|TEXTAREA|SELECT/.test(t.tagName)&&t.type!=='range')return;
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?w.redo():w.undo()}
  else if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='y'){e.preventDefault();w.redo()}});
})();
