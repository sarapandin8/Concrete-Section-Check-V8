# SLAB.REVIEW61 — กรอง peak และค่าเฉลี่ยโซน

พัฒนาต่อจาก ENDZONE60 โดยคงตัวคำนวณ nominal และข้อมูลต้นฉบับ ผลกรอง/ค่าเฉลี่ยเป็น sensitivity study ที่แยกจากผลสำหรับ Summary/Report

## ผลจากโครงการจริง

ใช้ JSON (32) และ Excel ต้นฉบับสี่ไฟล์ชุดเดิม ไม่แก้แรงหรือตัดข้อมูลในไฟล์นำเข้า

| รายการ | จำนวน |
|---|---:|
| Source records ของ Top Slab | 146,432 |
| Nominal records หลังละเว้น connection/end zones เดิม | 120,192 |
| Records ที่กรองเพิ่มในผลศึกษา | 6,960 |
| Physical nodes ที่พบอย่างน้อยหนึ่ง LC/Step เข้าเกณฑ์ | 244 |
| กลุ่ม node + LC + Step ที่เข้าเกณฑ์ | 1,740 |
| Records ที่เหลือในผลกรอง | 113,232 |
| โซนอัตโนมัติ | 1,202 |
| Zone × LC/Step records | 9,616 |

หนึ่ง node อาจเข้าเกณฑ์เฉพาะบาง LC/Step จึงไม่ตัดกรณีอื่นตามไปด้วย ในกลุ่มที่เข้าเกณฑ์จะตัดผลของทุก element ที่ใช้ node นั้นร่วมกัน และเก็บแรงทั้งแปดองค์ประกอบไว้ตรวจย้อนกลับ

| การตรวจ | Nominal D/C สูงสุด | หลังกรอง peak | เฉลี่ยโซนหลังกรอง |
|---|---:|---:|---:|
| N–M field | 1.844326 | 1.060729 | 0.704037 |
| One-way shear screen | 5.535920 | 3.864592 | 2.119779 |
| Top longitudinal | 0.996491 | 0.996491 | 0.333392 |
| Bottom longitudinal | 1.844326 | 1.060729 | 0.593105 |
| Top transverse | 0.822377 | 0.822377 | 0.532043 |
| Bottom transverse | 1.410412 | 0.959756 | 0.704037 |
| Concrete compression | 1.758156 | 1.010624 | 0.700509 |

**ผลกรองยังเกิน 1 ทั้ง shear และ N–M** ไม่ได้ตัดซ้ำหรือเพิ่มความแรงของตัวกรองจนผ่าน ค่าเฉลี่ยโซนที่ต่ำกว่า 1 ไม่ใช่การอนุมัติแบบหรือการยืนยัน local checks

| จุดควบคุมหลังกรอง | D/C | X (ม.) | Y (ม.) | LC / Step | Element / Joint |
|---|---:|---:|---:|---|---|
| N–M | 1.060729 | 1.00804 | 2.300 | U2A / Max | 1384-8 / ~404 |
| Shear | 3.864592 | 19.44643 | −3.500 | U2A / Min | 1681-12 / ~4913 |

จุดเดิม ~517 (U2A/Max) และ ~4603 (U2A/Min) ถูกกรองในผลศึกษา ค่าที่สูงต่อเนื่องเป็นบริเวณหรือมีเพื่อนบ้านไม่เพียงพอยังคงอยู่ ไม่ตัดเพราะ D/C สูงเพียงอย่างเดียว

## วิธีใช้งาน

1. Analysis → Slab Reinforcement → **Calculate Slab Reinforcement** ปุ่มเดิมเพียงครั้งเดียว
2. เลือก **Review basis**:
   - **Nominal nodes**: ผล nominal เดิม
   - **Peaks excluded · study**: ผลหลังกรองจุดกระโดด; กากบาทสีม่วงคือตำแหน่งที่ละเว้นในผลศึกษา
   - **Zone averages · study**: ผลตรวจจากแรงเฉลี่ยตามโซนหลังกรอง
3. เลือก Result to review และ Load case to review เพื่อดูกราฟ โดยไม่รัน solver/ตัวกรองซ้ำ
4. เปิด **Peak review / Zone averages · study** เพื่อดูสมการ ตารางก่อน–หลัง รายการ node และดาวน์โหลด CSV

การ์ดสถานะและตารางเหล็ก nominal ยังคงใช้ผลเดิมและระบุให้เห็นชัด ผลศึกษาติดป้าย REVIEW REQUIRED ไม่แทนที่ Summary/Report และไม่บันทึกเป็น engineering results ใน Project JSON ไม่เพิ่มไฟล์นำเข้าหรือช่องยืนยัน

## เกณฑ์กรอง — ใช้รอบเดียวกับข้อมูลเดิม

ตรวจ magnitude ของแรงภายใน LC/Step เดียวกันจาก node ที่ยังอยู่ในขอบเขต nominal:

- one-ring neighbours มาจาก connectivity จริงของ shell รวม node ตามแนวทแยง
- ที่ shared node ใช้ magnitude สูงสุดของแต่ละ element ไม่เฉลี่ยก่อนตรวจ
- ต้องมีเพื่อนบ้านที่ใช้ได้อย่างน้อย 4 node และมีเพื่อนบ้านตรงแนวอยู่สองด้านอย่างน้อยหนึ่งทิศทางในแกนสะพาน
- ต้องมากกว่าเพื่อนบ้านทุกจุด เป็น strict local maximum
- ต้องมากกว่า median ของเพื่อนบ้าน **2 เท่า** และ modified score **3.5** พร้อมกัน
- เมื่อดัชนี N–M หรือ V เข้าเกณฑ์ จะละเว้นเวกเตอร์แรงทั้งชุดใน node/LC/Step นั้น ไม่เลือกตัดเฉพาะองค์ประกอบที่ทำให้ไม่ผ่าน

