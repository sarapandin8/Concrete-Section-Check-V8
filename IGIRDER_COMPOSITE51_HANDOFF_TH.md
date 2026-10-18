# IGIRDER.COMPOSITE51 — U/slab anchorage trace and Calculate reuse

ต่อจาก ZIP COMPOSITE50 ที่ตรวจ checksum แล้ว รุ่นนี้เพิ่มการตรวจเรขาคณิตและระยะพัฒนาแรงบริเวณ U–slab อัตโนมัติ ลดการตรวจซ้ำ และแก้การแสดงโมเดลซ้ำในหน้า Shear **ยังไม่ใช่การยืนยันกำลัง full composite สำหรับออกแบบจริง และไม่ได้เพิ่ม/ลด nominal Vn/Tn/V–T**

## สิ่งที่เปลี่ยน

1. อ่าน E, D, B, ขนาด/ระยะ U และ cover/ขนาดเหล็กพื้นจากข้อมูลเดิม วางระดับเหล็กขวางและเหล็กยาวบน–ล่างโดยตรวจพิกัดเหล็กยาวกับ inventory ที่ใช้วิเคราะห์จริง ไม่สมมติตำแหน่ง x ของเหล็กพื้นหรือ strand
2. ตรวจความยาว hook จากระดับเหล็กแต่ละชั้นเพิ่มเติมจากการตรวจที่รอยต่อ เนื่องจาก AASHTO 5.8.2.4.2 ต้องพัฒนาแรง tie ที่ขอบเขต extended nodal zone ระดับเหล็กที่แสดงเป็น inspection plane เท่านั้น ไม่ถือเป็น node face ที่พิสูจน์แล้ว
3. แสดงรูป **ระดับ** U/เหล็กพื้นและแรงยึด U เป็น kN ต่อขาจริง ณ ขีดกำลังของโมเดล แยกจาก N/mm และไม่ถือว่าเป็นแรงที่วัด/กู้คืนจากโครงสร้างจริง ไม่มีการวาดแนว hook หรือขอบเขต node ที่ไม่มีข้อมูลยืนยัน
4. ใช้ผล torsion ของสถานี/เวกเตอร์เดียวกันร่วมกับการตรวจ concurrent row โดยเรียกฟังก์ชันตรวจเดิมพร้อม source/station guards ลดการตรวจ torsion ซ้ำและการสร้าง dataframe หนึ่งแถวซ้ำ ไม่ลดจำนวน source vectors
5. ทำ key ของ nominal fps จาก geometry/materials/steel/settings และ **axial target, moment sign, tension-half boundary ที่ส่งเข้า solver จริงครบชุด** ไม่อาศัยค่าแรงจาก load-case fingerprint หรือการปัดเศษ การ reuse อยู่เฉพาะการกด Calculate ครั้งนั้น
6. LP reuse ใช้ Supplies และ action arguments เท่ากันทุกค่าเท่านั้น ไม่มีการปัด θ/แรง/ขนาด และคืนสำเนา witness แยกแต่ละแถว ไม่มี cache ผลใหม่ลง Project JSON
7. เอาโมเดล composite ที่แสดงซ้ำภายในแผง code reference ของหน้า Shear ออก คงโมเดลหลักและ code reference คนละนิยามไว้ มีแผง U–slab ใหม่หนึ่งแผงต่อ girder พับไว้เริ่มต้น ไม่เพิ่มช่องกรอก checkbox หรือปุ่มรัน

## ข้อค้นพบจาก JSON โครงการเดิม

ใช้ `concrete_section_pro_project_31_COVER38.json` เดิม SHA-256:
`0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`

ข้อมูลที่บันทึกไว้คือ slab 350 mm, E=150 mm, B=200 mm, U DB12, D=72 mm ไม่มีการเปลี่ยน E ตามข้อความสนทนาเก่าโดยไม่แก้ input จริง

สูตร geometry เมื่อใช้ tension hook เดิม:

```text
B = slab thickness − E
r_center = (D + db)/2
z_straight_top = B − r_center − db/2
ldh_available(z_plane) = B − z_plane
z_latest_exit = B − ldh_required
```

z วัดขึ้นจากรอยต่อ ไม่ใช่แกนอ้างอิงแรงของ CSI

