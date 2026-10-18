# IGIRDER.CLEAN39 — ลบฟอร์มซ้ำและกำหนดวิธีพัฒนากำลัง composite

17 ตุลาคม 2026 · ต่อจาก COVER38

**สถานะ: งานลบฟอร์ม legacy เสร็จแล้ว ส่วนตัวคำนวณกำลัง full composite Vn / Tn / V–T สำหรับออกแบบยังไม่เสร็จ รุ่นนี้ไม่ใช่การส่งมอบตัวคำนวณกำลังเต็มระบบ**

## เป้าหมายที่ต้องรักษา

แอปต้องคำนวณระบบ I-girder–U-dowel–slab ร่วมกันจากเหล็กและคอนกรีตที่มีอยู่จริง ผู้ใช้ยังนำเข้า Girder forces จาก CSiBridge และกรอกข้อมูลจากแบบเป็นหลัก ไม่ต้องเดาแรงรอยต่อ ค่า slip หรือค่าสอบเทียบแบบจำลอง

การตรวจคาน I เพียงส่วนเดียวแล้วเปลี่ยนชื่อผลเป็น composite ไม่บรรลุเป้าหมาย การรวม slab ใน flexure หรือผ่าน interface shear ก็ยังไม่เท่ากับคำนวณกำลัง composite torsion ครบ

Vn มีหน่วยแรง Tn มีหน่วยแรงคูณระยะ ส่วน V–T เป็นการตรวจแรงร่วม/ขอบเขตกำลัง ไม่ใช่การนำ Vn กับ Tn มาบวกเชิงตัวเลข

## งานที่ทำจริงใน CLEAN39

- ลบ Advanced — legacy research tools, Show legacy research inputs และตาราง closing bar / manual overlap ออกจากหน้าผู้ใช้
- ลบทางแสดง archived composite model results ของสมมติฐานเก่า
- ตัดการเรียก solver COUPLED34 จาก Calculate Flexure แม้ project เก่าหรือ session จะยังมี enabled / opt-in เป็น true
- แก้ข้อความแนะนำในหน้าข้อมูลรอยต่อและหน้า Torsion ไม่ให้ชี้กลับไปยังฟอร์มที่เลิกใช้
- คง Slab mesh บน–ล่าง, ลำดับเหล็กขวางอยู่นอก/เหล็กยาวอยู่ใน, U geometry และ dowel zones ใน editor หลักชุดเดียว
- คงปุ่ม Calculate Flexure และการตรวจ section flexure / interface shear / selected-section detail review เดิม
- เปลี่ยน runtime bundle version เพื่อไม่ยอมรับ bundle เก่าเป็นผลของ orchestration ใหม่นี้

ไฟล์ historical model ยังอยู่เพื่ออ่านโครงการ/ทดสอบพฤติกรรมเดิมและใช้ helper ที่ station review พึ่งพา แต่ไม่มีทางเรียกฟอร์มหรือ solver เก่าจาก workflow ปกติ และข้อมูลเก่าไม่ได้ถูกนำมาแทน mesh / U detail หลัก

ไม่มีการเปลี่ยนสมการกำลัง ไม่มีการเปิด full-composite PASS ไม่มีการแก้แรง CSI ไม่มีการย้ายเหล็กหรือ strand และไม่มีการเปลี่ยน input JSON หรือเพิ่มการบันทึกผลคำนวณลง JSON ใช้ Project JSON ปัจจุบันต่อได้

## วิธีที่เลือกสำหรับพัฒนาตัวคำนวณ

เลือกวิธีหน้าตัด AASHTO สำหรับบริเวณที่เข้าเงื่อนไข ร่วมกับแบบจำลองถ่ายแรงสามมิติแบบ Strut-and-Tie ในบริเวณรอยต่อ/บริเวณที่ต้องตรวจ load path โดยต้องตรวจขอบเขตการใช้แต่ละวิธี ไม่อ้างว่า STM สามารถยกเว้นข้อกำหนด torsion detailing ได้โดยอัตโนมัติ

### 1. เส้นทางกำลังที่เข้าเงื่อนไขวิธีหน้าตัด

ใช้ AASHTO LRFD 2020 ข้อ 5.7 สำหรับ sectional shear–torsion และ 5.7.4 สำหรับ interface shear โดยอ้างอิง geometry ของเส้นทางรับแรงและเหล็กที่พัฒนาแรงได้จริง

- หา Ao / ph จากเส้นทางปิดที่ตรวจสอบได้ ไม่ใช้ slab effective width Be เป็นความกว้างเซลล์แรงบิดโดยตรง
- ใช้เหล็กขวางชุดเดียวรับ concurrent shear กับ torsion ตาม 5.7.3.6.1 และตรวจ concrete limit / longitudinal reserve ร่วมด้วย
- รักษา Nu, M2, M3, V2, V3, T ที่เกิดพร้อมกันและจุดอ้างอิงเดียวกัน ถ้าสูตรหรือ implementation รองรับเพียงระนาบเดียว ต้องไม่ตัด M2 / V3 ทิ้งเพื่อเข้าสูตร
- ตรวจ development, strand transfer/debonding และกำลังที่ถูกใช้ไปกับ axial/flexure ไม่ใช้พื้นที่เหล็กทั้งชุดซ้ำเป็น reserve ของ torsion

