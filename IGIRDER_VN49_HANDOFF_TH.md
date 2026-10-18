# IGIRDER.VN49 — แก้หน้า Vn และเวลารัน

ฐานพัฒนา: ZIP COMPOSITE48 ที่ส่งก่อนหน้า ไม่ใช้ Segmental Box Girder เป็นฐานของงาน I-girder นี้

## ปัญหาที่พบจาก Vn.pdf

PDF หน้า 2–4 และ 10 แสดงว่า composite model คำนวณได้ 0/304 แถวต่อ girder ข้อความจริงคือ “Explicit strand x positions must be finite, unique and match the strand count” จึงไม่มีตัวเลขในผลหลักทั้ง 608 แถว ปัญหานี้ต่างจาก interface/effective-width REVIEW ของ code route

หน้า Shear นำ Model Tn/V–T ขึ้นก่อน Vn และเลือกแถวควบคุม V–T มีข้อความซ้ำหลายตำแหน่ง ข้อความ equal controlling cases แสดงชื่อไฟล์/แถวเต็มจำนวนมาก อีกทั้ง Vn/Vn,max ซึ่งเป็น capacity cap ถูกนำไปแข่งกับ Vu/φVn ในการเลือก case แม้ cap จะไม่ถูกละเมิด

## สิ่งที่แก้

1. Pooled V/T model ใช้แรงรวมตามชั้น y ของ strand ไม่ได้ใช้พิกัด x จึงแยกข้อกำหนดนี้ออกจาก 3D spatial truss หากพิกัด x ไม่มี/ผิดรูปแบบจะเก็บเป็น unknown โดยไม่สมมติ x=0 ไม่จัด strand ใหม่ และไม่แก้ input จริง การวิเคราะห์ spatial 3D ยังบังคับพิกัด x ที่ตรวจได้ตามเดิม
2. หน้า Shear ใช้แถว V-only D/C สูงสุดของแต่ละ girder แสดง Model Vn ที่คง M3/N จริง, |Vu|, nominal D/C และกราฟเฉือน โดยไม่เอาค่า Tn/combined D/C มาเป็น metric หลักในหน้า Vn
3. กราฟแต่ละสถานีใช้ demand และ capacity จากแถวเดียวกัน เลือกตาม V-only D/C ไม่หาร envelope ที่มาจากคนละแถว มี governing marker และเครื่องหมาย × สำหรับ end-region ที่อยู่นอกโมเดล เส้นเชื่อมเป็นเพียงการช่วยอ่าน
4. แสดง Be, t slab, h I, dv, f’c ของ I/slab, fixed θ, การจัดสรรแรงให้ I hoops/U และบทบาทของเหล็กยาวพื้น พร้อมสูตรและหน่วยใน Calculation trace
5. หากคำนวณไม่ได้จะแสดงสาเหตุและจำนวนแถวที่ได้รับผลกระทบ ไม่แสดงชุด capacity cards ว่าง/None ตามปกติ ย่อข้อความ tied cases เป็นจำนวน พร้อมเก็บรายละเอียดในตาราง audit และลดหัวข้อ/การ์ดบริบทที่ซ้ำใน Bridge Composite ULS
6. Vn/Vn,max ต่ำกว่า/เท่ากับ 1 เป็นการใช้ capacity cap ไม่ใช่ demand utilization จึงไม่นำมาเลือก case แทน Vu/φVn หากเกิน 1 ยังรักษา violation ไว้

## สิ่งที่เปลี่ยนเพื่อให้เร็วขึ้น

- ตรวจว่า bar อยู่ใน polygon/hole ครั้งเดียวต่อ section context และใช้ขอบ compression block ที่เทียบเท่าการตัด polygon เดิม ลดการสร้าง Point/centroid ซ้ำในทุกขั้นสมดุล
- เก็บ section response แบบ exact ตาม c และ steel/development limits ใน cache ที่จำกัดขนาดต่อ Calculate ไม่มีการปัด Nu/แรงอื่น ไม่มี interpolation กำลัง และไม่เปลี่ยนเกณฑ์การหาราก
- ใช้ composite-model snapshot ร่วมระหว่าง Shear/Torsion/V–T เมื่อ engineering hash ตรงทุก input การแก้ loads/section/steel ทำให้ผลเก่าไม่ตรง hash และต้องคำนวณใหม่
- การเปิดดูผลไม่คำนวณใหม่ ไม่มีการบันทึกผลเหล่านี้ลง Project JSON หรือผล design ใน Summary / Report / QA

| การวัด | COMPOSITE48 | VN49 | ขอบเขต |
|---|---:|---:|---|
| Calculate Shear 32 แถว, ครั้งที่ 1 | 8.394 s | 3.420 s | measured ใน runtime เดียวกัน หลัง warm-up LP |
| Calculate Shear 32 แถว, ครั้งที่ 2 | 7.288 s | 3.351 s | fresh calculation state, ข้อมูลชุดเดียวกัน |
| Nominal composite-model scan 608 แถว | 369.616 s ที่บันทึกไว้ก่อนหน้า | 48.959 s | model scan; ไม่ใช่เวลาทั้งหน้า/ทุกปุ่ม |

การกด Torsion และ Shear + Torsion หลัง Shear ใน AppTest ใช้ model snapshot เดิมและเพิ่ม model calculation calls = 0 แต่ code-check route ของ check ที่เลือกยังทำงานตามหน้าที่ เวลาจริงขึ้นอยู่กับจำนวนแถว geometry และเครื่องที่รัน ไม่รับประกัน 49 วินาทีสำหรับทุกโครงการ

