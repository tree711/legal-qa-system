<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue'
import {chat,health,searchLaw,type Message,type Reference} from './api'

type Session={id:string;title:string;messages:Message[];updatedAt:number}
const sessions=ref<Session[]>(JSON.parse(localStorage.getItem('legalqa-sessions')||'[]'))
const currentId=ref(localStorage.getItem('legalqa-current')||'')
const input=ref(''); const loading=ref(false); const online=ref(false); const useRag=ref(true); const topK=ref(3)
const references=ref<Reference[]>([]); const steps=ref<string[]>([]); const summary=ref(''); const model=ref(''); const elapsed=ref(0); const lowConfidence=ref(false)
const view=ref<'chat'|'search'|'about'>('chat'); const searchQuery=ref(''); const searchResults=ref<Reference[]>([]); const searchLoading=ref(false)
const inspectorOpen=ref(true); const sidebarOpen=ref(false); const toast=ref(''); const scroller=ref<HTMLElement|null>(null)
const current=computed(()=>sessions.value.find(s=>s.id===currentId.value))
const examples=[
 {tag:'劳动关系',text:'六个月劳动合同可以约定两个月试用期吗？'},
 {tag:'合同权益',text:'公司一直不签书面劳动合同怎么办？'},
 {tag:'违约责任',text:'网络订单成功后商家单方面取消是否违约？'},
 {tag:'行政程序',text:'行政处罚听证需要满足哪些程序要求？'}
]
const viewTitle=computed(()=>view.value==='chat'?'法律法规智能问答':view.value==='search'?'法条证据检索':'系统与方法')
const viewSubtitle=computed(()=>view.value==='chat'?'本地模型 · 检索增强 · 多 Agent 审慎作答':view.value==='search'?'从本地法律知识库中定位直接依据':'关于能力边界、证据链与使用方式')

