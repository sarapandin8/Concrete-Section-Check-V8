import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output=process.argv[2] ?? root+'/qa/evidence/igird_csiimport1';
await fs.mkdir(output,{recursive:true});
const workbook=Workbook.create();
const sheet=workbook.worksheets.add('Left Exterior Girder');
sheet.showGridLines=false;
const headers=['Layout Line Distance','Girder Distance','ItemType','P','V2','V3','T','M2','M3'];
const units=['m','m','','KN','KN','KN','KN-m','KN-m','KN-m'];
const rows=[headers,units,...[0,5,10,15,20].flatMap(x=>['Max','Min'].map(step=>[x,x,step,null,null,null,null,null,null]))];
sheet.getRange('A1:I12').values=rows;
sheet.getRange('A1:I12').format={font:{name:'Arial',size:11,color:'#1F2937'},verticalAlignment:'center',rowHeight:24};
sheet.getRange('A1:I1').format={fill:'#274E71',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:40,borders:{preset:'inside',style:'thin',color:'#FFFFFF'}};
sheet.getRange('A2:I2').format={font:{name:'Arial',size:10,italic:true,color:'#64748B'},horizontalAlignment:'center',fill:'#F1F5F9'};
sheet.getRange('A3:I12').format.fill='#FFF8DE';
sheet.getRange('A3:B12').setNumberFormat('0.000');
sheet.getRange('D3:I12').setNumberFormat('0.0000');
sheet.getRange('A3:B12').format.horizontalAlignment='right';
sheet.getRange('D3:I12').format.horizontalAlignment='right';
sheet.getRange('C3:C12').format.horizontalAlignment='left';
sheet.getRange('A1:B12').format.columnWidth=23;
sheet.getRange('C1:C12').format.columnWidth=13;
sheet.getRange('D1:I12').format.columnWidth=15;
sheet.getRange('J1:J12').format.columnWidth=3;
sheet.getRange('K1:K12').format.columnWidth=105;
sheet.getRange('K1:K10').values=[
 ['CSiBridge girder forces → Concrete Section Pro'],
 ['Yellow cells: replace example stations and enter all six factored forces.'],
 ['Example span: 20 m. Copy actual CSiBridge member rows; keep Max and Min.'],
 ['Station x = Girder Distance. Layout Line Distance is retained as source metadata.'],
 ['Mapping: M3→Mux; V2→Vuy; T→Tu; M2→Muy; V3→Vux; P→Nu.'],
 ['Keep CSI signs. P is positive in tension; conversion occurs inside the solver.'],
 ['Fill every force cell, including explicit zeros. Blank cells cannot be imported.'],
 ['Keep repeated stations. Import preserves every row in its original order.'],
 ['Max/Min alone does not establish simultaneous Mu/Nu/Vu/Tu. Coupled checks require review.'],
 ['Source format: Bridge_ULS_Left_Exterior_Max_Min_Template CSiBridge.xlsx (user supplied).'],
];
sheet.getRange('K1:K10').format={font:{name:'Arial',size:11,color:'#475569'},wrapText:false,verticalAlignment:'center'};
sheet.getRange('K1').format.font={name:'Arial',size:13,bold:true,color:'#274E71'};
sheet.getRange('C3:C12').dataValidation={rule:{type:'list',values:['Max','Min']}};
sheet.freezePanes.freezeRows(2);
workbook.recalculate();
const inspected=await workbook.inspect({kind:'region',sheetId:'Left Exterior Girder',range:'A1:I12',maxChars:2600,tableMaxRows:12,tableMaxCols:9});
await fs.writeFile(output+'/template_inspection.txt',inspected.ndjson??JSON.stringify(inspected));
const preview=await workbook.render({sheetName:'Left Exterior Girder',range:'A1:K12',scale:1,format:'png'});
await fs.writeFile(output+'/template_preview.png',new Uint8Array(await preview.arrayBuffer()));
const file=await SpreadsheetFile.exportXlsx(workbook);
await file.save(output+'/Bridge_Beam_ULS_CSiBridge_Template.xlsx');
const assets=root+'/assets/templates';
await fs.mkdir(assets,{recursive:true});
await fs.copyFile(output+'/Bridge_Beam_ULS_CSiBridge_Template.xlsx',assets+'/Bridge_Beam_ULS_CSiBridge_Template.xlsx');
console.log('Template exported, inspected, and rendered.');
