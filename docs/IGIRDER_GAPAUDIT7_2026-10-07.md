# IGIRDER.GAPAUDIT7 — Torsion report charts and missing-ratio audit

วันที่ 2026-10-07

Baseline: concrete-section-pro_IGIRDER-COMPACT6.zip

SHA-256: fb78ca10119c2a89ef03adefff5734abbd6d786db5ebc6d33e1bfe8bfd6a4a0d

## สิ่งที่พบจาก PDF

Torsion result(7).pdf แสดง Interior Girder 2 ที่ x=5.000 m:
Tu=1.58 kN-m, threshold=27.72 kN-m, Threshold status=BELOW THRESHOLD,
Transverse/Longitudinal status=NOT REQUIRED และสถานะรวมของแถว=REVIEW
จึงไม่มี strength/detailing D/C ให้พล็อตที่จุดนี้

PDF พิมพ์ตาราง Streamlit เป็นภาพเฉพาะ viewport แม้เปิดส่วนรายละเอียดแล้ว
ตาราง Exterior แสดง x=0–9 m จึงยังใช้ PDF นี้ยืนยันสาเหตุของช่องว่าง x=12–14 m
ไม่ได้ ต้องตรวจ stored rows ในแอปหรือ CSV ที่เพิ่มในรุ่นนี้
ไม่ได้คำนวณโครงการของผู้ใช้ซ้ำจาก PDF

Source PDF SHA-256:
abf3d0327fea109159bf135e00a4ba40ccfd9123e3b95ee8bfaa64e53fce88fb

## กราฟหลักสำหรับรายงาน

Torsion เปิด Selected case — demand / capacity เป็นค่าเริ่มต้น
แสดง Tu กับ ±φTn จาก stored station diagram ของ girder และ case เดียวกัน
ใช้ φTn ที่คำนวณแยกไว้แล้วในจุด BELOW THRESHOLD / Tu=0 ด้วย
เส้นกำลังจึงต่อเนื่องผ่านจุดเหล่านี้เมื่อข้อมูลและรายละเอียดพร้อม
ค่าที่ไม่พร้อมจริงยังเป็น NaN พร้อมเครื่องหมาย × และจำนวนจุดในภาพ

Analysis และ Report / QA ใช้ make_torsion_case_figure ร่วมกัน
ภาพมีชื่อ girder, load case, หน่วย, stored controlling ratio/station,
จำนวน FAIL/REVIEW/BELOW THRESHOLD และคำอธิบาย diagram resistance ในตัวภาพ
ย้ายข้อความ control ลงใต้กราฟเพื่อไม่ทับเส้นหรือขอบคาน
คง shared chart size 1440×560 และเว้นที่สำหรับหมายเหตุในภาพ

Report / QA เพิ่มส่วนพับเปิด Torsion report chart — stored results
เลือก girder/case ได้และแสดง case ที่ control จากผลเดิม
Create report chart PNG แล้ว Download report chart PNG ส่งออก PNG 2880×1120
จากกราฟเดียวกับ Analysis โดยสร้างภาพเมื่อกดปุ่มเท่านั้น
Report ใช้เฉพาะ packages ที่ตรงกับ input hash ปัจจุบันและมี stored diagram
รวมการตรวจตาราง design member ที่แก้หลัง bank save; ไม่แสดงผลเก่าที่ stale
ไม่มีการเรียก solver หรือเปลี่ยน result/input cache ระหว่าง review/export

## การแสดงผลใหม่

- ใน Overview — utilization จุดที่ไม่มี numeric D/C มีหมุดสถานะที่ขอบล่างกราฟ
  ○ สีเขียว: stored BELOW THRESHOLD ที่มีค่าแรง/threshold สอดคล้องกัน
  หรือ NO DEMAND ที่ตรวจพบ Tu ต้นทางเป็นค่าศูนย์จริงภายใน tolerance เดิม
  × สีเทา: numerical check UNAVAILABLE ให้ตรวจ source/detailing/status
