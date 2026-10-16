# IGIRDER.EDIT33 — แก้ตาราง U-dowel พับกลับและค่าช่องถัดไปหาย

## สาเหตุที่ยืนยันได้

ในรุ่น DOWEL32 ตารางเปลี่ยน widget key ตามข้อมูลที่บันทึก และหัวข้อ Dowel detail เปลี่ยน label ตามจำนวนช่องที่ยังไม่กรอกโดยไม่มี key คงที่ หลังบันทึก A แล้ว การกรอก B ทำให้ตารางถูกสร้างใหม่ ค่า B ไม่ถูกเก็บและหัวข้อพับกลับ

จำลองใน app.py จริงด้วยเบราว์เซอร์ได้ว่า A=120 ถูกเก็บ แต่ B=180 กลับเป็นค่าว่าง หัวข้อปิด และ scroll กระโดด 379 px ไม่ใช่เพียงปัญหาการแสดงผล

## สิ่งที่แก้

- รักษา seed และ widget key ของตารางตลอดการกรอกต่อเนื่อง โดยใช้กับระยะ A–F, Dowel layout และตาราง joint forces แบบ advanced
- เพิ่ม key คงที่ให้ Dowel detail และ Dowel layout จึงไม่พับกลับเมื่อจำนวนช่องว่างเปลี่ยน
- เมื่อกลับเข้าหน้ากรอก ใช้ค่าที่บันทึกในโมเดลแล้วเป็น seed ใหม่ กรณี Copy zoning ใช้ข้อมูลที่สั่งคัดลอกโดยไม่เอา edit เก่ามาทับ
- เมื่อโหลด Project JSON ล้างเฉพาะสถานะ editor ที่เกี่ยวข้อง เพื่อไม่ให้ค่าแก้ไขจากโมเดลเก่ารั่วไปโมเดลใหม่
- สถานะ editor เป็นข้อมูล UI ใน session เท่านั้น ไม่ได้เพิ่ม field ใน Project JSON และไม่ใช่ solver-result persistence

## การตรวจสอบ

- py_compile ของ app.py และไฟล์ Python ที่แก้ไขผ่าน
- ชุดทดสอบที่เลือก 321 รายการผ่าน, 0 fail/error/skip มี 7 warnings เดิม ไม่ได้อ้างว่าทดสอบทั้ง repository
- เบราว์เซอร์ Chromium 130 บน app.py จริง ที่ 1440 และ 1280 px: แก้ A–F, ล้างค่า, กรอกใหม่และแก้ซ้ำรวม 9 ครั้งในแต่ละรอบ ค่าเก็บครบ หัวข้อเปิดค้าง และ scroll เปลี่ยน 0 px หลังแต่ละ commit
- ที่ 1280 px ตรวจทั้ง Enter และ Tab รวมถึงปิด/เปิด Edit composite / dowel inputs แล้วค่าคงเดิม
- ไม่พบ page error หรือ Streamlit exception และไม่มี solver call ระหว่างกรอก
- AppTest ตรวจการเพิ่ม/ลบแถวใน Dowel layout, Copy zoning, แทนข้อมูลภายนอก และโหลด JSON ใหม่ ไม่ใช้ edit เก่าซ้ำ
- ภาพหน้าจอ QA ใช้ตรวจภายในเท่านั้น ไม่รวมในไฟล์ส่งมอบ

## การใช้งาน

บันทึก Project JSON ปัจจุบันก่อนเปลี่ยนรุ่น แล้วเปิดแอปจาก ZIP EDIT33 และโหลด JSON นั้นกลับ ใช้เส้นทาง Analysis → ULS Strength → Flexure → Final — Composite → Edit composite / dowel inputs ตามเดิม ไม่ต้องกด Calculate เพื่อบันทึกแต่ละช่อง

ควรตรวจค่าที่เคยกรอกในรุ่นก่อนอีกครั้ง เพราะยืนยันได้ว่าบาง commit อาจไม่ถูกเก็บ รุ่นนี้ไม่ได้เติมค่าที่เคยหายหรือสมมติค่าที่ผู้ใช้ยังไม่ทราบ

สูตรกำลัง ULS/SLS, raw CSiBridge forces และ schema ของ Project JSON ไม่เปลี่ยนแปลง การแก้ไขนี้ไม่เพิ่ม Tn หรือ composite V–T resistance

## Repo summary

```text
EDIT33: Fix lost second-cell edits and collapsing dowel details; preserve editor state, re-entry inputs and safe model reloads.
```
