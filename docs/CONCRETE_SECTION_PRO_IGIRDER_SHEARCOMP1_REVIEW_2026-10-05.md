# Concrete Section Pro — IGIRDER.SHEARCOMP1

วันที่ 2026-10-05 — แก้ φVn สำหรับ Final-Composite ตาม AASHTO LRFD 9th Edition (2020) Section 5 ที่ผู้ใช้ให้มา

## สิ่งที่แก้

เดิม dv ใน I-Girder ใช้ค่าขั้นต่ำจากความลึก precast เป็นหลัก จึงไม่ได้ใช้แรงอัด/แรงดึงและความลึกหน้าตัด Final-Composite อย่างครบถ้วน ขณะนี้คำนวณสมดุลหน้าตัดที่แต่ละสถานี จาก deck+girder พร้อมลดกำลังลวดและเหล็กตาม development แล้วหาจุดรวมแรง C/T และ de แบบถ่วงด้วยแรงตาม 5.7.2.8 จากนั้นใช้ dv=max(ระยะ C–T, 0.9de, 0.72h) โดย h รวม deck ส่วน bv และ f'c ใน Vc/ขีดจำกัด web ยังคงเป็น web ของ girder ไม่ใช้ความกว้างหรือกำลัง deck แทน web

แก้ความเค้นสำหรับเกณฑ์ระยะ stirrup เป็น vu=(|Vu|−φVp)/(φ bv dv) ตาม 5.7.2.8-1 ก่อนเลือกเกณฑ์ 5.7.2.6 เดิมไม่มี φ ในตัวหาร จึงอาจเลือกเกณฑ์ spacing ผ่อนคลายเกินไป ในโมเดลลวดตรงนี้ Vp=0

การหา dv ของลวด debonded ใช้ κ=2 ตาม C5.7.2.8 แม้ตั้งค่าบริการว่าไม่มีแรงดึง และไม่ให้ sleeve รับกำลัง bond ระยะ transfer/development เริ่มจากจุดเริ่ม bond ของแต่ละกลุ่ม สำหรับลวด 12.7 mm ค่า 60db=762 mm ไม่เปลี่ยนไปวัดจาก bearing

