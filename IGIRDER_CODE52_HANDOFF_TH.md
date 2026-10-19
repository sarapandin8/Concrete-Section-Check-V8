# IGIRDER.CODE52 — Compact code-based workspaces

ต่อจาก `concrete-section-pro_IGIRDER-COMPOSITE51.zip` โดยให้ Shear, Torsion และ Shear + Torsion ใช้ผลตรวจตาม code เป็นหน้าหลัก และย้ายโมเดล U + เหล็กพื้นไว้ในแผงกรณีศึกษาแบบพับ

## วิธีใช้

1. โหลด Project JSON เดิม แล้วไป Analysis → ULS Strength
2. เลือก Shear / Torsion / Shear + Torsion และกด Calculate ของ check นั้นเพียงปุ่มเดียว โปรแกรมตรวจ girder ที่นำเข้าด้วย section และรายละเอียดร่วมกัน **ถ้าต้องการดูทั้งสามส่วน ให้รัน Shear + Torsion ครั้งเดียว** เพราะผลนั้นมี code frames ของ Shear และ Torsion ครบและเก็บพร้อม input hash ของแต่ละ check แล้ว
3. ค่าเริ่มต้นเลือก girder และ load case ควบคุมอัตโนมัติ เปลี่ยน `Girder to review` และ `Load case to review` เพื่อดูผลเดิมโดยไม่รัน solver ใหม่ สำหรับ CSI envelope ให้สลับแท็บ Max / Min
4. เปิด `Calculation details / Equations` หรือ `Load cases / Source audit` เมื่อต้องการตรวจสูตร แถวแรง และเหตุผลของสถานะ ส่วน `Check settings / Section, support & development` เก็บข้อมูลตั้งค่าไว้ในแผงพับด้านบน

Shear/Torsion แสดง demand คู่กับ design resistance; Shear + Torsion แสดง D/C ขององค์ประกอบร่วม ไม่มีการบวกค่าแรงเฉือนกับแรงบิดซึ่งมีหน่วยต่างกัน บัตรสถานะใช้ทุก load case ของ girder นั้น การเลือกดูกรณีที่ผ่านจึงไม่ลบ FAIL / REVIEW ของกรณีอื่น แท็บ Max/Min เริ่มที่ bound ควบคุมของ load case ที่เลือก บนจอแคบกราฟเลื่อนแนวนอนเพื่อคงความชัดของชื่อ แกน และคำอธิบาย

## กรณีศึกษาเดิม

เปิด `Case study — Composite model (LP)` แล้วกด `Run case study — selected girder` เฉพาะเมื่อต้องการศึกษา โมเดลยังใช้ปลอก I, U สองขา และเหล็กยาวพื้นเดิม รันทุก source case ที่เข้าเงื่อนไขของ girder ที่เลือก ไม่รันกับทุก girder ตามปุ่ม Calculate หลัก

ผลเก็บแยกแบบ runtime และผูกกับข้อมูลปัจจุบัน ไม่เข้า code result cache, Summary หรือ Report และไม่เปลี่ยนข้อมูล section/เหล็ก/แรง การเปลี่ยนข้อมูลไม่แสดงผลกรณีศึกษาเก่าราวกับเป็นผลปัจจุบัน

## ขอบเขตการตรวจตาม code

- คงเครื่องคำนวณและสมการ code เดิม รวม strength, minimum reinforcement, spacing, development, effective width, interface และ source/concurrency gates
- Shear ใช้ composite compression/tension resultants และ dv ตาม route เดิม โดย web และคอนกรีต web เป็นคาน I การยอมรับ composite ยังขึ้นกับการถ่ายแรงที่รอยต่อ
- Torsion ใช้ qualified closed I-hoop และ Ao/ph ของ route นั้น ไม่เพิ่มกำลังบิดของ U + slab อัตโนมัติ การตรวจเหล็กยาวและแรงร่วมยังคงอยู่
- คง CSI Tu ที่จุดรายงานเดิม ไม่มีการย้ายไป centroid คาน I นโยบายแปลง M2/M3 เดิมไม่เปลี่ยน
- สถานะ REVIEW จากจุดอ้างอิงแรง/ความพร้อมของกำลัง, envelope concurrency หรือรายละเอียดที่ยังไม่ยืนยันยังไม่ถูกเปลี่ยนเป็น PASS
- LP เป็น nominal case study ที่ยังไม่ยืนยันกำลัง full composite สำหรับออกแบบจริง การย้ายไปแผงกรณีศึกษาไม่ได้ยืนยันแบบจำลองดังกล่าว
- กราฟครอบคลุมช่วง 0–L; missing capacity/D/C ยังเป็น missing ไม่เติมศูนย์หรือคาดการณ์กำลังที่ปลายคาน

## แก้ปัญหาที่ทำให้การคำนวณหยุด

การหาแรงควบคุมเดิมกรองค่าด้วย numeric conversion แต่ยังเรียก absolute value บน Series ต้นฉบับ ทำให้ข้อความตัวเลขบางชุดหยุดการสร้างผล V–T ได้ รุ่นนี้ใช้ค่าตัวเลขที่แปลงแล้ว เลือกแถวแบบ positional เพื่อรองรับ index ซ้ำ และคง unknown/nonfinite/bool เป็น unavailable โดยไม่เปลี่ยน source table

## ผลตรวจซอฟต์แวร์

รายละเอียดผลตรวจรุ่นนี้อยู่ใน `qa/evidence/code52/` และ release note ภายนอก ZIP

- JSON โครงการเดิม SHA-256 `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`: 640 source rows, 2 imported girder banks
- เทียบกับ code frames ของ COMPOSITE51 โดยแยกเฉพาะ LP sidecar ออก: ทั้ง 6 check packages และ DataFrame ครบ 30 คู่มี digest ตรงกันทุกค่าและสถานะ
- AppTest ใช้ app.py จริง ตรวจทั้งแบบ collection และ single member ทั้ง 3 checks; เปลี่ยน girder/load case และ redraw ไม่คำนวณใหม่; stale inputs ไม่แสดงกราฟเก่า
- ปุ่มกรณีศึกษาเรียก real LP เฉพาะสมาชิกที่เลือก โดย production caches ไม่เปลี่ยน และ Summary / Report ไม่เรียก solver
- Selected regression suite: 199 passed (มีคำเตือน pytest import rewrite ของ anyio 1 รายการ ไม่ใช่ผลวิเคราะห์ผิด)

การทดสอบข้างต้นเป็น software regression/UI verification ไม่ใช่ independent structural validation ของโมเดลร่วม

## Repo summary

Make code-based Shear/Torsion/V–T the compact primary workflow; retain U/slab LP as an explicit, collapsed case study. Preserve code equations, CSI Tu, engineering gates and input-only Project JSON; fix numeric-text governing-action selection.
