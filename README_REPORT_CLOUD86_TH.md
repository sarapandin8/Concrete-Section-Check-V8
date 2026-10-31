# REPORT.CLOUD86 — ลด RAM ก่อนเริ่มสร้าง Word

รุ่นนี้แก้ขั้นเตรียมข้อมูลรายงาน ต่อจาก REPORT.CLOUD85 / GitHub commit `5a81a5d4351719f901077552e11a83aae7f2c2ee`

## หลักฐานจาก Cloud log

Log ที่ได้รับใช้ Python 3.12.16, Streamlit 1.61.0 และ REPORT.CLOUD85 แล้ว จึงไม่ต้องเปลี่ยน Python หรือ delete/redeploy เพื่อแก้เวอร์ชันอีก

เมื่อเริ่ม Create Report วันที่ 1 พฤศจิกายน 2026 เวลา 03:46:14 ประเทศไทย:

- App RSS 993.8 MiB; container ใช้ 1,984 จาก 3,072 MiB; เหลือ 1,088 MiB
- ข้อความสุดท้ายอยู่ที่ 2% `Reading stored Analysis results` ก่อนเข้า Word builder และ static renderer
- Health check ภายหลังพบ connection reset ไม่มี traceback และไม่มี kernel OOM event ใน log ที่ส่งมา

จึงยังยืนยันไม่ได้ว่า Cloud ฆ่า process เพราะ OOM แต่สอดคล้องกับปัญหาทรัพยากรตามคำแนะนำ Streamlit และพบการขยายข้อมูลในขั้นนี้ที่ทดสอบซ้ำได้จริง

## สิ่งที่แก้

รุ่นก่อนอ่านทุก cell ผ่าน DataFrame.to_dict('records') แล้วสร้างสำเนา plain data ทั้งต้นไม้เพื่อคำนวณ signature; dataclass ยังถูก asdict ทำ deep copy ก่อนอีกชั้น ตาราง native shell และผลที่เก็บหลายชุดจึงขยาย RAM มาก แม้ยังไม่ได้เริ่มเขียน Word

- สร้าง signature โดยอ่าน DataFrame ทีละ record และอ่าน dataclass โดยไม่ deep copy ตาราง ใช้ลำดับและค่าของ JSON แบบเดิม
- คงการตรวจทุกช่องข้อมูล รวมถึงช่องสุดท้าย ไม่ลดแถว ไม่ใช้ repr แบบตัดข้อมูล และไม่ละเว้นผลลัพธ์จากการตรวจ STALE
- ตารางสำหรับรายงานอ่านผ่าน shallow views ของข้อมูลเดิม; metadata ของตารางแยกจากต้นทาง ใช้เฉพาะ synchronous read-only export
- JSON หลักฐาน input/result เขียนทีละส่วน พร้อมคงข้อมูลและรูปแบบ JSON เดิม
- เพิ่ม progress และการตรวจ headroom ระหว่างรวบรวม ULS, SLS, deflection, slab และอ่าน source records; callback อยู่ใน export context และถูกยกเลิกเมื่อออกจาก context
- ไม่มีการเพิ่ม cache ข้ามผู้ใช้หรือเก็บผล analysis ใน Project JSON

## ผลวัดและทดสอบ

ทดสอบ source signature ด้วยข้อมูลจำลองสองตาราง ตารางละ 100,000 แถว × 32 คอลัมน์ รวม 6.4 ล้านช่อง:

| รายการ | CLOUD85 | CLOUD86 |
|---|---:|---:|
| Peak RSS ของ process | 704.77 MiB | 227.00 MiB |
| Peak RSS ก่อนตรวจข้อมูล | 190.33 MiB | 189.17 MiB |
| เวลาเฉพาะ source signature | 18.935 s | 17.927 s |

Peak ลด 67.8% และ SHA-256 ของข้อมูลทั้งหมดตรงกัน ตัวเลขนี้เป็น benchmark จำลองของขั้นตรวจข้อมูล ไม่ใช่เวลาสร้างรายงานทั้งเล่มหรือโครงการจริงที่ล้มเหลว

ทดสอบ report regression 217 ข้อผ่าน มี pandas concat FutureWarnings เดิม 6 รายการ; py_compile app.py และโมดูลที่แก้ผ่าน ไม่ใช่การรันทุก test ใน repository

ทดสอบปุ่ม Create Report จริงด้วย AppTest, native Kaleido และจับ bytes ของ download จริง ครบ 7 กรณี:

