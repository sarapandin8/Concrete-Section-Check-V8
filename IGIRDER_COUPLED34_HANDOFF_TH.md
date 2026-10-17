# IGIRDER.COUPLED34 — ส่งมอบโมเดล coupled เพื่อการทบทวน

รุ่นนี้เพิ่มเครื่องคำนวณ **coupled research model** และคำอธิบายกราฟ Flexure
ที่ขาดตรงปลายคาน ยังไม่ใช่ Full composite Tn / V–T ที่ผ่าน structural validation
สำหรับยอมรับในการออกแบบจริง สถานะ production จึงยังเป็น **WITHHELD**

เริ่มจาก EDIT33 ที่ยอมรับแล้ว SHA-256
`3fdf9007243af31359f83f955b64d0a95b8ee6b7eea6f78666ed05edb28d6233`

## 1. สาเหตุกราฟปลายคานขาด

ตรวจซ้ำด้วย solver จริงจาก JSON อ้างอิงที่มีอยู่
`I_Girder_20m_FLEXURE31_REVIEW.json` SHA-256
`43c17a487707441244d4a366b44009f2f94f2cae93ae097bc61472332e2d47db`
ซึ่งไม่ใช่การอ่าน session ล่าสุดที่ยังไม่ได้ส่งออกเป็น JSON

Left Exterior Girder, x=20 m:

| Case / bound | CSI M3 (kN-m) | CSI P แรงดึงบวก (kN) | Mux ที่จุดอ้างอิงกำลัง (kN-m) | ผลหน้าตัด |
|---|---:|---:|---:|---|
| U1A Max | 0 | +0.795 | −0.151115 | NO EQUILIBRIUM |
| U1A Min | 0 | −0.749 | +0.142371 | มี φMn ประมาณ 0.603444 kN-m |
| U2A Max | 0 | +0.871 | −0.165561 | NO EQUILIBRIUM |

CSI M3 เป็นศูนย์ได้ แต่เมื่อ P กระทำเยื้องจากจุดอ้างอิงกำลัง จะมีส่วนเพิ่มโมเมนต์
จากการย้ายจุดอ้างอิง ในโมเดลนี้ cut end มีระยะพัฒนาแรงเป็นศูนย์สำหรับเหล็กและ
ลวดทุกกลุ่ม จึงไม่มีแรงดึงที่ได้รับเครดิตมารับ P ใน Max และหา axial–flexural
equilibrium ไม่ได้ โปรแกรมจึงเก็บ φMn เป็น unavailable และเว้นเส้นสีแดงไว้
กรณี Min มีแรงอัดเล็กน้อย จึงอาจหาสมดุล compression-controlled ได้

เพิ่มคำอธิบายและตารางใต้กราฟที่ `Why φMn is missing — source / development /
equilibrium` เพื่อแสดงสถานี case ค่า P/M3 การย้ายอ้างอิงและเครดิตเหล็กจริง
ข้อมูลและช่องว่างเดิมยังอยู่ ไม่คัดลอกกำลังจากภายในช่วงไปปิดปลายกราฟ
ต้องตรวจตำแหน่ง cut/bearing และรายละเอียดเหล็กยึดปลายที่มีจริงก่อนแก้ข้อมูล

## 2. ส่วน coupled ที่พัฒนาแล้ว

- คำนวณ nominal **Model Tn** ของวงปิดสมมติส่วนกลาง โดยใช้ระยะขา U เป็น
  ความกว้างวง ไม่ใช้ slab Be แทนความกว้างวงต้านบิด
- คาน เหล็ก U และเหล็กปิดวงใน slab เป็นเส้นทางต่อเนื่องที่ต้องผ่านทุกส่วน
  กำลังถูกจำกัดโดยส่วนอ่อน ไม่บวก Tn ของแต่ละส่วนเข้าด้วยกัน
- แรงใน U-leg ตัวแปรเดียวกันต้องผ่านทั้งข้อกำหนดของ truss และสมดุลรอยต่อ
  รวมแรงเปิด แรงม้วน และ friction/contact ไม่สร้างสำเนากำลัง dowel อีกชุด
- เก็บคู่แรงเฉือนตามยาวที่ทิศตรงข้ามกันจากการไหลของแรงบิดไว้ แม้ผลรวม qx
  เป็นศูนย์ ไม่แทน Girder Tu เป็นแรงม้วน mx ของรอยต่อ
- Model V–T คง M/N ไว้และเพิ่ม V/T พร้อมเวกเตอร์รอยต่อด้วยตัวคูณเดียวกัน
  ใช้กำลังเหล็กตามยาวที่พัฒนาแรงได้ชุดเดียวร่วมกับ M/N และ V/T
