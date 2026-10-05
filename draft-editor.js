// Drafts are previews until explicitly applied. Source notes stay out of speech.
let draftBusy = false;
let pendingVoiceDraft = null;
let transcriptionBusy = false;

async function loadResearchCapabilities() {
  const button = document.getElementById('researchAudioButton');
  button.disabled = true;
  try {
    const response = await fetch('/api/capabilities', {headers:{'Authorization':'Bearer ' + (localStorage.getItem('tca_studio_key') || '')}});
    if (!response.ok) return;
    const capabilities = await response.json();
    button.disabled = capabilities.transcriptionEnabled !== true;
    if (!button.disabled) document.getElementById('researchAudioStatus').textContent = 'Ready for an owner-confirmed audio excerpt.';
  } catch (_) { /* Keep the unverified path disabled. */ }
}

async function uploadResearchAudio() {
  if (transcriptionBusy) return;
  const ids = Array.from(selectedIds);
  const file = document.getElementById('researchAudioFile').files[0];
  const confirmedSource = document.getElementById('researchAudioConsent').checked;
  if (ids.length !== 1 || !file || !confirmedSource) {
    alert('Select one radar video, choose a permitted WAV excerpt, and confirm the source.');
    return;
  }
  if (file.size > 8 * 1024 * 1024) { alert('Use an audio excerpt under 8 MiB.'); return; }
  const startSeconds = Number(document.getElementById('researchAudioOffset').value);
  const replaceTranscript = document.getElementById('researchAudioReplace').checked;
  const status = document.getElementById('researchAudioStatus');
  transcriptionBusy = true;
  status.textContent = 'Transcribing with Gemini 3.5 Transcribe…';
  try {
    const audioBase64 = await new Promise((resolve,reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = () => reject(new Error('Could not read audio file'));
      reader.readAsDataURL(file);
    });
    const response = await fetch('/api/transcribe', {method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer ' + (localStorage.getItem('tca_studio_key') || '')},
      body:JSON.stringify({videoId:ids[0],audioBase64,startSeconds,replaceTranscript,confirmedSource})});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || 'Transcription failed (HTTP ' + response.status + ')');
    lastResearchResults = lastResearchResults.filter(r => r.videoId !== ids[0]);
    status.textContent = `Transcript saved (${result.segments} segments). Return to the radar and analyze the selected video to extract source-backed findings.`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    transcriptionBusy = false;
  }
}

function currentDraftSnapshot() {
  const id = localStorage.getItem('tca_active_ideation_id') || LAUNCH_CATALOG[0].id;
  const current = getCatalog().find(v => v.id === id) || LAUNCH_CATALOG[0];
  return {id, title:current.title, lastDraftId:current.lastDraftId || null,
    researchIds:current.researchIds || [],
    stage2:JSON.parse(localStorage.getItem(STORAGE_KEY_STAGE2) || JSON.stringify(DEFAULT_STAGE2)),
    stage3:JSON.parse(localStorage.getItem(STORAGE_KEY_STAGE3) || JSON.stringify(DEFAULT_STAGE3))};
}

function archiveDraft(snapshot) {
  const key = 'tca_revision_' + snapshot.id + '_' + Date.now() + '_' + crypto.randomUUID();
  // Archive must succeed before any replacement; storage errors abort the action.
  localStorage.setItem(key, JSON.stringify({...snapshot, archivedAt:new Date().toISOString()}));
}

function installDraft(snapshot) {
  const catalog = getCatalog();
  const index = catalog.findIndex(v => v.id === snapshot.id);
  if (index === -1) throw new Error('Episode no longer exists; nothing was applied');
  catalog[index] = {...catalog[index], title:snapshot.title, stage2:snapshot.stage2,
    stage3:snapshot.stage3, lastDraftId:snapshot.lastDraftId, researchIds:snapshot.researchIds};
  localStorage.setItem(STORAGE_KEY_CATALOG, JSON.stringify(catalog));
  localStorage.setItem(STORAGE_KEY_STAGE2, JSON.stringify(snapshot.stage2));
  localStorage.setItem(STORAGE_KEY_STAGE3, JSON.stringify(snapshot.stage3));
  loadState();
  if (typeof updateIdeationSelector === 'function') updateIdeationSelector(catalog);
  const title = document.querySelector?.('#stageView-1 h2');
  if (title) title.textContent = snapshot.title;
  syncToFirestore();
}

async function requestVoiceDraft(action) {
  if (draftBusy) return;
  if (action === 'narration' && !confirm('Approve the current seven beats for narration? AI will create a preview, not replace your script.')) return;
  handleEdit();
  const input = currentDraftSnapshot();
  const chosen = Array.from(selectedIds);
  const results = lastResearchResults.filter(r => r.status === 'analyzed' && chosen.includes(r.videoId));
  if (chosen.length && results.length !== chosen.length) {
    alert('Analyze all selected sources first, or clear the radar selection to draft without outlier research.');
    return;
  }
  const analysisIds = chosen.length ? results.map(r => r.analysisId) : input.researchIds;
  draftBusy = true;
  pendingVoiceDraft = null;
  document.getElementById('voiceDraftPreview').replaceChildren();
  const status = document.getElementById('voiceDraftStatus');
  status.textContent = 'Drafting a preview with Gemini 3.8 Flash… Existing beats and script are unchanged.';
  try {
    const response = await fetch('/api/draft', {method:'POST',
      headers:{'Content-Type':'application/json', 'Authorization':'Bearer ' + (localStorage.getItem('tca_studio_key') || '')},
      body:JSON.stringify({action, episodeId:input.id, title:input.title, blueprint:input.stage2,
        analysisIds, approved:action === 'narration'})});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || 'Drafting failed (HTTP ' + response.status + '). Current script was not replaced.');
    }
    const draft = await response.json();
    pendingVoiceDraft = {input, draft};
    renderVoiceDraft(draft);
    status.textContent = `${draft.voiceVersion} · ${draft.researchStatus} · ${draft.cached ? 'cached' : 'new'} preview. Review before applying.`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    draftBusy = false;
  }
}

