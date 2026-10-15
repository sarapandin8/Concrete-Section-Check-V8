# IGIRDER.DOWEL28 — เหล็กข้ามรอยต่อ I-girder / top slab

วันที่ 15 ตุลาคม 2026 · พัฒนาต่อจาก EQUILIBRIUM27

แอปรับแหล่งเหล็กข้ามรอยต่อเป็น dowel แยกจากปลอก I-girder แล้ว เพื่อให้การตรวจ interface shear ใช้ขนาด จำนวนขาที่ข้ามรอยต่อ ระยะเรียง และ fy ของเหล็กที่ทำหน้าที่จริง การเพิ่มปลอก I-girder จึงไม่เพิ่ม Avf ของ dowel แบบแยกโดยอัตโนมัติ โหลด CSiBridge จุดอ้างอิงแรง และเหล็ก slab ตามยาวเดิมยังคงเดิม

## ข้อมูลจากรูปและไฟล์เดิม

รูป C–C / D–D / E–E แสดง dowel DB12 @70 / @150 / @200 ตามลำดับ โดยการตีความรายละเอียดที่ใช้เตรียมข้อมูลนี้นับสองขาตั้งที่ข้ามรอยต่อในหนึ่งชุด ส่วนปลอกปิดของ I-girder เป็นเหล็กอีกชุดหนึ่ง

| หน้าตัด | Dowel | ขาข้ามรอยต่อต่อชุด | พื้นที่เหล็กข้ามรอยต่อต่อความยาว 1 m |
|---|---|---:|---:|
| C–C | DB12 @70 mm | 2 | 3,231.35 mm²/m |
| D–D | DB12 @150 mm | 2 | 1,507.96 mm²/m |
| E–E | DB12 @200 mm | 2 | 1,130.97 mm²/m |

คำนวณจาก n × πdb²/4 × 1000/s ข้างต้นเป็นปริมาณเหล็กตามรายละเอียด ไม่ใช่ผลรับรองกำลังหรือการฝังยึด จำนวนขาหมายถึงขาที่ตัดผ่านรอยต่อจริง ไม่ใช่จำนวนขาทั้งหมดของปลอก I

จุดที่ต่างจากข้อมูลเดิมคือปลอก transition ของ I-girder ใน JSON ใช้ @100 mm ขณะที่ dowel D–D ในรูปใช้ @150 mm จึงต้องมีตารางแยก การเปลี่ยนจาก @100 เป็น @150 ทำให้ปริมาณเหล็กข้ามรอยต่อที่มีขนาดและจำนวนขาเท่ากันลดลงหนึ่งในสาม แต่กำลังรอยต่อรวมไม่ได้เปลี่ยนในสัดส่วนเดียวกันเสมอ เพราะยังมี cohesion และขีดจำกัดของสมการกำลัง

รูปหน้าตัดไม่ได้ระบุช่วงตามยาวของ C/D/E ผู้ใช้เลือกกรอกช่วง dowel แยก จึงเว้น x_start_m / x_end_m เป็น null ทั้งสามรายการในไฟล์ DRAFT ไม่ยืมช่วงปลอก I ไม่สมมติความสมมาตร และไม่เติมความยาวเอง หาก C หรือ D เกิดซ้ำที่ปลายอีกด้าน ให้เพิ่มรายการพร้อมช่วงจริงตามแบบตามยาว

fy = 390 MPa ใน DRAFT มาจากข้อมูลวัสดุโครงการเดิม ไม่ใช่ค่าที่อ่านยืนยันได้จากรูป เหล็ก slab ตามยาวเดิม DB16 @200 ชั้นบน / @150 ชั้นล่างยังคงเดิม ป้ายเหล็กในรูป transverse section ไม่ถูกใช้แทนค่าตามยาวทั้งสองชั้นโดยอัตโนมัติ

## วิธีใช้

