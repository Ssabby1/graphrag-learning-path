
<template>
  <div class="page">
    <section class="hero card">
      <div class="hero-topline">
        <span class="eyebrow">{{ t('heroEyebrow') }}</span>
        <button class="lang-toggle" @click="toggleLanguage">{{ language === 'zh' ? 'ZH / EN' : 'EN / ZH' }}</button>
      </div>
      <h1>{{ t('heroTitle') }}</h1>
      <p class="hero-text">{{ t('heroBody') }}</p>
      <div v-if="showGuide" class="guide-box">
        <strong>{{ t('guideTitle') }}</strong>
        <span>{{ nextHint }}</span>
        <button class="ghost-button" @click="showGuide = false">{{ t('hideGuide') }}</button>
      </div>
      <div class="status-strip">
        <span class="status-chip" :class="serviceStatusClass">{{ t('serviceStatus') }} / {{ serviceStatusLabel }}</span>
        <span class="status-chip muted">{{ t('selectedTarget') }} / {{ selectedTarget ? displayConcept(selectedTarget) : t('notSelected') }}</span>
      </div>
    </section>

    <div v-if="uiError" class="error-banner card">
      <strong>{{ t('serviceNotice') }}</strong>
      <span>{{ uiError }}</span>
    </div>

    <section class="workspace card">
      <div class="section-head">
        <div>
          <div class="section-kicker">{{ t('plannerInput') }}</div>
          <h2>{{ t('plannerTitle') }}</h2>
          <p class="section-text">{{ t('plannerDescription') }}</p>
        </div>
        <button class="ghost-button" @click="bootstrap">{{ t('refreshData') }}</button>
      </div>

      <div class="step-row">
        <div v-for="step in steps" :key="step.key" class="step-card" :class="{ active: step.active, done: step.done }">
          <span class="step-index">{{ step.index }}</span>
          <div>
            <strong>{{ step.title }}</strong>
            <p>{{ step.desc }}</p>
          </div>
        </div>
      </div>

      <div class="field command-bar">
        <label class="command-label">{{ t('targetConcept') }}</label>
        <input v-model="targetQuery" class="text-input command-input" :placeholder="t('targetPlaceholder')" @focus="showTargetDropdown = true" />
        <button v-if="selectedTarget" class="chip-button" @click="clearTarget">{{ t('clearSelection') }}</button>
        <div v-if="showTargetDropdown && targetOptions.length" class="search-panel command-panel">
          <button v-for="item in targetOptions" :key="item.concept_id" class="search-option" @click="selectTarget(item)">
            <span class="option-title">{{ displayConcept(item) }}</span>
            <span class="option-meta">{{ item.concept_id }}</span>
            <span class="option-desc">{{ item.description || t('noDescription') }}</span>
          </button>
        </div>
      </div>

      <div class="planner-grid">
        <div class="planner-main">
          <div class="field">
            <label>{{ t('masteredConcepts') }}</label>
            <p class="field-hint">{{ t('masteredHelp') }}</p>
            <input v-model="masteredQuery" class="text-input" :placeholder="t('masteredPlaceholder')" @focus="showMasteredDropdown = true" />
            <div v-if="masteredConcepts.length" class="token-list">
              <span v-for="item in masteredConcepts" :key="item.concept_id" class="token">
                <span>{{ displayConcept(item) }}</span>
                <button class="token-remove" @click="removeMastered(item.concept_id)" :aria-label="t('removeMasteredAria')">x</button>
              </span>
            </div>
            <div v-if="showMasteredDropdown && masteredOptions.length" class="search-panel">
              <button v-for="item in masteredOptions" :key="item.concept_id" class="search-option" @click="addMastered(item)">
                <span class="option-title">{{ displayConcept(item) }}</span>
                <span class="option-meta">{{ item.concept_id }}</span>
                <span class="option-desc">{{ item.description || t('noDescription') }}</span>
              </button>
            </div>
          </div>

          <div class="field">
            <label>{{ t('learningQuestion') }}</label>
            <p class="field-hint">{{ t('questionHelp') }}</p>
            <textarea v-model="question" class="text-area" :placeholder="t('questionPlaceholder')" rows="4"></textarea>
          </div>

          <div class="planner-actions">
            <button class="ghost-button" @click="interpretQuestion">{{ plannerPending ? t('identifying') : t('identifyTarget') }}</button>
            <button class="primary-button" @click="recommendPath">{{ recommendPending ? t('generatePathPending') : t('recommendPath') }}</button>
            <button class="secondary-button" @click="runGraphRagQuery">{{ graphragPending ? t('generateExplanationPending') : t('generateExplanation') }}</button>
          </div>
        </div>

        <aside class="snapshot">
          <div class="section-kicker">{{ t('targetSnapshot') }}</div>
          <h3>{{ selectedTarget ? displayConcept(selectedTarget) : t('pickTarget') }}</h3>
          <p class="snapshot-copy">{{ selectedConceptDetail.description || t('targetSnapshotPlaceholder') }}</p>
          <div class="snapshot-list">
            <div class="info-stack"><span>{{ t('internalId') }}</span><strong>{{ selectedTarget?.concept_id || '-' }}</strong></div>
            <div class="info-stack"><span>{{ t('chapter') }}</span><strong>{{ selectedConceptDetail.chapter_name || '-' }}</strong></div>
            <div class="info-stack"><span>{{ t('plannerInterpretation') }}</span><strong>{{ plannerSourceLabel }}</strong><small class="muted-copy">{{ plannerSummaryText }}</small></div>
          </div>
        </aside>
      </div>
    </section>

    <section class="graph-section card">
      <div class="section-kicker">Graph View</div>
      <h2>Learning Path Graph</h2>
      <p class="section-text">The graph highlights the generated path in order.</p>
      <div ref="chartRef" class="chart"></div>
    </section>

    <section class="results-grid">
      <article class="card result-card">
        <div class="section-kicker">{{ t('pathResult') }}</div>
        <h2>{{ t('recommendationSummary') }}</h2>
        <p class="section-text">{{ recommendResult.explanation || t('pathPlaceholder') }}</p>
        <div class="chip-list">
          <span v-for="item in recommendPathCards" :key="item.concept_id" class="summary-tag">{{ item.label }}</span>
        </div>
        <div v-if="recommendResult.reasoning_steps?.length" class="list-block">
          <strong>{{ t('reasoningSteps') }}</strong>
          <ul>
            <li v-for="(item, index) in recommendResult.reasoning_steps" :key="index">{{ item }}</li>
          </ul>
        </div>
      </article>

      <article class="card result-card">
        <div class="section-kicker">{{ t('graphRagAnswer') }}</div>
        <h2>{{ t('naturalLanguageExplanation') }}</h2>
        <p class="section-text">{{ graphragResult.answer || t('graphRagPlaceholder') }}</p>
        <div class="chip-list">
          <span v-for="item in citationCards" :key="item.key" class="summary-tag soft">{{ item.label }} / {{ item.meta }}</span>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { fetchConceptCorpus, fetchConceptDetail, fetchGraphOverview, fetchGraphRagQuery, fetchHealth, fetchPlannerInterpret, fetchRecommendPath } from '../api/client';
