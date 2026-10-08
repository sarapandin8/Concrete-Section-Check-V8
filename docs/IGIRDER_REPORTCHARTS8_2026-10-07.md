# CONCRETE SECTION PRO — IGIRDER.REPORTCHARTS8

วันที่ 2026-10-07

ต่อจาก IGIRDER.GAPAUDIT7 ชุดเต็มที่ตรวจ SHA-256 และ ZIP CRC แล้ว:
3e5fe7a1f3b653e1f89ec78be328f2f879628615651be8a0c5ad672ece053810

## ขอบเขต

ขยาย Torsion report chart เดิมเป็นแผงพับเปิดเดียว:
**I-girder ULS report charts — stored results**

เลือกได้ครบ 4 checks:
- Flexure — Final Composite
- Shear
- Torsion
- Shear + Torsion

แต่ละ check เลือก girder และ load case ได้จากผลปัจจุบันของสมาชิกนั้น
ค่าเริ่มต้น Automatic — controlling load case ใช้ governing component D/C
จาก stored check rows จริง ไม่เลือกจากแรง envelope หรือแรงสูงสุดเพียงอย่างเดียว
หากค่าเท่ากัน แสดงทุก tied case ในข้อความและตาราง ranking
หากไม่มี numerical D/C หรือมีเพียง torsion investigation ratio
แสดง basis เดิมให้ชัด ไม่ยืนยัน strength PASS

## กราฟและข้อมูลรายงาน

Analysis และ Report ใช้ accepted figure builders เดิม:
- Flexure: signed Mux และ stored sectional φMn ของ Final Composite
- Shear: signed Vu และ ±φVn จาก stored station diagram/critical sections
- Torsion: signed Tu และ ±φTn จาก GAPAUDIT7 รวม qualified BELOW THRESHOLD / zero Tu
- Shear + Torsion: maximum available original component D/C ที่แต่ละ station และ Limit=1.0

กราฟแยก girder/case; source context สำหรับ CSI endpoints จำกัดอยู่ในสมาชิกเดียวกัน
ไม่สร้าง Tu/Vu/Mux หรือค่ากำลังใหม่ และไม่เติม NaN
ความต้านทานที่ขาดจริงยังขาด พร้อม status markers / audit ตาม route เดิม
Combined partial/source-blocked results ยังคงสถานะเดิม

ภาพมีชื่อ girder, case, code, หน่วย, selected-case numerical control/station
และจำนวน FAIL/REVIEW ของ case ที่เลือกและของสมาชิกนั้นจากทุก cases
การเปิดดู passing case จึงไม่ซ่อน failure/review ของ case อื่นใน girder เดียวกัน
หมุด governing เดิมยังอยู่; นำข้อความ control ไปไว้ใต้ภาพเพื่อไม่ทับเส้นหรือหัวกราฟ
ย่อ generic Shear demand legend เป็น Vu demand; ชื่อเต็มยังอยู่ใน hover และ metadata
Torsion ที่ไม่มี finite φTn ระบุว่าเป็น investigation threshold และ φTn unavailable

แผง source audit มี:
- Load-case ranking พร้อม controlling source row
- Component controls
- Full stored check rows ของ selected case
- Download selected stored check rows (CSV), UTF-8 BOM, original numeric precision
- Combined missing-ratio audit / CSV เมื่อมีข้อมูลไม่พร้อม

Create report chart PNG แล้ว Download report chart PNG ส่งออก 2880×1120
ใช้ shared layout 1440×560 / scale=2; สร้าง raster เมื่อกดปุ่มเท่านั้น
Result Summary cached I-girder figures ใช้ current cached case-scoped builders นี้ด้วย
workflow อื่นยังใช้ route เดิม

## Cache และขอบเขตการยอมรับผล

แผงใหม่อ่าน production runtime caches เท่านั้น
ตรวจ input hash และ result version เดิมก่อนใช้ผล
รวม active design table ที่แก้หลัง bank save; ไม่ให้ผลเก่าแสดงว่า current
คง single-table / manual-cache workflow และ Final Composite stage ownership
หาก girder ไม่มีผลปัจจุบัน ระบุชื่อไว้และบอกให้ Calculate ใน Analysis
ไม่สลับไปใช้กราฟสมาชิกอื่นแทน girder ที่ requested current result ไม่พร้อม