function newSession(){const s={id:crypto.randomUUID(),title:'新对话',messages:[],updatedAt:Date.now()};sessions.value.unshift(s);currentId.value=s.id;view.value='chat';sidebarOpen.value=false;resetMeta()}
function resetMeta(){references.value=[];steps.value=[];summary.value='';lowConfidence.value=false;model.value='';elapsed.value=0}
function removeSession(id:string){sessions.value=sessions.value.filter(s=>s.id!==id);if(currentId.value===id){currentId.value=sessions.value[0]?.id||'';resetMeta()}if(!sessions.value.length)newSession()}
function clearCurrent(){if(current.value){current.value.messages=[];current.value.title='新对话';current.value.updatedAt=Date.now();resetMeta();notify('当前卷宗已清空')}}
function switchView(next:'chat'|'search'|'about'){view.value=next;sidebarOpen.value=false}
function errorText(e:any){return e?.response?.data?.detail||e?.message||'请求失败，请检查后端服务。'}
function notify(text:string){toast.value=text;window.setTimeout(()=>{if(toast.value===text)toast.value=''},1800)}
async function copyText(text:string){try{await navigator.clipboard.writeText(text);notify('内容已复制')}catch{notify('复制失败，请手动选择文本')}}
function exportConversation(){
 if(!current.value?.messages.length){notify('当前没有可导出的对话');return}
 const body=current.value.messages.filter(m=>m.role!=='system').map(m=>`${m.role==='user'?'提问':'答复'}\n${m.content}`).join('\n\n────────────\n\n')
 const blob=new Blob([`衡鉴 · 法律问答记录\n${current.value.title}\n\n${body}`],{type:'text/plain;charset=utf-8'})
 const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`法律问答-${current.value.title}.txt`;a.click();URL.revokeObjectURL(url);notify('问答记录已导出')
}
async function send(text?:string){
 const q=(text??input.value).trim();if(!q||loading.value||!current.value)return
 input.value='';const before=[...current.value.messages];current.value.messages.push({role:'user',content:q})
 if(current.value.title==='新对话')current.value.title=q.slice(0,18);current.value.updatedAt=Date.now();loading.value=true;resetMeta();await nextTick();scrollBottom()
 try{
  const r=await chat(current.value.messages,topK.value,useRag.value)
  current.value.messages=r.messages;references.value=r.references;model.value=r.model;elapsed.value=r.elapsed_seconds;lowConfidence.value=r.low_confidence;steps.value=r.steps||[];summary.value=r.summary_result?.summary||''
 }catch(e){current.value.messages=[...before,{role:'user',content:q},{role:'assistant',content:`请求失败：${errorText(e)}`}]}finally{loading.value=false;await nextTick();scrollBottom()}
}
function scrollBottom(){scroller.value?.scrollTo({top:scroller.value.scrollHeight,behavior:'smooth'})}
async function doSearch(){if(!searchQuery.value.trim())return;searchLoading.value=true;try{searchResults.value=(await searchLaw(searchQuery.value,topK.value)).results}catch(e){notify(errorText(e))}finally{searchLoading.value=false}}
function isWebLink(url?:string){return !!url&&/^https?:\/\//i.test(url)}
watch(sessions,v=>localStorage.setItem('legalqa-sessions',JSON.stringify(v)),{deep:true});watch(currentId,v=>localStorage.setItem('legalqa-current',v))
onMounted(async()=>{if(!sessions.value.length)newSession();else if(!current.value)currentId.value=sessions.value[0].id;try{online.value=(await health()).status==='ok'}catch{online.value=false}})
</script>

<template>
<div class="app-shell" :class="{compact:!inspectorOpen}">
 <div v-if="sidebarOpen" class="mobile-backdrop" @click="sidebarOpen=false"></div>
 <aside class="sidebar" :class="{open:sidebarOpen}">
  <div class="brand"><div class="brand-seal">衡</div><div><strong>衡鉴</strong><span>LEGAL INTELLIGENCE</span></div></div>
  <button class="new-case" @click="newSession"><span>＋</span> 新建问答卷宗 <kbd>⌘ K</kbd></button>
  <nav aria-label="主导航">
   <button :class="{active:view==='chat'}" @click="switchView('chat')"><i>问</i><span>智能问答<small>基于证据生成答复</small></span></button>
   <button :class="{active:view==='search'}" @click="switchView('search')"><i>检</i><span>法条检索<small>定位原始法律依据</small></span></button>
   <button :class="{active:view==='about'}" @click="switchView('about')"><i>录</i><span>系统说明<small>能力、流程与边界</small></span></button>
  </nav>
  <div class="history-title"><span>近期卷宗</span><small>{{sessions.length.toString().padStart(2,'0')}}</small></div>
  <div class="session-list">
   <div v-for="s in sessions" :key="s.id" class="session" :class="{selected:s.id===currentId}" @click="currentId=s.id;resetMeta();sidebarOpen=false">
    <i>§</i><span>{{s.title}}</span><button title="删除卷宗" @click.stop="removeSession(s.id)">×</button>
   </div>
  </div>
  <div class="sidebar-foot"><div class="status"><i :class="online?'dot ok':'dot'"></i><span>{{online?'本地服务已连接':'本地服务未连接'}}</span><b>{{online?'ONLINE':'OFFLINE'}}</b></div><p>所有检索与生成均在本地完成</p></div>
 </aside>

 <main>
  <header class="topbar">
   <div class="title-group"><button class="mobile-menu" @click="sidebarOpen=true">☰</button><div><div class="eyebrow">司法知识工作台 / {{view==='chat'?'问答卷':view==='search'?'检索卷':'说明卷'}}</div><h1>{{viewTitle}}</h1><p>{{viewSubtitle}}</p></div></div>
   <div class="header-actions" v-if="view==='chat'">
    <button class="icon-action" title="导出问答记录" @click="exportConversation"><span>⇩</span> 导出</button>
    <button class="icon-action" title="清空当前对话" @click="clearCurrent"><span>⌫</span> 清空</button>
    <button class="icon-action evidence-toggle" :class="{active:inspectorOpen}" title="切换证据面板" @click="inspectorOpen=!inspectorOpen"><span>▤</span> 证据</button>
   </div>
  </header>

  <section v-if="view==='chat'" class="chat-layout">
   <div class="conversation">
    <div class="case-toolbar">
     <div class="case-id"><span>当前卷宗</span><b>{{current?.title||'新对话'}}</b></div>
     <div class="query-controls"><label class="rag-switch"><input type="checkbox" v-model="useRag"><i></i><span>引用法条</span></label><label class="select-wrap">证据数<select v-model="topK"><option :value="3">3 条</option><option :value="5">5 条</option><option :value="10">10 条</option></select></label></div>
    </div>
    <div class="messages" ref="scroller">
     <div v-if="!current?.messages.length" class="welcome">
      <div class="court-mark"><span>公</span><i>⚖</i><span>正</span></div>
      <div class="welcome-copy"><span class="section-kicker">LOCAL LEGAL ASSISTANT</span><h2>以法为据，审慎作答</h2><p>描述你的法律问题。系统会检索本地法规、整理直接依据，并展示完整的 Agent 处理过程。</p></div>
      <div class="practice-tags"><span>劳动关系</span><span>合同纠纷</span><span>行政程序</span><span>消费者权益</span></div>
      <div class="examples"><button v-for="x in examples" :key="x.text" @click="send(x.text)"><small>{{x.tag}}</small><span>{{x.text}}</span><b>→</b></button></div>
      <div class="welcome-note"><b>审慎提示</b><span>回答仅供学习与研究参考，不替代律师意见或司法裁判。</span></div>
     </div>
     <template v-for="(m,i) in current?.messages" :key="i">
      <div v-if="m.role!=='system'" class="message" :class="m.role">
       <div class="avatar">{{m.role==='user'?'问':'衡'}}</div>
       <div class="bubble"><div class="role"><span>{{m.role==='user'?'你的问题':'衡鉴答复'}}</span><small>{{m.role==='user'?'QUESTION':'GROUNDED RESPONSE'}}</small></div><div class="content">{{m.content}}</div><div class="message-actions"><button @click="copyText(m.content)">复制</button><button v-if="m.role==='assistant'" @click="input='请进一步解释上述回答中的法律依据。'">追问依据</button></div></div>
      </div>
     </template>
     <div v-if="loading" class="message assistant"><div class="avatar">衡</div><div class="bubble"><div class="role"><span>正在核验法条</span><small>REVIEWING EVIDENCE</small></div><div class="typing"><i></i><i></i><i></i><span>Agent 正在整理证据链</span></div></div></div>
    </div>
    <div class="composer"><div class="composer-box"><textarea v-model="input" placeholder="请输入需要研判的法律问题…" @keydown.enter.exact.prevent="send()"></textarea><div class="composer-foot"><span><kbd>Enter</kbd> 发送 · <kbd>Shift + Enter</kbd> 换行</span><button class="send" :disabled="loading||!input.trim()" @click="send()">提交研判 <b>↑</b></button></div></div></div>
   </div>

   <aside v-if="inspectorOpen" class="inspector">
    <div class="inspector-head"><div><span>CASE EVIDENCE</span><h2>证据与过程</h2></div><b :class="online?'secure':'secure offline'">{{online?'本地可信':'服务离线'}}</b></div>
    <div v-if="lowConfidence" class="warning"><b>依据可信度偏低</b><span>建议核验原始条文后再采用结论。</span></div>
    <div class="meta" v-if="model"><div><span>推理模型</span><b>{{model}}</b></div><div><span>处理耗时</span><b>{{elapsed.toFixed(1)}}s</b></div><div><span>法条依据</span><b>{{references.length}}</b></div></div>
    <div class="panel evidence-panel"><div class="panel-title"><div><span>01</span><b>引用法条</b></div><em>{{references.length}} 项证据</em></div><div v-if="!references.length" class="empty"><i>§</i><b>等待证据</b><span>完成问答后，直接依据会在此归档。</span></div>
     <article v-for="(r,i) in references" :key="i" class="reference"><div class="ref-head"><span>证据 {{String(i+1).padStart(2,'0')}}</span><em>{{Math.round(r.score*100)}}% 匹配</em></div><h3>{{r.law_name}}</h3><strong>{{r.article_no}}</strong><p>{{r.content}}</p><div class="ref-actions"><button @click="copyText(`${r.law_name} ${r.article_no}\n${r.content}`)">复制条文</button><a v-if="isWebLink(r.source_url)" :href="r.source_url" target="_blank" rel="noreferrer">查验原文 ↗</a></div></article>
    </div>
    <div class="panel" v-if="steps.length"><div class="panel-title"><div><span>02</span><b>处理记录</b></div><em>可追溯</em></div><ol class="timeline"><li v-for="(s,i) in steps" :key="s"><i>{{i+1}}</i><span>{{s}}</span></li></ol><div v-if="summary" class="summary"><b>结构化摘要</b><p>{{summary}}</p></div></div>
   </aside>
  </section>

  <section v-else-if="view==='search'" class="search-page">
   <div class="search-intro"><span class="section-kicker">EVIDENCE RETRIEVAL</span><h2>定位法条，核验证据</h2><p>直接检索本地法规知识库，不经过生成模型改写。</p></div>
   <div class="search-box"><span>⌕</span><input v-model="searchQuery" placeholder="输入法律问题、法规名称或关键词" @keyup.enter="doSearch"><select v-model="topK"><option :value="3">3 条证据</option><option :value="5">5 条证据</option><option :value="10">10 条证据</option></select><button class="primary" @click="doSearch">{{searchLoading?'检索中…':'开始检索'}}</button></div>
   <div v-if="!searchResults.length" class="search-empty"><i>法</i><div><b>检索结果将在这里呈现</b><span>建议使用完整问题，例如“六个月劳动合同的试用期上限”。</span></div></div>
   <div class="result-grid"><article v-for="(r,i) in searchResults" :key="i" class="reference large"><div class="result-rank">{{String(i+1).padStart(2,'0')}}</div><div class="ref-head"><span>{{r.chapter||'法律条文'}}</span><em>{{Math.round(r.score*100)}}% 匹配</em></div><h3>{{r.law_name}}</h3><strong>{{r.article_no}}</strong><p>{{r.content}}</p><div class="ref-actions"><button @click="copyText(`${r.law_name} ${r.article_no}\n${r.content}`)">复制条文</button></div></article></div>
  </section>

  <section v-else class="about">
   <div class="about-hero"><div><span class="section-kicker">ABOUT THE SYSTEM</span><h2>每一个结论，都应有据可查</h2><p>衡鉴是一套基于本地大语言模型、法律知识检索与多 Agent 调度的法规问答原型。</p></div><div class="principle-seal"><span>依据</span><b>＞</b><span>推断</span></div></div>
   <div class="feature-grid"><article><i>01</i><b>本地推理</b><p>通过 Ollama 调用本地模型，问题与回答无需发送至第三方服务。</p></article><article><i>02</i><b>检索增强</b><p>先从 FAISS 法律知识库检索，再要求模型基于直接条文作答。</p></article><article><i>03</i><b>多轮语境</b><p>将追问改写为可独立检索的问题，同时保留关键事实与前文对象。</p></article><article><i>04</i><b>过程留痕</b><p>法条引用、匹配度和 Agent 调度步骤均可见，便于复核与演示。</p></article></div>
   <div class="method-card"><div><span>01</span><b>提出问题</b><small>明确事实与争点</small></div><i>→</i><div><span>02</span><b>检索法条</b><small>召回并重排序依据</small></div><i>→</i><div><span>03</span><b>约束生成</b><small>结论、依据、说明</small></div><i>→</i><div><span>04</span><b>人工复核</b><small>核验适用与例外</small></div></div>
   <div class="boundary"><b>使用边界</b><p>系统用于课程研究、法律知识检索与原型验证。输出不构成正式法律意见，复杂案件应由具备资质的专业人员结合完整事实审查。</p></div>
  </section>
 </main>
 <div v-if="toast" class="toast">{{toast}}</div>
</div>
</template>
