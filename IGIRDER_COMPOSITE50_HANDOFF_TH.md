# IGIRDER.COMPOSITE50 — whole-girder interface shear

พัฒนาจาก `concrete-section-pro_IGIRDER-VN49.zip` เพื่อแก้เส้นทางแรงเฉือนที่รอยต่อของหน้าตัดประกอบ และอธิบายการใช้กำลัง U สองขาให้ตรวจย้อนกลับได้ รุ่นนี้ยังเป็น nominal model สำหรับทบทวนทางวิศวกรรม ยังไม่ใช่กำลัง full composite ที่ตรวจยืนยันครบสำหรับออกแบบจริง

## สิ่งที่แก้

1. โมเดลเดิมให้รอยต่อรับ longitudinal shear เฉพาะแขนง U ทั้งที่ใช้ slab กำหนดความลึกของหน้าตัดประกอบ รุ่นนี้ให้แรงเฉือนรวม `V_I + V_U` ผ่านการตรวจรอยต่อร่วมกัน
2. แยก `d interface` ออกจาก `dv web` โดยคำนวณจาก centroid ของกลุ่มเหล็กด้านล่างที่ใช้ใน Interface Shear เดิม ถึงกึ่งกลางความหนา slab ตามแนวทาง AASHTO LRFD 9th Edition, Article 5.7.4.5
3. U สองขายังคงใช้กำลังจริงร่วมกันสำหรับแขนง V/T และแรงยึดรอยต่อ เหล็กปลอก I และเหล็กยาว I/พื้นยังอยู่ใน inventory เดิม ไม่บวกกำลังเหล็กชุดเดียวซ้ำ
4. ตรวจสมดุลและข้อจำกัดกำลังซ้ำในหน่วยจริง แยกจากเมทริกซ์และ dual ของ LP ทั้ง 5 คำตอบต่อแถว: V, T, V–T, V ที่คง M/N จริง และ T ที่คง M/N จริง
5. เพิ่มตาราง AASHTO shear reference จากแถวแรงเดียวกัน: กำลัง web ที่มี `Vc + Vs(I)` และกำลังรอยต่อที่นับขา U เป็น Avf เปรียบเทียบแบบต่ออนุกรมโดยใช้ค่าต่ำสุด
6. หน้า Vn แสดงระยะทั้งสอง, แรงยึดของ U แต่ละขา, shear flow ที่แรงจริงและที่ขีดกำลัง nominal และตัวควบคุมกำลังโดยไม่เพิ่มช่องกรอกหรือปุ่มรัน
7. แก้การพิมพ์ A4 ที่ตัดด้านขวาของกราฟและตาราง: ใช้ภาพเวกเตอร์จากกราฟที่แสดงอยู่และตาราง HTML ตามมาตรฐานเดิมของแอป ปรับขนาดตามหน้ากระดาษ และคืนกราฟ interactive หลังพิมพ์ ไม่เรียก solver หรือสร้างภาพจากเซิร์ฟเวอร์เพิ่ม

สมการรอยต่อของโมเดลประกอบปัจจุบัน:

```text
V = VI + VU
d_interface = y_slab_mid - y_tension_steel
Σ Sx,j = (VI + VU) / d_interface
|Sx,j| ≤ μ Cj
```

`V`: N, `d`: mm, `Sx` และ `C`: N/mm ตามความยาวคาน; N/mm มีค่าเชิงตัวเลขเท่ากับ kN/m ระยะนี้เป็นเรขาคณิตในการตรวจรอยต่อ ไม่ใช่การย้ายแรง Tu จากจุดรายงาน CSI

โมเดลร่วมยังใช้ `Vc=0`, cohesion=0, มุม θ คงที่ และ shared concrete-flow ceiling ตามสมมติฐานเดิม ส่วน AASHTO reference ใช้ Vc และ cohesion ตาม code route ที่แยกไว้ ตารางทั้งสองมีนิยามต่างกันและไม่มีการนำกำลังมาบวกกัน

U อาจใช้กำลังทั้งหมดเป็นแรงยึดรอยต่อ ขณะที่ solver จัดสรรแรงเฉือนแนวดิ่งเข้าทาง I มากกว่า จึงต้องอ่านแรงขา U ที่แสดงคู่กับ V_U เสมอ ค่า V_U=0 เพียงคอลัมน์เดียวไม่ได้แสดงการใช้กำลัง U ทั้งระบบ