Review, changing check/girder/case, CSV และ PNG export:
- ไม่เรียก solvers หรือ calculate_member
- ไม่ activate girder / เปลี่ยน design member ใน Loads
- ไม่แก้ force tables, load bank, stored result frames หรือ manual/collection caches
- ไม่เปลี่ยนสมการ, ULS/SLS logic, source gates, development/threshold/acceptance decisions
- ไม่เปลี่ยน Project JSON, ไม่เพิ่ม result persistence และไม่เพิ่ม dependencies

ผล Flexure เป็น sectional resistance ของ composite section
overall composite acceptance ยังต้องยืนยัน effective width, development,
concurrent actions และ current interface shear ตามเกณฑ์เดิม
Result Summary และ Report-readiness cards ยังอ้างอิง design member ที่เลือกใน Loads
การเลือก report chart เป็นการเปลี่ยนมุมมองผลเท่านั้น

Calculate all ยังคงใช้ section, deck, reinforcement, prestress และ support model
ปัจจุบันร่วมกันทุก girderตาม baseline หากรายละเอียดสมาชิกต่างกัน ต้องแยก project models
Project JSON เก็บ input collection; เปิด project ใหม่แล้วต้อง Calculate ตามเดิม

## QA

- Final scoped regression 59 modules: **741 passed** in 124.39 s, Python 3.14.7
- Final targeted ReportCharts8 + GapAudit7: **42 passed**; 20 new behavior tests
- Initial Python 3.12.14 scoped regression: 740 passed; actual app routes/report widgets passed before final legend/missing-resistance-note polish
- Final actual app.py AppTest: Analysis/detailed routes of all 4 checks, interface-shear action, and Report/QA selectors + explicit PNG/CSV downloads PASS
- Report: 2 girders × 2 named cases × 4 checks = 16 case-scoped chart reviews; AUTO control, stale/pending hiding, no solver/cache/input changes PASS
- Collection AppTest: AUTO/named/ALL, source review, collapsed girder panels and stale hiding PASS
- py_compile PASS for app.py and changed production/QA modules
- Actual PNG dimensions 2880×1120 verified; figure has the selected member/case and explanatory footer
- Final runtime: Streamlit 1.61.0 / pandas 3.0.6 / PyArrow 24.0.0 / Plotly 5.24.1 / Kaleido 0.2.1

ทดสอบด้วย controlled hypothetical QA inputs ไม่ใช่การคำนวณโครงการผู้ใช้ซ้ำ
ตรวจภาพจากสอง girders/สอง cases และ legend/footer/title ของทั้งสี่ checks
ไม่มีการ push หรือ deploy และยังไม่ได้ทดสอบ live Streamlit Cloud
ใช้ AppTest ตรวจ entrypoint/widget/routes และ Plotly PNG ตรวจภาพ
ไม่ได้อ้างว่าเป็น full repository suite หรือมี live full-page browser screenshot
Inherited Streamlit Arrow automatic-fix/deprecation log messages ของตารางเดิมบางส่วน
ยังพบได้ใน full-app QA; ไม่มี fatal Streamlit exception ในชุด QA ที่รายงานนี้
ตาราง source audit ใหม่ใช้ result_table_for_display adapter

คำสั่งทำซ้ำจาก project root:

```bash
python -m py_compile app.py concrete_pmm_pro/ui/igird_uls_report.py concrete_pmm_pro/ui/igird_torsion_report.py concrete_pmm_pro/ui/igird_vt_workspace.py
python -m pytest -q tests/test_igird_reportcharts8.py tests/test_igird_gapaudit7.py
python qa/igird_reportcharts8_app_verify.py --output-dir qa/evidence/igird_reportcharts8/recheck
python qa/igird_casecontrol5_ui_verify.py --release IGIRDER.REPORTCHARTS8 --output-dir qa/evidence/igird_reportcharts8/collection_recheck
```

Scoped regression module list: qa/evidence/igird_reportcharts8/regression_modules.txt
Final Python 3.14 evidence: qa/evidence/igird_reportcharts8/python314
Collection AUTO/named/ALL evidence: qa/evidence/igird_reportcharts8/collection_ui
Historical baseline QA evidence retained

## Repository summary

Extend cached I-girder ULS report charts to all four checks with girder/load-case selection, controlling-case notes, and PNG/CSV export.
