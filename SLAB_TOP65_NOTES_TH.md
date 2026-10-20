# SLAB.TOP65 — Top slab ตาม AASHTO LRFD 2020

พัฒนาต่อจาก SLAB.SHEAR64 โดยคงเครื่องคำนวณ sectional ULS ที่ผ่าน regression เดิมไว้ รุ่นนี้รวมการตรวจเหล็กพื้น 4 ชั้นและแรงเฉือนให้อ่านผลในกระบวนการเดียว มีปุ่ม **Calculate Top slab** หนึ่งปุ่ม กราฟหนึ่งรูปต่อมุมมอง และผลอ่านอย่างเดียวใน Result Summary / Report / QA

## วิธีใช้กับผลวิเคราะห์น้ำหนักรถไฟเทียบเท่า

1. วิเคราะห์ CSiBridge ด้วยน้ำหนักและ load combinations ที่ต้องการ
2. Export ทั้ง 4 ชุดจากโมเดลรอบเดียวกัน โดยคง worksheets, headers และ units เดิม
3. เปิด Project JSON แล้วนำเข้าใน **Loads → Slab Shell Results**
4. เปิด **Analysis → Slab Reinforcement** กาง **CSI load basis / Ballast** เลือกฐานโหลดที่ใช้จริง และกรอกความหนา ballast ใต้หมอน เริ่มต้นกรณีศึกษานี้ 300 มม.
5. กด **Calculate Top slab** แล้วเลือก Reinforcement / One-way shear / Punching shear และกราฟ Plan map / Station D/C

| ชุดไฟล์เดิม | ตารางที่ต้องคงไว้ |
|---|---|
| Element Forces - Area Shells.xlsx | Element Forces - Area Shells: F11, F22, F12, M11, M22, M12, V13, V23 และ case/step |
| TABLE Objects And Elements - Areas(1).xlsx | Objects And Elements - Areas และ Objects And Elements - Joints รวม generated ~ joints |
| Area Assigment.xlsx | Area Bridge Object Flags, Area Overwrites - Thickness, Area Section Assignments, Typical / Advanced local axes ตามที่โมเดลใช้ |
| Connectivity Data.xlsx | Connectivity - Area, Joint Coordinates และ Connectivity - Frame สำหรับหาแนวคาน I |

ชื่อไฟล์และชื่อ load case เปลี่ยนได้ โปรแกรมตรวจจากโครงสร้างตาราง รองรับผล static ที่ StepType ว่าง และยังคง Max/Min ทุกแถวถ้ามี ไม่ต้องแนบ stress workbook, นิยาม load combination หรือ moving-load recording settings เพิ่ม

**แรงจาก CSI ใช้ตัวคูณ 1.00 ตลอดเส้นทางนี้** แอปไม่คูณ impact หรือ ULS factor ซ้ำ ไม่ย้ายจุดอ้างอิงแรง และไม่กระจายแรงผ่าน ballast ซ้ำ การแก้ ballast/ความกว้างแถบ/q ในหน้านี้เป็นการบันทึกฐานวิเคราะห์ ต้องวิเคราะห์ CSI ใหม่เองเมื่อเปลี่ยนโหลดจริง ความหนา ballast ไม่ถูกนำไปรวมเป็นความหนาหน้าตัด RC

ค่า 2.00 ม. และ 75 kN/m² เป็นค่าเริ่มต้นของกรณีศึกษาที่เคยหารือ ไม่ใช่ค่าเทียบเท่า U20 ที่ AASHTO กำหนดให้ใช้ทั่วไป และไม่ใช่การรับรองว่าจะครอบคลุมแรงเฉือนตามยาวจาก moving load หรือผลเฉพาะที่ของล้อทุกตำแหน่ง SOURCE MATCHED หมายถึงบันทึกฐานโหลดผูกกับชุดไฟล์นี้ ไม่ได้หมายถึงตรวจรับรองนิยามโหลดแล้ว

## ผลและขอบเขต

