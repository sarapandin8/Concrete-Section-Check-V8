# IGIRDER.FLEXCHART24 — ตรวจ Flexure และแก้กราฟ

วันที่ 2026-10-13 · พัฒนาจาก SLSIMPORT23 ที่ผู้ใช้แนบ

## ผลตรวจ Flexural.pdf

PDF เป็นหน้า **ULS Strength → Flexure → Final Composite** มี 2 girders และ load cases U1A/U1B/U2A/U2B ไม่ใช่หน้า SLS Stress

1. หน้า 4 เกิด `StreamlitDuplicateElementId` เมื่อแสดงกราฟเดียวกันทั้ง member collection และ Detailed checks ทำให้หน้าแอปหยุดก่อนแสดงรายละเอียดครบ
2. กราฟใน PDF เดิมถูกตัดข้ามหน้ากระดาษ และ legend สอง source occurrences ยาว/คล้ายกันเพราะมี Before/After คั่นระหว่าง Max/Min กับ set
3. ช่องว่างของเส้น φMn ที่ปลายคานเกิดจาก stored `NO EQUILIBRIUM` ไม่ใช่หลักฐานว่าข้อมูลแรงหาย เส้น Demand ยังมีข้อมูลเต็มช่วง 0–20 m ภายใต้ source rows ที่แสดง

| Girder / Station | ผลใน PDF | ความหมาย |
|---|---|---|
| Interior Girder 2, x=0 m | CSI P=+114.969 kN → solver Nu=-114.969 kN; NO EQUILIBRIUM | แรงดึงตามแกน แต่ไม่มี developed strand/ordinary-bar force ที่หน้าตัดปลายตามสมมติฐานปัจจุบัน |
| Interior Girder 2, x=20 m | CSI P=-0.308 kN → solver Nu=+0.308 kN; φMn=0.248 < \|Mu\|=1.192 kN-m | กำลังจาก section solve ที่ไม่มี developed steel ต่ำกว่าความต้องการ; D/C ประมาณ 4.8 จากค่าที่ปัดใน PDF |
| Left Exterior Girder, x=20 m | P=+0.795 kN ใน U1A; load cases อื่นแสดง +0.703/+0.871/+0.778 kN; NO EQUILIBRIUM | แรงดึงเล็กน้อยก็ยังไม่มี equilibrium หากไม่ให้ tensile steel/concrete resistance ณ cut end |
| ทุก load cases | Interior: 8 FAIL / 320 requiring review; Exterior: 4 FAIL / 320 requiring review | เป็นจำนวน source rows ในหลายเคส; FAIL กับ REVIEW อาจนับทับแถวเดียวกัน ไม่ใช่ 320 ตำแหน่งที่กำลังรับไม่พอ |
| Min / U1A ที่ x=10 m | Interior D/C=0.139; Exterior D/C=0.144 | ผ่านด้านตัวเลขสำหรับ bound/case ที่แสดง แต่ยังมี member/source/development gates |
| Girder–Deck Interface Shear | PASS; governing D/C=0.342 | ผ่านสำหรับ design member/result ที่แสดงใน PDF ไม่ได้ล้าง flexure endpoint failures |
| Effective width | Be=1,200 mm; REVIEW | ยังไม่ได้ยืนยัน width basis สำหรับการยอมรับ composite strength |
| Ordinary longitudinal bars | Full-span continuity/cutoff/anchorage ยังไม่ยืนยัน | Numerical PASS ยังเป็น REVIEW; ต้องตรวจแบบจริงและ development |

`D/C ∞` ในกรณี NO EQUILIBRIUM เป็นสถานะ failure เมื่อไม่มี resistance ที่ใช้ได้ ไม่ได้หมายความว่า applied moment มีค่ามหาศาล ห้ามลากเส้นข้าม NaN หรือใส่ φMn=0/กำลังเต็มแทนค่าที่ไม่มี

## ประเด็นที่ต้องตรวจจากโมเดลและแบบจริง

Project JSON เดิม `I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck350(3).json` มี note ยืนยันว่า x=0/20 m เป็นปลายคานและปลาย strand จริง; extension ซ้าย/ขวา=0 และ bearing offsets=0.4 m มี continuity/anchorage flags เป็น false

อย่างไรก็ตาม JSON เดิมเก็บโหลดจาก `ULS_Girder Force uploaded to app.xlsx [d29e5af1]` ส่วน PDF ใช้ `ULS_Girder Force uploaded to app-rev1.xlsx [d9e396d4]` จึงไม่ใช้ JSON เดิมเป็นการทำซ้ำผลล่าสุดหรือการรับรองการออกแบบ

