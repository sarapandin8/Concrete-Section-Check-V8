# IGIRDER.SOURCECONFIRM20 — Preserve saved CSI Correspondence

ฐาน: concrete-section-pro_IGIRDER-VTCONCURRENT19.zip
Baseline SHA-256: fc30ec2eedbbf96a86979e8ac4a5da6102fe934c111fc3412afda40739f5f872

## ปัญหาและสิ่งที่แก้
ทำซ้ำบั๊กได้: เริ่มนำเข้าแบบ Advanced, เลือก CSI Correspondence พร้อมยืนยันและหลักฐาน,
กด Replace แล้วปิด Advanced ทำให้ auto-import นำไฟล์เดิมเข้าซ้ำเป็น ENVELOPE ทับ CONCURRENT 640 แถว

- บันทึก upload signature หลัง explicit Replace/Add เพื่อไม่ให้การปิด Advanced นำเข้าไฟล์เดิมซ้ำ
- ตรวจ original source identity จาก load bank (file SHA, file name, sheet, original row,
  bridge object/girder/case/step/Before-After/occurrence) ก่อน auto-import ทับข้อมูล
  ทำให้บันทึก/โหลด Project JSON แล้วอ่านไฟล์เดิมยังคง source contract และการแก้ไขโหลดเดิม
- ไม่ย้ายคำยืนยันไปไฟล์ใหม่หรือกรณีที่แถวต้นฉบับไม่ครบ
- เพิ่มตาราง Saved force-vector source — used by Analysis ระบุจำนวนแถวพร้อม V+T
  และจำนวน source-blocked จากข้อมูลที่บันทึกแล้วจริง แยกจากค่าตัวเลือกที่ยังไม่กด Replace
- หากเลือก Static/Correspondence แต่ยังไม่ยืนยันหรือไม่มี Source basis จะกด Apply ไม่ได้
  พร้อมข้อความบอกข้อมูลที่ขาด; Envelope/unverified ยังคงนำเข้าได้และถูกกั้นจาก V+T ตามรุ่น19

## วิธีใช้
แทน source tree ด้วย ZIP รุ่น SOURCECONFIRM20 และเปิด Project JSON
หากรุ่นก่อนเคยทับคำยืนยันไปแล้ว ต้องนำเข้าใหม่หนึ่งครั้ง:
1. Upload ไฟล์ CSI เดิม เปิด Advanced import settings
2. Force-vector source = CSI Correspondence ตามข้อมูลจริง
3. ยืนยัน simultaneous factored ULS actions และกรอก Source basis
4. ยืนยันชื่อสมาชิก/ระยะและ raw CSI P sign ตามข้อมูลจริง แล้วกด Replace entire girder collection
5. ตาราง Saved force-vector source ต้องแสดง Concurrent rows ready for V+T ครบ เช่น 320 ต่อ girder
   และ Source-blocked rows = 0
6. ปิด Advanced หรือสลับหน้าได้ แล้วกด Calculate Shear + Torsion ใหม่

คำยืนยันระบุแหล่งแรง ไม่ทำให้คานผ่านกำลังอัตโนมัติ หลักฐานยังต้องตรงกับการส่งออก CSI จริง
และชุดแรงต้องครอบคลุม station/face/load states ที่ต้องตรวจ แอปไม่ได้รัน CSiBridge เอง

## ตรวจสอบ
- Scoped regression: 118 passed ใน 7 modules รวม test gate19, auto-load17,
  native CSI, torsion audit12, reportcharts8 และ sourceconfirm20
- Before/after AppTest: baseline ปิด Advanced แล้ว CONCURRENT 640 -> ENVELOPE 640;
  รุ่นแก้ยังคง CONCURRENT 640
- Full app.py AppTest: explicit commit, ปิด Advanced, Loads/Analysis navigation,
  2 girders / 640 rows, แรง/Case/Note เดิม, source readiness แสดงได้; zero exceptions
- Project JSON roundtrip: คำยืนยันยังอยู่ในแถวโหลด ไม่มี result-cache persistence เพิ่ม
- Real V+T engine: verified native source rows ที่ midspan ผ่าน source gate และคำนวณ
  finite transverse D/C ได้ด้วย hypothetical QA section/reinforcement ไม่ใช่การรับรองสะพานของผู้ใช้
- หน่วย/เครื่องหมาย/สมการ/geometry และ gate V+T รุ่น19 ไม่เปลี่ยน
- Compile app.py และโมดูลนำเข้าผ่าน
- ไม่ได้รันทั้ง repository suite, ไม่ได้รัน CSiBridge หรือ deploy และไม่มี full-page browser screenshot QA

Changed production file: concrete_pmm_pro/ui/girder_csi_import.py
Tests: tests/test_igird_sourceconfirm20.py
Full app verification: qa/igird_sourceconfirm20_app_verify.py
Evidence: qa/evidence/igird_sourceconfirm20/

No engineering equations changed. No ULS/SLS calculation logic changed.
No result-cache persistence added. Existing input-only Project JSON behavior is retained.

Repo summary: Preserve committed CSI Correspondence across automatic rereads and project reloads; show saved V+T source readiness and block incomplete source declarations.
