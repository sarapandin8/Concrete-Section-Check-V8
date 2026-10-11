# Concrete Section Pro — IGIRDER.CSIIMPORT14

พัฒนาต่อจาก **IGIRDER.REBARADVISOR13** เพื่อให้นำไฟล์ **Bridge Object Girder Forces** ที่ export จาก CSiBridge เข้าหน้า Loads ได้โดยตรง และเก็บข้อมูลต้นทางครบทุกแถว

## ผลตรวจไฟล์ที่ชาตรีส่งมา

ไฟล์ต้นทาง `ULS_Girder Force uploaded to app.xlsx` มี worksheet `Bridge Object Girder Forces` โดยแถว 1 เป็น TABLE title, แถว 2 เป็นหัวคอลัมน์, แถว 3 เป็นหน่วย และแถว 4–643 เป็นข้อมูล 640 แถว ไฟล์ต้นฉบับคงเดิมทุกไบต์

| คานต้นทาง | ชื่อเริ่มต้นในแอป | แถวข้อมูล | OutputCase | StepType / LocType | Distance |
|---|---|---:|---|---|---|
| Left Exterior Girder | BOBJ1 / Left Exterior Girder | 320 | U1A, U1B, U2A, U2B | Max/Min และ Before/After | 0–20 m |
| Interior Girder 2 | BOBJ1 / Interior Girder 2 | 320 | U1A, U1B, U2A, U2B | Max/Min และ Before/After | 0–20 m |

ทั้งสองคานมี 21 สถานี และแยกเป็น 16 vector series ต่อคาน ข้อมูล Before/After ที่ตำแหน่งเดียวกันเก็บแยกกัน ค่าแรงของสองด้านอาจต่างกัน แอปเก็บค่าแรงทั้งหกจากแถวเดียวกัน ไม่รวมแถวหรือสร้างเวกเตอร์ใหม่จากค่าสูงสุดของแต่ละองค์ประกอบ

SHA256 ต้นทาง: `d29e5af119bc94d3ce74acf6ee51978cd0ccb9b012a649ee26b32d1b0521a2c2`

## เปรียบเทียบกับ REBARADVISOR13

| รายการ | REBARADVISOR13 | CSIIMPORT14 |
|---|---|---|
| หลายคานอยู่ใน worksheet เดียว | ใช้ worksheet เป็นตัวแทนคาน จึงเสี่ยงรวมคานเข้าด้วยกัน | แบ่งตาม BridgeObj + Girder อัตโนมัติ |
| Before/After และชนิด combination | ใช้ลำดับแถวซ้ำช่วยแยก series | เพิ่ม LocType และ CaseType ในตัวตนของ series พร้อมเก็บ SectCutNum |
| ข้อมูลต้นทาง | เก็บ case, step, sheet, row และค่าแรงที่ map | เก็บครบทุกคอลัมน์ต้นทาง หน่วย TABLE title เลขแถว Excel และ SHA256 ใน Note ของแต่ละแถว |
| Native CSV มี TABLE title ที่จำนวนช่องไม่เท่ากับ header | อาจอ่านไม่สำเร็จ | อ่าน title/header/units/data ได้ครบ |
| Native export ขาดบางคอลัมน์ | มีโอกาสถูกตรวจเป็น app-column table | บังคับเข้าตัวตรวจ native และหยุดนำเข้าเมื่อข้อมูลไม่ครบ |
| CSV รวมหลายคานจากแอป | ต้องตรวจการแบ่งสมาชิกเอง | ตรวจ Girder และแยกสมาชิกเมื่ออัปโหลดกลับ |
| ตรวจย้อนกลับจากผลแรงเฉือน/แรงบิด | ตำแหน่งแบบ Governing x ไม่เชื่อมเลขแถวต้นทางครบ | เชื่อม physical LOAD STATION กลับต้นทาง พร้อมตำแหน่งจริงและค่าแรงทั้งหก; แถว interpolation เก็บ basis ระดับ series แยกต่างหาก |
| ฟังก์ชันคำนวณและ Rebar Advisor | สูตรและ workflow ของเวอร์ชัน 13 | คงสูตร Vn/Tn, composite/development gates และ Rebar Advisor ของเวอร์ชัน 13 |

