# SLAB.AASHTO62 — ตรวจหน้าตัดพื้นตาม AASHTO แยกทิศ

พัฒนาจาก `concrete-section-pro_SLAB-REVIEW61.zip` โดยคง source เดิมครบทั้งชุด เพิ่มเส้นทางตรวจองค์ประกอบหน้าตัดตาม AASHTO LRFD Ninth Edition (2020) เป็นหน้าหลักของ Analysis → Slab Reinforcement โมเดล REVIEW61 เดิมเปิดได้ใน Case studies / Legacy shell model และไม่รันเมื่อกด Calculate ของหน้าหลัก

## วิธีใช้

1. เปิด Project JSON เดิม แล้วนำเข้า Excel เดิมทั้งสี่ชุดใน Loads → Slab Shell Results ไม่ต้อง export ตารางเพิ่ม
2. กรอก/แก้เหล็กบน–ล่างสองทิศใน Slab mesh ของ Section Builder ตามเดิม เหล็กขวางอยู่ด้านนอก เหล็กยาวอยู่ด้านใน ตัวตรวจใช้ตำแหน่งที่คำนวณได้จริงและความหนา shell ที่แต่ละ corner
3. เข้า Analysis → Slab Reinforcement แล้วกด Calculate Slab Reinforcement หนึ่งครั้ง
4. ค่าเริ่มต้นแสดง Shear · transverse เลือก shear ตามยาว, Direct N–M, flexural shear tie, temperature minimum หรือ bar spacing ได้จากช่องเดียว กรอง load case ได้โดยไม่รัน solver ซ้ำ
5. Calculation trace / Equations แสดง source vector เดียวกันทั้งแปดแรง สมการ การแทนค่า และวัสดุ/เหล็กที่ใช้จริง Exclusions / Source audit แสดงจุดและเหตุผลที่ละเว้นพร้อม CSV
6. การ export source CSV ขนาดใหญ่ใช้ Prepare complete source / exclusions CSV ก่อน เพื่อไม่ให้สร้างข้อมูลขนาดใหญ่ทุกครั้งที่เปลี่ยนกราฟ

## การละเว้นตามข้อตกลง

กฎ geometry เดิมไม่เปลี่ยน: ละเว้น node บนแนว I-girder จาก Connectivity - Frame, แนว diaphragm จริงที่มีความยาวจำกัดจาก Area flags/Connectivity และช่วงปลายพื้นถึง bearing ทั้งความกว้าง รวม node บนขอบ bearing เขตยกเว้นอ่านจากค่าที่มีในโปรเจกต์ ไม่มีการเดาตำแหน่งใหม่

สำหรับไฟล์โครงการนี้ แนว I-girder Y = −3.7, −2.5, −1.3, +1.3, +2.5, +3.7 ม. และ diaphragm X = 0.325, 6.7, 13.275, 19.675 ม. เฉพาะความยาวจริงตามขวาง ช่วงปลายถึง bearing คือ X=0…0.4 และ 19.6…20 ม. รวมขอบ ไม่ขยายแนว diaphragm เข้าไปใน overhang

จากนั้นใช้ fixed one-pass peak rule เดิมของ REVIEW61: เปรียบเทียบขนาดแรงของ joint ใน case/step เดียวกันกับ one-ring neighbours ที่ยังอยู่ใน geometry scope ต้องมีเพื่อนบ้านอย่างน้อย 4 จุด มีคู่ตรงข้ามร่วมแนว เป็นค่าสูงสุดเฉพาะจุดจริง อัตราส่วนต่อ median >2 และ modified score >3.5 ไม่ใช้ D/C/ปริมาณเหล็กเป็นเกณฑ์ ไม่ตัดซ้ำหลายรอบ และไม่คัดแยกแรงบางองค์ประกอบไปจับคู่ข้ามแถว

ผลตรวจยืนยัน source keys ที่เหลือตรงกับ retained study ของ REVIEW61 ทุกแถว:

- Top Slab source 146,432 แถว
- ละเว้นตาม geometry/end zones 26,240 แถว
- ละเว้น isolated peak เพิ่ม 6,960 แถว
- เหลือตรวจ 113,232 แถว

แรงต้นทาง F11/F22/F12/M11/M22/M12/V13/V23 และ source identities ไม่เปลี่ยน จุดที่ละเว้นยังเก็บแรงเดิมไว้ แต่ไม่มี D/C และไม่ใช้สร้าง governing envelope ผลเฉลี่ยโซนอยู่ใน research workspace เท่านั้น ไม่ใช้แทนแรงออกแบบของหน้าหลัก ถ้าตารางที่จำเป็นต่อการระบุแนวต่อไม่ครบ จะหยุดตรวจแทนการข้ามกฎละเว้นอย่างเงียบ ๆ

