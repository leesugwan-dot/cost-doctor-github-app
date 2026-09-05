#!/usr/bin/env node
import {writeReport} from './scan.mjs';
const help='CostDoctor: node entry/cli.mjs --repo <repository> --output <new-folder-outside-repo> [--head <40hex>]';
try{
 const o={};if(process.argv.includes('--help')){console.log(help);process.exit(0);}
 for(let i=2;i<process.argv.length;i+=2){if(!['--repo','--output','--head'].includes(process.argv[i])||!process.argv[i+1]||o[process.argv[i]])throw Error('ARGUMENT_INVALID');o[process.argv[i]]=process.argv[i+1];}
 if(!o['--repo']||!o['--output'])throw Error('ARGUMENT_MISSING');
 const r=writeReport(o['--repo'],o['--output'],{expectedHead:o['--head']??null});console.log(JSON.stringify({status:r.verdict,report:'report.md',savings:'UNKNOWN',source_changed:false}));if(r.verdict==='NO_SUPPORTED_SOURCE')process.exitCode=2;
}catch(e){console.error(JSON.stringify({status:'FAIL_CLOSED',code:/^[A-Z_]+$/.test(e.message)?e.message:'IO_ERROR',next:'Read docs/TROUBLESHOOTING.md; use a real repository and a new output folder outside it.',raw_saved:false}));process.exitCode=2;}
