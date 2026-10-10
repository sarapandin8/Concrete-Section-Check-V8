# Concrete Section Pro — IGIRDER.REBARADVISOR13

เพิ่มคำแนะนำแก้ φTn และ Shear + Torsion จากไฟล์โครงการจริง โดยแสดงตำแหน่งที่คุมและขนาด/ระยะเหล็กปลอกที่ควรทดลอง พร้อมปุ่มคำนวณตรวจทุก case ของทุกคานอีกครั้ง

## เปิดใช้งาน

1. แตก ZIP และรัน `streamlit run app.py` ด้วย dependencies ใน `requirements.txt`
2. โหลด `I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck350.json` ฉบับเดิม
3. เข้า **Analysis → ULS Strength → Shear + Torsion** แล้วกด **Calculate Shear + Torsion — all … girders**
4. ดูตาราง **Reinforcement advisor — ตำแหน่งและวิธีแก้ไข** และกด **Calculate trial — ตรวจชุดปลอกที่แนะนำทุกคาน**
5. อ่าน **Trial remaining actions** เลือก **Action details** เพื่อดูข้อความเต็มและ case ที่คุม
6. หากเลือกใช้ชุดปลอกหลังตรวจรายละเอียดแบบจริง ให้แก้ **Sections → Rebar → Beam/Girder Shear Reinforcement Layout** แล้ว Calculate checks สำหรับ production ใหม่

## ผลจากไฟล์นี้

ระยะ x วัดจากปลายคานด้านซ้าย ข้อเสนอใช้ทั้งช่วง Zone ที่มีอยู่และเป็นตารางปลอกร่วมสำหรับทั้งสองคาน จำนวนขา 2 ขา และ fy 390 MPa คงตามข้อมูลเดิม

| ช่วง x (ม.) | Zone | ปลอกเดิม | ชุดทดลองที่ตรวจแล้ว | V+T transverse D/C สูงสุดหลังปรับ |
|---|---|---|---|---:|
| 0–1.5 | Left support | DB12 @70 มม. | DB12 @50 มม. | 0.955 |
| 1.5–4.5 | Left transition | DB12 @100 มม. | DB12 @80 มม. | 0.923 |
| 4.5–15.5 | Midspan | DB12 @200 มม. | DB12 @80 มม. | 0.979 |
| 15.5–18.5 | Right transition | DB12 @100 มม. | DB12 @50 มม. | 0.983 |
| 18.5–20 | Right support | DB12 @70 มม. | DB16 @70 มม. | 0.887 |

ชุดนี้ผ่านตัวเลข φTn, transverse V+T, shear strength/minimum และระยะปลอกครบ 10 คู่คาน/Zone ที่ตรวจ **ยังไม่ใช่ overall PASS** ผล overall V+T เป็น FAIL 8 คู่ และ REVIEW 2 คู่

ค่า Minimum trial spacing เริ่มต้น 50 มม. เป็นเงื่อนไขจัดเหล็กสำหรับการทดลองที่ผู้ใช้เปลี่ยนได้ ไม่ใช่ระยะขั้นต่ำจากมาตรฐาน หากแบบจริงยอมให้ระยะต่ำกว่านี้ แอปอาจเสนอใช้ขนาดเดิมแทนการเพิ่มขนาด ต้องตรวจ cover, การดัด/ยึดปลอก, ระยะห่างเหล็กและความหนาแน่นของกรงเหล็กจริงด้วย

## จุดที่ยังต้องแก้หลังเพิ่มปลอก

| คาน | x ที่คุม (ม.) | ด้านรับแรงดึง | Longitudinal D/C | แรงตามยาวที่ยังขาด (kN) |
|---|---:|---|---:|---:|
| Left Exterior Girder | 1 | ล่าง | 1.028 | 69.4 |
| Left Exterior Girder | 2 | ล่าง | 1.047 | 163.8 |
| Left Exterior Girder | 5 | ล่าง | 1.029 | 162.2 |
| Interior Girder 2 | 15 | ล่าง | 1.058 | 324.7 |
| Interior Girder 2 | 18 | ล่าง | 1.140 | 484.5 |
| Interior Girder 2 | 19 | ล่าง | 1.144 | 357.5 |

