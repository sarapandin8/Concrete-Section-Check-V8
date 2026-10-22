# SLAB.PUNCH75 — Apply load areas ตอบสนองและบันทึกชัดเจน

## ปัญหาที่พบ

เมื่อยังไม่มีพื้นที่ลงแรง ตารางเดิมส่งข้อมูลว่างเข้า Apply ได้ ตัวตรวจรับรายการว่างแล้วบันทึกและ rerun โดยไม่มีข้อความยืนยันหรือแจ้งข้อมูลที่ต้องกรอก จึงมองเหมือนปุ่มไม่ทำงาน และ Punching ยังไม่มีพื้นที่ที่จะนำไปคำนวณ

## การแก้ไข

- แสดงแถวว่างที่แก้ไขได้ทันที พร้อมชนิดคอลัมน์ตัวเลขที่ชัดเจน
- กด Apply โดยยังไม่กรอกพื้นที่ จะแจ้งให้กรอก centre X/Y (m) และ L/B (mm); ชื่อและ Vu เว้นได้
- ตรวจข้อมูลให้ผ่านก่อนบันทึก รายการที่กรอกไม่ครบ มิติไม่เป็นบวก หรือชื่อซ้ำ จะไม่ทับข้อมูลที่ Apply ไว้ก่อนหน้า
- บันทึกสำเร็จจะแสดง Applied พร้อมจำนวนพื้นที่นอก expander เพื่อให้ยังเห็นหลังรีเฟรช
- เปลี่ยน revision ของ editor เมื่อ commit ป้องกันการเพิ่ม/ลบแถวเดิมถูก replay กับตารางที่เพิ่งบันทึก
- หากลบพื้นที่ที่บันทึกไว้ทั้งหมดแล้ว Apply จะยืนยันว่า cleared และผลคำนวณเก่าไม่ใช่ผล current

## วิธีใช้

1. กรอกตำแหน่งศูนย์กลาง X/Y ในพิกัด global ที่นำเข้า หน่วย m และขนาด L/B ที่ผิวพื้น หน่วย mm โดย L ตามยาวสะพานและ B ตามขวาง
2. กด Apply load areas และตรวจข้อความ Applied / validation
3. กด Calculate Top slab เพื่อคำนวณหรือปรับผล Punching shear

ชื่อพื้นที่ที่เว้นไว้จะได้รับชื่อ P1, P2 ตามเดิม ส่วน Vu ที่เว้นใช้วิธี automatic bound เดิม พื้นที่ที่บันทึกจะรวมอยู่ใน Project JSON ตาม PROJECT74

## ขอบเขตและการตรวจสอบ

แก้ production file เฉพาะ ui/slab_shear64_workspace.py ไม่มีการเปลี่ยนสมการ Punching, critical perimeter, shell-force demand, exclusions, result hashes หรือ logic กำลังหน้าตัด ส่วน PROJECT74 และ COLOR73 คงตาม baseline ที่ตรวจ hash แล้ว

No engineering equations changed. No ULS/SLS calculation logic changed. No Project JSON schema changed. No additional result-cache persistence was added.

ตรวจด้วย Streamlit AppTest ใน app.py จริง ครอบคลุมตารางว่าง, partial/invalid input, การบันทึกโดยไม่รัน solver, การคำนวณหลัง Apply, Vu ว่าง/ระบุโดยตรง, ชื่ออัตโนมัติ, เพิ่ม/ลบหลายแถว, ล้างข้อมูล และ Project JSON round trip รวมทั้งทดสอบ punching resistance เดิม ดู SLAB_PUNCH75_VERIFICATION.json และ qa/evidence/slab_punch75/

ข้อมูล 127,680 แถวและ 7 ตาราง CSV ใน PROJECT74 เป็นหลักฐาน baseline; ไม่ได้รันโครงการจริงนั้นซ้ำสำหรับ UI patch นี้ การทดสอบรอบนี้ใช้ fixtures รวมกรณีความหนาสม่ำเสมอที่ระบุชัดเพื่อให้ทวน numeric punching results ได้ ไม่ใช่การแก้ข้อมูลโครงการผู้ใช้

ผลรอบ PUNCH75: targeted 34 กรณี และ regression 67 กรณี รวม 101 กรณีผ่านทั้งหมด; compile app.py และไฟล์ที่แก้/เพิ่มผ่าน
