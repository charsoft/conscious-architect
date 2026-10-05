const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const test=require('node:test');
const code=fs.readFileSync(require('node:path').join(__dirname,'../draft-editor.js'),'utf8');
function harness(confirmed=true) {
  const initial={id:'episode',title:'Original',stage2:{beat1:'My opening'},stage3:[{act:'Beat 1',content:'Manual script'}]};
  const store=new Map([['catalog',JSON.stringify([initial])],['s2',JSON.stringify(initial.stage2)],['s3',JSON.stringify(initial.stage3)]]);
  const alerts=[];let synced=0,uuid=0;
  const nodes=new Map();
  const context=vm.createContext({
    localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),key:i=>[...store.keys()][i],get length(){return store.size;}},
    LAUNCH_CATALOG:[initial],DEFAULT_STAGE2:initial.stage2,DEFAULT_STAGE3:initial.stage3,
    STORAGE_KEY_CATALOG:'catalog',STORAGE_KEY_STAGE2:'s2',STORAGE_KEY_STAGE3:'s3',
    getCatalog:()=>JSON.parse(store.get('catalog')),handleEdit:()=>{},loadState:()=>{},setStage:()=>{},
    syncToFirestore:()=>synced++,confirm:()=>confirmed,alert:m=>alerts.push(m),
    crypto:{randomUUID:()=>String(++uuid)},selectedIds:new Set(),lastResearchResults:[],
    document:{getElementById:id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',replaceChildren:()=>{}});return nodes.get(id);}},
  });
  vm.runInContext(code,context);
  function preview(action='options') {
    context.fixture={input:context.currentDraftSnapshot(),draft:{action,draftId:'draft',researchIds:[],result:action==='options'
      ?{options:[{title:'New title',blueprint:{beat1:'New opening'}}]}
      :{sections:Array.from({length:7},(_,i)=>({beat:i+1,name:'Section',spoken:'Spoken '+i,notes:'Camera note'}))}}};
    vm.runInContext('pendingVoiceDraft = fixture',context);
  }
  return {context,store,alerts,preview,synced:()=>synced};
}
test('options apply only after confirmation and leave existing narration intact',()=>{
  const h=harness();h.preview();const script=h.store.get('s3');h.context.applyVoiceDraft(0);
  assert.equal(h.store.get('s3'),script);
  assert.equal(JSON.parse(h.store.get('s2')).beat1,'New opening');
  assert.equal([...h.store.keys()].filter(k=>k.startsWith('tca_revision_')).length,1);
  assert.equal(h.synced(),1);
});
test('narration application keeps production notes outside spoken text',()=>{
  const h=harness();h.preview('narration');h.context.applyVoiceDraft();
  const script=JSON.parse(h.store.get('s3'));
  assert.equal(script.length,7);assert.equal(script[0].content,'Spoken 0');assert.equal(script[0].notes,'Camera note');
});
test('cancelled apply makes no replacement or cloud sync',()=>{
  const h=harness(false);h.preview();const before=JSON.stringify([...h.store]);h.context.applyVoiceDraft(0);
  assert.equal(JSON.stringify([...h.store]),before);assert.equal(h.synced(),0);
});
test('editing after generation invalidates the preview',()=>{
  const h=harness();h.preview();h.store.set('s2',JSON.stringify({beat1:'New manual edit'}));h.context.applyVoiceDraft(0);
  assert.equal(JSON.parse(h.store.get('s2')).beat1,'New manual edit');assert.equal(h.synced(),0);assert.ok(h.alerts[0].includes('changed'));
});
test('changing active episode invalidates the preview',()=>{
  const h=harness();h.preview();h.store.set('tca_active_ideation_id','another');h.context.applyVoiceDraft(0);
  assert.equal(h.synced(),0);assert.ok(h.alerts[0].includes('changed'));
});
test('failed backup prevents all replacement writes',()=>{
  const h=harness();h.preview();const before=JSON.stringify([...h.store]);
  h.context.localStorage.setItem=()=>{throw new Error('Quota exceeded');};h.context.applyVoiceDraft(0);
  assert.equal(JSON.stringify([...h.store]),before);assert.equal(h.synced(),0);
});
test('restoring a version recovers prior narration and title',()=>{
  const h=harness();h.preview('narration');h.context.applyVoiceDraft();h.context.restorePreviousDraft();
  assert.equal(JSON.parse(h.store.get('s3'))[0].content,'Manual script');
  assert.equal([...h.store.keys()].filter(k=>k.startsWith('tca_revision_')).length,2);
});
