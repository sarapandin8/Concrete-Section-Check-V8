# REPORT.EXPORT84 — แก้ขั้นตอน Create complete Word report

ต่อจาก concrete-section-pro_REPORT-RUNTIME83.zip (SHA-256 012f9ef945c5f539abf97de1ca86f4c1e2f7f1524178b9c6ef5fff1abe330196)

รุ่น RUNTIME83 ลดภาระตอนเปิดหน้า Report / QA ส่วนรุ่นนี้แก้ขั้นตอนสร้างรายงานหลังคลิก Create complete Word report ตามภาพล่าสุด

## สิ่งที่ตรวจพบและแก้ไข

ภาพแสดง CONNECTING ระหว่างสร้างรายงาน แต่ไม่มี traceback ใหม่ จึงยังยืนยันสาเหตุที่ process บน Cloud หลุดไม่ได้ ไม่ได้สรุปว่าเป็น OOM หรือข้อผิดพลาดของ dependency จากภาพอย่างเดียว

โค้ดเดิมเริ่ม Python และ Kaleido/Chromium ใหม่ทุกภาพ และโหลด Word ทั้งเล่มกลับเข้าหน่วยความจำอีกครั้งเพื่อดึงภาพเข้า evidence ZIP รุ่นนี้แก้ดังนี้:

- ใช้ตัวแปลงกราฟร่วมกันเป็นชุด สูงสุด 8 รูปต่อ process แล้วปิดและเริ่มชุดถัดไป เพื่อลด cold starts และจำกัดการสะสม allocation ของ Chromium มี renderer ทำงานพร้อมกันเพียงชุดเดียวต่อ process แอป
- แยก worker พร้อม process group ของตนเอง ปิดทั้งกลุ่มเมื่อจบ หมดเวลา หรือยกเลิก รวมถึงกรณี process แม่จบแต่ลูกยังค้างอยู่บน Linux
- ครอบคลุมทั้งการส่งข้อมูลเข้า pipe และการรอผลด้วย timeout เดียว ไม่ปล่อยการส่งข้อมูลเข้าตัวแปลงที่ค้างรอโดยไม่มีกำหนด
- ถ้ารูปที่จำเป็นสร้างไม่ได้ หยุดทันทีพร้อมหมายเลข ชื่อรูป และรายละเอียดข้อผิดพลาด ไม่รอ timeout ซ้ำจนครบทุกรูป และไม่เสนอไฟล์ที่รูปไม่ครบเป็น complete report
- แสดง progress ระหว่างอ่านผล เขียนบท สร้างรูป บันทึก Word และจัด evidence พร้อมบันทึกขั้นตอนลง log
- จัด CSV/JSON และรูปใน evidence แบบ streaming ดึงภาพจาก DOCX ZIP โดยตรง ไม่สร้าง Word object ทั้งเล่มซ้ำ คงข้อมูลทุกแถวและ precision เดิม
- กันการสร้างรายงานหนักพร้อมกันหลาย session ใน process เดียว หากมีรายงานอื่นกำลังสร้าง จะแจ้งให้ลองใหม่หลังงานนั้นเสร็จ

## เนื้อหาและรูปแบบรายงาน

ยังสร้างรายงานครบเป็นค่าเริ่มต้นด้วยการกดครั้งเดียว ไม่มีตัวเลือกเนื้อหาเพิ่ม ใช้ Word แม่แบบ BG40 R10 เดิมทุก workflow พร้อมรูป สมการ และภาคผนวก

เทียบตัวอย่าง I-girder ที่คำนวณไว้เดียวกันระหว่าง RUNTIME83 กับ EXPORT84: ทุก part ภายใน DOCX รวม 76 parts เหมือนกันทุก byte ทั้ง document XML, styles, theme และภาพทั้ง 58 รูป ข้อมูล CSV/JSON/PNG ใน evidence ตรงกันทุก entry ที่เกี่ยวข้อง ตัว ZIP/DOCX ทั้งไฟล์อาจมี byte ต่างกันจากเวลาใน ZIP headers โดยไม่เปลี่ยนเนื้อหา

ไม่แก้ engineering solvers, ผล Analysis, สถานะ FAIL/REVIEW/STALE, Project JSON, dependency versions หรือเพิ่ม result-cache persistence หมายเลขรูปแบบเนื้อหาในเอกสารยังเป็น REPORT.ALL82 เพราะแก้เฉพาะ runtime ของ export

