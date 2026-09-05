import fs from 'node:fs';import path from 'node:path';import {writeReport,markdown} from './scan.mjs';
try{
 const workspace=process.env.GITHUB_WORKSPACE,temp=process.env.RUNNER_TEMP,summary=process.env.GITHUB_STEP_SUMMARY,output=process.env.GITHUB_OUTPUT;
 if(!workspace||!temp||!summary||!output)throw Error('RUNNER_CONTEXT_MISSING');
 const repo=fs.realpathSync(workspace),sub=process.env.INPUT_REPOSITORY||'.',target=path.resolve(repo,sub);
 if(target!==repo&&!target.startsWith(repo+path.sep))throw Error('REPOSITORY_OUTSIDE_WORKSPACE');
 if(fs.existsSync(target)&&fs.realpathSync(target)!==repo&&!fs.realpathSync(target).startsWith(repo+path.sep))throw Error('REPOSITORY_OUTSIDE_WORKSPACE');
 const dir=path.join(temp,'costdoctor-'+process.pid+'-'+Date.now());
 const r=writeReport(target,dir,{expectedHead:process.env.GITHUB_SHA??null});
 for(const p of [summary,output])if(!fs.existsSync(p)||fs.lstatSync(p).isSymbolicLink()||!fs.statSync(p).isFile())throw Error('RUNNER_OUTPUT_INVALID');
 fs.appendFileSync(summary,markdown(r));fs.appendFileSync(output,`report-directory=${dir}\nscan-status=${r.verdict}\n`);
 console.log(JSON.stringify({status:r.verdict,savings:'UNKNOWN',raw_source_output:false}));if(r.verdict==='NO_SUPPORTED_SOURCE')process.exitCode=2;
}catch(e){console.error(JSON.stringify({status:'FAIL_CLOSED',code:/^[A-Z_]+$/.test(e.message)?e.message:'IO_ERROR',next:'See TROUBLESHOOTING. No repository fix applied.'}));process.exitCode=2;}