## การตรวจย้อนหลัง

ใช้ `concrete_section_pro_project_31_COVER38.json` SHA-256 `0ae85f6de0b753062393a70717105953836a4a7722449edfbdc0e91ba8f99fcb`

- ต้นทาง 640 แถว / 2 girders / 4 cases; คำนวณครบ 608 แถวภายในช่วงคาน อีก 32 แถวที่ x=0/L ระบุว่าต้องตรวจ end-region แยก
- ชุด regression ลบคอลัมน์ strand x จาก **สำเนาที่ใช้ทดสอบ** เพื่อทำซ้ำปัญหาใน PDF; ไม่แก้ไฟล์ JSON ต้นทาง แรง ขนาดหน้าตัด วัสดุ และ interface inputs
- ค่า Model Vn/Tn ที่ M=N=0, V-only/T-only D/C ที่ actual M/N และ V–T D/C ตรงกับ COMPOSITE48 ครบ 608 แถวภายใต้ tolerance ที่กำหนด ไม่มีการเพิ่มกำลังเพื่อบังคับให้ผ่าน
- ตรวจ SectionEquilibrium กับ 148 reference responses จากรุ่นที่ยอมรับ ครอบคลุมสองทิศการดัด polygon ที่มี hole, bars บนขอบ/ใน hole/นอก polygon และ steel/development limits
- 294 selected tests ผ่าน ไม่ใช่ full repository suite เพิ่ม test fixture ประกาศ analytical static concurrency ให้ถูกต้องใน ULS5 โดยยืนยันว่าล้มเหลวเหมือนกันบน COMPOSITE48 และไม่ผ่อน source gate ของข้อมูลโครงการ
- AppTest ของ app.py: Calculate สามหน้า ผ่านกรณีไม่มี strand x; Shear แสดง V governor; cached model ใช้ซ้ำข้าม check; redraw เพิ่ม solver calls = 0
- py_compile ของ app.py และ Python files ที่เปลี่ยนผ่าน
- สร้างกราฟ PNG 1440×560 ของทั้งสอง girders และตรวจภาพแล้ว ไม่มีการตรวจ browser screenshot เพราะดาวน์โหลด browser binary ไม่สำเร็จ จึงยังไม่อ้างว่าผ่าน browser/print QA ครบ

## วิธี composite ปัจจุบัน: อะไรมีส่วนอย่างไร

| ส่วนประกอบ | บทบาทในโมเดลนี้ |
|---|---|
| I-girder + slab concrete | สร้าง compression section เพื่อหา C–T และ dv; web width / web f’c เป็นของ I จริง |
| I hoops | เส้นทางแรงเฉือน I ใช้กำลังขาจริงและ spacing ที่สถานีนั้น |
| U-dowel สองขา | เส้นทาง U ใช้เพดานแรงขาเดียวกันร่วมกับการหนีบรอยต่อ ไม่บวกกำลังเต็มซ้ำ |
| เหล็กยาว I/strand/slab | longitudinal force reserve ที่มีระยะพัฒนาแรงและช่วงต่อเนื่องของแต่ละชั้น |
| slab transverse mesh | closure supply ของ U/slab path ตามสมมติฐานโมเดล; ไม่ใช่การยืนยัน node/closed cage จริง |

V-only คง M3/N จริงและ T=0 แต่ใช้ θ คงที่จากแถวแรงร่วมต้นทางตามนิยามเดิม Model Vn ที่ M=N=0 อยู่ใน trace เพื่อไม่ให้สับสนกับ capacity ที่มี moment/axial demand อยู่แล้ว

**วิธีกำลังยังไม่สมบูรณ์สำหรับ full-composite production design** โมเดลกำหนด Vc=0 และ shared concrete-flow ceiling โดยยังขาดการพิสูจน์ stress field, U–slab node, splitting/anchorage และ independent structural validation ของระบบนี้ การมี U/เหล็กพื้นใน inventory จึงไม่รับรองว่ากำลังจะเพิ่มเสมอ หาก concrete/longitudinal/interface เป็นตัวควบคุม เหล็กที่เพิ่มอาจไม่ได้ถูกใช้เต็ม

Code shear ใน expander แยกใช้ AASHTO Vc+Vs และ composite dv โดย Vs เป็นของปลอก I ส่วน U อยู่ใน nominal model ข้างบน ทั้งสองมีนิยามต่างกัน ไม่รวมผลเข้าด้วยกันหรือใช้ผลหนึ่งแทนอีกผลอัตโนมัติ ยังไม่มีการให้ φ แก่ nominal model หรืออนุมัติ full-composite design PASS

Tu ต้นทาง CSI ไม่ถูกย้ายไป centroid คาน I และการอ้างอิง M2/M3 ใน bending reader ยังเป็นของเดิม ชุดงานนี้แก้ regression/performance/presentation โดยไม่เพิ่มผลเข้ากำลัง design หรือเปลี่ยน Project JSON persistence

## วิธีใช้

ใช้ ZIP VN49 แทน COMPOSITE48 โหลด Project JSON เดิม แล้วไป Analysis → ULS Strength → Shear → Calculate Shear — all girders ใช้ตารางรวมเลือกเปิด girder เพื่อดูผล Vn, กราฟ และวิธี composite; เปิด Code shear เพื่อเทียบกับ code route และเปิด Calculation trace เพื่อตรวจหน่วย/การจัดสรรแรง

Repo summary: Fix pooled strand-x blockage; focus Shear on V governor and paired Vn chart; reuse exact section/model results; compact tied-case/context output; retain research-model acceptance limits.
