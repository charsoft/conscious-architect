const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const html = fs.readFileSync(require('node:path').join(__dirname, '../index.html'), 'utf8');
function fn(name) {
  const start = html.indexOf(`    function ${name}(`);
  assert.notEqual(start, -1);
  const end = html.indexOf('\n    }', start) + 6;
  return html.slice(start, end);
}
const fields = ['beat1','beat2','beat3','bridge_tech','bridge_limit','bridge_parallel','beat5','beat6','beat7'];
const blueprint = Object.fromEntries(fields.map(f => [f, `UNIQUE_${f}`]));
function harness(approved = true) {
  const store = new Map([['s2', JSON.stringify(blueprint)], ['s3', JSON.stringify([{content:'MANUAL EDIT'}])]]);
  const catalog = [{id:'episode',title:'My episode',pillar:'Agency',stage2:blueprint}];
  let rendered, synced = 0, captured = 0;
  const context = vm.createContext({
    DEFAULT_STAGE2: blueprint, LAUNCH_CATALOG: catalog,
    STORAGE_KEY_STAGE2:'s2', STORAGE_KEY_STAGE3:'s3', STORAGE_KEY_CATALOG:'catalog',
    localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},
    getCatalog:()=>catalog, confirm:()=>approved, handleEdit:()=>captured++,
    renderScriptBlocks:v=>rendered=v, setStage:()=>{}, showSaveBadge:()=>{},
    syncToFirestore:()=>synced++, loadState:()=>{}, alert:()=>{},
    lastResearchResults:[], requestVoiceDraft:()=>{}, closeDrawer:()=>{},
    selectedIds:new Set(['source']), OUTLIER_DATABASE:[{id:'source',channel:'Research',brickContribution:'Insight'}]
  });
  for (const name of ['compileScriptFromBlueprint','recompileScriptFromStage2','regenerateStagesFromCohort']) vm.runInContext(fn(name), context);
  return {context,store,catalog,state:()=>({rendered,synced,captured})};
}
test('all inline JavaScript parses; only one compiler handler exists',()=>{
  for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
  assert.equal((html.match(/function recompileScriptFromStage2\(/g)||[]).length,1);
});
test('all nine blueprint fields arrive in seven script sections',()=>{
  const h=harness(); h.context.recompileScriptFromStage2();
  const script=JSON.parse(h.store.get('s3'));
  assert.equal(script.length,7);
  for(const field of fields) assert.ok(JSON.stringify(script).includes(blueprint[field]));
  assert.ok(!JSON.stringify(script).includes('undefined'));
  assert.equal(h.state().synced,1); assert.equal(h.state().captured,1);
  assert.equal(h.catalog[0].stage3.length,7);
});
test('cancelled recompile preserves script and does not sync',()=>{
  const h=harness(false), before=h.store.get('s3'); h.context.recompileScriptFromStage2();
  assert.equal(h.store.get('s3'),before); assert.equal(h.state().synced,0); assert.equal(h.state().captured,0);
});
test('cohort adaptation requests a preview without changing beats or narration',()=>{
  const h=harness(), before=JSON.stringify([...h.store]);
  h.context.lastResearchResults=[{status:'analyzed'}];
  let action;
  h.context.requestVoiceDraft=v=>action=v;
  h.context.regenerateStagesFromCohort();
  assert.equal(action,'options'); assert.equal(JSON.stringify([...h.store]),before);
  assert.equal(h.state().synced,0);
});
test('cohort adaptation without verified findings preserves both stages',()=>{
  const h=harness(), before=JSON.stringify([...h.store]);
  h.context.requestVoiceDraft=()=>{throw new Error('Unexpected AI request');};
  h.context.regenerateStagesFromCohort();
  assert.equal(JSON.stringify([...h.store]),before); assert.equal(h.state().synced,0);
});
