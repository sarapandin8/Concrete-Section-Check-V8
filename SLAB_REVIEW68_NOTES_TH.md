# SLAB.REVIEW68 — ขอบเขตหน้าตัดพื้นและการถ่ายแรงบริเวณรองรับ

พัฒนาต่อจาก SLAB.IMPORT67 โดยใช้ AASHTO LRFD Ninth Edition (2020), Section 5 ที่โครงการให้มา ข้อมูลแรงอ้างอิงเดิมจาก CSI ยังคงเดิม ไม่มีการย้ายแรงไป centroid เพิ่มตัวคูณโหลด หรือเพิ่มจุดละเว้นเพื่อให้ผลผ่าน

## สิ่งที่แก้ไข

1. เดิมบริเวณปีกบน I-girder ถูกจัดเป็น local support review เฉพาะการตรวจตามขวาง แต่ยังนำแรงตามยาวที่อยู่บนพื้นที่เดียวกันไปตรวจเสมือนพื้นเดี่ยวกว้าง 1 ม. รุ่นนี้จัดพื้นที่สัมผัสรับปฏิกิริยาของทั้ง girder และ diaphragm เป็น **Local transfer REVIEW ในทั้งสองทิศทาง** เก็บแรงครบ 8 องค์ประกอบ ค่า sectional index เดิม และการตรวจ N–M ไว้ครบ
2. พื้นที่นี้ใช้ความกว้างปีกบนจากข้อมูลเดิม และความหนา diaphragm จากตาราง native geometry ไม่ใช่แถบที่เลือกจากค่าแรงสูง การละเว้น centerline, end-to-bearing และ REVIEW61 one-pass ที่ตกลงไว้ไม่เปลี่ยน ไม่มีการเพิ่ม mask ของ source
3. เพิ่มแผงพับ **AASHTO applicability / Local transfer review** แสดงตำแหน่ง กรณีโหลด ดัชนีเดิม และแจกแจง shear tie เป็นพจน์ M, N และ V โดยใช้เครื่องหมายแรงจริง
4. เพิ่ม selected section cuts สำหรับเปรียบเทียบแบบมีเครื่องหมาย อินทิเกรตผล native ภายใน element/case/step เดียว แยกสองด้านของขอบ FE และรายงานทั้ง signed กับ absolute integral ไม่เฉลี่ย envelope ต่างกรณีมารวมกัน
5. แถบเปรียบเทียบกว้างไม่เกิน 1 ม. ถูกตัดที่ขอบพื้น/พื้นที่สัมผัส และรายงานความกว้างจริง แหล่งข้อมูลขาดหรือถูกละเว้นที่มีน้ำหนัก interpolation ไม่เป็นศูนย์ทำให้แถบ **REVIEW ไม่มีค่าตัวเลข** ไม่หารปรับ partial coverage ให้เป็นผลผ่าน
6. General Procedure ใช้ขนาดมวลรวมหยาบจากช่องวัสดุเดิมเฉพาะที่ยืนยันแล้ว หากยังไม่ยืนยันใช้ ag=0 ไม่ยืนยันให้ผู้ใช้อัตโนมัติ สูตร simplified beta=2 / theta=45 ไม่เปลี่ยน
7. Summary และรายงานเก็บ Local transfer review พร้อมดัชนีเดิม ไม่ให้ตัวเลขนอกพื้นที่รองรับที่ต่ำกว่า 1 กลบประเด็นรอยต่อ

## การใช้ข้อผ่อนผัน

| รายการ | การใช้ในรุ่นนี้ |
|---|---|
| 5.7.3.5 จำกัดเหล็กที่ต้องการด้วย maximum moment | **ยังไม่ใช้** — ผลแรงที่มุม shell และ nominal UDL metadata ไม่ยืนยันเส้นทาง direct compression และ development ตามเงื่อนไข |
| 5.7.3.2 เลื่อน critical section ไป dv | **ยังไม่ใช้** — ต้องยืนยันลักษณะปฏิกิริยาและ concentrated load ภายใน dv จึงคง conservative physical-face checks |
| 5.7.3.4.2-7 ขนาดมวลรวมหยาบ | ใช้ค่าจากข้อมูลเดิมที่ยืนยันแล้วเท่านั้น พร้อม trace ag/sx/sxe |
| 5.7.1.2 / 5.7.3.1 local load paths | จัดขอบเขตตรวจเป็น REVIEW ไม่ได้ถือว่าโครงสร้างหรือ interface ผ่านแล้ว |

การแยก local transfer review เป็นการแก้ **ขอบเขตการใช้สมการ** ไม่ใช่การเพิ่มกำลังคอนกรีต ไม่ได้พิสูจน์ว่าค่าแรงสูงเป็น FEM error และไม่ได้ยกเว้น shear ทั้งระบบ งานนี้ยังไม่ใช่ full composite resistance / local STM solver