- ตรวจสมดุล ขอบเขตกำลัง ความเหมาะสมของคำตอบสูงสุดผ่าน LP duality และ
  ความไวต่อจำนวน contact strips 32/64
- การตรวจ actual V–T ต้องใช้ concurrent Girder/composite vector และจุดอ้างอิง
  CSI ที่ผูกกับไฟล์ ข้อมูล Beam-only, envelope ที่ไม่ยืนยัน concurrency,
  joint state ไม่ครบ/ซ้ำ หรือ M2/V3 ไม่เป็นศูนย์ จะไม่ได้ค่าตัวคูณ combined
- ข้อมูลใหม่ทำให้เฉพาะ research result เป็น stale ไม่ล้างผล Flexure ปกติ

## 3. ขอบเขตที่ต้องอ่านก่อนใช้ตัวเลข

**Model Tn เป็นกำลังของสมมติฐาน ไม่ใช่กำลังออกแบบที่รับรองแล้วของสะพานนี้**
เป็น pure torsion ที่ V=M=N=external joint loads=0 จึงไม่ใช่กำลังบิดที่เหลือ
ขณะมี M/N/V จริง ตัวคูณ Model V–T ก็ยังไม่ใช่ design acceptance

สมมติฐานปัจจุบันคือ cracked truss 45°, Vc=0, cohesion=0, วงปิดสี่เหลี่ยมส่วนกลาง
และกำลัง diagonal concrete ที่ยังไม่ได้ calibrate ตามกฎ stress–strain ของ
คอนกรีตแตกร้าว ใช้ ordinary-bar reserve สองครึ่งหน้าตัดที่อ่อนกว่า และยังไม่ให้
เครดิต prestress ใน reserve ของ research adapter ไม่ได้พิสูจน์การกระจายแรง
เข้ามุมวงและ nodal zones จากตารางเหล็กตามยาวเพียงอย่างเดียว

ยังไม่มี strain/slip/opening compatibility, slab transverse bending,
local splitting, nodal strength, splice bond transfer, dowel bending/shear,
fatigue และ end D-region ครบระบบ และยังไม่มีผลทดสอบกายภาพของชุด
girder–slab–U-dowel นี้รองรับ การผ่าน unit tests จึงไม่ใช่ structural validation

ตัวแอปแสดง `Production acceptance: WITHHELD` และไม่ส่งตัวเลข research ไปเป็น
กำลังออกแบบใน Result Summary / Report / QA ไม่มี checkbox หรือข้อความ
อ้างอิงรูปที่ใช้ปลดล็อก production ได้

ข้อ AASHTO 2020 5.10.8.2.6d ให้ตรวจการต่อเนื่องและการยึดปลายวงต้านบิด
รวมถึงรายละเอียด hook 135° และเงื่อนไข lap ของ paired U units การมี U-dowel
หัก 90° ที่ตรวจพัฒนาแรงดึงผ่าน ไม่ได้พิสูจน์วงต้านบิดรวมโดยอัตโนมัติ
ไม่ได้หมายความว่ารอยต่อ U 90° ไม่สามารถถ่ายแรงบิดได้ แต่ต้องพิสูจน์กลไก
และขอบเขตของระบบนั้นด้วยวิธีที่สอดคล้องกับรายละเอียดจริง

## 4. ใช้งานที่หน้าใด

1. เปิดแอปรุ่นใหม่และโหลด **JSON ล่าสุดของตนเอง** ตามปกติ
2. เข้า Analysis → ULS Strength → Flexure → Final — Composite
3. เปิด Edit composite / dowel inputs → Composite V–T — research model inputs
4. เปิด Include coupled composite model in Calculate หากต้องการทบทวนโมเดลนี้
5. ใช้ geometry, materials, A–F และ dowel zoning เดิม ใส่เพิ่มเฉพาะเส้นผ่านศูนย์กลาง
   และ spacing ของเหล็กขวางปิดวง slab พร้อม actual straight overlap ระหว่าง
   U และ girder hoop แล้วระบุรายละเอียดวงและ drawing reference ตามที่มีจริง
6. กด **Calculate Flexure** ปุ่มหลักเดิม การเปิด/เปลี่ยนมุมมองไม่สั่ง solver ซ้ำ
7. อ่านผลที่ Composite V–T — coupled resistance / validation ใต้ผล Flexure

เหล็ก slab ตามยาวเดิมไม่ได้ถูกนำมาแปลงเป็นเหล็กขวางปิดวงโดยอัตโนมัติ
ค่า F ไม่ได้เท่ากับ actual lap ทุกกรณี และไม่เติมระยะที่ AASHTO ต้องการเป็นระยะ
ที่มีจริงในแบบ