1. เปิดชุดแอปใหม่นี้ด้วย `streamlit run app.py` แล้วเปิด `I_Girder_20m_DOWEL28_DRAFT.json`
2. ไปที่ Analysis → ULS → Final Composite และแผง Interface Shear / Composite action — girder/deck interface inputs
3. แหล่งเหล็กถูกตั้งไว้เป็น `Dowel bars — separate layout` เปิด `Dowel layout` แล้วกรอก Start x / End x เป็นเมตรบนแกน station ของสมาชิกเดียวกับ Loads พร้อมตรวจ db, Crossing legs, spacing และ fy ตามแบบจริง
4. ใช้คำประกาศ crossing/development/anchorage เดิมของโครงการให้ตรงกับรายละเอียดจริง แล้ว Calculate Interface Shear และคำนวณผล Final Composite ที่เกี่ยวข้องใหม่

ระยะที่วาดยื่นขึ้น 0.25 m และมิติแนวนอน 0.22 m เป็นข้อมูลรายละเอียด แต่สองค่านี้เพียงอย่างเดียวไม่ยืนยัน development/anchorage ทั้งสองด้าน แอปไม่ได้คำนวณรับรองการฝังยึดใหม่จากรูป และไม่มี checkbox ยืนยันเพิ่ม คำประกาศเดิมถูกใช้กับแหล่งเหล็กที่เลือกอย่างชัดเจน

ตัวเลือกแหล่งเหล็กมีสามแบบ:

| ตัวเลือก | แหล่งขนาด / ระยะ / ช่วง / fy | จำนวนขาที่นับ |
|---|---|---|
| Girder stirrups extended into slab | ตารางปลอก I เดิม | จำนวนขาปลอกในตารางเดิม |
| Dowel bars — use girder zoning, diameter and spacing | ผูกกับตาราง I โดยผู้ใช้เลือกอย่างชัดเจน | จำนวนขา dowel กรอกแยก |
| Dowel bars — separate layout | ตาราง dowel แยก | จำนวนขาข้ามรอยต่อของแต่ละรายการ |

ปุ่ม Copy current girder zoning into separate dowel layout เป็นการคัดลอกเมื่อกดเท่านั้น หลังคัดลอกแล้วตารางเป็นอิสระ ต้องแก้ให้ตรงรายละเอียด dowel จริงก่อนใช้ ไม่ใช่ปุ่มที่จำเป็นสำหรับ DRAFT ที่จัดให้

## พฤติกรรมการคำนวณและการเก็บข้อมูล

เลือกเหล็กแหล่งเดียวในการตรวจ interface ไม่บวกปลอก I เข้ากับ dowel แยก ใช้ Avf และ fy ของแหล่งที่เลือกในสมการ shear friction / เหล็กขั้นต่ำเดิมของ AASHTO LRFD 2020 ข้อ 5.7.4 โดยคง phi, cohesion, friction, ขีดจำกัด fy 60 ksi และ Pc = 0 เดิม

เมื่อข้อมูลไม่ครบ ช่วงไม่ครอบคลุมสถานี ช่วงซ้อน หรือไม่ยืนยันการข้ามรอยต่อและการฝังยึด ระบบไม่ให้เครดิตเหล็กที่ไม่พร้อม และแสดง REVIEW โดยไม่ย้อนกลับไปใช้ปลอก I แทน เมื่อสถานีตรงรอยต่อสองช่วง ใช้กำลังส่วนเหล็กของช่วงที่อ่อนกว่า ไม่บวกพื้นที่ทั้งสองช่วง ข้อยกเว้นเหล็กขั้นต่ำสำหรับปลอกที่ยื่นและฝังยึดตามเงื่อนไขเฉพาะเดิมไม่ถูกแสดงเป็นสิทธิ์ของ dowel แยกโดยอัตโนมัติ

Calculation trace เพิ่ม Connector source, Connector zone, db, crossing legs, spacing และ Avf source basis JSON เก็บเฉพาะ input dowel พร้อม null ที่ยังไม่ทราบ เมื่อแก้ข้อมูลรอยต่อ ผล ULS เดิมที่เกี่ยวข้องถูกล้างเพื่อให้คำนวณใหม่ ไม่มีการเพิ่มการบันทึก solver-result cache ถาวร และไม่มี solver rerun จากการเปิด Summary / Report

