import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const EXT=new Set(['.py','.js','.mjs','.cjs','.ts','.tsx','.jsx','.json','.yml','.yaml','.toml','.md','.mdx','.rst']);
const SKIP=new Set(['.git','.github-cache','node_modules','vendor','dist','build','.venv','venv','__pycache__','.cache','costdoctor-entry']);
const MAX_VISITED=5000,MAX_FILE_BYTES=262144,MAX_TOTAL_BYTES=5242880,MAX_LINE_CHARS=8192;
const secretName=n=>/(^\.env(?:\.|$)|credentials|secrets?|tokens?|private.?key|\.pem$|\.key$)/i.test(n);
const HASH=b=>crypto.createHash('sha256').update(b).digest('hex');
const CATEGORY_ORDER=['RUNTIME_CODE','CONFIG','TEST_EVAL','DOCS_EXAMPLE','GENERATED_VENDOR','UNKNOWN'];
const categoryFor=rel=>{
 const parts=rel.split('/').map(x=>x.toLowerCase()),base=parts.at(-1)||'';
 if(parts.some(x=>['node_modules','vendor','dist','build','generated'].includes(x)))return 'GENERATED_VENDOR';
 if(parts.some(x=>['test','tests','eval','evals','fixture','fixtures'].includes(x))||/(^|[._-])(test|spec|fixture|eval)([._-]|$)/i.test(base))return 'TEST_EVAL';
 if(parts.some(x=>['docs','examples','example','samples'].includes(x))||['.md','.mdx','.rst'].includes(path.extname(base)))return 'DOCS_EXAMPLE';
 if(['.json','.yml','.yaml','.toml'].includes(path.extname(base))||/(config|settings|prompt|policy)/i.test(base))return 'CONFIG';
 return 'RUNTIME_CODE';
};
const confidenceFor=(category,{invocation=false,activeRetry=false,llmCache=false}={})=>{
 if(category==='DOCS_EXAMPLE'||category==='GENERATED_VENDOR'||category==='UNKNOWN')return 'WEAK';
 if((category==='RUNTIME_CODE'||category==='CONFIG')&&(invocation||activeRetry||llmCache))return 'STRONG';
 return 'MEDIUM';
};
const lineAt=(text,index)=>{const start=text.lastIndexOf('\n',index)+1,end=text.indexOf('\n',index);return text.slice(start,end<0?text.length:end).slice(0,MAX_LINE_CHARS);};
export const RULES=[
 {id:'MODEL_CALL',rx:/\b(?:chat|generate|embed|embeddings|completion|completions|invoke)\s*\(/gi,title:'모델 호출 후보',next:'실제 호출인지 확인하고 같은 입력의 중복 호출부터 측정하세요.'},
 {id:'RETRY_LOOP',rx:/\b(?:retry|retries|max_retries|maxRetries|backoff|tenacity)\b/gi,title:'재시도 설정 후보',next:'활성 재시도 한도와 실패 후 재작업을 확인하세요. 비활성 설정은 위험으로 세지 않습니다.'},
 {id:'CACHE_SIGNAL',rx:/\b(?:cache|cached|lru_cache|cache_control)\b/gi,title:'캐시 사용 후보',next:'AI 요청 문맥 재사용인지 일반 파일·CI 캐시인지 구분하고 적중률을 측정하세요.'},
 {id:'TOKEN_LIMIT',rx:/\b(?:max_tokens|max_output_tokens|num_predict|num_ctx|context_window)\b/gi,title:'토큰·문맥 제한 후보',next:'입출력 길이와 품질을 함께 측정한 후 제한을 조정하세요.'}
];
const emptyRuleStats=()=>Object.fromEntries(RULES.map(r=>[r.id,{source_category_counts:Object.fromEntries(CATEGORY_ORDER.map(c=>[c,0])),strong:0,medium:0,weak:0}]));
export function scan(repo,{expectedHead=null}={}){
 const begin=performance.now(),cpu=process.cpuUsage();
 if(!fs.existsSync(repo)||!fs.statSync(repo).isDirectory()||fs.lstatSync(repo).isSymbolicLink())throw Error('REPOSITORY_INVALID');
 if(expectedHead!==null&&!/^[a-f0-9]{40}$/.test(expectedHead))throw Error('HEAD_INVALID');
 const base=fs.realpathSync(repo),manifest=[],counts=Object.fromEntries(RULES.map(r=>[r.id,0])),ruleStats=emptyRuleStats();
 const coverage={visited:0,analyzed_files:0,analyzed_bytes:0,excluded_directories:0,excluded_generated:0,self_files_skipped:0,sensitive_names_skipped:0,unsupported_files:0,symlinks_skipped:0,oversized_files:0,binary_files:0,read_errors:0,bound_exceeded:false,skipped_due_to_size:0,max_file_bytes:MAX_FILE_BYTES,max_total_bytes:MAX_TOTAL_BYTES};
 const retry={signal_count:0,active_config_count:0,disabled_config_count:0,unknown_config_count:0,docs_or_test_count:0,configured_values:[],negative_evidence:'NONE'};
 const cache={signal_count:0,llm_relevant_candidates:0,ordinary_cache_candidates:0,irrelevant_or_docs_candidates:0,repeated_payload_candidate:false};
 const model={signal_count:0,invocation_candidates:0,sdk_import_candidates:0,config_candidates:0,docs_or_test_candidates:0};
 const overlap=Object.fromEntries(['MODEL_CALL+RETRY_LOOP','MODEL_CALL+CACHE_SIGNAL','MODEL_CALL+TOKEN_LIMIT','RETRY_LOOP+CACHE_SIGNAL'].map(k=>[k,0]));
 function walk(dir,depth){
  if(depth>12||coverage.visited>=MAX_VISITED){coverage.bound_exceeded=true;return;}
  let dh;try{dh=fs.opendirSync(dir);}catch{coverage.read_errors++;return;}
  const entries=[];try{let e;while((e=dh.readSync())){if(entries.length>=512){coverage.bound_exceeded=true;break;}entries.push(e);}}finally{dh.closeSync();}
  for(const e of entries.sort((a,b)=>a.name.localeCompare(b.name,'en'))){
   if(++coverage.visited>MAX_VISITED){coverage.bound_exceeded=true;return;}
   const p=path.join(dir,e.name),rel=path.relative(base,p).replaceAll(path.sep,'/'),category=categoryFor(rel);
   if(rel==='.github/workflows/costdoctor.yml'){coverage.self_files_skipped++;continue;}
   if(e.isSymbolicLink()){coverage.symlinks_skipped++;continue;}
   if(secretName(e.name)){coverage.sensitive_names_skipped++;continue;}
   if(e.isDirectory()){if(SKIP.has(e.name)){coverage.excluded_directories++;if(['vendor','node_modules','dist','build'].includes(e.name))coverage.excluded_generated++;continue;}walk(p,depth+1);continue;}
   if(!e.isFile()||!EXT.has(path.extname(e.name).toLowerCase())){coverage.unsupported_files++;continue;}
   let fd;
   try{
    if(!fs.realpathSync(p).startsWith(base+path.sep)){coverage.symlinks_skipped++;continue;}
    fd=fs.openSync(p,fs.constants.O_RDONLY|(fs.constants.O_NOFOLLOW||0));const st=fs.fstatSync(fd);
    if(!st.isFile()||st.size>MAX_FILE_BYTES){coverage.oversized_files++;coverage.skipped_due_to_size++;continue;}
    if(coverage.analyzed_bytes+st.size>MAX_TOTAL_BYTES){coverage.bound_exceeded=true;coverage.skipped_due_to_size++;return;}
    const b=Buffer.alloc(st.size);const length=fs.readSync(fd,b,0,b.length,0);if(length!==b.length){coverage.read_errors++;continue;}
    if(b.includes(0)){coverage.binary_files++;continue;}
    const text=b.toString('utf8');coverage.analyzed_files++;coverage.analyzed_bytes+=b.length;manifest.push([rel,HASH(b)]);
    const lines=text.split(/\r?\n/).slice(0,10000).map(line=>line.slice(0,MAX_LINE_CHARS));
    for(const rule of RULES){
      rule.rx.lastIndex=0;const matches=[...text.matchAll(rule.rx)];counts[rule.id]+=matches.length;ruleStats[rule.id].source_category_counts[category]+=matches.length;
      const activeRetry=category!=='DOCS_EXAMPLE'&&category!=='TEST_EVAL'&&/\b(?:max_retries|maxRetries|num_retries|retries|retry_count|attempts|stop_after_attempt)\s*[:=({]/i.test(text)&&!(/\b(?:max_retries|maxRetries|num_retries|retries|retry_count)\s*[:=]\s*0\b/i.test(text));
      const llmCache=rule.id==='CACHE_SIGNAL'&&/\b(?:prompt|input|token|model|llm|embedding|cache_control|system|context)\b/i.test(text);
      for(const match of matches){const line=lineAt(text,match.index||0),invocation=rule.id==='MODEL_CALL'&&!/^\s*(?:from|import)\b/i.test(line);const conf=confidenceFor(category,{invocation,activeRetry,llmCache});ruleStats[rule.id][conf.toLowerCase()]++;}
    }
    const imports=[...text.matchAll(/(?:^|\n)\s*(?:from|import)\s+[^\n]*(?:openai|anthropic|gemini|langchain|ollama|upstage|azure|bedrock|ChatOpenAI|OpenAI)/gi)];
    const invocations=[...text.matchAll(/\b(?:invoke|generate|chat\.completions(?:\.create)?|responses\.create|messages\.create|generateContent|completion)\s*\(/gi)];
    model.sdk_import_candidates+=imports.length;model.invocation_candidates+=invocations.length;if(category==='DOCS_EXAMPLE'||category==='TEST_EVAL')model.docs_or_test_candidates+=imports.length+invocations.length;else model.config_candidates+=imports.length;
    const retryMatches=[...text.matchAll(/\b(?:max_retries|maxRetries|num_retries|retries|retry_count|attempts|stop_after_attempt)\s*[:=]\s*(\d{1,3})/gi)];
    for(const m of retryMatches){const value=Math.min(100,Number(m[1]));retry.configured_values.push(value);if(category==='DOCS_EXAMPLE'||category==='TEST_EVAL')retry.docs_or_test_count++;else if(value===0)retry.disabled_config_count++;else retry.active_config_count++;}
    const retrySignals=[...text.matchAll(/\b(?:retry|retries|max_retries|maxRetries|backoff|tenacity)\b/gi)];retry.signal_count+=retrySignals.length;
    const cacheMatches=[...text.matchAll(/\b(?:cache|cached|lru_cache|cache_control)\b/gi)];cache.signal_count+=cacheMatches.length;
    if(cacheMatches.length){const llm=/\b(?:prompt|input|token|model|llm|embedding|cache_control|system|context)\b/i.test(text),ordinary=/\b(?:dependency|package|filesystem|file|ci|build|artifact|npm|pip)\b/i.test(text);if(llm)cache.llm_relevant_candidates+=cacheMatches.length;else if(ordinary)cache.ordinary_cache_candidates+=cacheMatches.length;else cache.irrelevant_or_docs_candidates+=cacheMatches.length;}
    for(const line of lines){const hit={};for(const rule of RULES){rule.rx.lastIndex=0;if(rule.rx.test(line))hit[rule.id]=true;}for(const [a,b] of [['MODEL_CALL','RETRY_LOOP'],['MODEL_CALL','CACHE_SIGNAL'],['MODEL_CALL','TOKEN_LIMIT'],['RETRY_LOOP','CACHE_SIGNAL']])if(hit[a]&&hit[b])overlap[`${a}+${b}`]++;}
   }catch{coverage.read_errors++;}finally{if(fd!==undefined)fs.closeSync(fd);}
  }
 }
 walk(base,0);manifest.sort((a,b)=>a[0].localeCompare(b[0],'en'));
 retry.negative_evidence=retry.disabled_config_count>0&&retry.active_config_count===0?'RETRY_DISABLED_OBSERVED':retry.active_config_count>0?'RETRY_ACTIVE_CONFIGURED':retry.signal_count?'RETRY_CONFIG_UNKNOWN':'NONE';
 cache.repeated_payload_candidate=cache.llm_relevant_candidates>0;
 const total=Object.values(counts).reduce((a,b)=>a+b,0),limited=coverage.bound_exceeded||coverage.symlinks_skipped>0||coverage.oversized_files>0||coverage.read_errors>0;
 const findings=RULES.map(r=>{const st=ruleStats[r.id],cat=Object.entries(st.source_category_counts).sort((a,b)=>b[1]-a[1])[0],signalConfidence=st.strong>0?'STRONG':st.medium>0?'MEDIUM':'WEAK';return {rule:r.id,title:r.title,signal_count:counts[r.id],confidence:'HEURISTIC_REVIEW_REQUIRED',signal_confidence:signalConfidence,source_category:cat&&cat[1]>0?cat[0]:'UNKNOWN',source_category_counts:st.source_category_counts,next_action:r.next};});
 return {schema:'costdoctor.repository-entry.v1',report_schema_version:'4.0.0',verdict:coverage.analyzed_files===0?'NO_SUPPORTED_SOURCE':limited?'PARTIAL_SCAN':'SCAN_COMPLETE',diagnosis_status:total?'REVIEW_SIGNALS':'NO_MATCH_IN_SCANNED_SCOPE',scope:'Bounded static text signals, including tests/examples/comments. Not measured calls, defects or proven waste.',expected_head:expectedHead,head_binding:'Caller/runner context, not independently authenticated',snapshot_sha256:HASH(JSON.stringify(manifest)),coverage,findings,signal_analysis:{source_category_counts:Object.fromEntries(CATEGORY_ORDER.map(c=>[c,findings.reduce((n,f)=>n+(f.source_category_counts[c]||0),0)])),model_call:{...model,signal_count:counts.MODEL_CALL},retry,cache,overlap},savings:{status:'UNKNOWN',usd:null,tokens:null,reason:'No authenticated usage/price/quality Before-After evidence supplied'},quality:{status:'NOT_MEASURED'},rollback:{needed:false,reason:'Repository read-only; no fix applied'},privacy:{raw_source_output:false,filenames_output:false,credentials_requested:false,repository_sent_to_external_service:false},execution:{wall_ms:performance.now()-begin,cpu_ms:Object.values(process.cpuUsage(cpu)).reduce((a,b)=>a+b,0)/1000,model_calls:0,network_calls:0,paid_calls:0},production_authority:false,external_user_verified:false};
}
export function markdown(r){
 const labels={MODEL_CALL:'모델 호출 후보',RETRY_LOOP:'재시도 후보',CACHE_SIGNAL:'AI 요청 문맥 재사용 후보',TOKEN_LIMIT:'토큰·문맥 제한 후보'};const coverage=r.coverage||{},analysis=r.signal_analysis||{};
 return ['# CostDoctor 저장소 진단',`상태: **${r.verdict}** — 절감 검증 완료가 아닙니다.`,`검사한 파일: ${coverage.analyzed_files||0}개 / ${coverage.analyzed_bytes||0} bytes`,`분석 범위: ${coverage.bound_exceeded||coverage.oversized_files?'일부 범위(크기·안전 한도 적용)':'분석 대상 범위 내 완료'}`,'','| 확인할 항목 | 정적 신호 수 | 신뢰도 |','| --- | ---: | --- |',...(r.findings||[]).map(x=>`| ${labels[x.rule]||x.title} | ${x.signal_count} | ${x.signal_confidence||'MEDIUM'} |`),'',`재시도 활성 설정: ${analysis.retry?.active_config_count||0}개 · 비활성 설정: ${analysis.retry?.disabled_config_count||0}개`,'**실제 비용·토큰 절감: UNKNOWN.** 신호 수는 실제 호출 수나 낭비량이 아닙니다.','대상 코드·모델 API는 실행하지 않았습니다. 원문 코드·파일명·비밀키는 결과에 포함되지 않습니다.',''].join('\n');
}
export function writeReport(repo,out,options={}){
 const b=fs.realpathSync(repo),requested=path.resolve(out),parent=path.dirname(requested);if(!fs.existsSync(parent)||fs.lstatSync(parent).isSymbolicLink())throw Error('OUTPUT_PARENT_INVALID');const o=path.join(fs.realpathSync(parent),path.basename(requested));if(o===b||o.startsWith(b+path.sep))throw Error('OUTPUT_MUST_BE_OUTSIDE_REPOSITORY');if(fs.existsSync(o))throw Error('OUTPUT_EXISTS');const r=scan(repo,options);fs.mkdirSync(o);fs.writeFileSync(path.join(o,'report.json'),JSON.stringify(r,null,2),{flag:'wx'});fs.writeFileSync(path.join(o,'report.md'),markdown(r),{flag:'wx'});return r;
}
