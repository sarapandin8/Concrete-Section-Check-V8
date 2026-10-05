# IGIRDER.MEMBERCHARTS3 — Separate ULS graphs for every imported girder

วันที่ 5 ตุลาคม 2026

Baseline: concrete-section-pro_IGIRDER-MULTIGIRDER2.zip
Baseline SHA-256: c9bd5b0e0b9a9715f755427edd106e328de2af9a6ea2a168c7cabd10dcf4d378

## สิ่งที่แก้

เพิ่มมุมมอง All imported girders — separate charts ใน Analysis ULS สำหรับสมาชิกใน collection จาก Loads ให้คำนวณและแสดง Flexure Final Composite, Shear, Torsion และ Shear + Torsion แยกตาม girder ไม่รวมเส้น demand ของคนละสมาชิกไว้ในกราฟเดียว ทุกกราฟหลักมีหัวข้อ Girder: ตามชื่อที่ผู้ใช้กำหนดตอน import

ปุ่ม Calculate ของมุมมองนี้คำนวณ check ที่เลือกสำหรับทุก girder ที่มี Active rows โดยใช้ชุดแรงทั้งหมดของ girder นั้นกับ solver เดิม คงทุก case/step/repeated station และ source gate เดิม ไม่มีการสร้าง envelope ข้ามองค์ประกอบ

แต่ละสมาชิกมี runtime result และ input hash แยกกัน กราฟอ่านผลที่คำนวณไว้เท่านั้น เปลี่ยน Chart view หรือ Case ไม่เรียก solver ซ้ำ เปลี่ยนแรงของสมาชิกหนึ่งทำให้ผลของสมาชิกนั้น STALE; เปลี่ยนข้อมูล model ที่ใช้ร่วมกันทำให้ผลสมาชิกที่ได้รับผลกระทบต้องคำนวณใหม่

## วิธีใช้

1. Loads: upload ตารางสำหรับ Exterior Girder และ Interior Girder 2 พร้อมทุก case กำหนด Physical girder / member name ให้ถูกต้องข้ามไฟล์ แล้ว Replace/Add girder collection
2. Analysis → ULS Strength: เลือก check เช่น Flexure
3. สำหรับ Flexure เลือก Final — Composite
4. Girder results view: เลือก All imported girders — separate charts (เป็นค่าเริ่มต้นเมื่อมี collection)
5. ตรวจรายชื่อ girder และจำนวน Active rows / Vector series
6. กด Calculate [check] — all N girders (current model)
7. ดูกราฟแยกใต้ชื่อ Girder: Exterior Girder และ Girder: Interior Girder 2 แต่ละกราฟมีแรงและกำลังเฉพาะสมาชิกนั้น
8. ทำเช่นเดียวกันกับ Shear, Torsion และ Shear + Torsion
9. Shear/Torsion มี Overview — utilization และ Selected case — demand / capacity แยกตัวเลือกของแต่ละสมาชิก ไม่มี widget key ชนกัน
10. หากต้องการหน้าเดิมพร้อมรายละเอียด composite interface acceptance ให้เลือก Selected girder — detailed checks และเลือกสมาชิกที่ต้องการใน Loads

## การอ่านกราฟ

- Flexure: Mux demand ทุก case ของ girder ที่ระบุ เทียบกับ φMn Final Composite ของ girder นั้น; x-axis ครอบคลุมเต็มช่วงสมาชิก ใช้การจัด legend และการรวม capacity ที่ตรงกันจาก baseline
- Generic case ชื่อยาวใช้ Mux C1/C2/... ภายในกราฟนั้นเพื่อไม่ให้ชื่อที่ย่อซ้ำกัน Full case/source identity อยู่บน hover, figure metadata และตาราง audit
- Native CSI case ใช้ compact Max/Min/vector labels ของ baseline
- Shear/Torsion: Overview แสดง governing available utilization จาก case/check ที่เกิดคู่กันจริง; Selected case แสดง signed demand และ capacity ของ case ที่เลือก
- Shear + Torsion: ใช้ combined workspace เดิมแยกตามสมาชิก มี source/readiness/status และ Calculation trace / Equations; ข้อมูลไม่ครบจะไม่แสดงเป็น overall PASS
- กราฟหลักระบุชื่อ girder ในตัวภาพ รวมทั้งเมื่อดาวน์โหลดภาพผ่าน Plotly