const zh = { heroEyebrow:'知识图谱驱动的学习规划',heroTitle:'先说你想学什么，我们把路径和依据整理给你',heroBody:'按知识点名称搜索，或直接用一句自然语言描述目标。系统会帮你识别关键概念、生成推荐路径，并补充文字解释。',guideTitle:'你可以这样开始',hideGuide:'收起',serviceStatus:'服务状态',selectedTarget:'当前目标',notSelected:'未选择',serviceNotice:'服务提示',plannerInput:'路径输入',plannerTitle:'从目标知识点开始规划',plannerDescription:'先选目标，再补充已掌握知识点或学习问题。',refreshData:'刷新数据',targetConcept:'目标知识点',targetPlaceholder:'输入知识点名称、ID 或描述关键词',noDescription:'暂无描述',masteredConcepts:'已掌握知识点',masteredHelp:'这里支持和目标知识点一样的检索下拉，你可以按名称查看对应编号再选择。',masteredPlaceholder:'输入已掌握知识点名称、ID 或描述关键词',learningQuestion:'学习问题',questionHelp:'例如：如果我想学习布尔代数，应该先掌握什么？',questionPlaceholder:'输入一句自然语言问题',identifying:'正在识别...',identifyTarget:'从问题中识别目标',generatePathPending:'正在生成路径...',recommendPath:'生成学习路径',generateExplanationPending:'正在生成解释...',generateExplanation:'生成文字解释',targetSnapshot:'目标概览',pickTarget:'请选择一个目标知识点',targetSnapshotPlaceholder:'选中目标后，这里会显示基础信息。',internalId:'内部 ID',chapter:'章节',plannerInterpretation:'问题识别结果',plannerInterpretationIdle:'你还没有解析学习问题。',pathResult:'路径结果',recommendationSummary:'推荐摘要',pathPlaceholder:'点击“生成学习路径”后，这里会显示推荐结果。',reasoningSteps:'推理步骤',graphRagAnswer:'文字解释',naturalLanguageExplanation:'自然语言说明',graphRagPlaceholder:'点击“生成文字解释”后，这里会显示回答。',clearSelection:'清除',removeMasteredAria:'移除已掌握知识点',online:'在线',checkRequired:'需要检查',backendUnavailable:'后端不可用',conceptNotFound:'未找到知识点',requestFailed:'请求失败',chooseTargetFirst:'请先选择一个目标知识点。',stepTargetTitle:'选定目标',stepTargetDescription:'先确认你想学的知识点。',stepQuestionTitle:'补充背景',stepQuestionDescription:'告诉系统你已经会什么，或直接写问题。',stepResultTitle:'查看结果',stepResultDescription:'生成路径和解释。',hintSelectTarget:'先搜索并选择一个目标知识点。',hintAddBackground:'目标已经选好了，现在可以补充已掌握知识点或学习问题。',hintGeneratePath:'信息已经足够，可以直接生成学习路径。',hintReadResult:'路径已经生成，可以继续生成文字解释。' };
const en = { heroEyebrow:'Graph-Backed Learning Planner',heroTitle:'Tell us what you want to learn, and we will lay out the path and evidence',heroBody:'Search by concept name or describe your goal in one sentence. The system helps identify key concepts, generate a learning path, and explain the result.',guideTitle:'You can start here',hideGuide:'Hide',serviceStatus:'Service',selectedTarget:'Current target',notSelected:'Not selected',serviceNotice:'Service notice',plannerInput:'Path input',plannerTitle:'Start from the concept you want to learn',plannerDescription:'Choose a target, then add mastered concepts or a learning question.',refreshData:'Refresh data',targetConcept:'Target concept',targetPlaceholder:'Type a concept name, ID, or description keyword',noDescription:'No description',masteredConcepts:'Mastered concepts',masteredHelp:'This field now supports the same searchable dropdown as the target field, so you can see names and IDs before selecting.',masteredPlaceholder:'Type a mastered concept name, ID, or keyword',learningQuestion:'Learning question',questionHelp:'Example: If I want to learn Boolean algebra, what should I study first?',questionPlaceholder:'Enter one natural-language question',identifying:'Identifying...',identifyTarget:'Identify from question',generatePathPending:'Generating path...',recommendPath:'Generate learning path',generateExplanationPending:'Generating explanation...',generateExplanation:'Generate explanation',targetSnapshot:'Target snapshot',pickTarget:'Choose a target concept',targetSnapshotPlaceholder:'Basic information will appear here after you choose a target.',internalId:'Internal ID',chapter:'Chapter',plannerInterpretation:'Question interpretation',plannerInterpretationIdle:'You have not parsed a learning question yet.',pathResult:'Path result',recommendationSummary:'Recommendation summary',pathPlaceholder:'Click “Generate learning path” to see the result here.',reasoningSteps:'Reasoning steps',graphRagAnswer:'Written explanation',naturalLanguageExplanation:'Natural-language explanation',graphRagPlaceholder:'Click “Generate explanation” to see the answer here.',clearSelection:'Clear',removeMasteredAria:'Remove mastered concept',online:'Online',checkRequired:'Check required',backendUnavailable:'Backend unavailable',conceptNotFound:'Concept not found',requestFailed:'Request failed',chooseTargetFirst:'Please choose a target concept first.',stepTargetTitle:'Choose a target',stepTargetDescription:'Start with the concept you want to learn.',stepQuestionTitle:'Add context',stepQuestionDescription:'Tell the system what you already know, or ask a question.',stepResultTitle:'Read the result',stepResultDescription:'Generate the path and explanation.',hintSelectTarget:'Start by searching for a target concept.',hintAddBackground:'The target is ready. Now add mastered concepts or a learning question.',hintGeneratePath:'You have enough context. Generate the learning path next.',hintReadResult:'The path is ready. You can generate the written explanation next.' };
const COPY = { zh, en };
const language = ref('zh');
const uiError = ref('');
const health = ref({});
const overview = ref({});
const conceptCorpus = ref([]);
const targetQuery = ref('');
const masteredQuery = ref('');
const selectedTargetId = ref('');
const masteredIds = ref([]);
const selectedConceptDetail = ref({});
const recommendResult = ref({});
const graphragResult = ref({});
const question = ref('');
const showTargetDropdown = ref(false);
const showMasteredDropdown = ref(false);
const plannerResult = ref({});
const plannerPending = ref(false);
const recommendPending = ref(false);
const graphragPending = ref(false);
const showGuide = ref(false);
const chartRef = ref(null);
const chartIns = ref(null);
const t = (k) => COPY[language.value][k] || k;
const conceptMap = computed(() => conceptCorpus.value.reduce((acc, item) => ((acc[item.concept_id] = item), acc), {}));
const selectedTarget = computed(() => conceptMap.value[selectedTargetId.value] || null);
const masteredConcepts = computed(() => masteredIds.value.map((id) => conceptMap.value[id]).filter(Boolean));
const serviceStatusClass = computed(() => (health.value?.status === 'ok' ? 'ok' : 'warning'));
const serviceStatusLabel = computed(() => (health.value?.status === 'ok' ? t('online') : t('checkRequired')));
const targetOptions = computed(() => filterConcepts(targetQuery.value));
const masteredOptions = computed(() => filterConcepts(masteredQuery.value, masteredIds.value));
const heroMetrics = computed(() => [{ label: 'Courses', value: overview.value.course_count ?? '-', note: 'Graph' }, { label: 'Chapters', value: overview.value.chapter_count ?? '-', note: 'Structure' }, { label: 'Concepts', value: overview.value.concept_count ?? conceptCorpus.value.length ?? '-', note: 'Corpus' }, { label: 'Prereqs', value: overview.value.prerequisite_rel_count ?? '-', note: 'Edges' }]);
const steps = computed(() => [{ key:'target', index:'01', title:t('stepTargetTitle'), desc:t('stepTargetDescription'), active:!selectedTargetId.value, done:Boolean(selectedTargetId.value) }, { key:'context', index:'02', title:t('stepQuestionTitle'), desc:t('stepQuestionDescription'), active:Boolean(selectedTargetId.value) && !recommendResult.value.path?.length, done:Boolean(masteredIds.value.length || question.value.trim()) }, { key:'result', index:'03', title:t('stepResultTitle'), desc:t('stepResultDescription'), active:Boolean(recommendResult.value.path?.length), done:Boolean(recommendResult.value.path?.length || graphragResult.value.answer) }]);
const nextHint = computed(() => !selectedTargetId.value ? t('hintSelectTarget') : !masteredIds.value.length && !question.value.trim() ? t('hintAddBackground') : !recommendResult.value.path?.length ? t('hintGeneratePath') : t('hintReadResult'));
const plannerSourceLabel = computed(() => plannerPending.value ? t('identifying') : plannerResult.value.interpretation_source || '-');
const plannerSummaryText = computed(() => plannerResult.value.summary || t('plannerInterpretationIdle'));
const recommendPathCards = computed(() => (recommendResult.value.path || []).map((id) => ({ concept_id:id, label:displayConceptById(id) })));
const citationCards = computed(() => (graphragResult.value.citations || []).map((item, index) => ({ key:`${item.concept_id}-${index}`, label:displayConceptById(item.concept_id), meta:[item.kind, item.source, item.score != null ? `score ${Number(item.score).toFixed(2)}` : ''].filter(Boolean).join(' / ') })));
function normalizeQuery(v) { return v.trim().toLowerCase(); }
function filterConcepts(query, excludeIds = []) { const q = normalizeQuery(query); const excluded = new Set(excludeIds); const pool = conceptCorpus.value.filter((item) => !excluded.has(item.concept_id)); return (!q ? pool : pool.filter((item) => `${item.concept_id} ${item.name} ${item.description}`.toLowerCase().includes(q))).slice(0, 8); }
function displayConcept(item) { if (!item) return t('notSelected'); return item.name ? `${item.name} (${item.concept_id})` : item.concept_id; }
function displayConceptById(id) { return displayConcept(conceptMap.value[id] || { concept_id:id, name:'' }); }
function mapError(resp) { if (!resp || resp.ok) return ''; if (resp.status === 503) return `${t('backendUnavailable')}: ${resp.detail}`; if (resp.status === 404) return `${t('conceptNotFound')}: ${resp.detail}`; return `${t('requestFailed')}: ${resp.detail}`; }
function selectTarget(item) { selectedTargetId.value = item.concept_id; targetQuery.value = item.name || item.concept_id; showTargetDropdown.value = false; if (!question.value.trim()) question.value = language.value === 'zh' ? `如果我想学习${item.name || item.concept_id}，应该先掌握什么？` : `If I want to learn ${item.name || item.concept_id}, what should I study first?`; }
function clearTarget() { selectedTargetId.value = ''; targetQuery.value = ''; selectedConceptDetail.value = {}; recommendResult.value = {}; graphragResult.value = {}; }
function addMastered(item) { if (!masteredIds.value.includes(item.concept_id)) masteredIds.value = [...masteredIds.value, item.concept_id]; masteredQuery.value = ''; showMasteredDropdown.value = true; }
function removeMastered(id) { masteredIds.value = masteredIds.value.filter((value) => value !== id); }
async function bootstrap() { uiError.value = ''; const [healthResp, overviewResp, corpusResp] = await Promise.all([fetchHealth(), fetchGraphOverview(), fetchConceptCorpus()]); if (healthResp.ok) health.value = healthResp.data; else uiError.value = mapError(healthResp); if (overviewResp.ok) overview.value = overviewResp.data; else uiError.value = uiError.value || mapError(overviewResp); if (corpusResp.ok) conceptCorpus.value = corpusResp.data.items || []; else uiError.value = uiError.value || mapError(corpusResp); }
async function interpretQuestion() { uiError.value = ''; if (!question.value.trim() || plannerPending.value) return; plannerPending.value = true; const res = await fetchPlannerInterpret({ question: question.value.trim() }); plannerPending.value = false; if (res.ok) { plannerResult.value = res.data; if (res.data.target_concept_id && conceptMap.value[res.data.target_concept_id]) selectTarget(conceptMap.value[res.data.target_concept_id]); if (Array.isArray(res.data.mastered_concepts) && res.data.mastered_concepts.length) masteredIds.value = [...new Set(res.data.mastered_concepts.filter((id) => conceptMap.value[id]))]; return; } uiError.value = mapError(res); }
async function recommendPath() { uiError.value = ''; if (!selectedTargetId.value || recommendPending.value) { if (!selectedTargetId.value) uiError.value = t('chooseTargetFirst'); return; } recommendPending.value = true; const res = await fetchRecommendPath({ target_concept_id: selectedTargetId.value, mastered_concepts: masteredIds.value }); recommendPending.value = false; if (res.ok) { recommendResult.value = res.data; return; } uiError.value = mapError(res); }
async function runGraphRagQuery() { uiError.value = ''; if (!selectedTargetId.value || graphragPending.value) { if (!selectedTargetId.value) uiError.value = t('chooseTargetFirst'); return; } graphragPending.value = true; const fallbackQuestion = question.value.trim() || (language.value === 'zh' ? `如果我想学习${selectedTarget.value?.name || selectedTargetId.value}，应该先掌握什么？` : `If I want to learn ${selectedTarget.value?.name || selectedTargetId.value}, what should I study first?`); const res = await fetchGraphRagQuery({ question: fallbackQuestion, target_concept_id: selectedTargetId.value, mastered_concepts: masteredIds.value }); graphragPending.value = false; if (res.ok) { graphragResult.value = res.data; return; } uiError.value = mapError(res); }
function toggleLanguage() { language.value = language.value === 'zh' ? 'en' : 'zh'; }
function dismissGuide() { showGuide.value = false; window.localStorage.setItem('graph-planner-guide-dismissed', 'true'); }
function renderChart(path = []) {
  if (!chartIns.value) return;
  if (!Array.isArray(path) || !path.length) {
    chartIns.value.setOption({
      backgroundColor: 'transparent',
      tooltip: {},
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        label: { show: true, color: '#334155', fontWeight: 600 },
        data: [{ id: 'EMPTY', name: 'Generate a path to see the graph', symbolSize: 84, itemStyle: { color: '#E8EDF2', borderColor: '#B8C3D1', borderWidth: 1.5 } }],
        links: [],
        force: { repulsion: 260 }
      }]
    });
    return;
  }
  const nodes = path.map((id, index) => ({
    id,
    name: displayConceptById(id),
    symbolSize: index === path.length - 1 ? 88 : 64,
    itemStyle: {
      color: index === path.length - 1 ? '#E7D2A8' : '#C9D7E7',
      borderColor: index === path.length - 1 ? '#8E6D35' : '#58789A',
      borderWidth: 1.8
    },
    label: { color: '#1E293B', fontWeight: 600, width: 150, overflow: 'break' }
  }));
  const links = path.slice(0, -1).map((source, i) => ({
    source,
    target: path[i + 1],
    lineStyle: { color: '#8FA6BE', width: 2.2, opacity: 0.8 }
  }));
  chartIns.value.setOption({
    backgroundColor: 'transparent',
    tooltip: {},
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 10],
      force: { repulsion: 340, edgeLength: 150 },
      emphasis: { focus: 'adjacency' },
      label: { show: true },
      data: nodes,
      links
    }]
  });
}
function handleDocumentClick(event) { const target = event.target; if (!(target instanceof HTMLElement)) return; if (!target.closest('.field') && !target.closest('.command-bar')) { showTargetDropdown.value = false; showMasteredDropdown.value = false; } }
watch(selectedTargetId, async (id) => { if (!id) return; const res = await fetchConceptDetail(id); if (res.ok) selectedConceptDetail.value = res.data; });
watch(() => recommendResult.value.path, (path) => { nextTick(() => renderChart(path || [])); });
watch(() => graphragResult.value.path, (path) => { if (!recommendResult.value.path?.length) nextTick(() => renderChart(path || [])); });
onMounted(async () => {
  showGuide.value = window.localStorage.getItem('graph-planner-guide-dismissed') !== 'true';
  document.addEventListener('click', handleDocumentClick);
  chartIns.value = echarts.init(chartRef.value);
  renderChart([]);
  await bootstrap();
});
onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick);
  if (chartIns.value) chartIns.value.dispose();
});
</script>