## ผลทดสอบ

กดปุ่มจริงผ่าน Streamlit AppTest ใช้ native Kaleido และตรวจ exact download bytes โดยบล็อก solver ระหว่าง export ผ่านครบ 7 workflow:

| Workflow | รูปใน Word | สมการ Word | สถานะที่คงไว้ |
|---|---:|---:|---|
| I-girder | 58 | 219 | FAIL |
| Bridge beam | 6 | 40 | FAIL |
| Building beam | 6 | 43 | FAIL |
| Column | 5 | 32 | REVIEW |
| Crossbeam CIP | 13 | 18 | REVIEW |
| Crossbeam segmental | 11 | 12 | FAIL |
| Railway U-girder | 7 | 45 | FAIL |
| รวม | 106 | 409 | คงตามผลต้นทาง |

ทุก workflow เปิดหน้าซ้ำอีก 3 ครั้งโดยไม่สร้าง Word/PNG ใหม่ ไม่มี process ลูกที่ยังทำงานเหลือหลัง export และไม่มี content-selection checkbox

ตัวอย่าง I-girder เดียวกันบนเครื่องทดสอบ:

| การวัด | RUNTIME83 | EXPORT84 |
|---|---:|---:|
| เวลาตั้งแต่กด Create จนแสดง download | 64.577 s | 22.607 s |
| Peak RSS รวม app และ native descendants | 689.92 MiB | 638.44 MiB |
| การเริ่ม renderer worker | 58 ครั้งตามโค้ดเดิม | 8 ครั้งตามขนาดชุด |

ตัวเลขเป็นการวัดเฉพาะตัวอย่างนี้ ไม่ใช่ข้อกำหนดทรัพยากรสำหรับทุกโครงการ วัด Linux process tree ทุก 50 ms โดยผลรวม RSS นับ shared pages ซ้ำได้ ไม่ใช่ PSS/USS หรือการวัดบน Streamlit Cloud โดยตรง

ผ่าน regression tests 199 ข้อ (6 pandas FutureWarnings) ครอบคลุมการรักษาเนื้อหาครบ การใช้ renderer ร่วมและ recycle โดยไม่ซ้อนกัน timeout ที่มี process ลูกค้าง การยกเลิกแล้วเริ่มรายงานใหม่ การหยุดที่รูปแรกเมื่อผิดพลาด progress และความเท่ากันของ evidence ดูจำนวนและผลจริงใน RELEASE_REPORT_EXPORT84.json / REPORT_EXPORT84_VERIFICATION.json

เครื่องทดสอบใช้ Python 3.12.14, pandas 2.2.3, Streamlit 1.61.0, Plotly 5.24.1, Kaleido 0.2.1 และ python-docx 1.2.0 ส่วน log Cloud ก่อนหน้าใช้ Python 3.14.10 และ pandas 3.1.0 จึงยังต้องยืนยันการใช้งานกับ project จริงหลังอัปเดต Cloud โดยไม่อ้างว่าพิสูจน์สาเหตุการหลุดได้แล้ว

## ติดตั้ง

นำไฟล์ภายในโฟลเดอร์ concrete-section-pro ของ ZIP ไปอัปเดต repository ที่ Streamlit ใช้งานให้ครบ รวมไฟล์ใหม่ concrete_pmm_pro/reporting/static_image_worker.py แล้ว Reboot app จาก Manage app

หลังเปิดใหม่ โหลด Project JSON และทำ Analysis ตามขั้นตอนเดิม จากนั้นเปิด Report / QA และกด Create complete Word report จะมีแถบความคืบหน้าระบุขั้นตอนและรูปที่กำลังสร้าง เมื่อสำเร็จจะแสดงปุ่ม Download complete Word report โดยอัตโนมัติ

แพ็กเกจนี้ยังไม่ได้ deploy/reboot live app ให้ ผล Analysis ใน session ต้องคำนวณใหม่หลัง reboot ตามพฤติกรรมเดิม

## English repository summary

```text
REPORT.EXPORT84: Stabilize complete Word report creation with bounded, reusable
Kaleido worker batches, process-tree cleanup, per-figure progress and fail-fast
errors. Stream evidence CSV/JSON/images without reopening the full Word DOM.
Preserve the complete BG40 R10 document, source values and engineering statuses.
```
