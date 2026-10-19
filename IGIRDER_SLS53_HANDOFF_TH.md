# IGIRDER.SLS53 — SLS / Stress & Cracking

พัฒนาต่อจาก CODE52 ให้หน้า SLS ของ Bridge I-girder กระชับและใช้กราฟเป็นผลหลัก งาน Shear, Torsion และ Shear + Torsion ของ CODE52 ยังคงอยู่

## วิธีใช้

1. เปิด Project JSON เดิม ไป **Analysis → SLS / Stress & Cracking**
2. ถ้านำเข้า SLS หลาย girder ให้เลือก **SLS girder** แล้วกด **Calculate SLS Stress** ครั้งเดียว โปรแกรมคำนวณทุกช่วงงานและทุกเคสของ girder ที่เลือก
3. เลือก Transfer / Lifting / Construction / Service และ load case เพื่อดูกราฟ ค่าเริ่มต้นเลือกเคสควบคุมของช่วงงานนั้น Service เลือกดู I-girder หรือ Slab / CIP ได้ การเปลี่ยนตัวเลือกกราฟไม่รันเครื่องคำนวณใหม่
4. เปิด **Check settings / Stress limits** เมื่อต้องตั้งฐานขีดจำกัด และเปิด **Calculation details / Equations** หรือ **Load cases / Source audit** เพื่อตรวจสูตร ความเค้นรายจุด และแถวแรง ดาวน์โหลด CSV ได้จากแผง Source audit

หลังแก้ geometry, วัสดุ, prestress, โหลด, girder หรือเงื่อนไข stress limit ให้กด Calculate ใหม่ ผลเก่าถูกซ่อนและไม่ถูกนำไปใช้เป็นผลปัจจุบันใน Summary / Report

## สิ่งที่แก้

- ลดส่วนหัวซ้ำ บัตรสรุปซ้ำ และแบบฟอร์มทดลองออกจากหน้าหลัก เหลือสรุปสามบัตร กราฟหลักหนึ่งกราฟ และแผงรายละเอียดแบบพับ โดยใช้การนำทางและข้อมูลโครงการใน sidebar เดิม
- แกนกราฟกำหนด 0–L พร้อมหน่วย m / MPa สีเส้น Top / Bottom และเส้น compression / tension limit คงที่ แยกชนิดเส้นได้ ไม่วางข้อความยาวทับเส้นกราฟ และไม่ตัด governing marker ที่ปลายคาน
- ชื่อกราฟมี stage, component, girder และ case เพื่อให้ภาพที่ export มีบริบท ข้อความยาวตัดขึ้นบรรทัดตามพื้นที่ บนมือถือเลื่อนเฉพาะกราฟในแนวนอนได้
- สรุปครอบคลุมทุกเคสที่คำนวณของ **girder ที่เลือก** การเลือกดูเคสที่ผ่านไม่ซ่อน FAIL / REVIEW ของเคสอื่น และไม่ได้เป็นการอนุมัติ SLS ของ girder ทั้งสะพาน
- สรุป Service ใช้ผลตรวจวัสดุ Beam / Slab ชุดเดียวกับกราฟ แทนการนำ extreme fiber ของหน้าตัดแปลงมาสรุปคู่กับกราฟวัสดุคนละชุด เก็บความละเอียดเต็มในการจัดอันดับและปัดเฉพาะตอนแสดงผล
- ไม่แทนแรงที่ว่าง/ไม่ใช่ตัวเลข/NaN/Infinity ด้วยศูนย์ ไม่แสดงผลเก่าเมื่อคำนวณไม่ได้ ข้อมูลอ้างอิงแรงที่ต้องทบทวน การคำนวณ prestress ที่ไม่พร้อม และ source stations ที่ไม่ครอบคลุมปลายคานยังแสดง REVIEW พร้อมเหตุผล
- ไม่มีการบังคับความเค้นที่ปลายคานให้เป็นศูนย์ ไม่มีการต่อค่าผ่านข้อมูลความเค้นที่หายไปหรือ extrapolate ปลายกราฟ
- ใช้ stress engine, staged Pe(x), losses, section basis, ขีดจำกัดตาม code และสัญญาข้อมูล CSI เดิม ผล runtime ไม่เพิ่มเข้า Project JSON และ Summary / Report ไม่เรียก stress solver

## ขอบเขตผล

ยังเป็นการตรวจ **elastic N–Mx stress-limit preview** ตาม route เดิม กราฟนี้ไม่ได้เพิ่มการคำนวณ crack width, cracked-section response, principal tension, long-term redistribution หรือการตรวจ end-zone รายละเอียดอื่น สถานะที่ต้อง REVIEW และเงื่อนไขยืนยันเหล็กสำหรับขีดจำกัดที่สูงขึ้นยังคงอยู่

JSON โครงการเดิมที่ใช้ตรวจซอฟต์แวร์ยังไม่มี imported SLS member bank มีแถวเริ่มต้นสามช่วงงาน จึงใช้ staged auto-loads และ prestress เดิมในการทดสอบ การตรวจ import เพิ่มใช้ native CSI fixture 240 แถว / 2 girder ซึ่งแยกจากผล SLS ของโครงการจริง

## ผลตรวจ

- Base ZIP: `concrete-section-pro_IGIRDER-CODE52.zip`, SHA-256 `1c19193938c0a1a0b43877bd21cc65154d2a8652372900744afc1c79f4f05368`
- Project JSON SHA-256: `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`
- เทียบ native engine ของ CODE52 กับผล SLS53: raw 22 ชุด และ split 22 ชุด ตรงกันครบทุกค่าทุกคอลัมน์ โดย split 13 ชุดมีข้อมูล อีก 9 ชุดว่างตามช่วงงานที่ไม่มี composite split
- Actual `app.py` AppTest: JSON เดิม และ CSI fixture ทั้งสอง girder; Calculate เรียก station engine สี่ครั้งต่อ girder ครบทุกช่วงงาน การเปลี่ยน stage / case / component และ Summary / Report ไม่เรียกเพิ่ม ตรวจ ULS input เดิมและ Project JSON input-only แล้ว
- ชุด regression ที่เลือก: **163 passed** รวม SLS, prestress, material/profile routing, CODE52, navigation, chart readability, Summary และ Report มีคำเตือนเดิมจาก pytest import rewrite และ pandas concatenation 7 รายการ
- Browser: desktop 1600 / 1280 px และมือถือ 390 px ตรวจทุก stage รวม Service Beam / Slab, full span, title / axes / legend bounds และการไม่ซ้อนทับ พร้อมตรวจ A4 vector print
- หลักฐานอยู่ใน `qa/evidence/sls53/` และรันทวนได้ด้วย `qa/igird_sls53_verify.py --project <project.json> --out <external-directory>`

ผลข้างต้นเป็นการตรวจซอฟต์แวร์และการแสดงผล ไม่ใช่การเปลี่ยน FAIL ของโครงการให้เป็น PASS หรือการรับรองแบบโครงสร้าง

## Repo summary

Compact the I-girder SLS workspace around one explicit calculation and one stress graph. Preserve native stress equations; fix all-case governing scope, Service Beam/Slab consistency, stale-result handoff, missing-input handling and chart/print layout. Retain CODE52 ULS behavior.
