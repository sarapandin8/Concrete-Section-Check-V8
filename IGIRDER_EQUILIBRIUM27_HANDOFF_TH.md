# IGIRDER.EQUILIBRIUM27 — ตรวจสมดุล Girder / Beam / Slab

วันที่ 15 ตุลาคม 2026 · พัฒนาต่อจาก CSIREF26 ที่ส่งมอบแล้ว

เพิ่มตัวตรวจสมดุลแรงทั้งหกจาก worksheets Girder, Beam และ Slab ในไฟล์เดียวกัน หลังถ่ายโมเมนต์มาที่จุดเดียวกัน พร้อมแยกส่วนประกอบของ Tu ในหน้า Loads รุ่นนี้เป็นการเตรียม demand ให้ตรวจสอบย้อนกลับได้ก่อนพัฒนากลไก composite shear–torsion ไม่ได้เพิ่ม nominal resistance หรือเปิดให้ผลตรวจที่ยังไม่ครบเป็น PASS

## วิธีใช้

เปิดแอปด้วย `streamlit run app.py` ใช้ Project JSON ของ CSIREF26 เดิมได้ ใน Loads → ULS อัปโหลดไฟล์ที่มี worksheets Girder / Beam / Slab ตามเดิม แล้วเปิด `Girder / Beam / Slab force equilibrium`

สำหรับไฟล์ DL ตัวอย่าง เลือก Force source เดิมเป็น `Static case / explicit step` เพื่อระบุว่าเป็น static state เดียวกัน ไม่มี checkbox หรือช่องยืนยันใหม่จาก milestone นี้ ไฟล์ที่มีเฉพาะ Girder ยังนำเข้าได้เหมือนเดิมและไม่สร้างการตรวจ component ที่เดาขึ้นมา

แผงตรวจแสดงสรุปแต่ละ Girder, ระยะเยื้องที่ระบุจากข้อมูล และการแตกค่า torque ที่จุด |Girder T| สูงสุด พร้อมดาวน์โหลด CSV ของทุกจุดตัด การเปลี่ยน source dropdown และเปิดดูผลตรวจไม่แก้ตัวเลข Loads, project reference setting หรือผล Analysis ที่เก็บไว้

## สมการและการระบุจุดอ้างอิง

ใช้ r ของแต่ละ component เทียบกับจุดรายงาน Girder, หน่วย m/kN/kN-m และ convention CSI ตาม CSIREF26:

```text
P_G  = P_B + P_S
V2_G = V2_B + V2_S
V3_G = V3_B + V3_S
T_G  = T_B + T_S + r2B V3_B + r2S V3_S − r3B V2_B − r3S V2_S
M2_G = M2_B + M2_S − r3B P_B − r3S P_S
M3_G = M3_B + M3_S − r2B P_B − r2S P_S
```

อ่านและแปลงหน่วยด้วยตัวนำเข้า CSI เดิม ระบุ r2 จากสมการ P/M3 และ r3 จาก P/M2 โดยไม่ fit ค่า T จากนั้นตรวจ T เป็น independent prediction ทั้งชุดและสถานี holdout ซึ่งแยกตามตำแหน่ง station ทั้งสถานี จึงไม่เอาหน้าตัดคนละ face ที่ x เดียวกันไปอยู่คนละชุดฝึก/ตรวจ

ค่า offsets เป็นการระบุเชิงประจักษ์จากแรง ไม่ใช่ metadata จุดกำเนิดที่ CSiBridge ส่งมา ระบบไม่เอาค่านี้ไปแก้ CSI reference profile หรือใช้คำนวณกำลังอัตโนมัติ สมมติว่าแกน local ของ component ตรงกันอยู่แล้ว ไม่ได้ระบุการหมุนแกนจากข้อมูลนี้ ความสอดคล้องทางสมดุลไม่ได้พิสูจน์ load path, cracking, reinforcement, interface strength หรือความถูกต้องทั้งหมดของ FE model

แยกตาม source file, bridge/member, case, case type, step, step number, control identity, cut face, section cut, occurrence และ station ไม่ใช้ผล fit ข้ามไฟล์หรือข้าม load state หากชุดจุดตัดของทั้งสามชิ้นไม่ตรงกัน จะไม่จับคู่บางส่วน หากสมการระบุสอง offsets ไม่ได้อย่างอิสระหรือไม่มีสถานีพอสำหรับ holdout จะรายงาน ORIGIN UNRESOLVED

Tolerance สำหรับตรวจความสอดคล้องของ export คือ 0.005 kN / kN-m ไม่ใช่ allowable load หรือเกณฑ์กำลังออกแบบ ไม่เรียกผลสมดุลว่า design PASS