### 2. U-dowel 90° และ slab mesh ต้องมี joint load path ที่พิสูจน์ได้

ข้อ 5.10.8.2.6d ของ AASHTO 2020 มีข้อกำหนดสำหรับ closed stirrups / splice และระบุการยึดเหนี่ยว transverse torsion reinforcement ด้วย standard 135° hooks รอบเหล็กยาว จึงไม่ถือว่าการมี U-hook 90° กับตะแกรงพื้นทำให้เป็น closed torsion hoop ตามวิธีหน้าตัดโดยอัตโนมัติ

อย่างไรก็ตาม 90° hook อาจเป็น anchorage ของ tension tie ใน STM ได้เมื่อเข้าเงื่อนไขของวิธีนั้นและตรวจครบ การมี hook/ระยะฝังเพียงอย่างเดียวยังไม่ยืนยันกำลังของระบบ

STM ที่จะใช้ต้องมี:

- สมดุลสามมิติและ load entry / boundary ที่แทนโครงสร้างจริง รวมผลแรง ณ ขอบบริเวณที่ตรวจและแรงภายนอกภายในบริเวณนั้น
- คอนกรีตคานและ slab แยกกันที่ construction joint เชื่อมด้วย contact/friction และเหล็กข้ามรอยต่อ ไม่สร้าง concrete bridge หรือฐานรองรับพื้นปลอม
- compression struts, tension ties และ nonhydrostatic nodal zones ที่มีหน้ารับแรงจริงตาม 5.8.2.2–5.8.2.6
- tie anchorage ณ ขอบ extended nodal zone ตาม 5.8.2.4.2 และ 5.10.8 ไม่ใช้ระยะ hook วัดจาก interface แทนระยะที่ node เสมอไป
- crack-control / splitting / confinement และ deformation capacity ที่เพียงพอสำหรับ assumed force redistribution
- ขา U สองขา ส่วนโค้ง และ hook เป็นเหล็กชิ้นเดียวกัน ไม่สร้างแหล่งกำลังอิสระซ้ำ ร่วมใช้กำลังกับแรงที่รอยต่อและ shear/torsion

ไม่จำเป็นต้องบังคับทำ nonlinear slip analysis ในทุกการตรวจที่เข้าเงื่อนไขวิธีมาตรฐาน แต่สมมติฐาน contact/perfect bond/ductility ของแบบจำลองที่สร้างขึ้นเองต้องมีหลักฐานรองรับ การตรวจ KKT หรือสมดุลเชิงตัวเลขไม่ใช่หลักฐานยืนยันโครงสร้างทั้งหมด

### 3. ผลลัพธ์และการพิสูจน์ว่านับ composite จริง

ตัวคำนวณเป้าหมายต้องรายงาน Vn, Tn และขอบเขต/อัตราส่วน V–T แยกหน่วยและกรณีทดสอบให้ชัด ระบุด้วยว่าเป็น pure resistance หรือ conditional resistance เมื่อคง N/M ไว้ พร้อม governing component / station / concurrent case และ trace การใช้กำลังเหล็กและคอนกรีต

ต้องทดสอบเทียบคานล้วนกับระบบ composite บนแรงและจุดอ้างอิงเดียวกัน โดยตรวจอย่างน้อย:

1. เอา U ออกแล้วเส้นทางถ่ายแรงที่อาศัย U ต้องหายไป ไม่มีแรงลัดผ่าน joint หรือ rigid boundary
2. เปลี่ยนเหล็กพื้นบน–ล่าง/ตำแหน่ง/กำลังคอนกรีตแล้วผลกลไกที่เกี่ยวข้องต้องตอบสนอง และยังคงข้อจำกัดกำลังส่วนอื่น
3. เพิ่ม mesh ที่ไม่ใช่ตัวควบคุมไม่จำเป็นต้องเพิ่มกำลัง; อ่อนกำลังวัสดุใดต้องไม่ทำให้ feasible strength domain โตขึ้น
4. shear, torsion, axial/flexure และ interface actions ใช้กำลังเหล็กชุดเดียวกัน ไม่บวก Tn ของคาน + dowel + slab แบบแยกอิสระ
5. ตรวจ T สองทิศ, slab opening, contact loss, development ใกล้ปลายคาน, shear สองทิศ และรูปหน้าตัด I/ส่วนตัน
6. เทียบสมการมาตรฐาน/ตัวอย่างคำนวณอิสระ และความไวต่อ mesh / boundary ถ้าอยู่นอกขอบเขตวิธีมาตรฐาน ต้องมี validation ที่เหมาะกับรายละเอียดนั้น
7. คำนวณทุก station/case ที่จำเป็นก่อนสรุป governing member ไม่ใช้สถานีที่ |T| สูงสุดเพียงสถานีเดียวแทน utilization envelope