## ขอบเขตที่สำคัญ

**Current model ใช้ร่วมกันในการคำนวณ collection:** หน้าตัด, effective deck width, เหล็ก, strand/debonding, prestress, stirrup/torsion hoop, support settings ยังเป็นชุด model ปัจจุบัน ไม่ได้สร้าง section/model profile แยกสมาชิกใน milestone นี้

หาก Exterior และ Interior มีรายละเอียดต่างกัน ต้องใช้ Project model ที่ตรงกับสมาชิกนั้นก่อนยอมรับผล การแยกกราฟไม่ได้สร้างกำลังเฉพาะหน้าตัดที่ยังไม่ได้กำหนด ถ้าข้อมูลหน้าตัดและค่าที่มีผลต่อ resistance เหมือนกัน เส้น φMn อาจเท่ากันได้แม้กราฟและ demand จะแยกกัน

Flexure collection แสดง sectional strength; composite acceptance ยังต้องยืนยัน effective width, development, concurrent force source และ girder–deck interface shear ของสมาชิกนั้นใน detailed workspace การตรวจ Bearing/D-region, STM, composite torsion force flow, deck transverse design และข้อจำกัดอื่นตาม baseline ยังแยกต่างหาก

Runtime collection results ไม่บันทึกลง Project JSON; JSON เก็บ collection inputs และ selected member ตาม MULTIGIRDER2 ต้องคำนวณใหม่หลัง load

Result Summary/Report QA เดิมแสดง selected member เท่านั้น ไม่ใช่รายงานรวมทุก girder ผล collection ของสมาชิกอื่นไม่เขียนทับ selected-member result cache

Construction — Noncomposite ยังคง workflow เดิม; การแยกกราฟชุดนี้เป็น imported Final ULS

## Validation

- Regression: 628 tests passed สำหรับ I-girder/girder workflows และ Project IO
- Targeted checks หลังปรับ labels, equation display และ full-span charts: 52 tests passed
- New tests: 10 cases ครอบคลุม independent solver source rows ทั้งสี่ checks, active/case isolation, exact VT frame equality กับ engine เดิม, ไม่แก้ไข model inputs, staleness จากแรงรายสมาชิกและ shared model, full-span range และ named graph identity
- Streamlit AppTest: สอง girders × สอง ULS cases; ทั้งสี่ checks มีกราฟชื่อสมาชิกแยกครบ ตัวเลือก Case แยกกัน เปลี่ยนหน้า/กราฟไม่เรียก solver ซ้ำ ผล Interior ที่เปลี่ยนแรงแสดง STALE และไม่วาดกราฟเก่า
- Rendered chart PNG: 8 named figures จาก real solver output; ตรวจภาพ Flexure และ Combined V+T ด้วยตา
- Compileall app.py / concrete_pmm_pro ผ่าน
- ไม่อ้างว่าตรวจภาพ browser ของแอปทั้งหน้า; ใช้ AppTest ตรวจ UI state และ PNG ตรวจหน้าตากราฟ
- ไม่มีการเปลี่ยนสมการกำลังรับแรง; ใช้ engines จาก accepted baseline แยกต่อสมาชิก

## Changed files

- concrete_pmm_pro/ui/igird_member_results.py: collection workspace, per-member solve/hash/runtime results, named graphs
- concrete_pmm_pro/ui/analysis_page.py: collection view entry points for Final Flexure and VT
- concrete_pmm_pro/ui/igird_vt_workspace.py: per-member widget prefix, graph title, remove inherited single-case note from overview
- concrete_pmm_pro/ui/igird_combined_vt.py: pass member title to combined chart
- tests/test_igird_membercharts3.py and qa/evidence/igird_membercharts3/

Repo summary: Calculate and display separate named ULS graphs for every imported girder across flexure, shear, torsion, and combined shear–torsion checks.
