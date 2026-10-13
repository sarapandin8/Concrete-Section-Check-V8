# IGIRDER.IMPORTSIMPLE21 — Simple ULS load import

ฐาน: concrete-section-pro_IGIRDER-SOURCECONFIRM20.zip
Baseline SHA-256: 29b88e5d201b1044c6e3e09bb64e739b401f7cf5ec9c427c23f3147aa5a024c1

## วิธีใช้
หน้าปกติเหลือ 3 ขั้นตอน:
1. เลือกไฟล์ Excel/CSV จาก CSiBridge
2. Force source: เลือก CSI Correspondence สำหรับชุดแรงพร้อมกันจาก moving-load correspondence,
   Static case / explicit step สำหรับชุดแรงของ static case/step เดียว หรือ Envelope / unverified
   สำหรับขอบเขตแรงที่ยังไม่ยืนยันการเกิดพร้อมกัน
3. กด Import loads แล้วไป Analysis → Calculate Shear + Torsion

ปุ่ม Import loads ใช้ไฟล์ที่เลือกแทนชุดโหลดเดิม แอปแยก girder, case, Max/Min,
Before/After และคงแรงทั้งหกองค์ประกอบตามข้อมูลเดิม ไม่ต้องพิมพ์ Source basis
และไม่ต้องติ๊กยืนยันชื่อคาน, concurrency, และ CSI P ซ้ำหลายช่อง

การเลือกประเภทแรงและกดนำเข้าเป็นคำประกาศของวิศวกร แอปบันทึกชนิดและข้อความยืนยันให้เอง
ไม่ใช่การพิสูจน์การตั้งค่า CSI โดยอัตโนมัติ การเลือก Envelope/unverified ยังคงถูกกั้นจาก V+T
การเลือก Static ให้แถว Max/Min ของ moving load ไม่เปลี่ยนแถวเหล่านั้นเป็น concurrent

More import options เก็บการเลือกชีต, ตั้งชื่อคาน, append และการเลือกชนิดแรงต่างกันรายไฟล์
ตัวเลือกปกติใช้ได้กับ native Bridge Object Girder Forces โดยไม่ต้องเปิด Advanced
ไฟล์ที่ต้อง mapping ยังคงมีเส้นทาง mapping ให้ใช้พร้อมปุ่ม Replace/Add เดิม

Imported loads แสดง Rows / Concurrent / Unverified ของแต่ละ girder
ค่าตัวเลือกที่เปลี่ยนยังไม่แก้โหลดที่บันทึกจนกว่าจะกด Import
การกลับหน้าหรือเปิด Advanced ไม่ทับข้อมูลเดิม คำยืนยันอยู่ใน input Project JSON ตามระบบเดิม
แอปจำชนิดแรงสำหรับไฟล์เดิมที่มีชื่อ/hash ตรงกัน ไฟล์ใหม่ไม่รับคำยืนยันจากไฟล์เก่าโดยอัตโนมัติ
ค่า P ยังเป็น raw CSI P ตามกติกานำเข้าเดิม มีคำอธิบายก่อนกด Import
app-column files ต้องใช้กติกาเครื่องหมายเดียวกัน ส่วน metadata เก่าที่มากับไฟล์ยังไม่ถูกเปลี่ยนโดยเดา

## สิ่งที่ปรับ
- แสดงชนิดแรงทั้ง 3 แบบพร้อมกันเป็น radio buttons ในหน้าปกติ ไม่ต้องเปิดเมนูหรือ Advanced เพื่อเลือก Correspondence
- นำ required free text และ checkbox ยืนยันซ้ำออก ใช้การเลือกชนิดและปุ่มนำเข้าเป็นคำประกาศ
- ใช้ explicit Import เพื่อไม่ให้เพียงอัปโหลด/เปลี่ยนตัวเลือกทับโหลดทันที
- ลดตารางซ้ำและข้อความยาวในหน้าปกติ รายละเอียดและ mapping อยู่ใน expander
- ใช้ shell/style เดิม และข้อความ UI ภาษาอังกฤษให้สอดคล้องกับแอป

## Validation
- Scoped engineering/import/report regression: 118 passed ใน 7 modules
- Simple-flow tests บน real Streamlit: 8 passed; มี pytest preload warning 1 รายการ ไม่มี test failure
- Full app.py AppTest: 2 girders / 640 source rows, ไม่มี mandatory free text/checkbox,
  import, navigation, Advanced toggle และ JSON roundtrip; zero exceptions และแรง/Note เดิมครบ
- Browser: เลือกไฟล์จริง เลือก CSI Correspondence กด Import loads และได้ concurrent source;
  1440/1100 px ตรวจภาพล่าสุดแล้ว ไม่มี clipping/overlap/missing glyphs ในส่วนที่แก้;
  zero JavaScript errors. ภาพหน้าจอใช้ตรวจภายในเท่านั้น ไม่รวมใน ZIP
- Compile app.py และโมดูลที่แก้ผ่าน
- ไม่ได้รัน repository test suite ทั้งหมด, ไม่ได้รัน CSiBridge และไม่ได้ deploy
- QA section/reinforcement เป็น hypothetical model สำหรับตรวจ flow ไม่ใช่การรับรองสะพานของผู้ใช้

Changed production file: concrete_pmm_pro/ui/girder_csi_import.py
New tests: tests/test_igird_importsimple21.py
Full app verification: qa/igird_importsimple21_app_verify.py
Evidence: qa/evidence/igird_importsimple21/

No engineering equations changed. No ULS/SLS calculation logic changed.
No result-cache persistence added. Source declaration and import UI behavior changed.

Repo summary: Simplify ULS import to file, force source and Import loads; remove required source text and repeated confirmations while preserving concurrency gates and source metadata.
