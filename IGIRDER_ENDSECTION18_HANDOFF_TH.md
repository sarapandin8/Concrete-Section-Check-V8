# Concrete Section Pro — IGIRDER.ENDSECTION18

วันที่ส่งมอบ: 12 ตุลาคม 2026

พัฒนาจาก `concrete-section-pro_IGIRDER-AUTOLOAD17.zip` และเก็บไฟล์ baseline ครบทั้ง 1,996 รายการ

## วิธีใช้

1. เปิด Project JSON เดิม ไปที่ **Sections → Section Builder → Solid End Sections**
2. เปิด **Enable solid precast end sections**
3. ตามแบบที่ส่งมา ระบุหัวตันซ้าย/ขวา **1.50 ม.**, taper ซ้าย/ขวา **0.25 ม.**, ความกว้าง **600 มม.** ความสูงรับจากหน้าตัดเดิม **1,500 มม.**
4. ใช้ slider ดูรูปหน้าตัดและตารางเขตตามระยะ
5. ใน **Coordinates and drawing confirmations** ตรวจพิกัดปลายหล่อบนแกน CSI, chamfer และรายละเอียดเหล็ก/การรองรับก่อนยืนยัน
6. กด **Calculate** ใหม่ใน Analysis หลังแก้ค่า ผลเก่าจะเป็น **STALE**

ค่าตั้งต้นไม่ยืนยันรายละเอียดจากแบบโดยอัตโนมัติ โหลดของแต่ละ girder ยังแยกกัน ส่วนหน้าตัด/วัสดุ/เหล็กเป็น shared model ของ collection เช่นเดิม หากสอง girder มีรายละเอียดต่างกันให้ใช้คนละ Project Model

## เปรียบเทียบ

| เรื่อง | AUTOLOAD17 | ENDSECTION18 |
|---|---|---|
| หน้าตัดตามความยาว | รูป I เดียว | หัวตัน → taper → I → taper → หัวตัน |
| ช่องระบุระยะ | ไม่มี | หัวตันและ taper ซ้าย–ขวาแยกกัน |
| Shear | bv ของหน้าตัดเดิม | bv, Vc, limit และ dv ตามหน้าตัดตำแหน่งจริง |
| Torsion | รูปหน้าตัดเดิม | Acp/Pcp/Ao/ph คำนวณใหม่ตามตำแหน่ง |
| Flexure/composite depth | context หน้าตัดเดิม | แยก context/reference ตาม polygon และ Nu/sign |
| Shear + Torsion | หน้าตัดเดิม | ใช้ Ao/ph/bv/dv/εs/β/θ ของจุดนั้น |
| Interface shear | flange เดิม | Auto ใช้ผิวสัมผัส precast/deck ของจุดนั้น |
| กราฟ | จุดแรงนำเข้า | hover ชนิดหน้าตัดและแนวรอยต่อ; Vn/Tn มี geometry samples |
| JSON/CSI | นำเข้าอัตโนมัติแยก girder | บันทึกหัวตันใน JSON และคงค่าแรงทั้งหกเดิม |

## พิกัดและหลักคำนวณ

ปลายหล่อเริ่มต้นเป็น x=0 และ x=L บนแกน Loads เดิม แบบแสดงความยาวหล่อ 19.95 ม. ในช่วงรวม 20.00 ม. หากตรวจยืนยันว่า CSI Distance=0 อ้างจากปลายช่วงรวมที่มีช่องว่าง 0.025 ม. แต่ละด้าน ให้ตั้งปลายหล่อ x=0.025 และ x=19.975 ม. หาก CSI อ้างจากปลาย girder อยู่แล้วให้ใช้พิกัดตามนั้น แอปไม่ย้ายแรงหรือเดาต้นกำเนิดระยะ

แถวที่อยู่นอกปลายหล่อยังคงอยู่ แต่แสดง SECTION UNAVAILABLE / REVIEW และไม่มีค่ากำลัง ไม่ยืดกำลังจากจุดข้างเคียง ระยะ debond/development ของ strand วัดจากปลายหล่อจริง ส่วนช่วงเหล็ก deck คงใช้แกน Loads

หัวตันเป็นสี่เหลี่ยมเต็มของ precast ความสูง/ระดับ y ใช้หน้าตัด I เดิม taper เคลื่อนขอบด้านข้างไปหาสี่เหลี่ยมตามสัดส่วนระยะเชิงเส้น รองรับ chamfer แยกจาก C1 เดิม วัสดุและตำแหน่งเหล็ก/strand ใช้ข้อมูลที่มีอยู่ ไม่สร้างเหล็กหัวตันให้เอง และไม่รวม diaphragm เป็นเนื้อ precast

