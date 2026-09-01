<template>
  <section ref="sectionRef" class="graph-section" :class="{ fullscreen: isFullscreen }" aria-labelledby="graph-heading">
    <header class="graph-heading">
      <div><span class="section-eyebrow">Graph Inspection</span><h2 id="graph-heading">{{ copy.graphTitle }}</h2><p>{{ copy.graphHelp }}</p></div>
      <button type="button" class="button button-secondary" @click="toggleFullscreen">{{ isFullscreen ? copy.exitFullscreen : copy.fullscreen }}</button>
    </header>
    <div ref="chartRef" class="chart" role="img" :aria-label="pathDescription"></div>
  </section>
</template>
<script setup>
import { GraphChart } from 'echarts/charts';
import { TooltipComponent } from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
echarts.use([GraphChart,TooltipComponent,CanvasRenderer]);
const props=defineProps({result:{type:Object,default:()=>({})},masteredIds:{type:Array,default:()=>[]},conceptMap:{type:Object,default:()=>({})},copy:{type:Object,required:true},language:{type:String,default:'en'}});
const sectionRef=ref(null);const chartRef=ref(null);const chart=ref(null);const isFullscreen=ref(false);
const pathDescription=computed(()=>{const path=props.result.path||[];return path.length?path.map(displayName).join(' → '):props.copy.graphEmpty;});
function displayName(id){const item=props.conceptMap[id]||{};const name=props.language==='en'?item.name_en||item.name:item.name||item.name_en;return name?`${name} (${id})`:id;}
function render(){
  if(!chart.value)return;const path=Array.isArray(props.result.path)?props.result.path:[];const graphNodes=props.result.graph_nodes?.length?props.result.graph_nodes:path;
  const graphEdges=props.result.graph_edges?.length?props.result.graph_edges:path.slice(0,-1).map((id,index)=>[id,path[index+1]]);
  if(!graphNodes.length){chart.value.setOption({series:[{type:'graph',layout:'force',roam:true,label:{show:true,color:'#53636f'},data:[{id:'EMPTY',name:props.copy.graphEmpty,symbolSize:74,itemStyle:{color:'#eef3f2',borderColor:'#b7c4c1',borderWidth:1}}],links:[],force:{repulsion:420,edgeLength:180}}]},true);return;}
  const pathSet=new Set(path);const masteredSet=new Set(props.masteredIds);const targetId=path.at(-1);
  chart.value.setOption({tooltip:{formatter:({data})=>data.name||''},series:[{type:'graph',layout:'force',roam:true,draggable:true,edgeSymbol:['none','arrow'],edgeSymbolSize:[0,9],force:{repulsion:isFullscreen.value?720:560,edgeLength:isFullscreen.value?220:180,gravity:.05},emphasis:{focus:'adjacency'},label:{show:true,color:'#16252d',fontWeight:600,width:145,overflow:'break'},data:graphNodes.map((id)=>({id,name:displayName(id),symbolSize:id===targetId?82:masteredSet.has(id)?54:62,itemStyle:{color:id===targetId?'#ccefe8':masteredSet.has(id)?'#f0e2b8':'#e7edec',borderColor:id===targetId?'#087c6b':masteredSet.has(id)?'#8a6b18':'#7b918d',borderWidth:id===targetId?3:1.5}})),links:graphEdges.map(([source,target])=>({source,target,lineStyle:{color:pathSet.has(source)&&pathSet.has(target)?'#159582':'#a9b7b4',width:pathSet.has(source)&&pathSet.has(target)?2.5:1.2,opacity:.9}}))}]},true);
}
async function toggleFullscreen(){if(document.fullscreenElement===sectionRef.value)await document.exitFullscreen?.();else await sectionRef.value?.requestFullscreen?.();}
function onFullscreenChange(){isFullscreen.value=document.fullscreenElement===sectionRef.value;nextTick(()=>{chart.value?.resize();render();});}function onResize(){chart.value?.resize();}
watch(()=>[props.result,props.masteredIds,props.language],()=>nextTick(render),{deep:true});
onMounted(()=>{chart.value=echarts.init(chartRef.value);render();window.addEventListener('resize',onResize);document.addEventListener('fullscreenchange',onFullscreenChange);});
onBeforeUnmount(()=>{window.removeEventListener('resize',onResize);document.removeEventListener('fullscreenchange',onFullscreenChange);chart.value?.dispose();});
</script>
<style scoped>
.graph-section{padding:clamp(24px,4vw,44px);border:1px solid var(--line);background:var(--surface)}.graph-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:22px}.graph-heading h2{margin:6px 0 0;font:600 clamp(1.65rem,3vw,2.3rem)/1.12 var(--font-display);letter-spacing:-.025em}.graph-heading p{max-width:64ch;margin:10px 0 0;color:var(--muted);line-height:1.6}.section-eyebrow{color:var(--accent-strong);font:700 .72rem/1 var(--font-data);letter-spacing:.12em;text-transform:uppercase}.chart{min-height:500px;margin-top:22px;background:var(--surface-alt)}.graph-section:fullscreen{width:100vw;height:100vh;padding:28px;background:var(--page);overflow:hidden}.graph-section.fullscreen .chart{height:calc(100vh - 130px);min-height:0}@media(max-width:760px){.graph-heading{display:grid}.chart{min-height:420px}}
.button{min-height:46px;padding:0 18px;border:1px solid var(--line-strong);border-radius:0;background:transparent;color:var(--ink-soft);font:700 .78rem/1 var(--font-data);cursor:pointer;transition:background-color .18s ease,color .18s ease,border-color .18s ease,transform .18s ease}.button:hover{border-color:var(--ink);color:var(--ink);transform:translateY(-1px)}
</style>
