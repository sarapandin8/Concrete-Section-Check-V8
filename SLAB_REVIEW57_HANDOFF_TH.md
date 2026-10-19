# SLAB.REVIEW57 — ค่าอ้างอิงการดัดตามมาตรฐานและสาเหตุที่ควบคุมผล

พัฒนาต่อจาก SLAB.CHECK56 โดยคงผลแรงร่วม N–M และเหล็กที่ต้องการเดิม เพิ่มการตรวจอ้างอิงตามมาตรฐานและคำอธิบายผลในหน้าเดิม

## สิ่งที่เพิ่ม

- การ์ด **Controlling check** ระบุข้อที่คุม D/C ของโมเดล พร้อม element และตำแหน่ง
- **What controls / All-case check breakdown** แสดงผลเหล็ก 4 กลุ่ม คอนกรีต แรงเฉือน shrinkage minimum และ maximum spacing แยกกัน แต่ละแถวเก็บ LC / Max–Min / element / joint ของตัวเอง
- จำนวนจุดในตารางใหม่เป็น **unique elements** ไม่ใช่จำนวนแถว corner/case ที่ซ้ำใน element เดียว
- ใน **Calculation trace / Equations** แสดงผลตรวจของ source record ที่กำลังดู และแยก **N–M tie / Shear tie addition / Tie driver** เพื่ออธิบายที่มาของ As required
- ตัวเลือกกราฟเพิ่ม **Code flexure reference** และ **Minimum sufficient screen**
- **Code flexure / Minimum reinforcement reference** แสดง Mu จาก moment triad ของแถวเดิม, φMn อ้างอิง, tensile strain และอัตราส่วนการตรวจขั้นต่ำ
- CSV element envelope เพิ่ม controlling check, φMn reference และเหตุผลที่ REVIEW พร้อมปุ่ม CSV สรุปทุกกลไก

คำนวณด้วยปุ่มเดิม **Calculate Slab Reinforcement** ครั้งเดียว เปลี่ยน view / LC โดยไม่เรียก solver ซ้ำ ไม่มีช่องเหล็กเพิ่ม ไม่มีการกรอก fy/fu ที่ไม่ทราบค่า

## วิธีใช้

1. เปิด Project JSON และนำเข้า Excel ทั้งชุดเดิมใน **Loads → Slab Shell Results**
2. ไป **Analysis → Slab Reinforcement** แล้วกด **Calculate Slab Reinforcement**
3. ดู **Overall section** หรือเหล็กแต่ละกลุ่มเป็นผลหลักของแรงร่วม N–M
4. เปิด **What controls / All-case check breakdown** เมื่อต้องการทราบว่าข้อใดไม่ผ่าน และ LC / ตำแหน่งใดควบคุม
5. เปิด **Calculation trace / Equations** เพื่อตรวจองค์ประกอบแรงของ source record เดียวกัน
6. ใช้ **Code flexure reference / Minimum sufficient screen** เป็นการตรวจอ้างอิงในขอบเขตที่แอปแจ้งไว้

## ความหมายของค่าอ้างอิงใหม่

ใช้ RC strip กว้าง 1 ม. เหล็กรับดึงของ mat นั้น ตำแหน่งเหล็กจริง และ equivalent rectangular block ตาม AASHTO LRFD 9th Edition ก่อนให้ φ = 0.90 ต้องตรวจว่า tensile strain ถึง tension-control limit

ค่า φMn นี้เป็น **N=0 tension-mat-only reference** ไม่ใช่กำลัง N–M เต็มระบบ ไม่คิดเพิ่มกำลังเหล็ก mat ฝั่งตรงข้าม และไม่ใช้แทน field ของ shell ที่มีแรงเมมเบรน

สำหรับ minimum reinforcement ใช้เงื่อนไขเพียงพอ **Mr ≥ 1.33Mu** ถ้าผ่านภายในขอบเขต N=0 reference ก็เพียงพอสำหรับสาขานี้ หากเกินจะคง **REVIEW** เพราะเกณฑ์มาตรฐานใช้ค่าที่น้อยกว่าระหว่าง 1.33Mu และ Mcr การเกินสาขาที่แรงกว่าจึงยังไม่ใช่หลักฐานว่าข้อขั้นต่ำไม่ผ่าน

กราฟเป็นสีเทาเมื่อมีแรงเมมเบรนหรือยังยืนยัน strain/material scope ไม่ได้ ตัวเลขที่ไม่มีค่าไม่ได้หมายถึงแรงเป็นศูนย์ ค่า reference และผลขั้นต่ำใหม่นี้ไม่เพิ่ม As required ของโมเดลเดิม และไม่เปลี่ยนสถานะโมเดลให้เป็นการรับรองออกแบบจริง

## ผลจากชุดตัวอย่างจริง

- ตรวจพื้นครบ 146,432 แถว / 4,576 elements / 276 Areas
- จำนวน Preview PASS / Preview FAIL / REVIEW ของ field และ As required สูงสุดทั้ง 4 กลุ่มตรงกับ CHECK56
- D/C สูงสุด 19.734 ของ field อยู่ที่ Bottom longitudinal, U2A / Max, element 1698-5, joint 826, X = 19.675 ม., Y = −2.500 ม.
- ที่ record นี้ N–M tie = 2,340.423 N/mm และ nominal shear-tie addition = 7,715.892 N/mm; เมื่อแปลง N–M tie ด้วย φs แล้ว ส่วนเพิ่มจาก shear คิดเป็นประมาณ 75% ของ tensile requirement ของ mat นี้ในโมเดล
- คอนกรีตของ record เดียวกันมี D/C = 15.176 ส่วน shear applicability ยังต้อง REVIEW ตัวเลข As จุดนี้จึงยังต้องประเมินบริเวณถ่ายแรงก่อนจัดเหล็กจริง
- ข้อมูลจริงมีแรงเมมเบรนทุกแถว ค่าอ้างอิง N=0 จึงคง REVIEW ทั้งชุด โดยผลหลักยังเป็น coupled N–M เดิม

ใช้ JSON ตัวอย่าง COVER38 ที่มีอยู่ในการทดสอบ ตัวเลขนี้ไม่ใช่การยืนยันโครงการปัจจุบันที่ผู้ใช้ยังไม่ได้บันทึก และไม่ใช่ bar schedule สำหรับก่อสร้าง

## ขอบเขต

ยังเป็น section preview พร้อม conservative shear screens คงข้อที่ต้องแยกตรวจ ได้แก่ combined N–M minimum qualification, Mcr branch, anchorage/development, load-transfer regions, cover/exposure, punching/local wheel effects, fatigue และ SLS ไม่ได้เพิ่มการยืนยัน full 3D N–M–V หรือ complete deck code acceptance

หน้าจอหลักยังมีกราฟเดียว ปุ่ม Calculate เดียว และตัวเลือก view / LC สองตัว รายละเอียดเพิ่มเติมพับเก็บได้ ข้อมูลแรงเดิมและ Project JSON schema ไม่เปลี่ยน ผลพื้นเป็น session-only และแยกจาก Summary / Report ของคาน

รายละเอียดสมการและผลตรวจอยู่ใน **SLAB_REVIEW57_METHOD.md** และ **SLAB_REVIEW57_VERIFICATION.json**

## Repo summary

Add scoped AASHTO RC bending and sufficient minimum-reinforcement references, preserving coupled N–M results when membrane actions are present. Explain controlling checks and shear-tie contributions with exact source records, unique-element counts and CSV summaries. Retain one Calculate action and explicit REVIEW gates; verify hand examples, regression tests and the complete shell-data browser flow.