function renderVoiceDraft(draft) {
  const box = document.getElementById('voiceDraftPreview');
  box.replaceChildren();
  const text = (parent, value) => {
    const node = document.createElement('p');
    node.className = 'whitespace-pre-wrap text-sm';
    node.textContent = value;
    parent.appendChild(node);
  };
  const button = (parent, label, handler) => {
    const node = document.createElement('button');
    node.className = 'px-4 py-2 bg-amber-700 rounded-lg mt-3';
    node.textContent = label;
    node.onclick = handler;
    parent.appendChild(node);
  };
  if (draft.action === 'options') {
    draft.result.options.forEach((option, index) => {
      const card = document.createElement('details');
      card.className = 'bg-black/20 rounded-xl p-4 space-y-3';
      const heading = document.createElement('summary');
      heading.textContent = `${index + 1}. ${option.title}`;
      card.appendChild(heading);
      text(card, `Hook: ${option.hook}\n\nWhy: ${option.rationale}\nKeywords: ${option.keywords.join(', ')}`);
      text(card, 'Research references: ' + (option.sourceIds.join(', ') || 'None — editorial suggestion'));
      for (const [key, value] of Object.entries(option.blueprint)) text(card, `${key}: ${value}`);
      button(card, 'Use this title & seven-beat blueprint', () => applyVoiceDraft(index));
      box.appendChild(card);
    });
  } else {
    text(box, `${draft.result.wordCount} spoken words · about ${draft.result.estimatedMinutes} minutes at 140 words/minute`);
    draft.result.sections.forEach(section => {
      const card = document.createElement('details');
      card.className = 'bg-black/20 rounded-xl p-4';
      const heading = document.createElement('summary');
      heading.textContent = `Beat ${section.beat}: ${section.name}`;
      card.appendChild(heading);
      text(card, section.spoken);
      text(card, 'Production notes (not spoken): ' + section.notes);
      box.appendChild(card);
    });
    text(box, 'Review before recording:\n' + draft.result.reviewNotes.join('\n'));
    button(box, 'Apply reviewed narration to Stage 3', () => applyVoiceDraft());
  }
}

function applyVoiceDraft(optionIndex) {
  if (!pendingVoiceDraft || draftBusy) return;
  handleEdit();
  const current = currentDraftSnapshot();
  const {input, draft} = pendingVoiceDraft;
  if (JSON.stringify(current) !== JSON.stringify(input)) {
    alert('The episode or its text changed after this preview was requested. Generate a fresh preview; nothing was replaced.');
    return;
  }
  if (!confirm('Apply this reviewed draft? A local backup will be saved first; cloud saves also archive the previous version.')) return;
  try {
    const next = JSON.parse(JSON.stringify(current));
    if (draft.action === 'options') {
      const option = draft.result.options[optionIndex];
      if (!option) throw new Error('Choose a valid option');
      next.title = option.title;
      next.stage2 = {...next.stage2, ...option.blueprint};
      // Existing Stage 3 is deliberately preserved until narration is approved.
    } else {
      next.stage3 = draft.result.sections.map(s => ({act:`BEAT ${s.beat}: ${s.name}`, content:s.spoken, notes:s.notes}));
    }
    next.lastDraftId = draft.draftId;
    next.researchIds = draft.researchIds;
    archiveDraft(current);
    installDraft(next);
    pendingVoiceDraft = null;
    document.getElementById('voiceDraftPreview').replaceChildren();
    document.getElementById('voiceDraftStatus').textContent = draft.action === 'options'
      ? 'Blueprint applied. Stage 3 is unchanged; approve your beats to generate narration.'
      : 'Reviewed narration applied. Production notes remain separate from speech.';
    if (draft.action === 'narration') setStage(3);
  } catch (error) {
    alert(error.message + '. Your archived version remains available if a local write failed.');
  }
}

function restorePreviousDraft() {
  handleEdit();
  const current = currentDraftSnapshot();
  const prefix = 'tca_revision_' + current.id + '_';
  const versions = [];
  for (let i=0; i<localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key.startsWith(prefix)) versions.push(JSON.parse(localStorage.getItem(key)));
  }
  versions.sort((a,b) => b.archivedAt.localeCompare(a.archivedAt));
  if (!versions.length) { alert('No local revision is available for this episode.'); return; }
  if (!confirm('Restore the previous local version? The current version will also be backed up.')) return;
  try {
    archiveDraft(current);
    installDraft(versions[0]);
    pendingVoiceDraft = null;
    document.getElementById('voiceDraftPreview').replaceChildren();
    document.getElementById('voiceDraftStatus').textContent = 'Previous local version restored.';
  } catch (error) { alert(error.message); }
}