การ upload Loads จาก CSiBridge ใช้ช่องเดิม ผล combined ที่ actual loads ยัง
ต้องมี joint/free-body state ที่มีต้นทางชัดเจน ตาราง advanced จึงเปิดไว้สำหรับ
ข้อมูลดังกล่าว ไม่แทนค่าแรงที่ไม่ทราบด้วยศูนย์ และยังไม่ได้ทำ automatic recovery
จาก Beam/Slab states ใน milestone นี้ ภาพล่าสุดแสดง component files=0 จึง
ยังไม่มีข้อมูลชุดนั้นให้ตรวจสมดุลใน session ตามภาพ

`mz` ใน advanced research states เป็น **background** ของโมเมนต์จากแรงเฉือน
ตามยาว ไม่ใช่ Girder Tu และไม่ใช่ total interface moment ที่นำมาใส่ซ้ำกับ
ส่วน circulatory ที่โมเดลเพิ่มเอง ต้องแยกด้วย free body ที่ตรวจสอบได้

## 5. ผลตรวจสอบซอฟต์แวร์

- ชุดทดสอบที่เลือก: **362 ผ่าน**, 0 fail/error/skip ประกอบด้วยเดิม 321 และ
  ทดสอบใหม่ 41 มี warning เดิมเกี่ยวกับ pytest/pandas รวม 7 รายการ
- Compile ผ่าน app.py และไฟล์ที่เกี่ยวข้อง
- Browser จริง 1440 และ 1280 px: กด Calculate ครั้งเดียวคำนวณ 2 girder,
  กราฟเริ่มต้น 1 กราฟ, ช่องว่าง x=20 และหลักฐาน development ยังอยู่
- ทดสอบการกรอกใหม่ต่อเนื่อง 3 ช่อง: ค่าครบ panel เปิดอยู่ กราฟ Flexure ยังอยู่
  และไม่มี solver ซ้ำเมื่อแก้เฉพาะข้อมูล research / review
- ตรวจ JSON input roundtrip, reset widgets เมื่อโหลดโครงการใหม่ และยืนยันว่า
  research numerical results ไม่ถูกบันทึกเป็นผลออกแบบ
- ตรวจ raw Loads ไม่เปลี่ยนหลังคำนวณและหลังแก้ข้อมูลใหม่

Browser ใช้รายละเอียด U/closure **สมมติสำหรับ QA** เพื่อให้เดินเครื่องคำนวณได้
ครบ ไม่ใช่การยืนยันค่าในแบบของผู้ใช้ และไม่ได้สร้าง JSON ใหม่ไปแทนโครงการจริง
ผลทดสอบ 362 รายการเป็น selected regression gate ไม่ใช่คำกล่าวว่า full repo
suite หรือแบบจำลองโครงสร้างจริงผ่านทั้งหมด

ตัวอย่าง independent analytical benchmarks ของวงสมมติ Ao=200,000 mm²:

| กรณีจำกัดกำลังของโมเดล | ผลเทียบสมการอิสระ |
|---|---:|
| Girder leg 250 N/mm เป็นส่วนอ่อน | Model Tn = 100.000 kN-m |
| U-leg 250 N/mm เป็นส่วนอ่อน | Model Tn = 100.000 kN-m |
| Slab closure 250 N/mm เป็นส่วนอ่อน | Model Tn = 100.000 kN-m |
| Longitudinal reserve 100 kN, ph=3000 mm | Model Tn = 29.629630 kN-m |
| Diagonal flow cap 100 N/mm | Model Tn = 40.000 kN-m |

ตัวเลขตารางนี้เป็นกรณีทดสอบสมมติ ไม่ใช่ค่ากำลังสะพานของผู้ใช้

## 6. งานที่ยังจำเป็นก่อน Full composite design acceptance

ต้องปิดให้ครบอย่างน้อยสามส่วน: รายละเอียดวงถ่ายแรงจริงและ anchorage/nodes,
แรงร่วมพร้อม reference/free-body ที่ตรวจสมดุลได้, และโมเดล compatibility /
material response ที่เทียบผลทดสอบ composite system อิสระ การปรับ φ หรือบวก
กำลัง dowel เข้ากับ Tn เดิมไม่สามารถทดแทนส่วนเหล่านี้ได้

รายละเอียดสมการ ขอบเขต และแผน validation อยู่ใน
`docs/design/igird_coupled34.md` พร้อมหลักฐานทดสอบใน
`qa/evidence/igird_coupled34/`

สูตรและผล ULS/SLS เดิมยังใช้ engine เดิม ไม่มีการยกเว้น failure ที่ปลายคาน
หรือเพิ่ม result-cache persistence ของโครงการ

Repo summary:

```text
Explain flexure end gaps and add an isolated composite V-T research solver with shared dowel resources, signed joint equilibrium, source guards and hard structural-validation holds.
```
