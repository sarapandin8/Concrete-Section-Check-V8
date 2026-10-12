# Concrete Section Pro — IGIRDER.AUTOLOAD17

พัฒนาต่อจาก `concrete-section-pro_IGIRDER-VTCHART16.zip` เพื่อให้การอัปโหลดไฟล์ CSiBridge ที่มีสองคานจัดแรงให้ถูกคานทันที ลดความสับสนระหว่างการเลือกไฟล์กับการรับข้อมูลเข้าแอป

## ขั้นตอนใหม่

1. เข้า Loads → ULS Loads และเลือกไฟล์ต้นฉบับ CSiBridge `Bridge Object Girder Forces`
2. แอปตรวจข้อมูลทั้งไฟล์ แล้วแทนที่ชุดแรง ULS เดิมอัตโนมัติ พร้อมแยกตาม `BridgeObj + Girder`
3. เมื่อสำเร็จ จะแสดง `Loads assigned by Girder` และข้อความสีเขียว `Last successful import` พร้อมชื่อไฟล์และจำนวนแถว
4. ไป Analysis แล้วกด Calculate ของรายการตรวจที่ต้องการ ระบบคำนวณทุกคานใน collection แยกจากกัน โดยใช้เฉพาะแรงของคานนั้น

ไม่ต้องกด Apply/Replace ไม่ต้องตั้งชื่อคาน ไม่ต้องเลือก worksheet หรือกด Use this girder สำหรับไฟล์ native รูปแบบที่ส่งมา การนำเข้าไม่เรียก solver อัตโนมัติ และไม่ได้หมายความว่าผลการออกแบบผ่าน

## เปรียบเทียบกับ VTCHART16

| รายการ | VTCHART16 | AUTOLOAD17 |
|---|---|---|
| รับไฟล์ native ที่มีสองคาน | เลือกไฟล์ ตั้งค่า และกด Replace | ตรวจไฟล์แล้วรับข้อมูลทันที |
| แยกแรงรายคาน | รองรับผ่านตัวเลือกนำเข้า | ใช้ BridgeObj + Girder อัตโนมัติ |
| ปุ่มรับข้อมูล | Replace / Add tables | ไม่มีในเส้นทาง native ปกติ |
| ชื่อคาน กรณีโหลด และหน่วย | มีช่องตั้งค่าบนหน้าแรก | อ่านจากไฟล์ native |
| ดูตารางของอีกคาน | เลือกคานแล้วกด Use this girder | เลือกแล้วเปลี่ยนทันที |
| ยืนยันการรับข้อมูล | ไม่มีข้อความสำเร็จคงอยู่หลัง rerun | แสดงชื่อไฟล์ จำนวนคาน และจำนวนแถว |
| แผนผังคอลัมน์และ template | อยู่ก่อนช่องอัปโหลด | ย้ายเข้า expander |
| เพิ่มไฟล์ต่อชุดเดิม / Correspondence | ตัวเลือกบนหน้าหลัก | ใช้ Advanced import settings |
| ผล ULS เดิม | ใช้ hash ตรวจความล้าสมัย | ล้าง cache ULS เมื่อรับชุดแรงใหม่ และให้ Calculate ใหม่ |

แก้ production เพียงสองไฟล์: `concrete_pmm_pro/ui/girder_csi_import.py` และ `concrete_pmm_pro/ui/loads_page.py` สูตร Vn, Tn, Shear+Torsion และตัวอ่าน/แมปแรง CSI จาก VTCHART16 คงเดิม

## ผลตรวจไฟล์จริง

ใช้ไฟล์ native ที่ตรงกับ `ULS_Girder Force uploaded to app.xlsx` และสำเนา `(1).xlsx` ทุกไบต์ SHA256 `d29e5af119bc94d3ce74acf6ee51978cd0ccb9b012a649ee26b32d1b0521a2c2`

| คาน | แถว | OutputCase | ตำแหน่ง |
|---|---:|---|---|
| BOBJ1 / Left Exterior Girder | 320 | U1A, U1B, U2A, U2B | 0–20 m |
| BOBJ1 / Interior Girder 2 | 320 | U1A, U1B, U2A, U2B | 0–20 m |

