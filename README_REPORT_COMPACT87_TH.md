# REPORT.COMPACT87

แก้การตรวจข้อมูลต้นทางที่ช้า และทำรายงาน Word แบบกระชับเป็นค่าเริ่มต้นสำหรับทุก workflow

## สิ่งที่พบจาก log

ชุด REPORT.CLOUD86 อยู่ที่ 8% นานกว่า 934 วินาที ในขั้น Verifying complete source data without copying result tables โดยท้าย log ยังมี RAM เหลือ 1,139.7 MiB และ Python เป็น 3.12.16 อยู่แล้ว หลักฐานรอบนี้จึงชี้ไปที่การตรวจข้อมูลต้นทางก่อนสร้าง Word ไม่ใช่ข้อสรุปว่า Word มีหน้ามากเกินไปหรือ Python ผิดเวอร์ชัน

## สิ่งที่แก้

- เปลี่ยน fingerprint จาก JSON ทีละเซลล์เป็น SHA256 ของข้อมูลครบทุกเซลล์แบบแบ่งบล็อก รวมชนิดข้อมูล ดัชนี และชื่อคอลัมน์ ไม่สุ่มข้อมูลและไม่ตัดแถว การแก้เซลล์สุดท้ายยังทำให้รายงานเดิมเป็น STALE
- ตรวจวัตถุตารางที่ถูกอ้างอิงซ้ำเพียงครั้งเดียวภายในการตรวจหนึ่งรอบ ยกเลิก memo เมื่อจบรอบ จึงไม่ใช้ hash เก่ากับข้อมูลที่ถูกแก้ในตำแหน่งเดิม
- ปุ่ม Create Word report สร้างเฉพาะ Word โดยอัตโนมัติ ไม่รอสร้าง ZIP ของข้อมูลดิบทั้งหมด ผู้ใช้ไม่ต้องเลือกเนื้อหารายงาน
- คงบท สูตร การแทนค่า ผลลัพธ์ และกราฟที่มีใน Analysis ทั้งหมด ตารางผลยาวแสดงแถวควบคุมแยกกรณีโหลด ขั้นตอน และสถานะ พร้อมจำนวนแถวต้นทาง ไม่ผสมแรงจากคนละแถวเป็นชุดแรงใหม่
- เปลี่ยนตาราง Parameter/Value เป็นข้อความกระชับโดยเก็บทุกค่า รวมแถวเหล็กเสริมที่มีคุณสมบัติเหมือนกันโดยแสดงหมายเลขเหล็กครบ ลดช่องว่างระหว่างบทและจัดกราฟพื้น/การโก่งตัวให้กะทัดรัดขึ้น
- คง Word styles, theme, ขนาดกระดาษ และหัวกระดาษ BG40 R10 เดิม ปรับการแบ่งหน้าและการนำเสนอเนื้อหาสำหรับฉบับกระชับ
- คง FAIL, REVIEW, STALE, missing checks, source coupling และข้อจำกัดเดิม ไม่แก้สมการหรือ solver ทางวิศวกรรม ไม่เพิ่มการบันทึก result cache ใน Project JSON
- ข้อมูลดิบครบยังเรียกได้ใน Additional download — source evidence → Prepare source evidence ขั้นนี้เป็นทางเลือกและอาจใช้เวลาตามขนาดข้อมูล

## ผลทดสอบ

- Targeted report/regression tests 228 ผ่าน มี pandas FutureWarning เดิม 6 รายการ ไม่ใช่การรันทุก test ใน repository
- ทดสอบปุ่มสร้างและ payload ที่ดาวน์โหลดจริงทั้ง 7 workflow ด้วย renderer จริง รวม 106 รูป และ 409 สมการ Word; ปิด solver ระหว่างทดสอบ Report
- เปิดหน้า Report ซ้ำ 3 ครั้งต่อ workflow โดยไม่สร้าง Word หรือกราฟใหม่ ทดสอบการเตรียม source ZIP แยกภายหลังด้วย workflow เสา
- ตัวอย่าง I-Girder: 58 รูป 219 สมการ ตาราง Word ลดจาก 79 เป็น 56; ฉบับที่จัดหน้าใหม่ประมาณ 64 หน้า ทั้งหมดเป็นข้อมูลตัวอย่าง ไม่ใช่ข้อมูลโครงการจริงของผู้ใช้
- Benchmark แหล่งข้อมูล 100,000 แถว × 32 คอลัมน์ อ้างอิงสองตำแหน่ง: CLOUD86 เดิม 17.927 วินาที; COMPACT87 ประมาณ 1.07 วินาที
- Benchmark 1,000,000 แถว × 32 คอลัมน์ อ้างอิงสองตำแหน่ง: ประมาณ 1.35 วินาที ทั้งสอง benchmark ใช้ตารางร่วมหนึ่งวัตถุ จึงมี 3.2 และ 32 ล้านเซลล์ที่แตกต่างกันตามลำดับ
- เวลาสร้าง Word ตัวอย่าง I-Girder ในเครื่องทดสอบประมาณ 16–19 วินาที ไม่ใช่การรับประกันเวลาบน Streamlit Cloud; ยังไม่มี runtime state ของโครงการที่เกิดปัญหาให้ทดสอบซ้ำโดยตรง
- ตรวจ syntax ด้วย py_compile และ render Word เพื่อตรวจตาราง สมการ กราฟ legend และ caption

## วิธีอัปเดต

1. ใช้ PATCH กับ repository ที่เป็น REPORT.CLOUD86 หรือใช้ ZIP เต็มเมื่อไม่แน่ใจว่าไฟล์เดิมครบหรือไม่
2. แตก ZIP แล้ววางไฟล์ตามโครงสร้างเดิมใน repository sarapandin8/Concrete-Section-Check-V8; app.py ต้องอยู่ที่ root เดิม ห้ามอัปโหลด ZIP เพียงไฟล์เดียวแทนการแตกไฟล์
3. Commit/push ไป branch ที่ Streamlit ใช้ deploy แล้วรออัปเดตโค้ด จากนั้นเปิด Report/QA และตรวจว่ามีข้อความ REPORT.COMPACT87
4. โหลดโครงการและรัน Analysis ที่ต้องการตามปกติ แล้วกด Create Word report เพียงครั้งเดียว

ชุดนี้ไม่ได้แก้ dependency หรือบังคับเปลี่ยน Python ข้อมูล log ล่าสุดเป็น 3.12.16 แล้ว และยังไม่ได้ push/deploy เว็บจริงจากเซสชันนี้ การเชื่อมต่อ GitHub ที่ใช้ก่อนหน้านี้ปฏิเสธการเขียนด้วย HTTP 403 จึงส่งมอบเป็นชุดไฟล์พร้อมอัปเดต

คู่มือ Streamlit ระบุว่า Community Cloud ติดตาม commit ใน repository และอัปเดตแอปอัตโนมัติ:
https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/edit-your-app

## Repo summary

Speed up full-source verification and make compact BG40 Word reports the default while preserving all calculations, figures, and engineering status gates.

Baseline: concrete-section-pro_REPORT-CLOUD86.zip

Baseline SHA256: 04ef13af8af092e4f8137f000d24d0c0df5b43fe61db86748bbceed51f45db9d

ขนาด ZIP, SHA256, รายการไฟล์เปลี่ยน และผลทดสอบแยก workflow อยู่ใน REPORT_COMPACT87_VERIFICATION.json ที่ส่งมอบคู่กัน
