# IGIRDER.VTCONCURRENT19 — Concurrent V+T source gate

ฐาน: concrete-section-pro_IGIRDER-ENDSECTION18.zip ที่ผู้ใช้ส่งมา

## สิ่งที่แก้
- ตรวจหลักฐานแหล่งแรงก่อนเรียกเครื่องคำนวณ V+T: ต้องเป็น CONCURRENT, ยืนยัน concurrency, มีข้อความหลักฐาน และ source_mode เป็น correspondence หรือ static ที่ไม่ใช่ Max/Min
- Envelope, unverified, metadata ไม่ครบ และตารางกรอกเองที่ไม่ระบุหลักฐาน เป็น SOURCE BLOCKED / NOT CALCULATED ไม่มี design D/C หรือ capacity ไม่ออก PASS/FAIL จากเวกเตอร์ดังกล่าว
- เก็บแรงดิบในคอลัมน์ Source เพื่อ trace เท่านั้น ไม่จับคู่ Vu และ Tu ใหม่ ไม่ลดแรงหรือเปลี่ยน Envelope ให้เป็น Correspondence
- ใช้แถว physical station ที่นำเข้าเท่านั้น ไม่ interpolate ข้าม station เพราะ Correspondence คนละ station อาจมาจากคนละตำแหน่งรถ ต้องส่งออกแรงพร้อมกันที่ critical shear sections มาตรวจด้วย
- รองรับชุดข้อมูลผสม: ตรวจเฉพาะแถวที่ยืนยันแล้ว เก็บแถว blocked และไม่ให้ PASS กลบ source blocker; numerical controlling ratio มาจากแถวที่คำนวณได้เท่านั้น
- เปลี่ยน result version ทำให้ cache V+T รุ่นเดิมต้องคำนวณใหม่ตามระบบตรวจ version/hash เดิม
- Summary แยก SOURCE BLOCKED จาก engineering FAIL; หาก check อื่น fail จริง overall ยัง FAIL
- ตัวนำเข้า app-column บันทึก source_mode เพิ่มเติม ชุดเก่าที่ไม่มีข้อมูลนี้ยังถูกกั้น ต้องนำเข้าพร้อมหลักฐานใหม่

## วิธีใช้
แทน source tree ด้วย ZIP นี้ เปิด JSON แล้วกด Calculate Shear + Torsion ใหม่
JSON ชุดที่ส่งมาจะได้ SOURCE BLOCKED ทั้ง 640 แถว เป็นพฤติกรรมที่ถูกต้องตามแหล่งข้อมูลที่มี
นำเข้า verified factored ULS simultaneous Mu/Nu/Vu/Tu โดยใช้ Force-vector source = CSI Correspondence หรือ Static combination / explicit step ที่ตรงกับข้อมูลจริง พร้อมยืนยันและบันทึก Source basis
ห้ามเลือก Correspondence เพียงเพื่อปลดล็อก Envelope การประกาศของผู้ใช้ต้องอ้างอิงผลจริง; แอปไม่ได้รัน CSI หรือพิสูจน์ตำแหน่งรถให้เอง
ต้องให้ข้อมูลครอบคลุม girder, หน้าตัด, Before/After, load state และ critical sections ที่ต้องตรวจ รวมหลายชุดควบคุมตามความเหมาะสม ไม่ถือว่าชุด Tmax ชุดเดียวครอบคลุม interaction ทุกกรณี

## การตรวจสอบ
- Final scoped regression: 109 passed ใน 5 modules (gate19, CSIIMPORT14, CSI import, torsion audit12, reportcharts8)
- Actual JSON ของผู้ใช้: 640 rows, SOURCE BLOCKED ทุกแถว, zero finite design D/C
- Native CSI fixture: 640 rows ถูกกั้น และ spy ยืนยันว่าไม่เรียก station solver
- ทดสอบ confirmed static/correspondence ส่งแรงเดิมเข้าตัวคำนวณ ไม่มีจุด interpolate; mixed source และ missing evidence ถูกกั้น
- ทดสอบสมการเดิมกับ independent benchmarks ผ่าน หลังเพิ่มหลักฐาน static ให้ hypothetical QA fixtures
- Summary/source review ไม่มี engineering failure หรือ governing numeric ratio จาก blocked rows
- Streamlit AppTest ของ V+T workspace ผ่าน ไม่มี exception; ข้อความ blocked/source action แสดงได้
- Compile app.py และ application modules ที่แก้ผ่าน
- ไม่ได้รันทั้ง repository test suite, ไม่ได้รัน CSiBridge, ไม่ได้ deploy และไม่มี full-page browser screenshot verification

No engineering equations changed. V+T source eligibility and station selection changed.
No result-cache persistence added. Force values and geometry are unchanged.
Standalone flexure/shear/torsion routes remain outside this milestone; existing independent failures remain visible.

Regression evidence: qa/evidence/igird_vtconcurrent19/
Historical QA files are retained as historical evidence, not fresh validation of this release.

Repo summary: Gate I-girder V+T before solving, reject envelope/unverified vectors, preserve source-only evidence, invalidate old results, and distinguish source-blocked summaries from strength failures.
