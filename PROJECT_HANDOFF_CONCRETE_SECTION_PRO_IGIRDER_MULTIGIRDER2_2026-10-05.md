# IGIRDER.MULTIGIRDER2 — Multiple girders and multiple ULS cases

วันที่ 5 ตุลาคม 2026

Baseline: concrete-section-pro_IGIRDER-MULTICASE1-DECKULS1.zip
SHA-256 baseline: 8f0d30b4bffbfb0a0ba1a0be67b9235bc2fef7f437a2b88439c89562185f46f3

## สิ่งที่แก้

รุ่นก่อนหลายไฟล์ถูกจำกัดให้เป็น girder เดียว และหนึ่งไฟล์เลือกได้หนึ่ง worksheet จึงยังไม่รองรับงานที่ต้องเก็บหลาย girder จากหลาย load case

รุ่นนี้ใช้การนำเข้าแบบเดียวสำหรับหนึ่งไฟล์หรือหลายไฟล์ เลือกหลาย worksheet ได้ โดยเริ่มเลือก worksheet ของ girder ทั้งหมด เก็บชุดแรงแยกตาม Physical girder / member name และ Case Name ทุกชุด คงแรงทั้งหกองค์ประกอบและ repeated station ตามแหล่งข้อมูล ไม่รวมแรงแต่ละองค์ประกอบจากคนละเหตุการณ์

## วิธีใช้

1. เปิด Loads → Final Composite ULS → Import Excel / CSV
2. Upload ไฟล์ทั้งหมดที่ต้องการ แต่ละไฟล์อาจมีหลาย girder และหลาย OutputCase
3. ในแต่ละไฟล์เลือก Worksheets to import ได้หลายรายการ เลือกเฉพาะแรงของ individual girder
4. ระบุ Physical girder / member name ของแต่ละ worksheet ชื่อของสมาชิกเดียวกันในต่างไฟล์ต้องตรงกัน เช่น Left Exterior Girder ใน ULS1 และ ULS2 ใช้ชื่อเดียวกัน หากชื่อ worksheet เป็นชื่อ load case ให้แก้ช่องนี้เป็นชื่อ girder จริง หาก girder อยู่คนละ span ต้องใช้ชื่อแยก เช่น Span 1 / G1 และ Span 2 / G1
5. หากไม่มี OutputCase ให้ระบุ Factored ULS combination name แยกตามไฟล์ แรงต้องเป็นผล ULS ที่ใส่ load factors แล้ว
6. ระบุ Force-vector source ตามข้อมูลจริง Envelope / unverified ไม่ถูกแปลงเป็น concurrent เพียงเพราะแยกไฟล์ตาม load case การยืนยัน Static/Correspondence และหลักฐานยังคงจำเป็นตามรุ่นก่อน
7. ยืนยันชื่อสมาชิกและ station origin ของแต่ละสมาชิก และ raw CSI P sign (tension positive, compression negative)
8. กด Replace entire girder collection เพื่อแทนที่ชุดที่เก็บทั้งหมดด้วยทุกตารางที่เลือก หรือ Add tables to girder collection เพื่อเพิ่ม โดยคงสมาชิก/กรณีเดิม เมื่อมีตารางเก่าที่ไม่มี collection ระบบมีช่องชื่อ girder สำหรับเก็บตารางเก่านั้นเมื่อ Add
9. ใต้ส่วน import มี Imported girder collection และจำนวน Rows / Vector series ของแต่ละสมาชิก เลือก Girder to design แล้วกด Use this girder — all imported load cases
10. ตารางแก้ไขหลักและ Analysis จะรับเฉพาะ girder ที่เลือกพร้อมทุก load case ที่ Active ตรวจหน้าตัด เหล็ก ลวดอัดแรง และ support settings ให้ตรงกับสมาชิก แล้วคำนวณแต่ละ check ใหม่
11. Save Project JSON เก็บ collection ทุกสมาชิกและสมาชิกที่เลือก การแก้ไขตารางของสมาชิกที่เลือกถูกเก็บก่อนสลับสมาชิกหรือ Save

## ขอบเขตที่ต้องเข้าใจ

- นี่คือ multi-member load collection และการเลือกสมาชิกสำหรับออกแบบด้วย workflow เดิม ไม่ใช่การคำนวณหลายหน้าตัดอัตโนมัติในครั้งเดียว
- หน้าตัด เหล็ก ลวดอัดแรง และ support settings ยังเป็นค่าปัจจุบัน ไม่ได้สร้าง model profile แยกต่อ girder หากสมาชิกมีรายละเอียดต่างกันต้องเปลี่ยนข้อมูล model ให้ตรงก่อนคำนวณ หรือบันทึก Project JSON แยกสำหรับแบบออกแบบของแต่ละสมาชิก
- การเลือกใน dropdown เพียงอย่างเดียวยังไม่เปลี่ยนชุดแรง ต้องกด Use this girder
- ผลเดิมต้องคำนวณใหม่หลังเปลี่ยนสมาชิก ระบบ hash เดิมใช้ชุดแรง/case ในการตรวจความเป็นปัจจุบันของผล ไม่มีการเพิ่ม result-cache persistence
- Vector series รวม Max/Min, step และ row-set suffix ไม่ใช่จำนวน ULS combination โดยตรง
- หากข้อมูลยังเป็น Max/Min แบบแยกองค์ประกอบ ข้อจำกัดการรับรอง coupled checks ของรุ่นก่อนยังคงอยู่
- Deck ULS Final และข้อจำกัด composite torsion / bearing D-region / STM / negative-moment route ของ DECKULS1 ยังคงตาม baseline ไม่ได้เพิ่มสมการกำลังรับแรงใน milestone นี้

## Validation

- Regression: 618 tests passed (I-girder, girder workflows, Project IO)
- หลังปรับส่วนเก็บ legacy table และข้อความ UI: targeted regression 61 tests passed
- Streamlit AppTest: 2 workbooks × 2 girder worksheets × 2 ULS cases รวม 12 rows; active member 6 rows; สลับสมาชิกคงข้อมูล; duplicate append disabled; เพิ่ม ULS3 ได้ 18 rows โดย active member 9 rows; Replace กลับเหลือเฉพาะชุดที่เลือก 6 rows
- Actual CSI fixture: 6 girders × 80 rows = 480 rows / 2,880 force values คงเดิมหลังการเลือกสมาชิก ตรวจ exact DataFrame equality
- Compileall app.py และ concrete_pmm_pro ผ่าน
- ไม่มีการยืนยันภาพหน้าจอจาก browser; ตรวจ interactive state ด้วย AppTest

## Changed files

- concrete_pmm_pro/io/girder_load_bank.py: member collection, activate/save, duplicate keys
- concrete_pmm_pro/ui/girder_csi_import.py: unified multi-file/multi-sheet import, member mapping, collection selector
- concrete_pmm_pro/ui/loads_page.py: collection panel and input metadata sync
- concrete_pmm_pro/io/project_io.py: persist collection + member selection, clear previous project member state
- concrete_pmm_pro/ui/analysis_page.py: visible selected imported girder context
- tests/test_igird_multigirder2.py: isolation, edits, duplicates, replace, Project IO
- qa/evidence/igird_multigirder2/: UI acceptance, regression evidence, actual fixture check

Repo summary: Store multiple girder ULS tables and select each member with all its load cases for analysis.