## ผลจาก JSON โครงการเดิม

ต้นทาง: `concrete_section_pro_project_31_COVER38.json`

- SHA-256: `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`
- 640 source vectors จาก 2 imported girder banks; คำนวณ nominal model ได้ครบ 608 แถวภายในช่วงคาน
- 32 แถวที่ x=0 และ 20 m ระบุแยกเป็น end-region scope; ไม่สร้างกำลังสมมติที่ปลายคาน
- 122 แถวที่ torque ต่ำกว่า threshold ยังคำนวณได้
- source forces, section, reinforcement, interface inputs และ Tu ต้นทางไม่ถูกแก้
- ชุด regression ตัดคอลัมน์ตำแหน่ง strand x ออกจากสำเนาในหน่วยความจำ เพื่อยืนยันว่าโมเดล y-layer ไม่ต้องการพิกัด x ที่ไม่ใช้ ไฟล์ JSON จริงยังเหมือนเดิม
- ข้อมูลวิเคราะห์ที่นำเข้ามี 2 girder banks แม้เรขาคณิตสะพานจะมี 6 girders ไม่สร้างแรงของอีก 4 girders ขึ้นเอง

| Girder | x ควบคุมเฉือนล้วน (m) | Case / step / location | Model Vn ที่ M/N จริง (kN) | Nominal V D/C | Nominal V–T D/C ที่ควบคุม |
|---|---:|---|---:|---:|---:|
| Interior Girder 2 | 14.0 | U2A / Max / After | 600.274 | 0.790 | 1.554 ที่ x=2 m |
| Left Exterior Girder | 6.0 | U2A / Min / Before | 600.274 | 0.813 | 0.938 ที่ x=18 m |

V-only คง M3/N จริง ตั้ง T=0 และคง θ จากเวกเตอร์แรงร่วมต้นทาง ส่วน V–T ใช้ V/T ที่เกิดร่วมกันในแถวเดียว ไม่ใช้ค่าสูงสุดจากต่างแถวมารวมกัน

เมื่อเทียบ VN49 ด้วย source vector เดียวกันทุกแถว:

- pure Model Vn เปลี่ยน 595/608 แถว; V-only D/C เปลี่ยน 608/608 แถว
- pure Model Tn และ T-only D/C ไม่เปลี่ยนทั้ง 608 แถว
- nominal V–T D/C เปลี่ยน 114 แถว แต่ค่าควบคุมสูงสุดของทั้งสอง girder ยังเท่าเดิม
- 58 แถวเกิน nominal V–T; ทั้งหมดอยู่ใน Interior Girder 2
- independent force audit ผ่านทั้ง 608 แถว × 5 คำตอบ; ความคลาดเคลื่อนสัมพัทธ์สูงสุดประมาณ `3.04e-14`

ที่แถวเฉือนล้วนควบคุมของ Interior x=14 m: |Vu|=474.341 kN, Model Vn=600.274 kN และ AASHTO reference แบบต่ออนุกรมมี φV=1,418.414 kN ตัวเลขต่างกันเพราะ reference มี Vc และ cohesion และใช้ข้อกำหนด code shear คนละชุดกับ LP จึงไม่ถือว่าค่าที่สูงกว่าเป็น full-composite V–T resistance โดยอัตโนมัติ

## วิธีใช้

1. เปิดโปรเจกต์ JSON เดิมในแอปรุ่นนี้
2. เข้า Analysis → ULS Strength → Shear
3. กด `Calculate Shear — all 2 girders (current model)` ครั้งเดียว
4. เปิด `Girder: ...` เพื่อดูกราฟ, Vn, การใช้แรงขา U, shear flow ที่รอยต่อ และ AASHTO reference

Torsion และ Shear + Torsion ใช้โมเดลร่วมที่คำนวณไว้แล้วเมื่อ input hash ตรงกัน การเปลี่ยนข้อมูลจะทำให้ผลเดิม stale การเปิดดูหน้าและ Summary/Report ไม่เรียกตัวคำนวณโมเดลซ้ำ

## ขอบเขตที่ยังต้องพัฒนา