- ต้องการ ldh = 190.803 mm; จากรอยต่อมี B=200 mm จึงผ่าน dimension check เดิม
- ขาตรง U อยู่เหนือรอยต่อถึง 152 mm; hook ด้านนอกสูง 200 mm
- เหล็กขวางบนอยู่สูง 302 mm และเหล็กยาวบน 286 mm สูงกว่าช่วงขาตรงของ U แสดงว่าแบบจำลองยังต้องระบุเส้นทางถ่ายแรงผ่านคอนกรีต/node ไม่สามารถสมมติว่า U ครอบตะแกรงบนโดยตรง
- เหล็กขวางล่างอยู่สูง 48 mm ถ้าใช้ระนาบนี้เป็นจุดเริ่มวัด จะเหลือ ldh 152 mm ขาด 38.803 mm; เหล็กยาวล่างสูง 64 mm จะเหลือ 136 mm ขาด 54.803 mm
- ถ้าต้องพัฒนาเต็ม fy ด้วย hook route เดิม ขอบเขต node ที่ใช้วัดระยะต้องอยู่สูงจากรอยต่อไม่เกิน 9.197 mm

**ข้อขาดจาก inspection plane ไม่ใช่คำตัดสินว่าโครงสร้างวิบัติ** เพราะยังไม่ได้กำหนด extended node / strut ที่แท้จริง ไม่ได้นำช่องว่างนี้ไปหักกำลัง LP ด้วยอัตราส่วนสมมติ และไม่ถือว่า dimension checks ผ่านเท่ากับพิสูจน์การปิด torsion cage แล้ว

## ผลตรวจที่ยังคงเดิม

- 640 original vectors จาก 2 imported girder banks; 608 interior vectors คำนวณได้ครบ
- 32 physical end vectors ระบุเป็น end-region scope แยก; ไม่เติมกำลังสมมติที่ x=0/20 m
- มี 122 below-threshold torsion rows ที่ยังคำนวณ nominal model ได้
- เปรียบเทียบ COMPOSITE50 กับ COMPOSITE51: nominal Vn, Tn, V-only capacity/DC, T-only DC, V–T DC และ code shear series reference **เท่ากันตรงทุกค่าใน 608 แถว** รวมทั้ง CSI/raw/used forces
- independent force audit ผ่าน 5 คำตอบต่อแถว; residual สูงสุดประมาณ 3.04e−14 เป็น software verification ไม่ใช่ structural validation

| Girder | V-only D/C ควบคุม | V–T D/C ควบคุม |
|---|---:|---:|
| Interior Girder 2 | 0.790 | 1.554 |
| Left Exterior Girder | 0.813 | 0.938 |

ทั้งหมดเป็น nominal model ไม่มี φ ของโมเดลร่วม Interior ยังเกิน nominal V–T; Exterior อยู่ใน nominal envelope แต่ยังไม่ใช่ผลยอมรับสำหรับออกแบบจริง มี 58 แถวเกิน nominal V–T ทั้งหมดใน Interior

## วิธีใช้

โหลด Project JSON เดิม → Analysis → ULS Strength → Shear / Torsion / Shear + Torsion → กด Calculate ปุ่มเดิม → เปิด Girder → `U–slab anchorage / node — automatic geometry`

แผงใหม่แสดงระดับ ระยะที่ใช้ตรวจแบบมีเงื่อนไข และแรง U ต่อขา ณ ขีดกำลังของคำตอบปัจจุบัน ไม่เพิ่มข้อมูลที่ผู้ใช้ต้องกรอก การเปลี่ยน input ทำให้ผลเก่า stale; Summary/Report/QA และการเปิดแผงไม่เรียก solver

## งานที่ยังขาดก่อนยอมรับกำลัง full composite

ต้องสร้าง stress field/STM ที่มีขอบเขต node, strut faces, tie transfer และ anchorage/splitting ครบจริง โดยใช้ตำแหน่ง U/เหล็กพื้นและแรงที่จุดรายงาน CSI ปัจจุบัน การตรวจใหม่ให้ข้อจำกัดด้านระยะที่วัดได้สำหรับงานนี้ แต่ไม่ได้สร้าง Acn หรือกำลัง node ขึ้นเอง

LP เดิมยังใช้ fixed angle, Vc=0/cohesion=0 และ assumed concrete/longitudinal budgets; M2/V3, end D-regions, การรับแรงที่จุด CSI ครบทั้งระบบ, resistance factor และ independent structural validation ยังต้องพัฒนา ไม่มี accepted Vn/Tn/V–T จากโมเดลร่วมในรุ่นนี้

แหล่งวิธี: AASHTO LRFD 9th Edition (2020) 5.8.2.4.2, 5.10.8.2.4a, 5.10.8.2.6d ในไฟล์มาตรฐานที่ผู้ใช้ให้ และ [FHWA-NHI-17-071 STM Design Examples](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf) คู่มือ FHWA อ้างอิง AASHTO 8th Edition ใช้ประกอบแนวทาง node/anchorage ไม่แทนข้อกำหนด 2020

## Repo summary

Trace actual U/slab anchorage planes, reuse exact Calculate states, and remove duplicate shear-model rendering; preserve every nominal resistance and original CSI Tu.