## ตัวอย่างที่ตรวจซ้ำ

ใช้ JSON32 และไฟล์ static CSI ล่าสุดทั้ง 4 ชุด โดยปรับเหล็กให้ตรงรูปที่ใช้คุยกันอย่างเปิดเผย: บน DB16@150 และล่าง DB20@150 ทั้งสองทิศ transverse clear cover40มม. ไม่ใช่ผลของ JSON32 ที่ไม่แก้ไข ขนาดมวลรวม20มม.ใน JSON ยังไม่ยืนยัน จึงใช้ ag=0

| รายการ | ค่าตัวเลขสูงสุดนอก finite reaction footprints | ตำแหน่ง X,Y (ม.) | ดัชนีเดิมใน Local transfer review |
|---|---:|---|---:|
| Shear ตามยาว | 0.576383 | 0.55268, 4.15000 | 2.468333 ที่ 1.00804, 3.92500 |
| Shear tie ตามยาว | 0.082987 | 0.55268, 0.86667 | 1.312982 ที่ 19.44643, 3.50000 |
| Shear ตามขวาง | 0.450406 | 18.76071, 3.30000 | 4.203145 ที่ 18.53214, 3.50000 |
| Shear tie ตามขวาง | 0.433775 | 6.47232, −4.00000 (support face) | 1.156780 ที่ 3.28482, 3.50000 |

ค่าตัวเลขสูงสุดของ N–M ตามขวาง0.314320 และตามยาว0.244685 ไม่เปลี่ยน สรุป shear/tie ยังคง **REVIEW** เพราะมี local regions และบาง support-face samples ที่ source ไม่พร้อม; ผลทั้งพื้นเป็น **REVIEW REQUIRED** ไม่ใช่ PASS

109,824 native slab records; retained84,864; source exclusions24,960 เท่าเดิม; retained local-transfer records18,144 ผล section-cut comparison16รายการมี source ครบ6รายการ อีก10รายการไม่มี numeric check ตามกติกาเดิม ข้อผ่อนผัน maximum-moment/dv ที่ใช้จริง=0

## วิธีใช้

1. เปิด `Loads → Slab Shell Results` นำเข้า Excel 4 ชุดเดิม: Element Forces - Area Shells, Objects And Elements - Areas, Area Assignments และ Connectivity Data ชื่อไฟล์ไม่บังคับ แยกตารางจาก schema
2. เหล็กตามยาวอยู่ในข้อมูล Slab longitudinal เดิม เหล็กขวางอยู่ใน Slab mesh เดิม ไม่ต้องกรอกซ้ำ
3. เปิด `Analysis → Slab Reinforcement` กด **Calculate Top slab** เพียงครั้งเดียว เลือกผลและกราฟที่ต้องการ
4. เปิดแผง **AASHTO applicability / Local transfer review** เมื่อต้องการดูสาเหตุและขอบเขต รายการ selected cuts ใช้เปรียบเทียบ ไม่แทน governing envelope / Summary
5. เปิด **Code scope / Details / Report** กด Prepare compact Top slab report เพื่อดาวน์โหลด Current / Proposal / Review68 ซึ่งแยกขอบเขตชัดเจน

ไม่มีการแก้กราฟด้วย smoothing ไม่มีการนำข้อเสนอเปลี่ยน spacing ไปใช้เอง และไม่เพิ่มการบันทึกผลลง Project JSON

## การทำซ้ำและแหล่งอ้างอิง

```bash
python qa/slab_review68_real_inputs.py --project PROJECT.json --exports FORCES.xlsx AREAS.xlsx ASSIGNMENTS.xlsx CONNECTIVITY.xlsx --output QA_DIRECTORY
```

เพิ่ม `--example-mats` เฉพาะเมื่อประสงค์ใช้สถานการณ์เหล็กตัวอย่างข้างต้น การทำซ้ำแบบนี้อ่าน JSON และ Excel ใหม่ทั้งหมด ไม่ใช้ runtime result cache

- AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), supplied Section5: Articles5.7.1.2,5.7.3.1–5.7.3.5 และ5.10.8
- FHWA-RC-24-0005, *Modified Compression Field Theory (MCFT) for Shear Load Rating – Pretensioned Example* (August2024), หน้า54: https://rosap.ntl.bts.gov/view/dot/77585/dot_77585_DS1.pdf ตัวอย่างนี้อธิบายหลักเงื่อนไข ไม่ได้ทำให้ railway slab นี้เข้าเงื่อนไขอัตโนมัติ
- ผลการทดสอบและ hash ไฟล์จริงอยู่ใน `SLAB_REVIEW68_VERIFICATION.json` และ `qa/evidence/slab_review68/`
