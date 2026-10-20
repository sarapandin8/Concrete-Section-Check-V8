# SLAB.DESIGN66 — ข้อเสนอระยะเรียงเหล็กที่ทวนคำนวณแล้ว

ต่อจาก TOP65 เพิ่มข้อเสนอระยะเรียงเหล็กพื้น 4 ชั้นจากผลตรวจที่คำนวณอยู่ ใช้ปุ่ม **Calculate Top slab** ปุ่มเดิม และนำเข้า **Excel 4 ชุดเดิม** ไม่ต้องกรอกเหล็กหรือกำลังวัสดุซ้ำ

## วิธีใช้

1. นำเข้า Project JSON และ 4 export sets ของ CSI ใน Loads → Slab Shell Results
2. เปิด Analysis → Slab Reinforcement แล้วกด Calculate Top slab
3. ตารางหลักและกราฟยังเป็นผลของเหล็กที่กรอกอยู่จริง เปิด **Suggested bar spacing · not applied** เพื่อดูข้อเสนอ
4. ข้อเสนอคงขนาดเหล็ก กำลังวัสดุ ความหนาพื้น และ cover / ตำแหน่งเหล็กเดิม เปลี่ยนเฉพาะระยะเรียงที่จำเป็นต้องเพิ่มเหล็ก
5. หากจะนำข้อเสนอไปใช้ ให้แก้ระยะเรียงตามยาวใน Section Builder และตามขวางใน Slab mesh แล้ว Calculate ใหม่ แอปไม่แก้ input ของโครงการให้อัตโนมัติ

## วิธีคำนวณ

- ใช้ผล N–M, flexural shear tie, temperature minimum และ maximum spacing ที่ควบคุมเป็นตัวเริ่มค้นหาข้อเสนอ
- เมื่อต้องแก้ N–M ให้พิจารณาเหล็กทั้งสองด้านของทิศทางนั้น แล้วคำนวณทวน strain-compatible resistance ไม่สมมติว่าเพิ่มเหล็กด้านใดด้านหนึ่งแล้วจะผ่านเสมอ
- ค้นระยะเรียงบน grid 10 มม. คงขนาดเหล็กเดิม ไม่ลดพื้นที่เหล็ก และไม่ต่ำกว่า trial clear-spacing bound ของเหล็กหล่อในที่ตาม 5.10.3.1.1 ใช้ aggregate input เดิม; ถ้ายังไม่ยืนยัน สาขานี้ยังเป็น REVIEW
- แต่ละก้าวใช้เผื่อค้นหา 2.5% กับระยะเรียงเท่านั้น ไม่แก้แรง ไม่เปลี่ยนตัวคูณโหลดหรือ phi ผลผ่าน/ไม่ผ่านของก้าวนั้นมาจากการคำนวณใหม่ด้วยสมการเดิม
- จำกัดไม่เกิน 4 ก้าวเพื่อควบคุมเวลา หากยังไม่พบระยะที่ผ่านจะแจ้ง **NO FEASIBLE SPACING FOUND** หมายถึงไม่พบในกระบวนการค้นหานี้ ไม่ใช่ข้อพิสูจน์ว่าไม่มีวิธีออกแบบอื่น
- คำนวณทุก retained native record และ available matching support-face record ของเหล็กข้อเสนอ เก็บ controlling vector จริงไว้ในรายงาน ไม่ประกอบแรงสูงสุดข้ามแถว/case
- คงแนว I-girder / diaphragm, bearing end zones และ REVIEW61 isolated-peak exclusions เดิม รวมถึง local-support REVIEW และ sample ที่ไม่พร้อมตรวจ
- ระยะเรียงอาจมีผลต่อ beta และกำลังคอนกรีตใน general procedure ของ AASHTO ตามสมการเดิม แต่ไม่ถูกเพิ่มเป็น slab Vs และไม่เปลี่ยนความหนาคอนกรีต