- ตรวจ section-cut location, Before/After, shell/diaphragm contribution และจุดอ้างอิง N/M3 ของแรงที่ปลายให้ตรงกับ strength section
- CSI แยก **Beam forces** (beam only) กับ **Girder forces** (beam + deck composite) ต้องใช้ source ให้ตรงกับหน้าตัดที่ตรวจ
- เนื่องจาก note เดิมยืนยัน physical cut ends จึงไม่เพิ่ม fictitious extension เพื่อทำให้ developed resistance ผ่าน
- ตรวจ ordinary bars และ deck bars ที่ถ่ายแรงเข้าสู่ end region: continuity, cutoffs, hooks/mechanical anchorage และ development ตามแบบจริง
- ตรวจ end D-region, bearing/end-block force transfer และ reinforcement แยกจาก beam-theory flexure station check
- ตรวจ effective width และ deck reinforcement แยกตาม Interior/Exterior หาก geometry/detailing ต่างกัน การคำนวณ collection ใช้ current shared model กับทุก girder
- ยังสรุปไม่ได้จาก PDF นี้ว่าต้องเพิ่ม strand หรือเพิ่มขนาดหน้าตัดทั้งคาน ต้องแก้ force-reference/end-detailing basis ก่อน

## การแก้ในรุ่นนี้

- ให้ Plotly figure มี stable key แยกตาม renderer location, source family และ Max/Min ป้องกัน duplicate element เมื่อเปิด Detailed checks
- รองรับชื่อ CSI ที่มี Before/After ในการย่อ legend เป็น Mux Max 1/2 หรือ Mux Min 1/2 โดยเก็บ source identity เต็มใน hover
- ใช้ shared chart layout จัด legend และ wrap report-note copy สำหรับหน้าจอ 1440/1100 px เก็บ report metadata เดิมทุกบรรทัด
- ใช้ print page-break guard ให้แต่ละ Plotly chart อยู่ด้วยกันใน browser PDF

**ไม่เปลี่ยนสมการ, resistance, imported forces, source-family qualification, development/anchorage assumptions, engineering statuses, Project JSON behavior หรือ result-cache persistence** Summary/Report ยังคงอ่าน stored results

## Verification

- ทำซ้ำ duplicate-ID failure ใน Streamlit จริงก่อนแก้
- Final targeted + inherited SLSIMPORT23 regression: **382 passed / 0 failed / 0 errors**, 23 test modules, Streamlit จริง; ดู `qa/evidence/igird_flexchart24/final_regression.txt` และ XML
- Actual app.py: 2 girders × Max/Min, collection + Detailed checks, demand/capacity + utilization, read-only Report; input/cache snapshots ไม่เปลี่ยน; review solver calls=0
- Browser: actual app.py กับ hypothetical QA checkpoint, 1440/1100 px, ไม่มี Streamlit/JavaScript error; legend/footer อยู่ครบในความกว้างกราฟ; browser PDF มีกราฟครบ 6 ใบพร้อมแกน x และ footer ในหน้าเดียวกันทุกใบ และตรวจภาพหน้า PDF แล้ว
- PNG/Plotly JSON สร้างจาก archived CSI forces และ hypothetical section สำหรับ software verification เท่านั้น ไม่ใช่ current rev1 project results
- Browser screenshots/checkpoint/print PDF เก็บเป็นข้อมูลตรวจภายในและไม่บรรจุใน release
- Source audit เทียบกับ accepted ZIP และ compile production modules ที่แก้

## อ้างอิง

- Streamlit Plotly chart key: https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart
- CSI beam versus composite girder forces: https://web.wiki.csiamerica.com/wiki/spaces/kb/pages/2020848/Beam%2Bvs%2Bgirder%2Bforces%2Bdisplayed%2Bon%2Bthe%2BBridge%2BObject%2BResponse%2BDisplay%2Bform
- FHWA transfer/development and zero strand force at bond start: https://www.fhwa.dot.gov/bridge/lrfd/pscus055.cfm

## ใช้งาน

ใช้ source tree ใน ZIP ใหม่ จากนั้นโหลด Project JSON ล่าสุด และ Calculate Flexure ใหม่ เปิด Detailed checks เพื่อตรวจ trace และ source audit เมื่อพิมพ์จาก browser กราฟแต่ละใบจะถูกย้ายไปหน้าใหม่หากพื้นที่ที่เหลือไม่พอ

ยังมี engineering endpoint FAIL/REVIEW ตามข้อมูลจริงจนกว่าจะปิด force-reference/development/detailing gates ไม่มีการ push/deploy หรือเปลี่ยนแอปที่ผู้ใช้เปิดอยู่

## Repo summary

Fix duplicate Max/Min flexure charts, preserve native source legends, and keep complete figures readable in browser and PDF reviews.