<style scoped>
.page{width:min(1320px,calc(100% - 48px));margin:0 auto;padding:clamp(24px,4vw,52px) 0 64px}.card{position:relative;overflow:hidden;border:1px solid rgba(15,23,42,.07);background:rgba(255,255,255,.9);border-radius:22px;box-shadow:0 10px 30px rgba(15,23,42,.05)}.hero,.overview-row,.workspace,.results-grid,.graph-section{display:grid;gap:20px;margin-bottom:20px}.hero,.overview-row,.workspace,.graph-section{grid-template-columns:1fr}.hero,.workspace,.graph-section{padding:26px}.hero-topline,.section-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.section-head.compact{margin-bottom:12px}.eyebrow,.section-kicker,.summary-label{display:inline-flex;color:#7c4a1d;font-size:.74rem;letter-spacing:.14em;text-transform:uppercase}.hero h1,.workspace h2,.graph-section h2,.result-card h2,.overview h2,.guide-box strong,.snapshot h3{margin:0;color:#0f172a;font-family:"Georgia","Times New Roman","Source Han Serif SC","Songti SC",serif;font-weight:600;line-height:1.08}.hero h1{max-width:13ch;font-size:clamp(2.4rem,4vw,4.2rem)}.hero-text,.section-text,.field-hint,.option-desc,.snapshot-copy,.metric small,.guide-box span,.step-card p,.list-block li{color:#475569;line-height:1.7}.guide-box{display:grid;gap:10px;padding:16px 18px;border-radius:18px;border:1px solid rgba(148,163,184,.14);background:rgba(248,250,252,.84)}.hero-actions,.planner-actions,.status-strip,.token-list,.chip-list{display:flex;gap:12px;flex-wrap:wrap}.overview{padding:22px}.hero-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.metric,.step-card,.snapshot{display:grid;gap:8px;padding:14px 16px;border-radius:16px;background:rgba(255,255,255,.72);border:1px solid rgba(148,163,184,.12)}.metric strong{color:#0f172a;font-size:clamp(1.7rem,3vw,2.5rem);font-family:"Georgia","Times New Roman","Source Han Serif SC","Songti SC",serif}.error-banner{display:flex;gap:10px;align-items:flex-start;padding:18px 22px;color:#9a3412;background:rgba(255,247,237,.96);border-color:rgba(234,88,12,.12)}.primary-button,.secondary-button,.ghost-button,.lang-toggle,.search-option,.token-remove,.chip-button{border:none;cursor:pointer;font:inherit}.primary-button,.secondary-button,.ghost-button,.lang-toggle,.chip-button{min-height:44px;padding:0 18px;border-radius:999px;transition:transform .18s ease,box-shadow .18s ease,background-color .18s ease,color .18s ease}.primary-button{color:#f8fafc;background:#1e3a5f}.secondary-button,.lang-toggle,.chip-button{color:#35506f;background:rgba(226,232,240,.8)}.ghost-button{color:#334155;background:rgba(241,245,249,.78)}.primary-button:hover,.secondary-button:hover,.ghost-button:hover,.lang-toggle:hover,.search-option:hover,.token-remove:hover,.chip-button:hover{transform:translateY(-1px)}.primary-button:focus-visible,.secondary-button:focus-visible,.ghost-button:focus-visible,.lang-toggle:focus-visible,.text-input:focus,.text-area:focus,.search-option:focus-visible,.token-remove:focus-visible,.chip-button:focus-visible{outline:none;box-shadow:0 0 0 4px rgba(37,99,235,.14)}.status-chip{display:inline-flex;align-items:center;min-height:38px;padding:0 14px;border-radius:999px;background:rgba(248,250,252,.9);color:#334155;border:1px solid rgba(148,163,184,.16)}.status-chip.ok{background:rgba(240,253,244,.92);color:#166534}.status-chip.warning{background:rgba(255,247,237,.92);color:#9a3412}.planner-flow{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,.72fr);gap:22px;margin-top:18px}.planner-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.step-card{grid-template-columns:auto 1fr;align-items:flex-start}.step-card.active{border-color:rgba(30,58,95,.28)}.step-card.done{background:rgba(245,248,251,.92)}.step-index{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:999px;background:#e8eef4;color:#1e3a5f;font-weight:700;font-size:.88rem}.command-bar,.field{position:relative}.command-bar{margin-top:22px;padding:18px 0;border-top:1px solid rgba(148,163,184,.16);border-bottom:1px solid rgba(148,163,184,.16);display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:14px;align-items:center}.command-label,.field label{color:#1e293b;font-weight:600}.planner-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(280px,.7fr);gap:28px;margin-top:24px}.planner-main{display:grid;gap:22px}.text-input,.text-area{width:100%;padding:15px 17px;border-radius:14px;border:1px solid rgba(148,163,184,.18);background:rgba(255,255,255,.94);color:#0f172a;transition:border-color .18s ease,box-shadow .18s ease}.command-input{min-height:52px}.text-area{min-height:120px;resize:vertical}.text-input::placeholder,.text-area::placeholder{color:#94a3b8}.search-panel{position:absolute;inset:calc(100% + 10px) 0 auto;z-index:12;max-height:300px;overflow:auto;padding:10px;border-radius:18px;border:1px solid rgba(148,163,184,.14);background:rgba(255,255,255,.98);box-shadow:0 16px 40px rgba(15,23,42,.08)}.search-option{width:100%;text-align:left;display:grid;gap:5px;margin-bottom:8px;padding:12px 14px;border-radius:18px;background:transparent;transition:background-color .18s ease,transform .18s ease}.search-option:last-child{margin-bottom:0}.search-option:hover{background:rgba(241,245,249,.92)}.option-title{color:#0f172a;font-weight:600}.option-meta,.info-stack span{color:#64748b}.token{display:inline-flex;align-items:center;gap:8px;min-height:38px;padding:0 12px;border-radius:999px;background:rgba(241,245,249,.95);color:#0f172a}.token-remove{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:999px;background:rgba(255,255,255,.9);color:#1e3a8a}.snapshot-list{display:grid;gap:14px;margin-top:12px}.info-stack{display:grid;gap:6px;padding-top:14px;border-top:1px solid rgba(148,163,184,.16)}.result-card{padding:22px}.chart{min-height:460px;border-radius:18px;background:linear-gradient(180deg,rgba(251,252,253,.98) 0%,rgba(243,246,249,.96) 100%)}.summary-tag{display:inline-flex;align-items:center;min-height:36px;padding:0 12px;border-radius:999px;background:rgba(241,245,249,.95);color:#334155}.summary-tag.soft{background:rgba(255,247,237,.9);color:#9a3412}.list-block ul{margin:8px 0 0;padding-left:18px}.results-grid{grid-template-columns:repeat(2,minmax(0,1fr))}@media (max-width:1200px){.planner-flow,.planner-grid,.hero-metrics,.command-bar,.planner-steps,.results-grid{grid-template-columns:1fr}.hero h1{max-width:none}}@media (max-width:720px){.page{width:min(100% - 20px,1320px);padding-top:18px}.hero,.workspace,.graph-section,.overview,.result-card{padding:20px;border-radius:18px}.hero-topline,.section-head,.guide-box{display:grid}}
</style>

