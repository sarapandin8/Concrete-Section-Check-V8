# IGIRDER.COMPACT6 — Compact girder results

วันที่ 2026-10-07

รวม Girder results view ทั้งสามทางเลือกเป็นหน้าผลเดียวสำหรับ Flexure → Final — Composite,
Shear, Torsion และ Shear + Torsion โดยยังเก็บผลของทุก girder และทุก load case
พร้อมทางเข้า detailed engineering checks เดิม

Baseline: concrete-section-pro_IGIRDER-CASECONTROL5.zip

SHA-256: 5acc3d7903bec270e4802ba7a9c4fed24c2b02d7e395247ed2085026410d4b1d

## หน้าผลใหม่

- ไม่ต้องเลือก Girder results view อีกต่อไป ใช้ collection workspace เดียว
- ตาราง Controlling load cases อยู่ด้านบน และยังแจ้ง FAIL / REVIEW / STALE ของทุก member
- ผลแต่ละ girder อยู่ในส่วนพับเปิด Girder: [ชื่อ] ซึ่งปิดไว้ตอนเริ่มต้น
- ภายในแต่ละ girder ยังเลือก Automatic — controlling load case, All load cases
  หรือ case ที่ต้องการได้ กราฟและตารางตรวจเปลี่ยนตาม case ที่เลือก
- ย้ายตาราง source control ฉบับเต็มและจำนวนแถว/series ไปไว้ใน
  Imported girders / controlling source audit เพื่อให้หน้าหลักสั้นลง
- Load-case ranking, controlling components, สมการ, variable definitions,
  calculation trace และ stored source rows ยังคงอยู่ในส่วนพับเปิดของแต่ละ girder
- Detailed checks — design member มีสวิตช์ Show detailed check workspace below
  เพื่อเปิด workspace รายละเอียดเดิมใต้ collection รวมถึง Calculate Interface Shear
  ใน Flexure Final Composite

Detailed checks ใช้ design member ที่เลือกใน Loads และทุก active case ของ member นั้น
ส่วนตัวเลือก load case ใน panel เปลี่ยนเฉพาะผลที่แสดง ไม่เปลี่ยน design member
หรือข้อมูลใน Loads การปิด panel ไม่ลบผลที่เก็บไว้

## ขอบเขต

ไม่มีการแก้สมการวิศวกรรมหรือ logic คำนวณ ULS/SLS การเลือก case ที่ control
เกณฑ์ acceptance, source/development gates, style กราฟ และ Arrow display adapter
ใช้ชุด CASECONTROL5 เดิม

Project JSON ยังเก็บ input collection ตามเดิม ผลคำนวณเป็น session cache
และต้อง Calculate หลังเปิด project ใหม่ ไม่มีการเพิ่ม result persistence
หรือเปลี่ยน dependency versions

Calculate collection ยังใช้ section/deck/reinforcement/prestress/support model
ปัจจุบันร่วมกันทุก girder หากรายละเอียดสมาชิกต่างกัน ต้องแยก project models
Result Summary และ Report / QA ยังสรุป design member ที่เลือกใน Loads

การเปลี่ยนตัวเลือก review และการเปิด detailed workspace ไม่เรียก force solvers ใหม่
ปุ่ม Calculate ที่ผู้ใช้กดเป็นการสั่งคำนวณอย่างชัดเจนตามเดิม

## ตรวจสอบ

- py_compile ผ่าน app.py, production module และ QA entry points ที่แก้
- Scoped regression 55 modules: 688 passed; ไม่ใช่การรัน tests ทั้ง repository
- Streamlit AppTest ตรวจครบ 4 checks, 2 girders และ 2 cases ต่อ girder
- ตรวจ AUTO / named case / All cases, panels ปิดตอนเริ่ม, stale-result hiding,
  invalid Flexure station reset และ session state ของ mode เดิม
- เปลี่ยน review แล้ว force-solver calls = 0; load bank, design member
  และ stored full frames คงเดิม
- actual app.py Analysis routes ผ่านครบ 4 checks และเปิด detailed route ได้
- ทดสอบกด Calculate Interface Shear จาก detailed route ของ Flexure จริง
  แล้วตรวจผลใน manual result cache สำเร็จ
- ตรวจภาพกราฟที่ export จาก workspace ทั้งสี่ประเภท โดยคง chart styles เดิม
- Python 3.12.14 / pandas 3.0.6 / Streamlit 1.61.0 / PyArrow 24.0.0

หลักฐาน: qa/evidence/igird_compact6/ui_verification.json,
app_integration.json, regression_modules.txt และภาพกราฟ / Plotly specs
QA ใช้ controlled hypothetical inputs ไม่ใช่ข้อมูลโครงการจริงของผู้ใช้

การเปิดหน้า local Streamlit ใน browser ของ workspace ไม่สำเร็จ
(connection refused) จึงยังไม่มี screenshot ของหน้าผล compact ทั้งหน้า
AppTest ตรวจ widget/layout states และเส้นทางใน app.py ได้ตามข้างต้น
ยังไม่ได้ push, deploy หรือทดสอบ UI ของรุ่นนี้บนแอปออนไลน์

## QA ที่ทำซ้ำได้

รันจาก root ของ project:

```bash
python -m py_compile app.py concrete_pmm_pro/ui/igird_member_results.py
python qa/igird_casecontrol5_ui_verify.py
python qa/igird_casecontrol5_app_verify.py
```

ไฟล์ QA สองตัวนี้ปรับให้ตรวจ COMPACT6 และเขียนหลักฐานใหม่ใน igird_compact6
หลักฐาน CASECONTROL5 เดิมยังอยู่ครบ
qa/igird_compact6_browser_app.py เป็น launcher สำหรับตรวจภาพด้วย hypothetical inputs
เท่านั้น; deployment entry point ยังคงเป็น app.py

## Repository summary

Unify I-girder result review into a compact workspace while preserving every load case, controlling summary, and detailed engineering check.
