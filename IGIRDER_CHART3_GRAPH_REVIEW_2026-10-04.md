# IGIRDER.CHART3 — ตรวจกราฟตลอดความยาวคาน

พัฒนาต่อจาก IGIRDER.VTQA1 โดยใช้ AASHTO LRFD 9th Edition (2020) จากไฟล์ SECTION 5 ที่ผู้ใช้ให้มา งานนี้แก้การจัดข้อมูลกราฟและเพิ่มตารางกำลังสำหรับกราฟระหว่าง Calculate ผลตัดสิน Shear, Torsion และ Combined V+T เดิมยังใช้แถวออกแบบเดิม

## สาเหตุที่กราฟขาด

Excel `CSiBridge_Left_Exterior_Max_Min_latest.xlsx` มี 80 แถวแรง และแรงทั้ง 6 ช่องรวม 480 ค่า แอปใช้ลำดับแถวซ้ำที่ station เดียวกันสร้างชื่อ set 1/2 โดย set ไม่ใช่ load case อิสระและไม่ใช่หลักฐาน Before/After

| กลุ่มในไฟล์ | จำนวนแถวเดิม | ช่วง x เดิม (ม.) | จุดปลายที่มีใน Excel |
|---|---:|---|---|
| Max / set 1 | 21 | 0–20 | แถว 3 และ 81 |
| Max / set 2 | 19 | 1–19 | จุดปลายร่วมอยู่ใน set 1 ของ Max |
| Min / set 1 | 21 | 0–20 | แถว 4 และ 82 |
| Min / set 2 | 19 | 1–19 | จุดปลายร่วมอยู่ใน set 1 ของ Min |

เมื่อหน้า Selected case กรองเหลือ set 2 ก่อนสร้างกราฟ จุดปลายร่วมของ Excel จึงไม่ถูกแสดง ทั้ง Shear, Torsion และ Mux ใช้ตัวสร้างเส้นแรงร่วมกัน

| ItemType | Excel row | x (ม.) | V2 → Vuy (kN) | T → Tu (kN-m) |
|---|---:|---:|---:|---:|
| Max | 3 | 0 | −692.468 | 119.6057 |
| Min | 4 | 0 | −1392.077 | 55.5027 |
| Max | 81 | 20 | 1409.165 | −58.0081 |
| Min | 82 | 20 | 674.661 | −134.3752 |

อีกสาเหตุหนึ่งเป็นคนละเรื่อง: Torsion เดิมคืนผลทันทีเมื่อ |Tu| ≤ 0.25φTcr จึงไม่มี φTn ในแถวนั้น แม้ข้อมูลหน้าตัดและเหล็กจะพร้อม กราฟเส้นกำลังจึงขาดกลางคาน การไม่ต้องออกแบบแรงบิดตามเกณฑ์นี้ไม่ได้ทำให้กำลังของหน้าตัดเท่ากับศูนย์

## สิ่งที่แก้

1. ใช้จุดปลายจริง x=0/L ร่วมกันเฉพาะ metadata ต้นทางที่ตรงกัน: schema, girder sheet, case, Max/Min, distance column และชนิด envelope ต้องมีแถวปลายเพียงแถวเดียวและแรงทั้งหกเป็น finite
2. กราฟคงทุกค่าเดิมตามเครื่องหมาย CSI จุดที่ใช้ร่วมแสดง originating case, worksheet, Excel row และคำว่า diagram only ใน hover ไม่มีการเพิ่มแถวในตาราง import หรือแถวออกแบบ ไม่มีการเติม station ภายใน ไม่มีการเลือกค่าเมื่อจุดปลายหลายแถวขัดแย้งกัน
3. Calculate สร้าง `shear_diagram_capacity_df` และ `torsion_diagram_capacity_df` เพิ่ม แถวที่มีกำลังเดิมใช้กำลังเดิม จุดปลายร่วมของ Shear ใช้แรงปลายจริงในการคำนวณ β/θ/φVn แทนแถว diagram เดิมที่กำหนดแรงศูนย์ ทำให้จุดปลายร่วมของ set 1/2 มีกำลังตรงกัน ส่วน Torsion ที่ต่ำกว่าเกณฑ์หรือ Tu=0 ประเมินสมการกำลังต่อด้วยแรงที่ station นั้นจริงและ source gates เดิม
4. ตารางใหม่ทุกแถวมี Status=`DIAGRAM ONLY` และ D/C=`NaN` ไม่เข้าการเลือก governing, Result Summary หรือการรับรอง Combined V+T แถวตัดสินเดิมไม่ถูกเขียนทับ
5. φTn ของกราฟใช้ 5.7.3.6.2: Tn=2Ao(At/s)fy cotθ สำหรับ λduct=1 ของหน้าตัดทึบใน route นี้; θ ใช้ General Procedure ที่แก้ Vu เป็น Veff จากแรงจริง ไม่มี θ=45° ที่สมมติขึ้น ไม่มีการคัดลอกกำลัง station ใกล้เคียงไปที่ปลาย
6. ช่วงที่ source ไม่พร้อมคงค่าไม่ทราบ มี × สีเทาที่ฐานกราฟด้วยพิกัด paper จึงไม่ใช่กำลังศูนย์ Hover และตาราง Missing capacity บอกสาเหตุ จุดกำลังที่เหลือเพียงจุดเดียวมี marker ให้เห็น ไม่หายไปเพราะ mode=lines
7. แกนกราฟ Shear, Torsion, Construction/Final flexure, interface shear และ Combined component view ครอบคลุม span จริง เส้น D/C ยังคงแสดงเฉพาะแถวออกแบบที่ประเมินได้ แถว support boundary ไม่ถูกเติม D/C