- N–M ตาม 5.6.2 / 5.6.3.2.5 ใช้เหล็กทั้งสองชั้นจริงของทิศทางนั้น พร้อม strain-based phi ตาราง Top/Bottom แยกกรณีโมเมนต์ลบ/บวก และรวม axial-dominant tension ในทั้งสองแถว ไม่ใช่การสร้างกำลังอิสระสองค่าแล้วนำมาบวก
- One-way shear ตาม 5.7.3 / 5.12.8.6.2 ใช้ N–M–V ของแถวเดียวกันและเหล็กด้านรับแรงดึง พร้อม support-face samples เดิม ไม่บวกเหล็กตะแกรงในระนาบหรือขา U เป็น slab Vs
- Flexural shear tie, sufficient flexural minimum, temperature minimum, maximum spacing และ required development length คงวิธีเดิม
- เพิ่ม clear spacing ของเหล็กขนานในพื้นหล่อในที่ตาม 5.10.3.1.1: max(1.5db, 1.5ag, 1.5 in) อ่าน aggregate input เดิม หากยังไม่ยืนยัน จะรายงาน trial และ REVIEW สำหรับสาขาที่ขึ้นกับ aggregate; การไม่ผ่าน absolute minimum ยังเป็น FAIL
- Punching คงวิธี critical perimeter ของ loaded area จริง ไม่สร้างพื้นที่ล้อจากจุด peak และไม่ถือว่าการเลือก UDL ทำให้ผ่าน punching อัตโนมัติ
- แนว I-girder, diaphragm, เขตปลายถึง bearing และ REVIEW61 one-pass isolated-peak exclusions คงเดิม พร้อม audit ของต้นฉบับ ไม่เพิ่มการตัดจุดตามค่า D/C

Station D/C แสดงค่าสูงสุดจริงในแต่ละสถานีตามแนวสะพาน ไม่เฉลี่ยแรงหรือ D/C และไม่ smooth เส้น จุดที่ไม่มีผลคำนวณเป็นช่องว่าง Scope markers อยู่บนแกนเสริมและไม่ใช่ค่า D/C สมมติ แกนนอนแสดงความยาวเต็ม แม้ปลายคานเป็นเขตที่ละเว้น

**รุ่นนี้เป็นกระบวนการตรวจ sectional ULS ตาม AASHTO ไม่ใช่ full-shell / full-deck acceptance** Nxy/Mxy interaction, simultaneous biaxial shear, local D-regions, available anchorage, fatigue และ SLS ยังต้องตรวจในขอบเขตที่เกี่ยวข้อง ผล FAIL มีลำดับสูงกว่า REVIEW และผลที่ล้าสมัยจะไม่ถูกแสดงเป็น PASS

## ตัวอย่างจากข้อมูลเดิม

ตัวอย่างใน `examples/slab_top65_original_inputs` ใช้ JSON32 และ 4 Excel เดิม จึงไม่ใช่ผลจากการวิเคราะห์น้ำหนักรถไฟเทียบเท่ารอบใหม่

| การตรวจ | D/C สูงสุด |
|---|---:|
| Direct N–M ตามขวาง | 0.441277 |
| Direct N–M ตามยาว | 0.366523 |
| One-way shear ตามขวาง | 1.490332 |
| One-way shear ตามยาว | 3.001741 |
| Flexural shear tie ตามขวาง | 1.235121 |
| Flexural shear tie ตามยาว | 2.077051 |

จึงยังมีรายการไม่ผ่านในข้อมูลเดิม ไม่มีการปรับค่ากำลังหรือลดแรงเพื่อทำให้ผ่าน ผลแรงทั้ง 8 องค์ประกอบและ source identities ไม่เปลี่ยน: 146,432 source records → 113,232 retained; 26,240 geometry/end exclusions + 6,960 peak exclusions

## การบันทึกและทดสอบ

Project JSON บันทึก input และฐานโหลดเท่านั้น ไม่บันทึก source Excel หรือผล solver cache เมื่อเปิด JSON/เริ่มแอปใหม่ ต้องนำเข้า 4 ชุดแล้ว Calculate ใหม่ การเปลี่ยนกราฟ/case, เปิด Summary/Report และเตรียม compact report ไม่รันเครื่องคำนวณซ้ำ หากฐานเหล็ก/geometry/source เปลี่ยนจะแสดง STALE

รายละเอียดผลทดสอบจริงและ runtime อยู่ใน `SLAB_TOP65_VERIFICATION.json` ตรวจสมการเดิม แรงต้นฉบับ form navigation, static cases, report freshness, กราฟ export และ live browser ที่ 1440/1280 px สคริปต์ทำซ้ำอยู่ใน `qa/slab_top65_real_inputs.py` และ `qa/slab_top65_browser_verify.py` โดย Playwright เป็น dependency สำหรับ QA เท่านั้น

## แหล่งอ้างอิง

- AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5 ที่ผู้ใช้ให้: 5.6.2, 5.6.3.2.5, 5.6.3.3, 5.7.3, 5.7.4, 5.10.3, 5.10.6, 5.10.8 และ 5.12.8.6
- [CSI — Shell force/stress output convention](https://docs.csiamerica.com/help-files/csibridge/Output_Conventions/Shell_Element_Internal_Forces_Stresses_Output_Convention.htm)
- [FHWA LRFD design example](https://www.fhwa.dot.gov/bridge/lrfd/pscus72.cfm) เป็นข้อมูลเปรียบเทียบวิธีตรวจ ไม่ใช้แทนมาตรฐานฉบับ 2020 หรือมาตรฐานรถไฟของโครงการ