แก้ไฟล์ production สองไฟล์: `concrete_pmm_pro/io/girder_csi_import.py` และ `concrete_pmm_pro/ui/girder_csi_import.py` พร้อมเพิ่มชุดทดสอบและไฟล์ QA ทั้งหมดใน baseline ZIP 1,951 entries ยังอยู่ครบ

## การ map ค่าและหน่วย

| CSiBridge | แอป | หน่วยที่ใช้ใน Loads | หน้าที่ใน I-Girder route |
|---|---|---|---|
| Distance / Girder Distance | Station x (m) | m | ตำแหน่งตามคาน |
| M3 | Mux | kN-m | แรงดัดแกนหลัก |
| V2 | Vuy | kN | แรงเฉือน |
| T | Tu | kN-m | แรงบิด |
| P | Nu ใน Loads | kN | เก็บ CSI raw P: บวก = tension, ลบ = compression |
| M2 | Muy | kN-m | ค่าอ้างอิงตามขอบเขต route เดิม |
| V3 | Vux | kN | ค่าอ้างอิงตามขอบเขต route เดิม |

ตัวนำเข้าอ่านหน่วยที่ประกาศในไฟล์และแปลงเป็น m/kN/kN-m พร้อมเก็บค่าดิบและหน่วยเดิม กรณีหน่วยไม่รองรับจะแจ้งข้อผิดพลาดและปิดปุ่ม Apply; native export ต้องมีแถวหน่วย ค่า P คงเครื่องหมายเดิม ส่วนการแปลงเป็น Nu บวกอัดใน solver ใช้ขั้นตอนเดิมของแอปเพียงครั้งเดียว

## วิธีใช้

1. แตก ZIP แล้วรันแอปตามวิธีเดิม เปิด Project JSON ที่มีหน้าตัดและเหล็กของงานนี้
2. ไป **Loads → ULS Loads → Final Composite ULS — Imported FEA Demand**
3. เปิด **Import Bridge Beam/Girder ULS station loads from Excel / CSV** แล้วอัปโหลด XLSX ต้นฉบับได้เลย คง TABLE title, headers และแถวหน่วยไว้
4. เลือก worksheet `Bridge Object Girder Forces` ตรวจ preview ว่าเป็น 640 แถว สองคาน คานละ 320 แถว และ 32 vector series รวม
5. เปิด **Source rows / units** ตรวจข้อมูลเดิม เลขแถว SectCutNum และ Before/After ได้
6. ยืนยันชื่อคาน/จุดเริ่ม station และ **All tables use raw CSI P signs** แล้วกด **Replace entire girder collection** สำหรับแทนชุดโหลดเดิม หรือ **Add tables to girder collection** สำหรับเพิ่ม case ใหม่ที่ไม่ซ้ำ
7. เลือก **Girder to design** แล้วกด **Use this girder — all imported load cases** ตรวจ section/rebar/prestress/support ของคานนั้นก่อน Calculate
8. ไป **Analysis** เลือก check และกด Calculate ผลเดิมต้องคำนวณใหม่เมื่อเปลี่ยนชุดโหลด การเปิด Loads หรือสลับหน้าทบทวนไม่เรียก solver
9. Save Project JSON เก็บตารางโหลดทุกคานและข้อมูลต้นทางใน Note; เมื่อเปิด JSON อีกครั้งให้ Calculate ใหม่ตาม workflow เดิม

ปุ่ม **Download all-member app CSV** ส่งออกทั้งสองคานพร้อม source Note; ปุ่ม **Download original-row audit CSV** ส่งออกคอลัมน์ต้นทางและค่าที่ map แล้ว CSV ที่จัดให้ในแพ็กมาจาก bank ที่ทดสอบจริง ไม่จำเป็นต้องแปลง XLSX ก่อนใช้แอปรุ่นนี้

## ประเด็นที่วิศวกรต้องยืนยัน