แรงที่ขาดเป็นผลคำนวณของชุดทดลองนี้ ไม่ใช่พื้นที่เหล็กที่เพิ่มแล้วรับประกันผ่าน การปรับเหล็กตามยาว/strand ต้องคำนวณ εs, θ, fps, development และ force equation ใหม่พร้อมกัน

ใกล้ปลายคานยังมีเงื่อนไข `Aps_developed × fps > As_developed × fy` ที่ไม่ผ่าน แม้บางแถวมี force D/C ≤ 1 ต้องตรวจด้านรับแรงดึง ตำแหน่ง strand, transfer/development/debonding และความเหมาะสมของ route; การเพิ่ม As อย่างเดียวอาจทำให้เงื่อนไขนี้แย่ลง

แรงนำเข้าทุกชุดมีเครื่องหมาย **ENVELOPE — REVIEW** และยังไม่ได้ยืนยัน concurrency แอปคงสถานะนี้ไว้ ต้องตรวจชุด Mu, Nu, Vu, Tu ที่เกิดพร้อมกันจาก case/step/ตำแหน่งเดียวกันและหลักฐานต้นทาง อีกทั้งข้อมูลการพัฒนากำลัง deck, interface girder–deck, effective-depth source และ negative composite scope ยังต้องตรวจตามรายการ Required actions

## สิ่งที่เพิ่มในแอป

- ตารางคำแนะนำจากทุก case และทุก station ที่เป็นผลปัจจุบัน แยกจาก case ที่เลือกดูบนกราฟ
- ระบุช่วงปลอกที่ต้องเพิ่ม จุด/คาน/case ที่คุม และตำแหน่ง sampled failure
- ทดลองลดระยะขนาดเดิมก่อน แล้วเพิ่มขนาดหากต่ำกว่า minimum trial spacing ที่เลือก
- คำนวณชุดทดลองด้วย solver เดิมอย่างชัดเจนผ่านปุ่ม ไม่ใช้การสเกล φTn อย่างเดียว
- แสดงผล transverse numerical checks และ overall V+T พร้อมสาเหตุ longitudinal/source ที่เหลือ
- ดาวน์โหลดตารางปลอกทดลอง ผลตรวจ และรายการแก้ไขเป็น CSV
- แยก trial cache จาก inputs และผล production; เปลี่ยน inputs/options แล้วซ่อนผลทดลองเก่าที่ stale

สูตรวิศวกรรม, solver production, Ao/ph ตามกรงปลอกจริง และรูปแบบ Project JSON ใช้ baseline TORSIONAUDIT12 เดิม ไม่มีการเพิ่มโมเดล deck strip สำหรับเพิ่ม Ao ใน milestone นี้ และไม่มี trial-result persistence ผล trial ไม่ส่งเข้า Result Summary / Report / QA

## การตรวจสอบและไฟล์ประกอบ

คำนวณโครงการจริงใหม่ 2 คาน × 320 source rows ตรวจ case/station/source row/Mu/Nu/Vu/Tu ก่อนและหลังว่าตรงกัน; production inputs และ caches ไม่เปลี่ยนจากการกดชุดทดลอง

ผ่าน scoped tests 191 รายการจาก 9 modules, rerun advisor 16 รายการหลังปรับ UI, compile, actual app.py AppTest และตรวจหน้าจอ Chromium ที่ 1680/1280 px รวมการกดปุ่ม trial จริง หน้าสรุป/รายงานถูก guard ไม่ให้เรียก solver ระหว่าง review และไม่เผยแพร่ผล trial ไม่ได้อ้างว่ารันทดสอบทั้ง repository ครบทุกไฟล์

ไฟล์หลักฐานอยู่ใน `qa/evidence/igird_rebaradvisor13/` ภายใน ZIP รวม CSV ก่อน/หลัง, source rows, validation และภาพหน้าจอ Source JSON ต้นฉบับและ pickle checkpoints ชั่วคราวไม่ได้แพ็กซ้ำ

ต้นฉบับ Project JSON SHA-256:
`12b43739fa137984c5f8ddc1f618e414a67893187d7bb57b29b3ab1de8bfb88d`

Baseline ZIP SHA-256:
`00d3b3ee7cf6d5013f945f5363ee8f2cc62038a9e487ea0c0149f971900edb82`

Repo summary:

```text
Add all-case I-girder stirrup recommendations and explicit isolated trial verification with remaining longitudinal/source actions.
```