การละเว้นเป็นขอบเขตการตรวจที่วิศวกรกำหนด ไม่ใช่ข้อพิสูจน์ว่าแรง FEM ผิด และไม่ใช่การรับรองกำลังของบริเวณที่ละเว้น

## แกนและแรง

ใช้ local axes จริงจาก Typical/Advanced assignments และลำดับจุดของ parent Area ควบคู่กับแนว bridge stations เพื่อหมุน N/M tensors และ V ให้ตรงกับแนวเหล็ก ตรวจ local 3 เพื่อจับคู่ top/bottom ให้ถูกต้อง ไม่มีการย้ายจุดอ้างอิงออกจาก shell midsurface

ในข้อมูลชุดนี้ Local 1 ตรงแนวยาวสะพาน/Global X ส่วน Local 2 ตรงแนวขวางของผิวพื้น รวม 46 Areas ที่ลาดขวาง Local 3 ตั้งฉากพื้นชี้ออกด้านบน การหมุนในระนาบเป็น identity ภายในความคลาดเคลื่อนตัวเลข

| ทิศตรวจ | N | M | V | เหล็ก |
|---|---|---|---|---|
| Longitudinal | Nx ← F11 | Mx ← M11 | Vx ← V13 | ยาวบน–ล่าง |
| Transverse | Ny ← F22 | My ← M22 | Vy ← V23 | ขวางบน–ล่าง |

V13/V23 ต่างกระทำตั้งฉากผิวพื้น ผ่านหน้าตัดที่ตั้งฉากแนว 1/2 ตามลำดับ M11 เป็นโมเมนต์บนหน้า normal 1 รอบ local 2 แต่ใช้ตรวจการดัด/เหล็กแนว 1 ไม่สลับ M11/M22 ตามชื่อแกนหมุน

## สมการ shear

ใช้ 1 เมตร strip หน่วย fc/fy เป็น MPa, h/dv เป็น mm และผลแรงต่อความกว้างเป็น kN/m

- 5.7.2.8: dv = max[0.9(h−ระยะถึงศูนย์กลางเหล็กด้านรับแรงดึง), 0.72h] แยกตามทิศและเครื่องหมายดัด ที่ M≈0 ใช้ mat ที่มี As ต่ำกว่าและขอบเขต dv แบบอนุรักษ์ของสองผิว
- 5.7.3.4.1: ใช้ β=2 และ θ=45° เฉพาะ RC strip ที่ไม่มี axial tension ในทิศนั้น และ h<406.4 mm ไม่มีการอ้างว่าเหล็ก mesh ในระนาบเป็น vertical stirrups
- 5.7.3.4.2: ใช้ εs = [max(|Mu|/dv,|Vu|)+0.5Nu+|Vu|]/(Es As,tension) โดย N/M/V/As มาจากทิศเดียวกัน Nu เป็นบวกเมื่อดึง ลบเมื่ออัด ใช้ Es=200,000 MPa ไม่มี Aps หรือ Vp ในพื้น RC นี้
- εs ติดลบใช้ศูนย์ตามทางเลือกที่ code อนุญาต ถ้าหน้าซึ่งตามปกติเป็นด้านอัดจากดัดอยู่ในแรงดึงด้วย ใช้สมมติฐาน cracked section ที่ไม่ให้ concrete tensile credit และเพิ่ม εs สองเท่า เป็นสมมติฐานอนุรักษ์ที่ระบุไว้
- ถ้า εs ที่คำนวณจริง >0.006 จะเก็บ REVIEW และไม่แสดงกำลังที่นำไปตัดสิน PASS ไม่ clip ค่าแล้วใช้ผลผ่าน
- sx ใช้ระยะชั้นเหล็กจริงเฉพาะเมื่อเข้าเกณฑ์ As ของชั้นนั้นไม่น้อยกว่า 0.003 bv sx และ sx≤dv; ag=0 เพื่อไม่เพิ่มกำลังจากขนาดมวลรวมที่ไม่ได้รับข้อมูล; sxe=sx·1.38/0.63 แล้วจำกัด 304.8…2,032 mm
- β=4.8/(1+750εs) × 51/[39+sxe/25.4]; θ=29+3500εs ข้อ 5.7.3.4.2-2/-3 ตัวหาร 39+sxe ใช้ sxe หน่วยนิ้วตามต้นฉบับ
- Vn=min(Vc,0.25fc bv dv), Vs=Vp=0 และ φv=0.90 ตาม 5.7.3.3/5.5.4.2 สำหรับ normal-weight RC
- แยก D/C_L=|Vx|/(φVn,L) และ D/C_T=|Vy|/(φVn,T) ไม่ใช้ sqrt(Vx²+Vy²) เป็น D/C ของทั้งสองทิศ

