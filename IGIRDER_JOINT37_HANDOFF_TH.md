# Concrete Section Pro — IGIRDER.JOINT37

วันที่ 17 ตุลาคม 2026 · พัฒนาต่อจาก STATION36

ฉบับนี้เพิ่มแบบจำลองถ่ายแรงคาน–U-dowel–พื้นแบบ 3 มิติ พร้อมตัวตรวจสมดุลและ compatibility ของกลไกที่สมมติไว้ ตรวจข้อมูลโครงการจริงแล้วพบ **แนว U ตัดกับพิกัดเหล็กยาว / strand 23 ตำแหน่งในแต่ละสถานีที่เลือก** จึงระงับผลกำลังของแบบจำลองใหม่ไว้ ค่า Full composite Tn, φTn และปัจจัย V–T สำหรับออกแบบจริงยังไม่ถูกยอมรับ

นี่เป็นข้อขัดแย้งของพิกัดใน input / แนวเหล็กที่โปรแกรมสร้าง ไม่ใช่ข้อสรุปว่ารายละเอียดก่อสร้างจริงมีข้อบกพร่อง และการทดสอบซอฟต์แวร์ผ่านไม่ใช่การรับรองโครงสร้าง

## สิ่งที่เพิ่มในรุ่นนี้

- สร้าง U ต่อเนื่องทั้งสองขา ส่วนโค้งคืนด้านล่าง hook90° และหาง hook ด้านบน ใช้พื้นที่เหล็กชุดเดียวตามแนว ไม่บวกกำลังขา / ส่วนโค้ง / หางเป็นกำลังอิสระซ้ำกัน
- แยกคอนกรีตคานกับพื้นเป็นคนละชุด node เชื่อมผ่าน contact ที่รับอัด / แรงเสียดทาน และเหล็ก U ที่ข้ามรอยต่อเท่านั้น พื้นไม่ยึดกับฐานรองรับของคานผ่าน end plate ร่วม
- ใช้แรงทั้งหกพร้อมกัน มี sparse LP สำหรับขีดจำกัดของกลไก และ complementary-energy QP สำหรับสถานะ compatible ภายในกฎวัสดุสมมติเดียวกัน
- เก็บ post-loss Pe เป็นสถานะอ้างอิงสมดุลในคาน ไม่บวก Pe ซ้ำเข้า Nu ไม่ลด Pe ด้วย φ และไม่หัก elastic shortening ซ้ำ หาก Pe ขัดกับเพดานแรงที่พัฒนาได้จะระงับการคำนวณแทนการลด Pe เงียบ ๆ
- ตรวจแนว U / hoop ที่สร้างขึ้นกับเหล็กยาวและ strand รายเส้น พร้อมรูป 3 มิติและเครื่องหมายสีแดง ระงับทั้งผลกำลังใหม่และการแสดงตัวเลข benchmark กรงคานรุ่นก่อนเมื่อผลตรวจปัจจุบันพบการตัดกัน
- ใช้ **Calculate Flexure** ปุ่มเดิม ไม่มีปุ่ม Run ใหม่และไม่มีช่องกรอกใหม่ในส่วนนี้ การเปิดผล / เปลี่ยนคานที่ดูไม่สั่งคำนวณซ้ำ

## ผลตรวจรายละเอียดจาก JSON โครงการ

| สถานีที่เลือก | U เทียบเหล็กยาว / strand | Hoop ที่สร้างขึ้นเทียบเหล็กยาว / strand | ผลกำลังใหม่ |
|---|---:|---:|---|
| BOBJ1 / Interior Girder 2, x19.000 ม., U2A / Max / Before | 23 ตำแหน่ง | 16 ตำแหน่ง | WITHHELD |
| BOBJ1 / Left Exterior Girder, x18.000 ม., U2A / Min / After | 23 ตำแหน่ง | 34 ตำแหน่ง | WITHHELD |