## ผลตรวจไฟล์จริง

| ชุดข้อมูล | ผล |
|---|---|
| DL / DEAD | 6 Girder × 46 จุดตัด = 276 จุด สมดุลสอดคล้องทั้งหกองค์ประกอบ |
| Maximum force residual | 0.001000 kN |
| Maximum moment residual | 0.000569141 kN-m |
| Maximum holdout moment residual | 0.000719466 kN-m |
| U2A | 12 กลุ่ม Girder/Max-Min แสดง ENVELOPE — NO VECTOR SUM ไม่ fit offsets |
| ไฟล์ Excel ต้นทาง | SHA-256 ก่อนและหลังตรงกัน |

ตัวอย่าง DL, Interior Girder 2, x = 18.76071 m, occurrence 2:

| ส่วนประกอบ torque | kN-m |
|---|---:|
| Beam T ที่จุด B | −0.856400 |
| Slab T ที่จุด S | +6.947500 |
| r2B V3_B | −1.346616 |
| r2S V3_S | +39.964964 |
| −r3B V2_B | −0.000115 |
| −r3S V2_S | −8.250910 |
| รวมเมื่อถ่ายมาที่จุด Girder | +36.458423 |
| Girder T จาก CSI | +36.458500 |

ตัวอย่างนี้แสดงว่าค่า Girder T มีส่วนจากแรงเฉือนและระยะเยื้องมากกว่าค่า Beam T เพียงอย่างเดียว ไม่ได้อนุญาตให้ใช้ Beam T ที่น้อยกว่าแล้วละเลย slab/interface หรือใช้ผลรวมกำลังของสองชิ้นแทนการตรวจทั้งระบบ

Max/Min ของแต่ละ component อาจถูกควบคุมด้วยคนละตำแหน่งรถหรือสถานะโหลด แม้แต่ละแถวมีคำประกาศ correspondence ก็ยังไม่ได้ระบุว่าทั้งสาม component ใช้สถานะเดียวกัน ตัวตรวจนี้จึงไม่เอา extrema จากทั้งสามแผ่นมาบวกหรือ fit ระยะเยื้องให้

## การตรวจโค้ด

- Compile app.py และโมดูลที่เพิ่ม/เปลี่ยนผ่าน
- ชุด targeted/regression 178 รายการผ่าน รวม 15 รายการใหม่ของ EQUILIBRIUM27 ครอบคลุม force reconstruction, horizontal eccentricity, torque holdout, unit conversion, rank deficiency, grid/face/step mismatch, envelope rejection, member/case isolation, duplicate components, malformed workbook handling และ read-only UI
- ชุดเดิมของ CSIREF26, ULS/SLS import, source declarations, composite flexure และกราฟอยู่ใน 178 รายการนี้
- UI ผ่าน Streamlit AppTest โดยไม่แก้ Loads, project metadata หรือ Analysis cache แต่ยังไม่มี browser screenshot verification สำหรับแผงใหม่นี้
- ไม่ได้อ้าง full-repository suite PASS; ข้อไม่ผ่านเดิม 7 ข้อที่บันทึกใน CSIREF26 ไม่ได้ถูกแก้ใน milestone นี้

## ขอบเขตที่ยังค้างและข้อมูลที่ต้องใช้

Full composite V2/V3/T resistance และ P–M2–M3 resistance ยังไม่เสร็จ I-girder hoop route และเงื่อนไข REVIEW เดิมยังทำงานอยู่ ยังไม่เปลี่ยน Ao, ph, f'c หรือให้เครดิตเหล็ก slab เพิ่มจากผล audit นี้

ขั้นกำลัง composite shear–torsion ต้องระบุกลไกรับแรงและรายละเอียดเหล็กจริง โดยเฉพาะเหล็กตามขวางของ slab, เหล็ก/การฝังยึดข้ามรอยต่อ slab–girder และการต่อเนื่องของ closed transverse/longitudinal reinforcement ไม่มีข้อมูลเหล่านี้ในผลแรงหกองค์ประกอบ จึงไม่สมมติว่า slab ทั้งแถบอยู่ใน closed torsion cage โดยอัตโนมัติ

ไม่มีการเปลี่ยนสูตรกำลัง ULS/SLS เดิม ไม่มี solver rerun ใน Result Summary / Report-QA ไม่มีการเพิ่ม persistent solver-result cache และไม่มี audit row ใดถูกนำไปเป็นผลออกแบบของ Analysis

Repo summary:

```text
IGIRDER.EQUILIBRIUM27: Audit common-origin Girder=Beam+Slab equilibrium, expose torsion contributions, reject envelope reconstruction, and preserve Loads/strength logic. 178 selected tests passed.
```