Flexural shear tie ตาม 5.7.3.5-1 ตรวจ mat ด้านดึงจากดัดในทิศนั้น: Treq=max[0,|Mu|/(φf dv)+Nu/(2φc)+|Vu|cotθ/φv] ใช้ φf=.90, φc=.75, φv=.90 และ Vs=Vp=0 ไม่บวกแรงเต็มจำนวนซ้ำทั้งสองผิว การพัฒนาแรง/การตัดเหล็กยังต้องตรวจแยก

## Direct N–M component

ใช้ strain compatibility ของ RC rectangular strip ตาม 5.6.2 และ 5.6.3.2.5 โดย εcu=.003, stress block α1/β1 ของ AASHTO, tension steel แบบ elastic–perfectly plastic และระดับ mat บน–ล่างจริง ไม่ให้กำลังเหล็กอัดที่ไม่มีข้อมูลการยึดรั้งการโก่งเดาะ หักพื้นที่ concrete ที่แทนที่ด้วยเหล็กออกจาก compression block และใช้ φ=.75… .90 ตาม tensile strain

สร้าง closed N–M design boundary จาก neutral-axis states สองเครื่องหมายดัด เชื่อมเฉพาะ states ที่ติดกัน ไม่ทำ convex hull แล้วหาจุดตัดกับ load ray (λNu,λMu) ใช้ D/C=1/λ ดังนั้นแรงแกนไม่หายไปเมื่อ M ต่ำมาก การเลือกความละเอียด curve มี unit/convergence checks

**Direct N–M ใช้คู่ Nx/Mx หรือ Ny/My ไม่ใช่ N–M field รวม Nxy/Mxy ของ REVIEW61 เดิม** จึงห้ามเทียบค่า max สองวิธีแล้วสรุปว่ากำลังพื้นเต็มระบบเพิ่มขึ้น F12/M12 ยังเก็บไว้ใน trace และเป็น shell-coupling REVIEW ที่ต้องจัดการแยก

## ผลรันไฟล์จริง

| การตรวจองค์ประกอบ | Max D/C | X (m) | Y (m) | กรณี |
|---|---:|---:|---:|---|
| Shear transverse | 5.844513 | 1.46339 | 2.30000 | U2A / Max |
| Shear longitudinal | 3.001741 | 1.00804 | −3.92500 | U2A / Max |
| Direct N–M transverse | 0.441277 | 9.98750 | 2.10000 | U2A / Max |
| Direct N–M longitudinal | 0.366523 | 0.55268 | 2.70000 | U2A / Min |
| Flexural shear tie transverse | 1.663026 | 17.61786 | 2.30000 | U2A / Max |
| Flexural shear tie longitudinal | 2.077051 | 19.44643 | 3.50000 | U2A / Min |
| Temperature minimum | 0.333392 | 8.57857 | −0.43333 | U1A / Max |
| Bar spacing | 0.666667 | 1.69107 | −5.50000 | U1A / Max |

จุด shear ไม่ผ่านอย่างน้อยหนึ่งทิศรวม 525 physical nodes โดยตามขวาง 450 nodes ตามยาว 462 nodes มีจุดซ้ำกันระหว่างสองทิศ 14 nodes มี general-procedure strain เกินขอบเขตในบาง source vectors ของทิศขวาง จึงยังมี REVIEW ไม่ถูกนับเป็น PASS

ตัวอย่าง Rank1057 เดิม (1420-8 / ~918 / U2A Min, X=2.82946,Y=−4.150): เดิม resultant screen D/C=1.566865 เปลี่ยนเป็น shear component ตามยาว 0.525681 และตามขวาง 0.031270 โดย φVn,L=198.808807 และ φVn,T=360.731178 kN/m ตัวเลขนี้ยืนยันว่า shared screening assumptions เดิมทำให้บางจุดอนุรักษ์มาก แต่ไม่ได้พิสูจน์ full shell acceptance

**Max shear ใหม่ 5.844513 ไม่ใช่ค่าเดียวกับ max เก่า 3.864592 และไม่ได้หมายความว่าตัวตรวจใหม่ลดกำลังทุกจุด** การคำนวณ strain ตามทิศทำให้บาง source vectors ที่เก่าเป็น REVIEW มีค่า shear ที่ตรวจได้แล้ว จึงเข้าร่วมการหา maximum ใหม่ ต้องเทียบค่าเก่า/ใหม่ที่ source เดียวกันและในขอบเขตเดียวกันก่อนสรุป