จำนวนข้างต้นเป็นพิกัดหน้าตัดที่แนวเหล็กซ้อนทับกัน ไม่ใช่จำนวนจุดชนตลอดสะพาน สถานี x19 เป็นส่วนตันปลายคาน ส่วน x18 เป็นหน้าตัด I และ hoop เป็นรูปที่โปรแกรมอนุมานจาก cover ซึ่งยังต้องตรวจเทียบแบบจริง

สำหรับรูป U ขาตรงร่วมตลอดคาน DB12, D=72 มม., เอวคาน200 มม. และ cover40 มม. ได้เงื่อนไขจำเป็น:

- ระยะ A ระหว่างศูนย์กลางขาต้องไม่น้อยกว่า D+db = **84 มม.** เพื่อวางส่วนโค้งล่างได้
- A ต้องไม่มากกว่า 200−2×40−12 = **108 มม.** เพื่อคง cover ที่เอวคาน
- เหล็กยาว DB16 ที่ x=±50 มม. ต้องเว้นรัศมีรวมกับ DB12 อย่างน้อย14 มม. การหลบแนวขาตรงจึงต้องใช้ **A≤72 หรือ A≥128 มม.** ซึ่งไม่ทับช่วง84–108

ดังนั้น **การปรับค่าแนะนำของ A อย่างเดียวแก้ไม่ได้** และเงื่อนไขนี้ยังไม่ได้รวมระยะห่างสุทธิตามมาตรฐานหรือ tolerance ก่อสร้างด้วย ต้องจัดพิกัดเหล็กยาว / strand และ U ให้สอดคล้องกันทั้งชุด หรือพิสูจน์รูป cage จริงที่ต่างจากแนวที่โปรแกรมอนุมาน

ค่า A100 ที่เสนอใน STATION36 ผ่านการคัดกรอง cover ของขา U เทียบขอบคอนกรีต แต่ยังไม่ได้พิสูจน์ว่าอยู่ร่วมกับเหล็กทุกเส้นได้ รุ่นนี้จึงเปิดเผยข้อจำกัดเพิ่ม ไม่ย้ายเหล็กหรือ strand ที่ระบุพิกัดไว้เพื่อสร้างผลผ่าน

JSON รุ่นนี้คงข้อเสนอ13ช่องของ STATION36 พร้อมประวัติค่าเดิมไว้ครบ เช่น A100, E150, B200 อัตโนมัติ, D=6db=72, C200, F1400 และเหล็กขวางพื้นบน / ล่าง **ข้อเสนอ** DB12@150 cover66 เหล็กเหล่านี้ยังเป็นข้อเสนอออกแบบ ไม่ใช่คำยืนยัน as-built

เมื่อเทียบกับ JSON STATION36 เปลี่ยนเพียง `metadata.igird_joint37_settings = {"enabled": true}` ไม่เพิ่มผลคำนวณลง Project JSON

## แรงจาก CSiBridge และขอบเขตที่ตรวจ

อ่าน raw load bank เดิมครบ640แถวจาก2 girders แล้วเลือกสถานีที่ |Tu| หลังแปลงจุดอ้างอิงสูงสุดในแต่ละ member การเลือกนี้ยังไม่ใช่การหาสถานี utilization สูงสุดทั้งสะพาน

| Girder / สถานี | P (kN) | V2 (kN) | V3 (kN) | T (kN·m) | M2 (kN·m) | M3 (kN·m) |
|---|---:|---:|---:|---:|---:|---:|
| Interior Girder 2 / x19 หลังแปลง | −17.429 | 880.295 | 325.320 | 333.7329 | 152.5732 | 956.4547 |
| Left Exterior / x18 หลังแปลง | −80.542 | 307.566 | −393.540 | −226.3334 | −519.5684 | 702.4529 |

ใช้เวกเตอร์โมเมนต์ทางกายภาพ `(T, −M2, M3)` ตาม mapping ของแอป และ `M_O = M_C + (C−O) × F` เพียงครั้งเดียว ไม่ตัด M2/V3 หรือบังคับ M3 ปลายคานเป็นศูนย์ ผู้ใช้ยังนำเข้า Girder forces แบบเดิม ไม่ต้องอัปโหลดแรงซ้ำสำหรับ milestone นี้