Final composite flexural/depth checks รวมรูป precast ของจุดนั้นกับ deck เดิมตาม route เดิม ส่วน web shear และ torsion เป็น precast เท่านั้น

AASHTO solid torsion ใช้ `be=Acp/Pcp` และ Ao ของแนวศูนย์กลาง effective wall ตาม C5.7.3.6.2 ส่วน ph มาจากแนวศูนย์กลางปลอกตาม cover+db/2 ไม่ใช้ Acp แทน Ao และไม่ใช้สูตร ACI `0.85Aoh`

หัวตัน 600×1,500 มม. ไม่มี chamfer ให้ Acp=900,000 มม.², Pcp=4,200 มม., Ao=495,918.367 มม.² ถ้า cover=40 มม. และปลอก DB12 จะได้ ph=3,832 มม. สำหรับ web เดิม 200 มม. จะได้ bv=600 มม. ที่หัวตัน, 400 มม. กลาง taper และ 200 มม. ในช่วง I การเพิ่ม bv ไม่เพิ่ม Vs เป็นสามเท่าโดยอัตโนมัติ

## กราฟและการยอมรับ

ไฟล์ CSI ชุดนี้มีจุดทุก 1 ม. จึงไม่ตรงช่วง taper 1.50–1.75 ม. เส้นกำลัง Vn/Tn เพิ่มจุดรอยต่อ/ภายในหัวตันและ taper โดย interpolate แรงทั้งเวกเตอร์ระหว่างสองแถวของ case เดียวกันเฉพาะภายในช่วงข้อมูล

จุดเหล่านี้ระบุ **CAPACITY DIAGRAM / DIAGRAM ONLY** และ interpolated source, D/C ว่าง ไม่เพิ่มแถว Loads ไม่เพิ่ม design PASS ไม่ใช้หา governing หากมีเวกเตอร์แรงขัดกันที่ x เดียวกันจะไม่ interpolate กราฟ Combined D/C ยังคงจุดตรวจจากแรงจริงเดิมและแนวรอยต่อหน้าตัด

กำลังที่ผ่านเชิงตัวเลขยังเป็น REVIEW ถ้ายังไม่ยืนยัน Mux/Nu อ้างกับ centroid ของหน้าตัดตำแหน่งจริง แอปไม่แปลง `Nu×eccentricity` โดยเดา reference ของ CSI การตรวจ bearing, transfer, anchorage และ D-region/strut-and-tie ของหัวตัน/taper ต้องตรวจแยก รวมถึงปลอกปิดและเหล็กตามยาวรอบหัวตันจริง การยืนยันปลอก I เดิมอย่างเดียวไม่ยืนยันหัวตัน

Native Max/Min moving-load bounds ยังคงเป็น ENVELOPE / REVIEW ตาม source gate เดิม ไม่เปลี่ยนเป็น concurrent actions โดยอัตโนมัติ ผล FAIL ที่ทราบยังเป็น FAIL

**ขอบเขตเวอร์ชันนี้คือหน้าตัดตามระยะสำหรับ ULS sectional checks** SLS stresses/deflection, FE stiffness/self-weight และ diaphragm design ยังคงโมเดลเดิม หากต้องเปลี่ยนความแข็ง/น้ำหนักในแบบจำลอง CSI ให้แก้ใน CSI แล้วนำแรงใหม่เข้าแอป

## ผลตรวจ

Compile, regression, AppTest ของ app.py จริง, native CSI และ browser มีหลักฐานใน `qa/evidence/igird_endsection18/` ตรวจซ้ำหลังการกู้สภาพแวดล้อมก่อนจัด ZIP

ตรวจค่าแรงเดิม 640 แถว / 2 girders และการใช้หัวตัน 1.50+0.25 ม. ผลกลางคานเท่าเดิม:

| Girder | Maximum numerical Combined D/C ก่อน | หลัง |
|---|---:|---:|
| BOBJ1 / Left Exterior Girder | 1.375059 | 1.375059 |
| BOBJ1 / Interior Girder 2 | 1.749330 | 1.749330 |

หัวตันเพิ่มกำลังเฉพาะช่วงที่กำหนด แต่ governing ยังอยู่นอกหัวตัน จึงยังต้องแก้จุดที่ไม่ผ่านในช่วง I การทดสอบไม่ได้เพิ่มเหล็กหรือยืนยันรายละเอียดที่ไม่มีข้อมูล

2 source-text tests เก่าเกี่ยวกับ UI/README ล้มเหลวใน AUTOLOAD17 เดิมเช่นกัน แยกตรวจและระบุใน validation ไม่เติมข้อความหลอกให้ทดสอบผ่าน ไม่มี solver cache/checkpoint ใหม่ใน ZIP

Repo summary: Add station-based solid ends and tapers for I-girder ULS geometry, capacity checks, previews and JSON inputs.