การนับส่วน composite อย่างถูกต้องไม่ได้รับประกันว่า Tn จะเพิ่ม เพราะ joint, anchorage, concrete หรือเหล็กส่วนอื่นอาจเป็นตัวควบคุม

## จุดติดขัดที่ตรวจพบในโครงการปัจจุบัน

Project 31 / COVER38 มี raw load bank 640 แถว รักษาแรงทั้งหกไว้ครบ ที่สองสถานีที่เลือกจากข้อมูลจริงพบแนว U ตัดกับพิกัดเหล็กยาว/strand 23 ตำแหน่งต่อสถานี กรง hoop ที่อนุมานก็มีจุดตัด ต้องตรวจให้ cage ในโมเดลตรงกับแบบจริงก่อนใช้ผลกำลัง

หลายรายการเหล็กยาวใน JSON มี Note ว่า Auto perimeter และบาง strand rows มี Note ว่า Auto section default ข้อความเหล่านี้บอกที่มาเริ่มต้น แต่ไม่ได้ยืนยันว่าผู้ใช้ไม่ได้แก้ตำแหน่งภายหลังหรือว่าตรงกับแบบจริง จึงไม่ย้ายพิกัดเหล่านี้เงียบ ๆ

สำหรับสมมติฐาน U ขาตรงเดิม DB12, D72, web200, cover40 ต้องมี A84–108 มม. แต่เหล็กยาว DB16 ที่ x=±50 มม. ทำให้ช่วงจำเป็นนั้นไม่เหลือค่าที่หลบได้ การเปลี่ยน A ค่าเดียวจึงไม่แก้ ต้องตรวจ cage/strand/U เป็นชุด ไม่ใช่ข้อสรุปว่ารายละเอียดก่อสร้างจริงมีข้อบกพร่อง

โมเดล JOINT37 เดิมเป็นการทดลองถ่ายแรงเฉพาะที่ยาว400 มม. โดยป้อนแรงเข้าคานและปล่อยปลายพื้นอิสระ อีกการทดลองป้อน torque เข้าพื้นโดยเฉพาะ ทั้งสองกรณีไม่ใช่ member sectional Tn และไม่ใช่การกู้แรง Beam/Slab จาก CSI ห้ามนำตัวเลข local experiment ไปแสดงเป็น full-composite member resistance

ส่วนที่ยังต้องพัฒนาคือตัวแทน nodal faces / anchorage และ boundary/load entry ที่ตรวจอ้างอิงได้ รวมถึง resistance model validation **การลบฟอร์มใน CLEAN39 ไม่ได้ทำส่วนเหล่านี้เสร็จ**

## ผลตรวจซอฟต์แวร์ของ CLEAN39

- ชุด regression ที่เลือก 468 tests ผ่าน มี warnings 7 รายการ; ไม่ได้อ้างว่ารัน test ทั้ง repository
- เพิ่ม 4 tests สำหรับการตัด legacy dispatch, หน้าผู้ใช้จริง และคำแนะนำที่ไม่ชี้ไปฟอร์มที่เลิกใช้
- Browser ใช้แอปจริงกับ Project31/COVER38 แสดงหนึ่งสถานีจริงต่อ member จาก bank640แถว ไม่ใช่ full-span browser capacity run
- กด Calculate Flexure หนึ่งปุ่ม: section/interface/station/joint อย่างละ2ครั้ง และ legacy0ครั้ง แม้ flag เก่าและ metadata enabled ยังเป็น true
- ตรวจแก้ cover4ครั้ง, การใช้ input เดียวกันใน Sections/Analysis, member switch และเปิด/ปิด review โดยไม่คำนวณซ้ำ ที่1440และ1280px; ไม่พบ browser exception
- ค่าแรงนำเข้าไม่เปลี่ยน ผลกำลัง full composite ที่ยังไม่พร้อมยังถูกระงับตามเดิม

หลักฐานข้อความอยู่ใน qa/evidence/igird_clean39/ ไม่บรรจุภาพหน้าจอใน ZIP

## แหล่งอ้างอิงวิธี

- ไฟล์ที่ผู้ใช้ให้: SECTION 5 CONCRETE STRUCTURES.pdf, AASHTO LRFD Ninth Edition 2020 — 5.5.1/C5.5.1, 5.7.3.6, 5.7.4, 5.8.2, 5.10.8.2.6d
- FHWA-NHI-17-071, Strut-and-Tie Modeling for Concrete Structures, Design Examples (2017), โดยเฉพาะการยึดเหนี่ยว tie และสมดุลสามมิติ ตัวอย่างนี้อ้าง AASHTO8th Edition จึงใช้ประกอบการตรวจวิธี ไม่แทนข้อกำหนด2020ของโครงการ: https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf

## Repo summary

Retire duplicate legacy composite controls and solver dispatch; retain shared slab/U inputs, current engineering gates and unchanged CSI loads. Full composite resistance implementation remains incomplete.