แบบจำลองใหม่มีความยาวเฉพาะที่400 มม. (2ช่วง×200) ไม่ใช่แบบจำลอง20 ม. โดยค่าเริ่มต้นป้อน wrench รวมเข้าหน้าตัดคานและปล่อยปลายพื้นอิสระ เป็นการทดลองถ่ายแรงเฉพาะที่ ไม่ใช่การกู้แรงส่วน Beam / Slab จาก CSI แบบจำลองทดลองอีกชุดป้อน pure roll เข้าพื้นเพื่อทดสอบเส้นทางถ่ายแรง แต่ไม่เรียกแรงนั้นว่า Girder Tu และไม่บวกผลเข้ากำลังคาน

เมื่อพิกัดตัดกัน ทั้ง LP ของ JOINT37 และ compatible-state QP ของโครงการจะไม่ถูกเรียก ผลใหม่ทุกช่องเป็นค่าว่างที่มีเหตุผลกำกับ ไม่ใช่ศูนย์กำลังหรือผล FAIL ที่รับรองแล้ว

## วิธีคำนวณและสิ่งที่ยังต้องตรวจ

สมดุลใช้ `Bf+p=0` พร้อมเพดานแรงสมาชิกและทรัพยากรร่วมของคอนกรีต ขีดจำกัดแบบจำลองต้องผ่านการตรวจสมดุล node, global wrench, free body พื้น, bounds, duality และ dual stationarity แยกจาก solver status

Contact ใช้ cohesion=0 และ friction cone แบบรูปแปดเหลี่ยมภายในวงกลม `sqrt(qx²+qz²) ≤ μC` แรงเฉือนสองทิศใช้ C ชุดเดียว พื้นที่สัมผัสและปริมาตร prism ไม่ถูกนับซ้ำ อย่างไรก็ตามกฎคอนกรีตที่จำกัด stress/volume ยังเป็นสมมติฐานใหม่ ไม่ใช่การตรวจหน้าของ nodal zone ครบตาม AASHTO

QP ลด complementary energy `½ Σ(f−f0)²/k` ภายในขอบเขตแรงเดียวกัน ตรวจทั้ง force / displacement compatibility และ KKT โดยใช้ nominal material bounds แยกจาก design-domain resistance factors มี spring stiffness ของ contact และ perfect embedded bond ที่ตั้งสมมติฐานไว้ กฎ friction แบบ associated flow มี dilation จึงยังไม่ใช่การทำนาย joint slip จริงที่สอบเทียบแล้ว

ตำแหน่ง hook และการมีเหล็กตะแกรงทั้งสองชั้นยังต้องตรวจ tie anchorage ณ ขอบ node จริง, concrete nodal faces, splitting / confinement และแรงที่ส่งเข้าตะแกรง การมี ldh เต็มจากรอยต่อไม่ได้หมายความว่าเต็ม fy ที่ node ใกล้ hook เสมอไป ตารางระยะ hook เทียบศูนย์กลาง mat เป็นเพียงตำแหน่งคัดกรอง **ไม่ใช่ผล FAIL ตามมาตรฐาน** โดยไม่ทราบขอบ node

ลำดับที่ต้องทำก่อนยอมรับ full composite resistance คือแก้ input geometry ให้เป็น cage ที่ตรวจเทียบแบบได้ กำหนดและตรวจ nodal faces / anchorage / slab continuity ให้ครบ แล้วสอบเทียบกลไกและผลกับคำตอบโครงสร้างอิสระที่เหมาะสม รวมถึงขอบเขตแรงร่วมจริงและความไวต่อ mesh / stiffness ไม่สามารถใช้จำนวนแบบทดสอบซอฟต์แวร์แทนขั้นตอนนี้ได้

