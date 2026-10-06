import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const here=path.dirname(fileURLToPath(import.meta.url));
const out=path.dirname(here);
const d=JSON.parse(await fs.readFile(path.join(here,'workbook_inputs.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('Findings');
const groups=wb.worksheets.add('School associations');
const variables=wb.worksheets.add('Variables');
const sources=wb.worksheets.add('Source audit');

function base(s,range){
  s.showGridLines=false;
  s.getRange(range).format.font={name:'Arial',size:11,color:'#243345'};
  s.getRange(range).format.verticalAlignment='center';
  s.getRange(range).format.rowHeight=23;
}
function header(s,range){
  s.getRange(range).format.fill='#31465C';
  s.getRange(range).format.font={name:'Arial',size:11,bold:true,color:'#FFFFFF'};
  s.getRange(range).format.horizontalAlignment='center';
  s.getRange(range).format.wrapText=true;
  s.getRange(range).format.rowHeight=38;
}
function title(s,cell,value){s.getRange(cell).values=[[value]];s.getRange(cell).format.font={name:'Arial',size:16,bold:true,color:'#243345'};}

base(groups,'A1:I14');
title(groups,'A2','Portuguese course failure by access and academic history');
groups.getRange('A3').values=[['Outcome: final grade below 10/20. Associations do not measure dropout or intervention effects.']];
groups.getRange('A3').format.font={name:'Arial',size:11,italic:true};
groups.getRange('A5:I5').values=[['Variable','Group','Students','Failure count','Failure rate','Lower 95%','Upper 95%','Mean G1','Mean final grade']];
const label={low_parent_education:'Both parents education ≤2',digital_exclusion:'No home internet',long_commute:'Travel over 30 minutes',disadvantage_proxy_group:'At least 2 access proxies',prior_failure:'Any prior course failure'};
const sub=d.subgroups.filter(x=>x.subject==='portuguese'&&Object.hasOwn(label,x.variable));
groups.getRange('A6:I15').values=sub.map(x=>[label[x.variable],String(x.group)==='1'?'Yes':'No',x.n,x.course_failure_n,null,x.wilson_lower_95,x.wilson_upper_95,x.mean_grade1,x.mean_final_grade]);
for(let i=6;i<=15;i++)groups.getRange(`E${i}`).formulas=[[`=D${i}/C${i}`]];
groups.getRange('A17').values=[['Source: Cortez (2008), UCI Student Performance; supplied student-por.csv and student.txt. https://doi.org/10.24432/C5TG7T']];
groups.getRange('A17').format.font={name:'Arial',size:10,italic:true};
header(groups,'A5:I5');
groups.getRange('A1:A17').format.columnWidth=32;
groups.getRange('B1:B17').format.columnWidth=12;
groups.getRange('C1:G17').format.columnWidth=14;
groups.getRange('H1:I17').format.columnWidth=18;
groups.getRange('E6:G15').setNumberFormat('0.0%');
groups.getRange('H6:I15').setNumberFormat('0.00');
groups.freezePanes.freezeRows(5);

base(summary,'A1:J31');summary.tabColor='#31465C';
title(summary,'A2','Student population and simulation findings');
summary.getRange('A4:B4').values=[['Prepared data','Count']];header(summary,'A4:B4');
summary.getRange('A5:B9').values=[['Conservative initialization profiles',d.summary.initialization_profiles],['Primary Portuguese profiles',d.summary.recommended_portuguese_profiles],['Unambiguous mathematics enrichments',d.summary.one_to_one_math_enrichments],['Generated reset fixtures',d.summary.synthetic_reset_rows],['Observed school dropout labels',0]];
summary.getRange('D4:F4').values=[['Portuguese group','Students','Failure rate']];header(summary,'D4:F4');
summary.getRange('D5:D6').values=[['At least 2 access proxies'],['Fewer than 2 access proxies']];
for(const [row,idx] of [[5,sub.findIndex(x=>x.variable==='disadvantage_proxy_group'&&String(x.group)==='1')],[6,sub.findIndex(x=>x.variable==='disadvantage_proxy_group'&&String(x.group)==='0')]]){
  summary.getRange(`E${row}:F${row}`).formulas=[[`='School associations'!C${idx+6}`,`='School associations'!E${idx+6}`]];
}
summary.getRange('F5:F6').setNumberFormat('0.0%');
summary.getRange('A11').values=[['The school label called Dropped_Out equals final-grade failure in every row.']];
summary.getRange('A12').values=[['Income, administrative withdrawal and intervention response remain unknown.']];
summary.getRange('A13').values=[['The large all-level school table uses an exactly reconstructable probability rule.']];
title(summary,'A15','Held-out prediction benchmarks');
summary.getRange('A17:G17').values=[['Task','Test students','Positives','Avg precision','ROC AUC','Brier','Recall at 10%']];header(summary,'A17:G17');
const tasks={school_context_failure:'School failure: context',school_period1_failure:'School failure: context + G1',higher_ed_enrollment_resolved_dropout:'University: declared enrollment',higher_ed_without_financial_status:'University: financial fields excluded'};
const bm=d.summary.baseline_metrics.filter(x=>x.model==='logistic');
summary.getRange(`A18:G${17+bm.length}`).values=bm.map(x=>[tasks[x.dataset],x.n,x.positive_n,x.average_precision,x.roc_auc,x.brier,x.recall_at_10pct]);
summary.getRange(`D18:F${17+bm.length}`).setNumberFormat('0.000');summary.getRange(`G18:G${17+bm.length}`).setNumberFormat('0.0%');
summary.getRange('A23').values=[['School predictions concern course failure. University predictions exclude unresolved Enrolled cases.']];
summary.getRange('A24').values=[['Financial-status timing needs verification before prospective university use.']];
summary.getRange('A26:B28').values=[['Primary policy/scenario cells',d.summary.experiment_primary_cells],['Held-out seeds per cell',30],['Planned episodes',null]];
summary.getRange('B28').formulas=[['=B26*B27']];
summary.getRange('A30').values=[['Sequential policy experiments are planned; they have not been run.']];
summary.getRange('A31').values=[['Read the report and experiment protocol for definitions, uncertainties and the CMDP design.']];
summary.getRange('A1:A31').format.columnWidth=40;
summary.getRange('B1:C31').format.columnWidth=15;
summary.getRange('D1:D31').format.columnWidth=29;
summary.getRange('E1:G31').format.columnWidth=15;

const vm=d.dictionary.map(x=>[x.variable,x.source_variable,x.definition,x.provenance,x.role,x.missing_n]);
base(variables,`A1:F${vm.length+4}`);title(variables,'A2','Primary student variable map');
variables.getRange('A4:F4').values=[['Variable','Source field','Definition','Provenance','Role','Missing rows']];header(variables,'A4:F4');
variables.getRange(`A5:F${vm.length+4}`).values=vm;
variables.getRange('A:A').format.columnWidth=39;variables.getRange('B:B').format.columnWidth=19;
variables.getRange('C:C').format.columnWidth=74;variables.getRange('D:E').format.columnWidth=26;variables.getRange('F:F').format.columnWidth=14;
variables.getRange(`A5:E${vm.length+4}`).format.wrapText=true;
variables.getRange(`A5:F${vm.length+4}`).format.autofitRows();
variables.freezePanes.freezeRows(4);
variables.freezePanes.freezeColumns(1);
variables.getRange(`A${vm.length+6}`).values=[['Source: supplied school codebook; UCI https://doi.org/10.24432/C5TG7T. Analyst mappings are labelled.']];

base(sources,'A1:F24');title(sources,'A2','Source selection and data quality');
sources.getRange('A4:F4').values=[['Source file','Rows','Columns','Missing cells','Recommended use','Reason']];header(sources,'A4:F4');
const decision=d.decisions.map(x=>[x.file.split('/').slice(-2).join('/'),x.rows,x.columns,x.missing_cells,x.recommended_use,x.reason]);
sources.getRange(`A5:F${decision.length+4}`).values=decision;
sources.getRange('A:A').format.columnWidth=62;sources.getRange('B:D').format.columnWidth=14;
sources.getRange('E:E').format.columnWidth=43;sources.getRange('F:F').format.columnWidth=85;
sources.getRange(`A5:F${decision.length+4}`).format.wrapText=true;sources.getRange(`A5:F${decision.length+4}`).format.autofitRows();
sources.freezePanes.freezeRows(4);
sources.freezePanes.freezeColumns(1);
sources.getRange('A22').values=[['Sources: supplied CSVs, READMEs, codebook and archive hashes. Full original paths and hashes are in source_manifest.csv.']];
sources.getRange('A23').values=[['University source: https://doi.org/10.24432/C5MC89. Bundle mirror: https://huggingface.co/datasets/EduDevCommons/Student-Dropout-Success-All-Academic-Levels']];
sources.getRange('A24').values=[['All original source hashes were unchanged after preparation.']];

// Check the affected formula dependencies with temporary edits, then restore them.
groups.getRange('D13').values=[[28]];
wb.recalculate();
if(Math.abs(summary.getRange('F5').values[0][0]-28/128)>1e-10)throw new Error('Group-rate dependency failed');
groups.getRange('D13').values=[[27]];
summary.getRange('B27').values=[[31]];
wb.recalculate();
if(summary.getRange('B28').values[0][0]!==4464)throw new Error('Episode-count dependency failed');
summary.getRange('B27').values=[[30]];
wb.recalculate();
if(summary.getRange('B28').values[0][0]!==4320)throw new Error('Restored episode count is wrong');
console.log((await wb.inspect({kind:'table',range:'Findings!A18:G21',include:'values,formulas',tableMaxRows:4,tableMaxCols:7,maxChars:2000})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1000})).ndjson);
for(const [name,range,file] of [['Findings','A1:G31','findings'],['School associations','A1:I17','associations'],['Variables',`A1:F${vm.length+6}`,'variables'],['Source audit','A1:F24','source_audit']]){
  const img=await wb.render({sheetName:name,range,scale:1.4,format:'png'});
  await fs.writeFile(path.join(here,file+'.png'),new Uint8Array(await img.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(out,'student_analysis.xlsx'));
console.log('Exported student_analysis.xlsx');
