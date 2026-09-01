<template>
  <section class="evidence-section" aria-labelledby="why-heading">
    <header class="section-heading">
      <div><span class="section-eyebrow">Evidence Pack 1.0</span><h2 id="why-heading">{{ copy.whyTitle }}</h2></div>
      <span class="evidence-count">{{ items.length }} {{ copy.citations }}</span>
    </header>
    <p class="section-copy">{{ copy.whyIntro }}</p>
    <ol v-if="items.length" class="evidence-list">
      <li v-for="(item, index) in items" :key="item.evidence_id" class="evidence-item">
        <span class="evidence-index" aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</span>
        <div class="evidence-body">
          <div class="relationship-line"><strong>{{ conceptName(item.from_concept) }}</strong><span aria-hidden="true">→</span><strong>{{ conceptName(item.to_concept) }}</strong></div>
          <p>{{ localizedReason(item.reason) }}</p>
          <dl class="evidence-meta">
            <div><dt>{{ copy.evidenceId }}</dt><dd translate="no">{{ item.evidence_id }}</dd></div>
            <div><dt>{{ copy.verification }}</dt><dd>{{ item.verification_status }}</dd></div>
            <div><dt>{{ copy.retrieval }}</dt><dd>{{ item.retrieval?.source || 'graph' }}</dd></div>
            <div v-if="item.confidence != null"><dt>{{ copy.confidence }}</dt><dd>{{ percent(item.confidence) }}</dd></div>
          </dl>
        </div>
      </li>
    </ol>
    <div v-else class="empty-state">{{ copy.noEvidence }}</div>
  </section>
</template>
<script setup>
const props=defineProps({items:{type:Array,default:()=>[]},copy:{type:Object,required:true},language:{type:String,default:'en'}});
function conceptName(concept){const name=props.language==='en'?concept?.name_en||concept?.name:concept?.name||concept?.name_en;return name?`${name} (${concept.id})`:concept?.id||'—';}
function localizedReason(reason){const parts=String(reason||'').split(/[；;]/).map((part)=>part.trim()).filter(Boolean);return parts.length>1?(props.language==='en'?parts.at(-1):parts[0]):reason;}
function percent(value){return new Intl.NumberFormat(undefined,{style:'percent',maximumFractionDigits:0}).format(value);}
</script>
<style scoped>
.evidence-section{padding:clamp(24px,4vw,44px);border:1px solid var(--line);background:var(--surface)}.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.section-heading h2{margin:6px 0 0;font:600 clamp(1.65rem,3vw,2.3rem)/1.12 var(--font-display);letter-spacing:-.025em}.section-eyebrow{color:var(--accent-strong);font:700 .72rem/1 var(--font-data);letter-spacing:.12em;text-transform:uppercase}.section-copy{max-width:68ch;margin:14px 0 28px;color:var(--muted);line-height:1.7}.evidence-count{white-space:nowrap;padding:8px 10px;border:1px solid var(--line);font:600 .75rem/1 var(--font-data);color:var(--muted)}.evidence-list{display:grid;margin:0;padding:0;list-style:none}.evidence-item{display:grid;grid-template-columns:50px minmax(0,1fr);gap:18px;padding:24px 0;border-top:1px solid var(--line)}.evidence-index{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:var(--accent-soft);color:var(--accent-strong);font:700 .78rem/1 var(--font-data)}.evidence-body{min-width:0}.relationship-line{display:flex;align-items:center;gap:12px;flex-wrap:wrap;color:var(--ink)}.relationship-line span{color:var(--accent);font-size:1.3rem}.evidence-body p{margin:10px 0 18px;color:var(--muted);line-height:1.7;overflow-wrap:anywhere}.evidence-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0}.evidence-meta div{min-width:0}.evidence-meta dt{margin-bottom:5px;color:var(--quiet);font:600 .68rem/1.2 var(--font-data);letter-spacing:.06em;text-transform:uppercase}.evidence-meta dd{margin:0;color:var(--ink-soft);font:500 .78rem/1.4 var(--font-data);overflow-wrap:anywhere}.empty-state{padding:22px;border:1px dashed var(--line-strong);color:var(--muted)}@media(max-width:760px){.section-heading{display:grid}.evidence-count{justify-self:start}.evidence-item{grid-template-columns:38px minmax(0,1fr);gap:10px}.evidence-meta{grid-template-columns:1fr 1fr}}
</style>