อ้างอิงหลัก: AASHTO LRFD 9th Edition (2020), Section5 ที่ผู้ใช้ให้ โดยเฉพาะ5.7.3.1,5.8.2,5.8.2.4.2,5.8.2.5 และ5.10.8 ตัวอย่างประกอบ [FHWA: Strut-and-Tie Modeling Design Examples](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf) และ [ASPIRE: Combined Shear and Torsion](https://www.aspirebridge.com/magazine/2017Spring/AASHTO-BridgeDesign-Aspire-SPG2017-Web.pdf) อิง edition ก่อนหน้า จึงไม่ใช้เปลี่ยน edition โครงการ ส่วนการเรียก QP ใช้ [OSQP public Python API](https://osqp.org/docs/interfaces/python.html)

## วิธีใช้

1. ใช้ source ZIP JOINT37 และติดตั้ง `requirements.txt` ซึ่งเพิ่ม `osqp>=1.0,<2`; constrained mesh ยังคงต้องใช้ Shapely>=2.1,<3
2. โหลด JSON `concrete_section_pro_project_31_JOINT37.json`
3. ไป Analysis → ULS Strength → Flexure → Final — Composite แล้วกด **Calculate Flexure**
4. เปิด **Girder–U-dowel–slab — coupled transfer review** เลือกคานที่ Girder to review แล้วหมุน / ซูมรูปเพื่อดูจุดสีแดง เปิด Input path conflicts / anchorage location เพื่ออ่านพิกัดและระยะที่ต้องตรวจ

ผลตัวเลขเป็น runtime ของ session โหลด JSON แล้วต้องคำนวณใหม่ ตัวคำนวณวิจัยไม่เขียนผลเข้า production resistance, Result Summary, Report / QA หรือ Project JSON และหน้าดูผลไม่เรียก solver ซ้ำ

## การตรวจส่งมอบ

- ชุดทดสอบที่เกี่ยวข้อง **442 รายการผ่าน, 7 warnings เดิม** รวม32กรณีใหม่ ไม่ได้อ้างว่ารันทั้ง repository
- ทดสอบอิสระของขา U สองขา: `Tmax=A(F−O/2)` เมื่อมี opening O และ `Tmax=A(F−P/(2μ))` ใน fixture ที่กำหนด shear ร่วม ทดสอบ no-U, reflection, opening และ elastic sticking slip เทียบคำตอบ spring โดยตรง ไม่ใช้โมเดลโครงการที่พิกัดขัดแย้งเป็น benchmark
- ตรวจ post-loss Pe ด้วยคำตอบ parallel PS / concrete ที่ทราบล่วงหน้า ทั้งแรงภายใน, incremental shortening และ external Nu แยกกัน รวมกรณี Pe เกินเพดานต้อง block
- Replay ข้อมูลจริงทั้ง2 member จาก bank640แถว source actions / transported actions ตรงรุ่นก่อน input ไม่เปลี่ยน และยืนยันว่า LP/QP ใหม่ไม่ถูกเรียกเมื่อ geometry ไม่พร้อม
- Browser QA ใช้ปุ่ม Calculate จริงกับ **หนึ่งแถวจริงที่เลือกต่อ member** โดยคง640แถวไว้ใน session ไม่ใช่การคำนวณ full-span640แถวใน browser ตรวจความกว้าง1440/1280 รูปและคำเตือนชัด การเปลี่ยนคาน / เปิดผลไม่คำนวณซ้ำ ไม่มี browser exception
- Compile app.py และโมดูลที่แก้แล้ว หลักฐานอยู่ใน `qa/evidence/igird_joint37/` ไม่มี browser screenshots / cache / ไฟล์ชั่วคราวในชุดส่งมอบ

Repo summary:

```text
JOINT37: Add continuous U-dowel / separated girder-slab transfer and nominal compatible-state mechanics.
Audit actual bar/strand paths; withhold intersecting input models and older displayed core limits.
442 selected tests; 640 raw rows preserved; full composite design resistance remains withheld.
```