**Distance:** CSiBridge เลือก origin และแนววัดระยะได้ตามการ export ต้องยืนยันว่า Distance ในไฟล์ตรงกับ Station x ของ physical girder และ origin ของ Project โดยแอปไม่เลื่อน origin ให้เอง ไฟล์นี้มีช่วง 0–20 m

**Max/Min:** ค่าแต่ละองค์ประกอบใน envelope ไม่ยืนยันว่าเกิดพร้อมกัน ค่าในไฟล์นี้จึงคง **ENVELOPE — REVIEW** สำหรับการยอมรับ final coupled checks และรักษา FAIL ที่พบจริง การยืนยันว่าเป็น concurrent ต้องมี source/export basis เช่น CSI Correspondence หรือ explicit static/step ที่ตรวจสอบแล้ว การเปลี่ยนชื่อไฟล์หรืออัปโหลด CSV กลับไม่เปลี่ยน envelope ให้เป็น concurrent

ข้อมูล M2/V3 เก็บครบตามต้นทาง การนำเข้าครั้งนี้คงขอบเขตอ้างอิงของ I-Girder route เดิม สูตร Vn/Tn และหลัก composite section ใช้ implementation ของ REBARADVISOR13

อ้างอิงทางการ CSI:

- [Show Bridge Forces/Stresses — distance and envelope settings](https://docs.csiamerica.com/help-files/csibridge/Home_tab/Display_panel/Show_Bridge_Forces_Stresses.htm)
- [Bridge Panel — Correspondence](https://docs.csiamerica.com/help-files/csibridge/Analysis_tab/Bridge_Panel.htm)

## การตรวจสอบ

- Compile app.py และไฟล์ที่เพิ่ม/แก้ ผ่าน
- Scoped regression **222 tests ผ่าน** ครอบคลุม native import ใหม่และ import เดิม, multi-girder/multi-case, axial signs, Project JSON, case review, Max/Min และ Rebar Advisor
- ตรวจทุก cell ของ 640 แถว: ระยะ ค่าแรงทั้งหก เครื่องหมาย สมาชิก case StepType LocType SectCutNum หน่วย เลขแถว และ SHA256 ตรงต้นทาง
- AppTest รัน **app.py จริง**: upload → replace → สลับคาน → JSON roundtrip → ป้องกัน append ซ้ำ → ปิด Apply สำหรับ native ที่ขาด V3 → อัปโหลด all-member CSV กลับ ผ่าน
- หน้า Analysis ของแอปจริงส่งครบ 640 source rows เข้าสู่ **Shear + Torsion** และ trace ค่าแรงทั้งหกตรงต้นทาง; Max/Min ไม่ออก PASS โดยอัตโนมัติ
- UI acceptance เดิม: สองไฟล์ สองคาน หลาย case, replace/add/switch และ duplicate guard ผ่าน
- ตรวจด้วย Chrome ในหน้าแอปจริง: อัปโหลด XLSX ต้นฉบับ, preview 640 แถว/สองคาน/32 series, เปิด Source audit และสลับ Interior Girder 2 ผ่าน; ไม่พบ JavaScript error

การทดสอบ calculation ใช้หน้าตัด 20 m จาก QA fixture และไม่ใช่การยืนยันว่าหน้าตัด/เหล็กของงานจริงผ่าน ต้องใช้ Project และรายละเอียดของคานที่ถูกต้องในการออกแบบ ไม่มีการอ้างว่าทดสอบผ่านทุก module ของ repository

QA fixture นี้ยังขาดข้อมูลที่จำเป็นของ torsion/development บางส่วน ผล calculation จึงเป็น DATA REQUIRED / REVIEW และบางแถวมีสถานะ PARTIAL การตรวจครั้งนี้ยืนยันว่าแต่ละเวกเตอร์และค่าอ้างอิงเข้าสู่ production route ถูกต้องครบ 640 แถว ส่วนการตรวจสูตรและ gates ใช้ regression ของ route ที่มีข้อมูลพร้อมแยกต่างหาก

**Repo summary:** Preserve complete native CSiBridge ULS exports by splitting BridgeObj/Girder members and retaining source rows, units, signs, provenance, and envelope review gates.