| Workflow | รูป | Native equations | สถานะวิศวกรรมที่คงไว้ |
|---|---:|---:|---|
| I-girder | 58 | 219 | FAIL |
| Bridge beam | 6 | 40 | FAIL |
| Building beam | 6 | 43 | FAIL |
| Column | 5 | 32 | REVIEW |
| Crossbeam CIP | 13 | 18 | REVIEW |
| Crossbeam segmental | 11 | 12 | FAIL |
| Railway U-girder | 7 | 45 | FAIL |

รวม 106 รูป / 409 สมการ ปิด solver ในขณะทดสอบ export; ไม่มี checkbox เลือกเนื้อหา; เปิด Report/QA ซ้ำ 3 ครั้งต่อกรณีไม่สร้าง Word/PNG ใหม่; ไม่เหลือ renderer child process

I-girder ตัวอย่างใช้ประมาณ 20.7 วินาทีบนเครื่องทดสอบ ไม่รับประกันเวลาบน Cloud ส่วนประกอบ Word ตรงกับรุ่น 85 ทั้งหมด (document.xml เทียบ canonical XML) และ source CSV/JSON ทั้ง 87 รายการตรงทุกไบต์ รูปแบบ BG40 R10 จึงคงเดิม

## นำขึ้นใช้งาน

สถานะการส่งมอบ: ชุดแก้ไขผ่านการทดสอบในเครื่อง แต่ยังไม่ได้บันทึกบน GitHub หรือ deploy เว็บจริง เพราะ GitHub integration ตอบ 403 Resource not accessible by integration ขณะสร้าง tree ไม่มีการแก้ branch main

ใช้ `concrete-section-pro_REPORT-CLOUD86-PATCH.zip` สำหรับอัปเดตจาก CLOUD85: แตก ZIP แล้วนำไฟล์และโฟลเดอร์ข้างในวางทับที่ root ของ repository เดิมซึ่งมี app.py อยู่ ห้ามอัปโหลดตัว ZIP หรือสร้างโฟลเดอร์ project ซ้อนอีกชั้น PATCH มีเฉพาะไฟล์ที่แก้/เพิ่ม และไม่เปลี่ยน app.py หรือ requirements.txt

บน GitHub เปิด repository → Add file → Upload files → ลากไฟล์และโฟลเดอร์ภายใน PATCH → Commit changes ไปที่ main; ชุด `concrete-section-pro_REPORT-CLOUD86.zip` เป็น source ทั้งโครงการสำหรับผู้ที่ต้องการชุดเต็ม

อัปเดต source files ใน repository ที่ Streamlit deploy อยู่ ระบบตรวจการเปลี่ยนแปลงจาก GitHub อัตโนมัติ ไม่ต้องเปลี่ยน requirements หรือ Python สำหรับรุ่นนี้

ตรวจ caption หน้า Report/QA ว่าเป็น `REPORT.CLOUD86` ก่อนทดสอบ ถ้า Cloud ยังติดหน้า error ให้สำรอง Project JSON แล้ว Reboot app เพื่อเริ่ม session ใหม่ โหลด input และรัน Analysis ตามปกติ จากนั้นกด Create complete Word report

ถ้ายังหยุด ให้ดาวน์โหลด Cloud log รอบใหม่ ข้อความ progress ในรุ่นนี้จะแสดงขั้นที่หยุดละเอียดขึ้น การยืนยันกับ project จริงยังจำเป็น เพราะรอบนี้ได้รับ log แต่ไม่ได้รับ Project JSON/runtime ของงานที่ล้มเหลว

## คำแนะนำ Streamlit ที่ใช้

- [Resource limits](https://docs.streamlit.io/knowledge-base/deploy/resource-limits): profile memory; reboot เป็นวิธีชั่วคราว
- [Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app): ตรวจ Cloud logs เมื่อขึ้น Oh no; การอัปเดต GitHub ส่งต่อไปแอป
- [Caching](https://docs.streamlit.io/develop/concepts/architecture/caching): การ serialize/copy ข้อมูลใหญ่มีต้นทุน; ไม่ใส่ st.cache_resource ครอบ state ผู้ใช้ที่เปลี่ยนแปลงได้

## Repo summary

```text
REPORT.CLOUD86: Stream complete report source fingerprints and JSON evidence without eager DataFrame records or dataclass deep copies; share read-only table storage and log preparation checkpoints. Preserve BG40 R10 Word content, source signatures, all figures/equations, and engineering status gates.
```

No engineering equations changed. No ULS/SLS calculation logic changed. No Project JSON behavior changed. No result-cache persistence added.

รายละเอียดเครื่องมือทดสอบและผลวัดอยู่ใน REPORT_CLOUD86_VERIFICATION.json; สคริปต์ทำซ้ำคือ qa/report_source86_benchmark.py และ qa/report_cloud86_ui_export.py
