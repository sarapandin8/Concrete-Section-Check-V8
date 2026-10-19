# IGIRDER.SLS54 — แก้ส่วนบนหน้า SLS ถูกบัง

ต่อจากแพ็กเกจ SLS53_REPACK โดยแก้เฉพาะระยะด้านบนของหน้า compact SLS

## สาเหตุและสิ่งที่แก้

แถบเครื่องมือ Streamlit สูง 60 px แต่ global style เว้น padding ด้านบนเพียง 24.8 px ทำให้ป้าย Analysis subpage เริ่มที่ประมาณ y=34 px และปุ่มแท็บเริ่มที่ y=57 px ซึ่งอยู่ใต้แถบเครื่องมือ อาการเกิดทั้งก่อนและหลังกด Calculate โดย scrollTop ยังเป็นศูนย์

รุ่นนี้กำหนด padding ด้านบน 4.75rem เฉพาะ main container ที่มี compact SLS navigation และเฉพาะ screen media ป้ายและปุ่มจึงอยู่ใต้แถบเครื่องมืออย่างครบถ้วน ไม่สั่งเลื่อนจอหรือรีเซ็ตตำแหน่งที่ผู้ใช้เลื่อนไว้ หน้าอื่นและระยะพิมพ์ A4 ใช้ค่าเดิม

## วิธีใช้

แตก ZIP ใหม่แล้วเปิดแอปตามเดิม โหลด Project JSON เดิมได้ และไป Analysis → SLS / Stress & Cracking → Calculate SLS Stress แถบเลือกงานด้านบนควรแสดงครบตั้งแต่เริ่มหน้า

## ผลตรวจ

- Browser จริงที่ความกว้าง 1768, 1280 และ 390 px: ตรวจส่วนหัวก่อนและหลังกดรัน รวมการเปลี่ยนช่วงงาน / คาน / พื้นบน desktop
- ตรวจตำแหน่ง scroll เมื่อกดคำนวณซ้ำ และตรวจ padding เมื่อเปลี่ยนไปหน้า ULS
- ชุดทดสอบ SLS, CODE52 และ navigation / app styles: **34 passed**
- A4 ยังเป็นหนึ่งหน้าตามกรณีทดสอบ
- Source ของ stress engine, แรง, prestress, ขีดจำกัด, การจัดอันดับเคส และผล Summary ไม่เปลี่ยน

หลักฐาน: `qa/evidence/sls54/verification.json` และ `selected_tests.txt`

## Repo summary

Fix clipped SLS navigation by clearing the top toolbar in the compact layout. Preserve calculation results, scroll position and A4 print spacing.