ไฟล์ DRAFT ยังคง raw Loads / force-reference snapshots, geometry, materials, เหล็ก slab และตารางปลอก I ของ CSIREF26 เดิม การแก้เฉพาะข้อมูล interface และการถอด analysis_results ที่เก่าได้รับการตรวจด้วยการเทียบข้อมูลทั้งโครงการ คำประกาศ anchorage เดิมยังเก็บเป็น generic connector declaration ส่วน legacy stirrups_cross_and_anchored ถูกตั้ง false สำหรับ dowel เพื่อไม่ให้แอปรุ่นเก่าเข้าใจว่าเป็นปลอก I ที่ยื่นเข้า slab

## ผลตรวจ

- Compile app.py และโมดูลที่เพิ่ม/เปลี่ยนผ่าน
- Selected targeted/regression tests ผ่าน 211 รายการ ไม่มี failure/error/skip รวม 20 test cases ของโมดูล DOWEL28
- ครอบคลุมการคำนวณปริมาณจากรูป แยก dowel จากการแก้ปลอก I, linked leg count, missing/gap/overlap/invalid input, conservative boundary, คัดลอกแล้วอิสระ, ไม่มีการนับซ้ำ, anchorage declaration, JSON null, stale-result invalidation และ UI persistence
- UI ทดสอบด้วย Streamlit AppTest ไม่เพิ่ม checkbox จากเดิมหนึ่งตัว ยังไม่มี browser screenshot verification ของแผงใหม่นี้
- ทดสอบไฟล์ DL จริงที่ Interior Girder 1, x = 10.45714 m: DRAFT ที่ยังไม่ทราบช่วงให้ REVIEW และ Avf credited = 0 mm²/m ไม่มีการใช้ปลอก I แทน
- SHA-256 ของ Excel DL ก่อน/หลังตรงกัน ปริมาณเหล็กในตารางข้างต้นตรวจด้วย probes สำหรับสมการเท่านั้น ไม่ใช้ช่วงสมมติเหล่านั้นใน DRAFT หรือผลออกแบบ
- ไม่ได้รัน full-repository suite ใน milestone นี้ และไม่ได้อ้างว่าแก้ข้อไม่ผ่านเดิม 7 ข้อที่บันทึกใน CSIREF26

หลักฐานอยู่ที่ `qa/evidence/igird_dowel28/` และสคริปต์ตรวจไฟล์จริง `qa/igird_dowel28_actual_review.py`

## ขอบเขตกำลังที่ยังไม่ครบ

รุ่นนี้แก้แหล่งเหล็กสำหรับ longitudinal interface shear checker เดิม ซึ่งใช้ demand จาก Vu/(bvi dv) ยังไม่ใช่แบบจำลอง traction จาก torque, uplift, slip หรือการกระจายแรงสามมิติเต็มรูปแบบ การมี dowel ไม่ได้ทำให้ slab ทั้งแถบเป็น closed torsion cage อัตโนมัติ และไม่เพิ่ม Ao/ph หรือให้เครดิต longitudinal Al จาก dowel

Full composite shear–torsion และ P–M2–M3 resistance ยังไม่เสร็จ กลไก I-hoop และเงื่อนไข REVIEW ของรุ่นก่อนยังอยู่ จึงยังสรุปว่ากำลังเฉือน/บิดรวมเพิ่มขึ้นหรือรับรองการใช้ Girder resultants ครบทุกองค์ประกอบไม่ได้

เอกสารอ้างอิง: AASHTO LRFD 9th Edition (2020), Section 5, 5.7.4 จากเอกสารโครงการ; [FHWA prestressed-girder interface shear example](https://www.fhwa.dot.gov/bridge/lrfd/pscus057.cfm) ใช้อธิบายเหล็กที่ข้ามรอยต่อจริง โดยเลขข้อในตัวอย่างเป็นฉบับเก่ากว่า; [WSDOT additional interface reinforcement](https://www.wsdot.wa.gov/eesc/bridge/software/Documentation/PGSplice/8.1/ug_dialogs_girder_details_additional_interface_shear_reinforcement.html)

Repo summary:

```text
IGIRDER.DOWEL28: Select independent dowel Avf for girder–slab interface checks; preserve I-hoop resistance and existing Loads; persist null-safe zoning and invalidate stale results. 211 selected tests passed.
```