## จุดปลายและข้อมูล development

แบบจำลอง QA กรณีแรกใช้ SD40 fy=390 MPa, เหล็กต่อเนื่อง, ld=1000 mm และไม่ยืนยัน anchorage ที่ปลาย ลวดอยู่ที่ physical cut ends จึงไม่มีส่วนที่พัฒนาแรงผ่าน bond ที่ x=0/L ใน General Procedure ที่คำนวณ εs ณ station จริงนี้ ตัวหาร EsAs+EpAps ที่ปลายเป็นศูนย์ ทำให้ไม่มี θ/φTn ที่รองรับ กราฟจึงระบุว่ากำลังปลาย unavailable แทนการคัดลอกค่าใกล้เคียง

QA กรณีที่สองใช้ข้อมูลวัสดุเดียวกันและกดยืนยัน full-strength anchorage ทั้งสองปลายผ่าน checkbox จริง ผลคือ θ และ φTn คำนวณที่ปลายได้ และเส้นกำลังทั้ง 4 กลุ่มมีค่าครบ 0–20 ม. นี่เป็นสมมติฐานทดสอบที่ระบุชัด ไม่ใช่การยืนยันรายละเอียดเหล็กของผู้ใช้ โปรแกรมไม่ได้ติ๊ก checkbox หรือกำหนด fy ให้โดยอัตโนมัติ

AASHTO 5.7.3.4.2 ยังอนุญาตให้ใช้ εs จากระยะ dv ในการประเมิน β/θ ใกล้ support ภายใต้เงื่อนไขเรื่อง concentrated load Route สำรองนั้นไม่ได้ถูกเปิดโดยอัตโนมัติในงานนี้ การยืนยัน simply supported เพียงอย่างเดียวไม่ใช่ข้อมูล concentrated-load/anchorage ที่ครบ

## ผลตรวจ

- กราฟแรง 4 กลุ่มมีจุด x=0…20 ครบ โดยแถวแรงเดิมยังมี 80 แถวและ 480 ค่าเท่าเดิม
- φTn กลางคานที่เคยหายเพราะ threshold กลับมาคำนวณได้ 17 station rows
- QA แบบไม่ยืนยันปลาย: ตารางกราฟ 84 แถว กำลังคำนวณได้ 76 แถว; 8 แถวปลายระบุ unavailable
- QA แบบยืนยันปลาย: ตารางกราฟ 84 แถว กำลังคำนวณได้ทั้งหมด 84 แถว
- เทียบ DataFrame ตัดสิน/critical/boundary ทั้ง 6 ตารางกับโค้ด VTQA1 แบบ `check_exact=True` ผ่าน: Shear 88 แถว, Torsion 80 แถว, Combined 88 แถว และตารางประกอบเดิมไม่เปลี่ยน
- ใช้ AppTest ของ app.py จริง ทดสอบ Calculate, การเปลี่ยนกรณี, checkbox anchorage, Flexure ทั้งสอง stage และ Interface Shear ไม่มี Streamlit exception การเปลี่ยนกรณีและ review ไม่เรียก solver หรือคำนวณตารางกำลังใหม่
- ตรวจสมการ θ/φTn และ θ/φVn ของตารางกราฟอย่างละ 84 station rows โดยแทนค่า US customary units อิสระ รวม 336 scalar comparisons เพิ่มจากการตรวจสมการ V/T เดิม
- ภาพ PNG เป็น scientific plots จากเส้นของ production Plotly และมี HTML ที่ฝัง Plotly JS ใช้ดูได้โดยไม่ต้องใช้ CDN ไม่ใช่ browser screenshot

ผล regression, compile, startup และ fresh ZIP verification อยู่ใน `qa/evidence/igird_chart3/fresh_validation_summary.json` ภายใน ZIP

## การใช้งาน

เปิดแอปจาก ZIP นี้แล้วกด Calculate Torsion หรือ Calculate Shear + Torsion ใหม่หนึ่งครั้ง เพื่อสร้างตารางกำลังสำหรับกราฟ เลือก Chart view → Selected case — demand / capacity แล้วเลือก Case for diagram ใช้ expander Torsion diagram capacity — station / source / θ trace ดูค่าที่นำมาสร้างเส้นแดง

P ยังคงอ่านจาก Excel ผู้ใช้กำหนด P=0 เองตามที่ตกลง ไม่มี override ในแอป V3/M2 ยังคงเป็น signed reference-only หน้าตัด V/T ยังเป็น precast I-girder ตาม route ที่ตรวจไว้; deck strength อยู่ใน Final-Composite flexure ไม่มีการเปลี่ยนไปใช้ ACI จากไฟล์ประกอบอื่น