จุดใหม่ Y=2.300 อยู่ห่าง girder CL=2.500 เพียง 0.200 m ขณะที่ top flange กว้าง 0.600 m จึงอยู่ใน footprint ของ flange ตามข้อมูลโครงการ เป็นประเด็น support load-transfer/design-section ที่ต้องตรวจต่อ ไม่ใช่เหตุให้ตัดออกเพิ่มโดยอัตโนมัติ รุ่นนี้คง geometry exclusions เดิม ไม่ขยายขอบเขตจนได้ผลผ่าน

## ขอบเขตการใช้ผล

PASS/FAIL ในตารางเป็นขององค์ประกอบหน้าตัดตามทิศนั้น ส่วน complete deck acceptance คง REVIEW REQUIRED เพราะ:

- การถ่าย Nxy/Mxy สู่เหล็กสองทิศ และ shear สองทิศพร้อมกันยังต้องตรวจเชิงระบบ; 5.7.3.1 กำหนดวิธี refined equilibrium/compatibility หรือ 3D STM เมื่อจำเป็นต้องพิจารณา biaxial shear
- กฎละเว้นแนวต่อ/ช่วง bearing ไม่ได้ยืนยันตำแหน่ง critical shear section ตาม 5.7.3.2 ต้องทราบ support face, ทิศทาง reaction และ concentrated load ภายใน dv จึงจะใช้ข้อกำหนดลด demand ใกล้ support ได้ รุ่นนี้ไม่ย้ายแรงจาก node ข้ามแนวต่อหรือสร้าง shear-free support zone เพิ่ม
- Anchorage/development และการตัดเหล็กยังไม่มีข้อมูล layout ครบ ใช้ As ที่มีแบบ full-development sectional basis เท่านั้น
- Flexural minimum ครบทั้ง 1.33Mu/Mcr, compression-member detailing/second-order, punching/local rail-load effects, fatigue และ SLS ไม่ได้ถูกปิดเป็น PASS ด้วยตารางนี้

ยังไม่ส่งผลใหม่เข้า girder Result Summary / Report และไม่เพิ่มการบันทึก result cache ใน Project JSON จึงไม่ยก component PASS ไปเป็นรายงานรับรองกำลังรวม

## การตรวจยืนยัน

- 125 focused tests ผ่าน รวม baseline import/geometry/axes/exclusions/research regressions และชุดใหม่สำหรับ hand calculations, strain, actual mat selection, N–M radial capacity, convergence, missing coverage, stale inputs, JSON transaction และ UI
- full-input Streamlit AppTest: 146,432 source records, ครบ 8 views และ load-case filter, หนึ่งกราฟต่อ view, solver รันครั้งเดียว, ไม่เรียก research solver, ไม่มี runtime exception
- Calculate-to-render ประมาณ 8.19 s; ตัวตรวจประมาณ 6.13 s ในสภาพแวดล้อมทดสอบ ไม่ใช่เวลา benchmark ของเครื่องผู้ใช้
- ตรวจแปด native actions และ source keys ไม่เปลี่ยน เทียบ retained keys กับ REVIEW61 filtered study ตรงทุกแถว ตรวจ no-D/C บน excluded records และคำนวณ shear capacity ซ้ำอย่างอิสระ
- render PNG ของกราฟหลัก 4 แบบและตรวจภาพด้วยตา ไม่มี title/legend/axis ซ้อนทับหรือขอบกราฟขาด ส่วนที่ไม่มีค่าเป็นสีเทา ไม่ใช่ช่องว่างของ mesh
- ยังไม่ได้ทำ manual screenshot review ของหน้า browser จริง: browser binary ในสภาพแวดล้อมทดสอบดาวน์โหลดไม่สำเร็จ การทดสอบ UI จึงใช้ AppTest พร้อมตรวจ PNG exports แยก ไม่อ้างว่าเทียบเท่าการตรวจ browser screenshot
- ไม่ได้รัน full repository suite และไม่ได้อ้าง independent full structural validation ของระบบพื้น

## อ้างอิง

1. AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5 ของโครงการ: 5.5.4.2, 5.6.2, 5.6.3.2.5, 5.7.2.8, 5.7.3.1–5.7.3.5, 5.10.3.2 และ 5.10.6
2. FHWA, Concrete Bridge Shear Load Rating Guide and Examples (2022), General Procedure และ concurrent force basis: https://www.fhwa.dot.gov/bridge/loadrating/pubs/hif22025.pdf — ใช้ช่วยตรวจสมการ ไม่ใช้ load-rating adjustments แทน design code
3. CSI, Shell Element Internal Forces/Stresses Output Convention: https://docs.csiamerica.com/help-files/csibridge/Output_Conventions/Shell_Element_Internal_Forces_Stresses_Output_Convention.htm
4. CSI, Show Shell Force/Stress Plots: https://docs.csiamerica.com/help-files/csibridge/Home_tab/Display_panel/Show_Shell_Force_Stress_Plots.htm