นี่เป็น **ข้อเสนอที่ทวน sectional checks** ไม่ใช่การหาพื้นที่เหล็กต่ำสุดหรือการรับรองระบบพื้นทั้งหมด Nxy/Mxy interaction, simultaneous biaxial shear, local support paths, available anchorage, fatigue และ SLS ยังต้องตรวจในขอบเขตที่เกี่ยวข้อง Numeric D/C ต่ำกว่า 1 ไม่ลบสถานะ REVIEW จากข้อมูลหรือเงื่อนไขที่ยังไม่ครบ

## ตัวอย่างจาก JSON32 และ 4 Excel เดิม

| เหล็ก DB16 | ระยะเดิม (มม.) | ข้อเสนอ (มม.) |
|---|---:|---:|
| ตามยาวบน | 200 | 90 |
| ตามยาวล่าง | 150 | 80 |
| ตามขวางบน | 150 | 150 |
| ตามขวางล่าง | 150 | 110 |

| การตรวจ | D/C เดิม | D/C ของข้อเสนอ |
|---|---:|---:|
| Direct N–M ตามยาว | 0.367 | 0.298 |
| Direct N–M ตามขวาง | 0.441 | 0.337 |
| Flexural shear tie ตามยาว | 2.077 | 0.935 |
| Flexural shear tie ตามขวาง | 1.235 | 0.946 |
| One-way shear ตามยาว | 3.002 | 3.002 |
| One-way shear ตามขวาง | 1.490 | 1.264 |

ข้อเสนอนี้ยังมี one-way shear ไม่ผ่าน และยังมี REVIEW ของขอบเขต / รายละเอียด จึงไม่แสดงว่าผ่านทั้งพื้น ข้อมูลตัวอย่างเป็นผลจากการวิเคราะห์เดิม ไม่ใช่ผล equivalent train UDL รอบใหม่ที่ผู้ใช้กำลังเตรียม

ตัวอย่างค้นพบข้อเสนอใน 1 ก้าว ทวน 113,232 native records และ 12,136 available support-face records ใช้เวลาประมาณ 3.75 วินาทีเพิ่มจากผลตรวจเดิมบน runtime ที่ทดสอบ เวลานี้ไม่รวมอ่าน Excel หรือคำนวณผลเดิม และไม่ใช่การรับประกันเวลาเครื่องผู้ใช้

## สถานะและรายงาน

ผลหลักใน Result Summary / Report / QA ยังเป็นเหล็กที่กรอกจริง ค่าของข้อเสนอไม่แทนผลหลัก Compact report แบ่งเป็น `Current/` และ `Proposal/` พร้อมสรุป 4 ชั้น, ตรวจหน้าตัด, shear ที่ยังต้องแก้, controlling vectors และประวัติก้าวค้นหา

ข้อเสนอผูกกับ source / geometry / reinforcement inputs หากเปลี่ยน inputs เชิงกลจะต้องคำนวณใหม่ การเปลี่ยน ballast / nominal UDL metadata อย่างเดียวไม่เปลี่ยนแรงหรือกำลังและใช้ข้อเสนอเดิมซ้ำได้ Project JSON ยังคงบันทึก input เท่านั้น ไม่บันทึก solver cache หรือข้อเสนอ เมื่อเปิด JSON หรือเริ่มแอปใหม่ให้นำเข้า 4 ชุดแล้ว Calculate ใหม่

## การทดสอบ

ตรวจทั้ง independent candidate cases, การสลับ tension mat ที่ M=0, one-way shear ที่ยังไม่ผ่าน, minimum-spacing bound, unknown aggregate, source / local-support coverage, controlling-vector rechecks, input immutability, cache freshness, report separation และ Project JSON ใช้ test suite รวม 241 tests พร้อม live browser 1440/1280 px กราฟและ navigation ไม่เพิ่มคำสั่งรันซ้ำ

รายละเอียดอยู่ใน `SLAB_DESIGN66_VERIFICATION.json` และทำซ้ำได้ด้วย `qa/slab_design66_real_inputs.py` / `qa/slab_design66_browser_verify.py`

สมการกำลังที่ใช้ยังเป็น AASHTO LRFD Ninth Edition (2020), Section 5 ตามไฟล์มาตรฐานที่ผู้ใช้ให้ ไม่เปลี่ยนเครื่องคำนวณ AASHTO63 หรือสูตร punching ของ SHEAR64
