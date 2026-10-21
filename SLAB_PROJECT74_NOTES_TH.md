# SLAB.PROJECT74 — เก็บ CSI shell inputs ใน Project JSON

เพิ่มการบันทึกชุดข้อมูลที่ Import & validate แล้วจาก Excel เดิมทั้ง 4 export sets ลง Project JSON โดยอัตโนมัติ เก็บ 11 ตารางที่ importer รองรับ รวม Connectivity - Frame เมื่อมี พร้อมทุกคอลัมน์ในตารางนั้น หน่วย ชื่อไฟล์/ตาราง บันทึกการนำเข้า และ SHA-256 ของไฟล์ต้นทาง

## วิธีใช้

1. เปิดแอปรุ่นนี้ แล้วนำเข้า Excel เดิมทั้ง 4 ชุด กด Import & validate shell data
2. กด Save Project JSON ตามเดิม ข้อมูล shell จะรวมอยู่ในไฟล์ JSON โดยอัตโนมัติ
3. เปิด JSON ที่บันทึกจากรุ่นนี้ หน้า Slab Shell Results จะแสดง Restored from Project JSON พร้อมข้อมูลที่ใช้งานได้ แม้กล่องเลือกไฟล์ Excel จะว่าง
4. ไป Analysis → Slab Reinforcement แล้วกดคำนวณใหม่ได้เลย อัปโหลด Excel อีกครั้งเฉพาะเมื่อจะเปลี่ยนผลวิเคราะห์ต้นทาง

JSON รุ่นเก่าที่ยังไม่มีชุดข้อมูล shell ต้องนำเข้า Excel ครั้งแรกแล้วบันทึก JSON ใหม่ ชุดตารางที่เก็บเป็น parsed input ที่แอปใช้งาน ไม่ใช่สำเนาไบนารีของ workbook หรือ worksheets ที่ importer ไม่ใช้

ไฟล์ที่เพิ่งเลือกใน uploader ยังไม่แทนข้อมูลจนกด Import & validate; Save เก็บชุดที่นำเข้าแล้วล่าสุด กด Clear shell package แล้วบันทึกจะเอาชุดข้อมูลออกจาก JSON ด้วย การเปิดโครงการที่ไม่มีชุดข้อมูล shell จะล้างชุดของโครงการก่อนหน้า

## ความครบถ้วนและประสิทธิภาพ

เก็บข้อมูลด้วย JSON ที่รักษาความละเอียด float แบบ round-trip แล้วบีบอัด gzip/base64 เพื่อลดขนาด ไม่ปัดแรง ไม่สร้าง envelope ใหม่ ไม่เปลี่ยน StepType / StepNum รวมถึงกรณี static ที่ StepType ว่าง

ตอนเปิดไฟล์ ตรวจ schema ความยาวและ SHA-256 ของข้อมูล แล้วตรวจหน่วย required columns ความซ้ำของ record และความเชื่อมโยง parent/element/corner/coordinates ด้วย validator เดิมอีกครั้ง หากข้อมูลเสียหายจะปฏิเสธก่อนเปลี่ยนโครงการที่เปิดอยู่

ชุดตารางที่ไม่เปลี่ยนจะไม่บีบอัดซ้ำทุกครั้งที่ sidebar rerun; ตรวจลายนิ้วมือของข้อมูล หน่วย และ provenance เพื่อให้แก้ไข/เปลี่ยน input แล้วได้ archive ใหม่ ไม่มีผลกำลังหน้าตัด กราฟ หรือรายงานใน archive ใหม่นี้ ผล Slab Reinforcement ต้องคำนวณใหม่หลังเปิด JSON

## ขอบเขต

No engineering equations changed. No ULS/SLS calculation logic changed. Project JSON now includes imported shell input tables. No additional analysis-result cache persistence was added. Shared COLOR73 palette, I-girder/bearing references and existing design exclusions are retained.

ดู SLAB_PROJECT74_VERIFICATION.json และ qa/evidence/slab_project74/ สำหรับผลทดสอบ การเปิดในกระบวนการใหม่ และการเทียบตาราง/ผลคำนวณจริง รายละเอียด 279 tests ใน PRINT72 และ 5 tests ใน COLOR73 เป็นหลักฐานย้อนหลัง ไม่ใช่ยอดทดสอบของ PROJECT74

PROJECT74 ตรวจ targeted tests 64 กรณี และ regression 92 กรณี รวม 156 กรณีผ่านทั้งหมด; compile app.py และไฟล์ที่แก้/เพิ่มผ่าน ใช้ไฟล์จริง 4 ชุด: 127,680 force records (Top Slab 109,824 records) / 11 ตาราง ตรวจครบทุกค่าหลังเปิด JSON และในกระบวนการใหม่ ผลคำนวณ CSV ทั้ง 7 ตารางตรงกับ PRINT72 แบบ byte-for-byte

JSON ตัวอย่างขนาด 25.48 MB รวมข้อมูลโครงการเดิม 15.87 MB; เปิดพร้อม validate/restore ประมาณ 4.88 วินาทีในเครื่องทดสอบ ผลความเร็วขึ้นกับข้อมูลและเครื่องของผู้ใช้