กำลังเฉือน φVn=φ min(Vc+Vs+Vp, 0.25 f'c bv dv+Vp) ยังใช้ General Procedure และตรวจขั้นต่ำ/spacing ของเหล็กขวาง การจำกัด fy ของ shear แยกจาก torsion ตาม scope ของ code; ไม่มีการเปิดข้อยกเว้น fy=100 ksi โดยอัตโนมัติ

## Bearing ห่างปลาย 0.4 m

บันทึกเป็นแนวกึ่งกลาง bearing ตามการตีความที่แจ้งให้ผู้ใช้ทราบ: ซ้าย x=0.4 m ขวา x=19.6 m ระยะกึ่งกลางรองรับ 19.2 m; คานและปลายลวดยังอยู่ x=0 และ 20 m กราฟยังใช้ความยาวคานจริง 20 m

ยังไม่ได้รับความยาว bearing ตามแนวคาน จึงไม่กำหนดขอบด้านในโดยสมมุติ ถ้า bearing ยาว wL/wR เมตร ขอบด้านในจะอยู่ xL=0.4+wL/2 และ xR=19.6−wR/2 ระยะ critical section ที่เข้าเงื่อนไข 5.7.3.2 ต้องวัด dv จากขอบด้านในนั้น ต้องทราบแรงปฏิกิริยา การมี concentrated load ภายใน dv และรายละเอียด end region ประกอบ; คานที่ยื่นสองด้านของ reaction area ต้องพิจารณาแต่ละด้าน

แอปมีช่อง Bearing locations / shear section basis ใน Shear/Torsion/Combined: เลือก Centerline หรือ Internal face และระบุความยาว bearing (0=ยังไม่ทราบ) เมื่อทราบ face จะเพิ่มจุดตรวจ face+dv โดยใช้ dv ณ จุดนั้น เป็น supplemental audit และยังคงตรวจแถวแรงต้นฉบับทุกแถว รวมส่วนยื่นปลายคาน ไม่มีการลด Vu หรือยกเว้นการตรวจใกล้ support อัตโนมัติ ไม่ย้ายจุดเริ่ม bond ของลวด และไม่เปลี่ยน automatic Construction-stage load model เป็น span 19.2 m

ช่องยืนยัน anchorage ของเหล็กตามยาวระบุ x=0/L ให้ชัดเจน: anchorage ที่ bearing ซึ่งอยู่ลึกเข้ามา 0.4 m อย่างเดียวไม่พิสูจน์ว่าที่ปลายคานจริงมีกำลังเหล็กเต็ม

## วิธีใช้งานรุ่นนี้

1. แตก ZIP แล้วรัน `streamlit run app.py` จากโฟลเดอร์ concrete-section-pro
2. เปิดโครงการเดิม ตรวจว่า composite enabled, Be/deck/web และวัสดุตรงกับงานจริง
3. ใน Analysis → ULS → Shear เปิด Bearing locations / shear section basis ตั้ง bearing ซ้าย/ขวา 0.4 m แบบ Centerline; ยังไม่ทราบความยาวให้คง 0 ไว้ หรือโหลด JSON ตัวอย่างที่ตั้งค่านี้แล้ว
4. คำนวณ Interface Shear ใน Flexure → Final — Composite และตรวจ effective width/รายละเอียด stirrup ที่ข้าม interface ก่อนใช้ผล Final-Composite ในการยอมรับแบบ
5. กด Calculate Shear หรือ Calculate Shear + Torsion อีกครั้ง เพราะผลเก่าถูกทำให้ stale เมื่อสมการ/วัสดุ/development/geometry/support/interface เปลี่ยน

JSON ตัวอย่างประกอบนำรูปหน้าตัด/deck 250 mm จากไฟล์โครงการที่ให้มา และนำแรง 80 แถวจาก `CSiBridge_Left_Exterior_Max_Min_latest.xlsx` ที่มีอยู่โดยตรง คงแรงทั้งหกตัวและเครื่องหมายทุกค่า รวม P ต้นฉบับซึ่งยังไม่เป็นศูนย์ทั้งหมด ไม่มี P=0 override และไม่แก้ Excel ถ้ามีไฟล์ที่ผู้ใช้แก้ P=0 แล้ว ให้ import ไฟล์นั้นผ่าน Loads ตามปกติ ตัวอย่างไม่ได้ยืนยัน fy/continuity/anchorage/hoop/interface/Be แทนผู้ใช้

## ขอบเขตและสถานะที่ยังแสดงตามจริง

- Final-Composite ใช้ concrete deck ใน C/T/de/dv และ tension-half สำหรับ εs ส่วน compression block ใช้ f'c ที่ต่ำกว่าของ deck/girder ทั้งหน้าตัดอย่างอนุรักษ์นิยม ตาม route Flexure เดิม ไม่ใช่ solver คอนกรีตหลายกำลัง
- เหล็ก deck ตามยาวไม่ได้รับเครดิตใน V/T จนกว่าจะมี development source ของมันโดยเฉพาะ ไม่เติมค่ากำลังให้ material ที่ยังขาด
- Interface Shear ต้องมี PASS ที่ตรงกับ input ปัจจุบัน และต้องยืนยัน Be สำหรับ strength จึงให้ยอมรับ composite action; ค่ากำลังเชิงตัวเลขยังแสดงพร้อม REVIEW/FAIL เมื่อข้อมูลไม่ครบ
- Standalone φTn ยังเป็นกำลังของ closed hoop/solid precast torsion section ตาม Ao/ph/Acp/Pcp ที่มี source; ความลึก flexural/strain ใช้ Final-Composite ได้ แต่ไม่ได้เพิ่มกำลัง torsion จาก deck โดยยังไม่มี hoop และ force-flow ของ composite
- Native CSI Max/Min แต่ละแถวใช้คัดกรองเชิงตัวเลข ยังไม่พิสูจน์ concurrency ของ Mu/Nu/Vu/Tu; M2 และ V3 คงเป็น reference
- Negative composite, bearing/D-region/strut-and-tie, end confinement, hook/lap และ shop drawings ยังคงต้องตรวจตามขอบเขตนั้น ไม่มีการอ้างว่าตรวจ end region ครบจากการให้ bearing coordinate อย่างเดียว
- กราฟแรงทุกกรณีครอบคลุม x=0–20; จุดที่ capacity ไม่มี source แสดง ×/เหตุผล และไม่คัดค่าจากภายในมาต่อเส้น สมมุติฐาน QA ที่ยืนยัน bar/material/anchors ครบให้ capacity ครบ 84 diagram points; สมมุติฐานนี้ไม่ถูกบันทึกเป็นการยืนยันของผู้ใช้

## หลักฐานตรวจสอบ

- Regression 53 modules: 661 passed; มี independent rectangular compression C/T/de benchmark, Nu=−200/0/+200, development/spacing/fy/manual dv, composite gate และ bearing geometry/save/reload/source preservation
- Streamlit AppTest ผ่านปุ่มจริงของ Shear, Torsion, Combined, Construction Flexure, Final Composite และ Interface; ไม่มี exception ตรวจ 16 case diagrams และไม่เรียก solver เมื่อเปลี่ยนกรณีหรือ review
- Independent US-unit V/T/combined substitution: 1,811 scalar comparisons; diagram θ/φVn/φTn เพิ่มอีก 336; depth bounds/spacing/εs อีก 1,312 ไม่เรียก production equation helper ในการแทนสมการ
- Latest raw Excel 80 rows/480 signed quantities preserved. P=0 เป็น controlled QA อีกชุดหนึ่ง; ไม่แก้ P ของไฟล์จริง
- ภาพ PNG/HTML เป็น scientific previews จากพิกัด Plotly ของ production ไม่ใช่ browser screenshots ภาพ QA ที่ระบุ verified anchors ใช้สมมุติฐานทดสอบเท่านั้น
- เวลา Calculate ใน environment ทดสอบประมาณ Combined 7.5 s, Shear 4.5 s, Torsion 3.3 s, Final Flexure 6.2 s; ผลจากไฟล์จริงไม่แก้ P โดยตรง Combined 4.4 s เวลาเครื่องผู้ใช้อาจต่างกัน

## แหล่งอ้างอิง

หลัก: PDF ผู้ใช้ `03-SECTION-5-CONCRETE-STRUCTURES.pdf`, AASHTO LRFD Ninth Edition (2020), printed pp. 5-30, 5-64–67, 5-70 เป็นต้นไป; 5.5.4.2, 5.7.2.3/.6/.8, C5.7.2.8, 5.7.3.2/.3/.4.2/.6, 5.9.4.3.2 และ 5.10.8.2.1

การตรวจ geometry เทียบหลักการ: [FHWA PSC girder shear example](https://www.fhwa.dot.gov/bridge/lrfd/pscus057.cfm), Step 5.7.2.1 ใช้ h=precast+structural slab และระยะ C/T ตัวอย่าง FHWA ใช้ edition เก่าที่เลข Article/critical-section rule ต่างกัน จึงไม่ใช้แทนข้อความ 5.7.3.2 ของ PDF ปี 2020
