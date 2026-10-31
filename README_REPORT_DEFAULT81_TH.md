# REPORT.DEFAULT81

รุ่นนี้พัฒนาต่อจาก concrete-section-pro_REPORT-BG40-80.zip
ให้รายงาน I-girder แบบ BG40 R10 เป็นรายงานมาตรฐานที่ผู้ใช้พบก่อนใน Report / QA

## ใช้งาน

1. ตั้งค่าโครงการและคำนวณผลที่ต้องใช้ในหน้า Analysis ตามขั้นตอนเดิม
2. เปิด Report / QA แล้วกด Create complete Word report
3. กด Download complete Word report (.docx)

ไม่ต้องเลือก Include figures, appendices, terminology, registries หรือ Max table rows
แม้ session เก่าเคยปิดตัวเลือกเหล่านี้ รายงานมาตรฐานก็รวมข้อมูลให้อัตโนมัติ
ชื่อโครงการ ผู้จัดทำ ผู้ตรวจ revision และวันที่ถูกนำมาใช้เป็นค่าเริ่มต้น
หากต้องการแก้ข้อความรายงาน ให้เปิด Report details — optional

## รายงานมาตรฐาน

ใช้แม่แบบ Word ที่สกัดจาก BG40_Final_Complete_R10.docx เดิม
คง styles, theme, ฟอนต์ ระยะขอบ หัวและท้ายกระดาษ ลำดับบท และเลขหน้า
รายงานมี 10 บท พร้อมสมการ Word ที่แก้ไขได้ การแทนค่า ผลตรวจ ตาราง หน้าตัด
กราฟแรง กราฟกำลัง/อัตราส่วน กราฟ stress และ deflection ตามข้อมูลที่มีจริง
รวมภาคผนวกและ figure register โดยไม่ต้องเลือกเพิ่ม

นำการจัดภาพสำหรับพิมพ์ที่เคยทำเพิ่มในตัวอย่างเข้าไปอยู่ในตัว Export แล้ว:

- ย้ายคำอธิบายยาวของกราฟ ULS มาเป็นคำบรรยาย Word ที่อ่านได้
- ย้ายค่าตรวจสอบใต้รูปหน้าตัดจุดควบคุมเป็นข้อความ Word เพื่อไม่ทับ legend
- จัดระยะและคำอธิบายแนว debonding ให้ไม่ชน station ticks
- วางพื้นที่คอนกรีตหลังสัญลักษณ์เหล็กพื้น และจัด legend ให้พอดีหน้ากระดาษ
- แสดงข้อความอธิบายที่มี from/in แยกจากสมการ เพื่อไม่ให้ PDF converter ตีความเป็นคำสั่งคณิตศาสตร์
- ไม่สร้างหน้าว่างจากคำอธิบายท้าย figure register
- แสดง missing labels แทนข้อความ nan และจัดหัวตารางให้อยู่กับข้อมูลแถวแรก

Report preview ใช้เปิดตรวจเท่านั้น การเลือกบท/รูปเพื่อดูตัวอย่างไม่เปลี่ยนเนื้อหาที่ส่งออก
Download report and source evidence (.zip) เป็นไฟล์เสริมที่เปิดได้ในหัวข้อแยก
ภายในเก็บ Word เดียวกัน ตารางเต็ม source register และรูปที่ฝังจริง

## สถานะและข้อผิดพลาด

รายงานใช้ input และ stored results ปัจจุบัน ไม่คัดลอกตัวเลขออกแบบจากเอกสาร BG40
ไม่คำนวณ ULS/SLS ซ้ำจากหน้า Report และไม่สร้างผลให้ checks ที่ยังไม่ได้คำนวณ
FAIL, REVIEW, SOURCE BLOCKED, NOT CALCULATED และ STALE ยังคงแสดงตามข้อมูลจริง

หากรูปที่ควรมีสร้างหรือฝังไม่สำเร็จ แอปแจ้งข้อผิดพลาดและไม่เสนอไฟล์นั้นเป็น complete report
เมื่อ input, stored result หรือข้อมูลรายงานเปลี่ยน ปุ่มดาวน์โหลดไฟล์เดิมจะถูกซ่อน
จนกดสร้างรายงานใหม่ ปุ่ม Build Draft Word Report แบบเก่าไม่แสดงใน workflow I-girder นี้

## Verification

218 targeted and regression tests passed in two non-overlapping suites.
ครอบคลุม Word structure, source fidelity, read-only behavior, stale bindings,
metadata, default content, renderer failure, Streamlit build/download widgets,
report foundation, report QA, Crossbeam, Railway U-girder และ sidebar project tools

ทดสอบปุ่มจริงผ่าน Streamlit AppTest ด้วย calculated sample state เดียวกับตัวอย่างเดิม
ใช้ Kaleido จริง ไม่แทนตัวสร้างรูป และไม่แก้เอกสารหลัง Export
ไฟล์ payload ที่ส่งให้ปุ่มดาวน์โหลดตรงกับ complete artifact ทุกไบต์
ได้ 10 บท 58 รูป สมการ Word 219 รายการ และตาราง 79 ตาราง
จำนวนนี้เป็นของชุดตัวอย่างเท่านั้น โครงการจริงขึ้นกับข้อมูลและ checks ที่คำนวณไว้
styles.xml และ theme ของแม่แบบเดิมไม่เปลี่ยน

ผลตรวจทางวิศวกรรมของชุดตัวอย่างเป็น FAIL และยังคง FAIL ในรายงาน
การทดสอบนี้ยืนยันระบบรายงาน ไม่ใช่การรับรองความปลอดภัยของแบบตัวอย่าง

## ขอบเขต

ค่าเริ่มต้น BG40 นี้ใช้กับ parametric I-girder ตามขอบเขตของรุ่น 80
workflow อื่นใช้รายงานของตนตามเดิม
No engineering equations changed. No ULS/SLS calculation logic changed.
No Project JSON behavior changed. No result-cache persistence added.

อัปเดต source repository ของ Streamlit ด้วยไฟล์ใน ZIP แล้วเริ่มแอปใหม่
ใช้ requirements.txt ที่มากับรุ่นนี้และรัน streamlit run app.py
การนำ ZIP ไปใช้เป็นขั้นตอนที่ทำให้เว็บออนไลน์เปลี่ยนเป็นรุ่นนี้