`I_NM = max( ||N + 6M/h||_F, ||N − 6M/h||_F )`

`I_V = sqrt(Vx² + Vy²)`

N/M เป็น symmetric tensors ในแกนเหล็ก Frobenius norm นับ xy สองครั้ง h หน่วย m ดัชนีทั้งคู่หน่วย kN/m

`modified score = 0.67448975 × (I − median(Ij)) / MAD(Ij)`

ใช้ numerical floor `max(abs(median) × 1e−12, 1e−9)` เมื่อ median/MAD เป็นศูนย์

**ratio 2 และเงื่อนไขพื้นที่เป็น heuristic เพื่อศึกษา ไม่ใช่ข้อกำหนด AASHTO/ACI** ค่า modified-score 3.5 เป็นแนวทางติดป้าย potential outlier ทางสถิติ ไม่พิสูจน์ว่าผล FEM ผิด ไม่ได้ตรวจสมมติฐาน distribution ของ FEM field และไม่ใช้ D/C หรือจำนวนเหล็กเป็นเกณฑ์

ไม่กรองซ้ำหลังตัดรอบแรก เพราะจะเปลี่ยนชุดเพื่อนบ้านและอาจไล่ตัดค่าที่ถูกต้อง

## การเฉลี่ยโซน

โซน = ช่วงตามยาวของ native Area × แถว mesh ตามขวางหนึ่งแถว จึงรักษาตำแหน่งตามขวาง ไม่เฉลี่ยทั้งช่วง girder รวมกัน โซนต้องต่อเนื่องเป็นสี่เหลี่ยมใน plan ที่ตรงกับแกนสะพาน และห้ามข้ามแนว girder/diaphragm ที่ตรวจพบ หาก geometry อยู่นอกขอบเขต จะปิดเฉพาะ zone study ไม่กระทบ nominal/peak study

เฉลี่ยแรง `(Nx, Ny, Nxy, Mx, My, Mxy, Vx, Vy)` ด้วยน้ำหนักชุดเดียวภายใน Zone + LC + Step โดยอินทิเกรต bilinear corner shape functions ด้วย 2×2 Gauss quadrature บนพื้นที่ฉายราบ ไม่ให้น้ำหนักเท่ากันทุก node โดยไม่คำนึงขนาด element

`Q_mean = sum(Ak × Qk) / sum(Ak)` สำหรับ samples ที่เหลือ

คำนวณ D/C ใหม่จากแรงเฉลี่ย ไม่เฉลี่ย D/C/As เดิม และใช้ความหนาต่ำสุดของโซนเดิมคำนวณกำลัง

ไม่แจกน้ำหนักของ sample ที่ถูกละเว้นกลับให้เต็มโซน CSV แสดง Full/Imported/Retained sample area, coverage, mean absolute actions และ Sign change ของแต่ละองค์ประกอบ เพื่อเห็นการหักล้างเครื่องหมาย ตำแหน่ง marker คือ centroid ของ samples ที่เหลือ ไม่ใช่ peak node

**เป็น retained-sample area mean ไม่ใช่การอินทิเกรต design strip ที่ตรวจสมดุลกับแรงภายนอกแล้ว** signed averaging อาจลดค่าเพราะเครื่องหมายหักล้างกัน จึงต้องดู raw field และ local response ร่วมด้วย input ที่ขาดบางมุมยังระบุ Source incomplete/grey

## ขอบเขตที่คงไว้

ยังละเว้นแนว girder Y = −3.7, −2.5, −1.3, 1.3, 2.5, 3.7 ม.; แนว diaphragm ภายในขอบเขตจริง; และหัวท้าย X = 0…0.4 / 19.6…20 ม. ตาม bearing reference ใน JSON ขอบเขตนี้ไม่เปลี่ยนตาม D/C

สมการกำลัง nominal ของ ENDZONE60 ไม่เปลี่ยน N–M sandwich field และ one-way shear เป็นการตรวจแยก Combined N–M–V ยังคง REVIEW เมื่อมี V; local wheel/punching, connection transfer, anchorage, fatigue และ SLS ไม่ถูกแทนที่ด้วยตัวกรอง/ค่าเฉลี่ย

## อ้างอิง

- [CSI — Show Shell Force/Stress Plots](https://docs.csiamerica.com/help-files/csibridge/Home_tab/Display_panel/Show_Shell_Force_Stress_Plots.htm): shared-joint variation, mesh review และ averaging ไม่ได้กำหนดเกณฑ์ลบ FEM results จาก ratio 2
- [CSI — Slab Moments and Shears](https://docs.csiamerica.com/help-files/safe/Program_Output/Slab_Moments_and_Shears.htm): selective averaging และข้อจำกัดที่ discontinuity เช่น support ไม่ได้รับรอง zone averaging ที่พัฒนานี้
- [NIST — Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm): modified score/MAD ใช้ติดป้าย potential outliers แยกจากการพิสูจน์ว่าข้อมูลผิด ไม่ใช่มาตรฐานออกแบบโครงสร้าง

## Verification

รายละเอียดชุดทดสอบ UI การตรวจภาพจริง source hashes และการตรวจ weighted resultants อยู่ใน `SLAB_REVIEW61_VERIFICATION.json` และ delivery metadata การทดสอบเป็น focused suite ไม่ใช่ full repository suite และไม่ได้ยืนยัน structural validity ของการลบ peak

## Repo summary

Add traceable one-pass peak screening and area-weighted zone review for slab shell results. Preserve nominal checks and raw actions, with before/after comparisons and CSV audits kept separate from design acceptance.
