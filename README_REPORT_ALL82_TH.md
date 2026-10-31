# REPORT.ALL82

พัฒนาต่อจาก concrete-section-pro_REPORT-DEFAULT81.zip (SHA256 da283e06ec27fe43dc4f46e3f94d336356aaa13a224fac282a7d38d73ca5635d)

## รูปแบบรายงานร่วมกัน

ทุก workflow ใช้แม่แบบ Word จาก BG40_Final_Complete_R10.docx เดิม โดยคง styles, theme, ขนาดหน้า ระยะขอบ header และลักษณะตาราง/สมการไว้ ชื่อ workflow และเนื้อหาบทเปลี่ยนตามผลคำนวณของสมาชิกนั้น ไม่ยกสมการ I-girder ไปใช้กับเสาหรือ Crossbeam

รองรับ Column/Pier/Wall/Pylon PMM และ V+T, Building Beam/Girder, Bridge Beam/Girder, Railway U-Girder, Precast I-Girder และ Portal Frame Crossbeam ทั้ง Cast-in-Place และ Precast Segmental

## วิธีใช้งาน

1. คำนวณ checks ที่ต้องการในหน้า Analysis ตามปกติ
2. เปิด Report / QA แล้วกด Create complete Word report
3. กด Download complete Word report (.docx)

ไม่ต้องติ๊กเลือกบท สมการ กราฟ หรือภาคผนวก รายงานรวมข้อมูลที่มีให้อัตโนมัติ และมี Source evidence ZIP เป็นตัวเลือกดาวน์โหลดเพิ่มเติม ส่วนข้อมูลโครงการและ preview ยุบไว้เพื่อลดความรก

## ข้อมูลและขอบเขต

รายงานใช้ stored Analysis results เท่านั้น ไม่รัน solver เพื่อเติมผลที่ขาด ไม่คัดลอกตัวเลขออกแบบจาก BG40 และไม่สร้าง Vmax–Tmax vector ใหม่จากคนละ case

PMM แสดง point cloud และ D/C จากผลเดิม Beam/Girder แสดง resistance/utilization แยก case Crossbeam ใช้กราฟ production เดิมที่รักษา physical joints และ section faces พร้อมแยก Transfer/Final Service และ camber/deflection ตาม source stage

ตารางยาวซ้ำ case และ station/direction/fiber ในทุก panel เพื่อรักษาตัวตนของแถว ข้อมูลเต็มความละเอียดคงอยู่ใน CSV และ stored-result snapshot ของ source ZIP

ผล FAIL, SOURCE BLOCKED, REVIEW, STALE และ NOT CALCULATED ยังคงแสดงตามข้อมูลจริง การได้ไฟล์ Word ครบรูปแบบไม่ได้หมายความว่า checks ที่ยังไม่คำนวณหรือขอบเขตที่ยังไม่รับรองผ่านแล้ว

ตรวจ fingerprint ของ Beam ULS และ Crossbeam ตาม source package รวมถึง PMM/SLS binding ที่มีอยู่ ผลเก่าที่ตรวจพบว่าไม่ตรงกับ inputs ถูกตัดออกจากผลปัจจุบัน ผล legacy ที่ไม่มี binding ระบุให้ตรวจสอบ ไม่อ้างว่ารับรองความเป็นปัจจุบัน

Recorded prestress-loss tables ที่ไม่มี binding เป็นหลักฐานให้ review; diagnostic/debug และ time-step QA ที่ final adoption ยังถูก block ไม่ใช้รับรองการออกแบบ รายละเอียดรอยต่อ แรงยึดเหนี่ยว seismic detailing, D-region และ full punching acceptance ยังคงตาม scope ของ Analysis เดิม

## การติดตั้ง

นำโค้ดจากโฟลเดอร์ concrete-section-pro ใน ZIP ไปอัปเดต repository ที่ Streamlit ใช้งาน แล้วให้แอป deploy/reboot ตามขั้นตอนเดิม ใช้ requirements.txt ที่ให้มา ไฟล์ ZIP นี้ไม่เปลี่ยนแอปบน live URL จนกว่า repository จะได้รับการอัปเดต

## สิ่งที่ตรวจสอบ

ดู RELEASE_REPORT_ALL82.json และ qa/evidence/report_all82 สำหรับผล pytest และหลักฐานทดสอบปุ่มดาวน์โหลดจริงผ่าน Streamlit AppTest พร้อม static renderer ตัวจริง ตัวอย่างใช้ข้อมูลสมมติที่คำนวณผ่าน production kernels และคงสถานะจริงทั้งหมด

ไม่มีการแก้สมการหรือ solver ULS/SLS/PMM ไม่มีการเปลี่ยน Project JSON และไม่เพิ่ม result-cache persistence