- หมุดใช้ตำแหน่งแนวดิ่งตามพื้นที่กราฟ ไม่ใช่ค่า D/C=0 และไม่ใช่ overall PASS
  ค่า D/C ที่เก็บไว้และเส้นที่ขาดจาก NaN ยังคงเดิม
- ใต้กราฟมีจำนวนจุดตามประเภท และคำเตือนเมื่อ case/station ใดขาด numeric result
  คำเตือนยังแสดงเมื่ออีก case มี numeric ratio ให้พล็อตที่ station เดียวกัน
- Missing-ratio stations / gap reasons เป็นส่วนพับเปิดพร้อมสถานะ เหตุผล
  Tu และ threshold ของทุก case/station ที่ไม่มี ratio
- Download missing-ratio station audit (CSV) เก็บ source file/sheet/Excel row,
  source coupling และเหตุผลครบทุกแถว พร้อมค่าตัวเลขจาก stored rows
  Curve gap=False หมายถึงอีก case ให้ค่าพล็อตที่ station นี้ได้
- ใน Torsion มีข้อความชี้ไปที่ Selected case — demand / capacity เดิม
  สำหรับดู Tu และ φTn ตามแนวคาน ค่า resistance สำหรับ diagram ที่คำนวณแยก
  ในขั้น Calculate ใช้ได้เมื่อรายละเอียดและแหล่งข้อมูลผ่านเกณฑ์เดิม
  ค่าที่ไม่พร้อมยังแสดงช่องว่าง และ diagram resistance ไม่ใช้แทนผลตัดสินออกแบบ
- Shear และ Shear + Torsion ใช้ audit สำหรับ numeric ratio ที่ไม่พร้อมเช่นกัน
  การจัดประเภท BELOW THRESHOLD / NO DEMAND ใช้เฉพาะ Torsion
  Flexure ใช้กราฟเดิม

## ขอบเขตที่คงเดิม

สมการวิศวกรรม, ULS/SLS calculation logic, demand/capacity, ratio envelope,
controlling load case, FAIL/REVIEW และ source/development acceptance gates
คงเดิม ไม่มีการเติม ratio เป็นศูนย์หรือเชื่อมข้ามค่าที่ไม่พร้อม
Investigation ratio ยังคงเป็นคนละ basis กับ strength/detailing ratio

Audit อ่าน stored rows เท่านั้น การเปิด panel, เปลี่ยน case หรือดาวน์โหลด CSV
ไม่เรียก solver ไม่เปลี่ยน load bank, design member หรือ cache ผลคำนวณ
Project JSON, result persistence และ dependency versions คงเดิม
หลังเปิด project ใหม่ยังต้อง Calculate ตาม workflow เดิม

NO DEMAND จาก stored row เพียงอย่างเดียวไม่ใช้ยืนยันว่าแรงเป็นศูนย์
หาก Tu ต้นทางหายไป/ไม่เป็นศูนย์ แสดง UNAVAILABLE ใน audit
threshold ที่หายไป/ไม่เป็นบวก/ขัดกับแรงก็ไม่ใช้จัดเป็น BELOW THRESHOLD
ยังคงสถานะรวมเดิมไว้เพื่อให้เห็น acceptance gates อื่น

## วิธีตรวจหลังอัปเดต

1. เปิด project แล้ว Calculate Torsion — all girders ตามปกติ
2. เปิด Girder: [ชื่อ] แล้วเลือก Automatic, load case ที่ต้องการ หรือ All load cases
   กราฟเริ่มต้นของ Torsion เป็น demand / capacity
3. เลือก Overview เมื่อต้องการดู D/C พร้อมหมุดและ Missing-ratio stations / gap reasons
   โหลด CSV เมื่อต้องการตรวจทุก station/case หรือส่งรายละเอียดเพิ่มเติม
4. ใน Report / QA เปิด Torsion report chart — stored results เลือก girder/case
   กด Create report chart PNG แล้ว Download report chart PNG
   ตรวจ source/detailing gates ของจุดที่ resistance ไม่พร้อมตามหมายเหตุในภาพ