- ยังต้องพิสูจน์ stress field และ strut/node/anchorage ของเส้นทาง U–slab ให้ครบตามวิธีที่เลือก การตรวจความยาว hook ผ่านเพียงอย่างเดียวไม่ใช่หลักฐานปิด torsion cage
- Vc=0 และการกำหนด concrete-flow/longitudinal pools ของ LP ยังไม่ใช่วิธีกำลังที่ตรวจยืนยันกับระบบจริงครบถ้วน
- AASHTO reference นับ U เป็นเหล็กรอยต่อ การให้ U เป็นปลอกเฉือนตาม code ยังต้องตรวจการยึดปลายล่างและการครอบคลุมหน้าตัดให้ครบ
- approximation รอยต่อรุ่นนี้ครอบคลุม positive bending การดัดกลับที่ slab เป็นด้านดึงระบุเป็น scope blocked โดยไม่เดาระยะ
- M2/V3, พฤติกรรมรอยต่อภายใต้แรงบิดทั้งระบบ, กำลังที่จุดอ้างอิง CSI และ end D-regions ยังไม่ผ่านการตรวจยืนยันครบ
- ไม่มี resistance factor ที่ยืนยันสำหรับโมเดลร่วมนี้ ค่า accepted Vn/Tn/V–T จึงยังเป็น null
- effective-width และ continuity flags เดิมถูกคงไว้ ไม่เปลี่ยนเป็นยืนยันแล้วให้เอง
- การถอด U ในตาราง same-model comparison เป็นการถอด connector จากหน้าตัดประกอบเดิม ภายใต้ c=0 กำลังถ่ายเฉือนของหน้าตัดประกอบอาจเป็นศูนย์ ค่านี้ไม่ใช่กำลัง I-girder เดี่ยว

วิธีที่ต้องพัฒนาต่อคือสร้างและตรวจ stress field/STM ของรอยต่อและบริเวณปิด U–slab ให้ครบ หรือใช้แบบจำลองวัสดุที่เหมาะสมพร้อม validation อิสระ การทดสอบซอฟต์แวร์ผ่านไม่แทนหลักฐานด้านนี้

## Verification

- 308 selected tests ผ่าน; ไม่ใช่ full repository suite
- มี analytical interface limit, invalid-depth guard, no-connector limit, signed V/T, tampered-witness rejection, native-SI code reference และ regression เดิม
- replay JSON ครบ 608 interior rows ใช้เวลาประมาณ 51 วินาทีในสภาพแวดล้อมทดสอบ
- AppTest ของ app.py จริง: Calculate Shear/Torsion/V–T เรียกโมเดลร่วม 2/0/0 ครั้งตามลำดับ; redraw ไม่เพิ่ม solver calls
- ผล browser/print QA สรุปอยู่ใน release note และ `qa/evidence/igird_composite50/browser_qa.json`
- ตรวจ A4 portrait และ A3 landscape รวมถึงการคืนกราฟหลังพิมพ์; ตาราง primary Shear และกราฟ 0–20 m แสดงครบ การทดสอบไม่ครอบคลุมเบราว์เซอร์และกระดาษทุกชนิด
- compile app.py และ Python modules ที่แก้ทั้งหมด

Project JSON ยังบันทึก input ตามพฤติกรรมเดิม ไม่เพิ่มการบันทึก analysis cache; สูตร Flexure, SLS และ CSI force import ไม่ได้แก้ใน milestone นี้

## แหล่งอ้างอิงวิธี

- AASHTO LRFD Bridge Design Specifications, 9th Edition (2020), Section 5 ที่ผู้ใช้ให้มา: 5.7.2.7, 5.7.3 และ 5.7.4.1–5.7.4.5
- [FHWA, PSC Girder Design Example, Step 5.7.7](https://www.fhwa.dot.gov/bridge/lrfd/pscus057.cfm): ตัวอย่างตรวจ horizontal interface shear จากแรงเฉือนรวม เป็นตัวอย่างต่าง edition จึงไม่ใช้ค่าคงที่ผิวรอยต่อรุ่นเก่ามาแทนค่าตาม AASHTO 2020
- [FHWA-NHI-17-071, Strut-and-Tie Modeling for Concrete Structures](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf): หลักการตรวจเส้นทางแรง strut/tie/node/anchorage ที่ยังต้องทำให้ครบสำหรับโมเดลประกอบ

## Repo summary

```text
Fix whole-girder interface shear transfer, audit shared U-leg forces, expose AASHTO reference checks, and prevent A4 clipping of Shear charts and tables while retaining design-validation gates.
```