เก็บทั้ง Max/Min, Before/After และแรง P, V2, V3, T, M2, M3 ครบทุกแถว แมป P → Nu ตามเครื่องหมาย CSI เดิม ไม่แทน P ด้วยศูนย์

ทดสอบ actual app.py ด้วยโมเดล JSON ของผู้ใช้: native upload รับข้อมูลโดยไม่มีการกด Apply, การคำนวณ Shear+Torsion เกิดเมื่อกด Calculate เท่านั้น และเรียกแยกสองคานรวมสองครั้ง ผล 320 แถวต่อคานมี Source Mux/Vuy/Tu/Nu ตรงกับแถวของคานนั้นทั้งหมด

ผลคำนวณจากชุดแรงใหม่ยังมี FAIL/REVIEW: คานริม maximum numeric D/C 1.375 และคานภายใน 1.749 ภายใต้ section/rebar model เดิม ตัวเลขนี้เป็นผลตรวจว่าการส่งแรงเข้าคำนวณถูกคาน ไม่ใช่การรับรองการออกแบบผ่านหรือการเปรียบเทียบสมรรถนะกับชุดแรงเก่า

## การคงข้อมูลและข้อจำกัด

- Native upload ปกติแทนที่ collection เดิมทั้งหมดด้วยไฟล์ที่เลือกอยู่ ไม่เพิ่มปนกับชื่อคาน/กรณีจากชุดเก่า
- ตรวจไฟล์ทั้ง batch ให้ผ่านก่อนเปลี่ยนข้อมูล ไฟล์ผิดหน่วย แรงไม่ครบหรือไฟล์ซ้ำจะไม่แทนที่ชุดเดิม และแสดงข้อผิดพลาด
- การ rerun หรือสลับหน้าด้วยไฟล์เดิมไม่รับข้อมูลซ้ำ จึงคงการแก้ไขตาราง Loads หลังนำเข้าไว้
- ถอดไฟล์ออกจาก uploader ไม่ลบแรงที่รับเข้าแล้ว
- ไฟล์ native ใหม่ที่มีเนื้อหาเปลี่ยนจะรับใหม่อัตโนมัติ และล้างผล ULS เก่า
- ผล Max/Min ยังคง ENVELOPE / REVIEW การอัปโหลดอัตโนมัติไม่ยืนยันความพร้อมกันของแรงแทนผู้ใช้ หากมีหลักฐาน Correspondence ให้ใช้ Advanced import settings
- รูปแบบ individual sheets / app-column tables และการ append ยังคงใช้เส้นทางตั้งค่าขั้นสูงเดิม
- คานทั้งสองใช้ section/rebar/prestress/support settings ชุดปัจจุบันร่วมกัน หากรายละเอียดคานต่างกัน ต้องแยกโมเดลหน้าตัดให้เหมาะสม
- Project JSON ยังคงบันทึก input-only; result cache ไม่ถูกเพิ่มเข้าไฟล์โครงการ

## Verification

Regression 145 tests ผ่าน, compile app.py และไฟล์ที่เกี่ยวข้อง 7 ไฟล์, actual AppTest ผ่านการนำเข้าอัตโนมัติ สลับคาน แก้ตารางโดยไม่โดนรับไฟล์ซ้ำ ป้องกัน partial invalid upload และ Save/Load Project source roundtrip ตรวจ browser upload จริงและ layout ที่ความกว้าง 1440/1100 px พร้อมสลับคานทันที

ZIP เป็นแอปเต็ม เก็บทุก entry จาก VTCHART16 ไม่มี cache หรือ runtime checkpoint ใหม่และไม่รวม browser screenshots หลักฐานอยู่ใน `qa/evidence/igird_autoload17/` ขนาดและ SHA256 อยู่ใน release validation ที่ส่งคู่กัน

Repo summary: Automatically import native CSiBridge ULS files, assign each girder its own loads, and remove extra apply and member-assignment steps.
