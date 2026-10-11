# Concrete Section Pro — IGIRDER.ALLCASE15

พัฒนาต่อจาก `concrete-section-pro_IGIRDER-CSIIMPORT14.zip` โดยแก้การเลือก All load cases ในกราฟ Shear และ Torsion ของหน้าผลแยกแต่ละ girder

## สาเหตุและผลหลังแก้

ตัวเลือก Load case to review ส่งทุก case ลงมาถูกต้อง แต่กราฟเดิมยังอยู่ในโหมด Selected case — demand / capacity และเลือก Case for diagram กลับเหลือ case เดียว จึงเห็น Vu Min 1 หรือ Tu Max 1 ตามภาพ แม้ข้อความด้านบนระบุ All load cases ปัญหานี้อยู่ในส่วนแสดงกราฟ

| หัวข้อ | CSIIMPORT14 | ALLCASE15 |
|---|---|---|
| All load cases — Shear/Torsion | กราฟ demand/capacity เลือกกลับเหลือ case เดียว | เปิด All cases — demand / capacity และพล็อตทุกชุดเส้นของ girder ที่กำลังดู |
| Case for diagram | ยังให้เลือก case ซ้ำภายในโหมด All | ไม่แสดงตัวเลือกซ้ำในโหมด All |
| กำลังต้านทาน | ผลคำนวณแยก Case ที่เก็บไว้ | ใช้ผลชุดเดิม จับคู่กับแต่ละ Case/station และรักษาเส้นต้านทานที่แตกต่างกัน |
| ชื่อเส้น | ชื่อ case ที่เลือก | Vu C1… / Tu C1…; hover เก็บชื่อเต็มและข้อมูลต้นทาง พร้อม Chart source key — all load cases |
| Overview — utilization | ค่าสูงสุดจากคู่ force/resistance ของแต่ละ case รายตำแหน่ง | หลักการเดิม พร้อมคำอธิบายว่า Overview เป็นค่าสูงสุดรายตำแหน่ง |
| Flexure, Max/Min และราย source vector | เส้นทางที่รับรองไว้เดิม | ใช้เส้นทางเดิม และทดสอบการสลับกลับจาก All |

ข้อมูล native CSI ที่ใช้ทดสอบมี 4 OutputCase × Max/Min × Before/After = 16 ชุดเส้นต่อ girder, 320 แถวต่อ girder รวม 640 แถว การวาดทุกเส้นไม่เปลี่ยนข้อมูลนำเข้า; เส้น demand ที่มีพิกัดตรงกันยังมีรายการ legend แยก แต่ภาพอาจซ้อนกันพอดี เส้นกำลังต้านทานที่ตรงกันใช้ legend ร่วมตามมาตรฐานเดิม ค่า ±φVn/±φTn ด้านลบเป็นกำลังต้านทานสะท้อนเครื่องหมาย ไม่ใช่ Min load case

## วิธีใช้

1. แตก ZIP ใหม่ลงโฟลเดอร์ใหม่ แล้วเปิดแอปจากโฟลเดอร์นั้น
2. โหลด Project JSON / นำเข้า ULS ด้วยวิธีเดิม แล้วกด Calculate Shear หรือ Calculate Torsion
3. เปิด Girder ที่ต้องการ → Load case to review → All load cases
4. Chart view จะเปิด All cases — demand / capacity โดยตรง ตรวจชื่อเต็มได้ที่ hover และ Chart source key — all load cases
5. ถ้าต้องการดูค่า utilization สูงสุดรายตำแหน่ง ให้เลือก Overview — utilization; ถ้าต้องการดู Max/Min ของ load case เดียว ให้เลือกครอบครัว CSI case ตามเดิม

## การตรวจสอบ

- Compile `app.py`, โมดูลที่แก้ และ QA/test scripts
- Scoped regression **243 passed**, 0 failures / errors: ครอบคลุม All-case charts, native CSIIMPORT14, Max/Min, Torsion Audit 12, Report charts, full-span/source boundaries, case control, per-member charts, V/T semantics, Rebar Advisor 13 และ Project JSON
- ตรวจชุดกราฟและ global readability เพิ่มเติมหลังจัด layout: **29 passed** (บาง test ซ้ำกับชุดหลัก ไม่รวมเป็นจำนวน test ที่ไม่ซ้ำ)
- Actual `app.py`: สอง girder × Shear/Torsion แสดงครบ 16 เส้นต่อ girder; ทดสอบ All → Overview → CSI family → source vector → All
- ระหว่างสลับกราฟ ปิดการเรียก solver ด้วย guard และตรวจ input tables / active member / runtime result caches คงเดิม
- Browser QA ตรวจจำนวน trace และการแสดง legend ของทุก case ใน Chrome; ตรวจภาพที่ความกว้าง 1440 และ 1100 px ภาพ QA เก็บภายนอก ZIP
- XLSX ต้นทางและ six force components ใช้ข้อมูลเดิมทุกค่า; ข้อมูล source audit ก่อนหน้าอยู่ครบ

โมเดลหน้าตัดสำหรับ QA เป็นตัวอย่างสมมติ ใช้ยืนยันการแสดงผล ไม่ใช่การรับรองหน้าตัดของโครงการผู้ใช้ สถานะ FAIL, REVIEW และข้อมูลที่ขาดยังใช้ผลและ gate เดิม ช่องว่างกำลังต้านทานไม่ถูกแทนด้วยศูนย์หรือค่าจาก case อื่น

## ขอบเขตที่คงเดิม

สูตร Vn/Tn, ตัวคูณ φ, General Procedure, composite/development/interface checks, Rebar Advisor 13, ULS/SLS solver, การนำเข้า CSIIMPORT14 และพฤติกรรม Project JSON ใช้ชุดเดิม ไม่มีการเพิ่มการบันทึกผลคำนวณลง Project JSON และไม่มีการเรียกคำนวณใหม่เพื่อสลับกราฟ

แก้ production code ใน `concrete_pmm_pro/ui/igird_member_results.py`, `concrete_pmm_pro/ui/igird_vt_workspace.py` และ shared chart style `concrete_pmm_pro/visualization/igird_uls_chart_display.py`, `concrete_pmm_pro/visualization/plot_readability.py` เพื่อให้ legend ทุก case ไม่ทับข้อความใต้กราฟแม้ผ่าน global style; `app.py` และ `requirements.txt` ใช้ไฟล์เดิมจาก CSIIMPORT14 แพ็กเกจเป็น full ZIP เก็บทุก entry จาก baseline และเพิ่ม test/QA/handoff ของงานนี้ ไม่มี runtime checkpoints, browser screenshots, `__pycache__`, `.pyc` หรือ `.pytest_cache` ที่สร้างใหม่อยู่ในแพ็กเกจ

Repo summary: Fix Shear and Torsion All load cases charts to plot every source series with its stored case-specific resistance.