## การตรวจสอบ

- py_compile ผ่าน app.py และ production/QA modules ที่แก้
- Scoped regression 58 modules: 721 passed รวม 22 tests ใหม่
  ไม่ใช่การทดสอบทุก module ใน repository
- ทดสอบผลจาก solver จริงร่วมกับ diagram resistance: D/C ที่ถูกละเว้นยังเป็น NaN,
  controlling ratio/case คงเดิม และการ render audit ไม่เรียก solver
- Streamlit AppTest collection ผ่าน Flexure, Shear, Torsion, Shear + Torsion,
  2 girders / 2 cases ต่อ girder รวม AUTO / named / ALL และ stale-result hiding
- Torsion ตรวจหมุด BELOW THRESHOLD / NO DEMAND, expander และ CSV download widgets
  พร้อมเก็บ omitted cases แม้อีก case ให้ numeric ratio ที่ station เดียวกัน
- actual app.py Analysis routing ผ่านทั้ง 4 checks และ detailed workspace
  รวมการกด Calculate Interface Shear แล้วพบผลใน accepted manual cache
- actual app.py Report / QA เลือก 2 girders และ named cases ได้
  กด Create report chart PNG แล้วพบ download widget; report solver calls=0
- ตรวจ cached resistance ต่อเนื่องผ่าน BELOW THRESHOLD/Tu=0 และไม่เติม D/C
  ตรวจ source-unavailable NaN, old/stale packages และการแก้ active table ก่อน bank save
- review solver calls=0, load bank/design member/stored frames คงเดิม
  ไม่มี Streamlit/Arrow exception ใน AppTest
- ตรวจภาพกราฟจาก collection ทั้งสอง girders, Report / QA และตัวอย่างเต็มช่วงคาน
  รวม ○ / × / NO DEMAND; ชื่อ girder/case, control และหมายเหตุอยู่ในภาพ
  ตัวอย่าง full-span QA มี φTn จริงครบ 8 stations รวมจุดใต้ threshold และ zero Tu
- Runtime: Python 3.12.14, pandas 3.0.6, Streamlit 1.61.0, PyArrow 24.0.0
  ยังไม่ได้ตรวจรุ่นนี้ใน Python 3.14 หรือบน live deployment

หลักฐานใน qa/evidence/igird_gapaudit7 ได้แก่ ui_verification.json,
app_integration.json, regression_modules.txt, verification_summary.json,
PNG/Plotly specs และ gap-audit CSV
QA ใช้ controlled hypothetical inputs; ภาพ QA ไม่ใช่ผลออกแบบโครงการของผู้ใช้

Local Streamlit QA server ตอบ health 200 แต่ cloud browser เปิด localhost ไม่ได้
(ERR_CONNECTION_REFUSED) จึงไม่มี screenshot ของหน้าเว็บทั้งหน้า
การตรวจ widget/app routes ทำด้วย AppTest และตรวจภาพ Plotly แยกตามข้างต้น
ยังไม่ได้ push หรือ deploy

## QA ที่ทำซ้ำได้

รันจาก root ของ project:

```bash
python -m pytest -q $(cat qa/evidence/igird_gapaudit7/regression_modules.txt)
python qa/igird_casecontrol5_ui_verify.py --release IGIRDER.GAPAUDIT7 --output-dir qa/evidence/igird_gapaudit7
python qa/igird_casecontrol5_app_verify.py --release IGIRDER.GAPAUDIT7 --output-dir qa/evidence/igird_gapaudit7
```

QA scripts รับ --release และ --output-dir เพิ่มเติม; default ของ baseline เดิมคงไว้
เพื่อไม่เขียนทับหลักฐาน milestone เก่าเมื่อใช้คำสั่งระบุ output ดังข้างต้น

## Repository summary

Use stored I-girder torsion station capacity in Analysis and Report/QA charts, with case selection, gap audits, and annotated PNG exports.
