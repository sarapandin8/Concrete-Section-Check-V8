# SLAB.AASHTO63 — เหล็กพื้นบน–ล่างและหน้าตัดตรวจตาม AASHTO

ฐานพัฒนา: SLAB.AASHTO62 รุ่น ZIP ที่แก้ความสมบูรณ์แล้ว อ้างอิง **AASHTO LRFD Bridge Design Specifications, Ninth Edition, 2020, Section 5** จากเอกสารของโครงการ

## วิธีใช้

1. เปิด Project JSON เดิม ตรวจเหล็กพื้น 4 กลุ่มในหน้าหลัก: บน–ล่าง ตามยาว–ตามขวาง เหล็กยาวอยู่ด้านในตามกติกาเดิม ไม่ต้องกรอกซ้ำ
2. Loads → Slab Shell Results: นำเข้า Excel เต็ม 4 ชุดเดิม รวมทุก worksheet ใน kN, m และทุกแถว U1A/U1B/U2A/U2B, Max/Min โปรแกรมใช้แรงในแต่ละแถวร่วมกันตามข้อมูลโครงการ
3. เก็บ Connectivity - Frame ไว้ใน Connectivity Data.xlsx เพื่อหาแนวคาน I ข้อมูลความหนา diaphragm อ่านจาก Area thickness overwrites ในชุดเดิม
4. Analysis → Slab Reinforcement → **Calculate Slab Reinforcement** ครั้งเดียว เลือกดูกราฟและ case ภายหลังโดยไม่คำนวณซ้ำ
5. เปิด **Top / Bottom reinforcement · code checks** เพื่อดูเหล็กจริงแต่ละกลุ่ม เปิด **AASHTO coverage / remaining checks** เพื่อดูขอบเขตที่คำนวณแล้วและที่ยังต้องตรวจ
6. แบบจำลองเดิมยังอยู่ใน **Case studies / Legacy shell model** และทำงานเมื่อสั่งเปิดเท่านั้น

## วิธีคำนวณและบทบาทเหล็ก

| การตรวจ | บทความ | เหล็ก / วิธีที่ใช้ |
|---|---|---|
| Direct N–M รายทิศทาง | 5.6.2, 5.6.3.2.5 | Strain compatibility, εcu=0.003, α1/β1 และ φ ตาม tensile strain; เหล็กบน–ล่างตามพื้นที่/ระดับจริงทั้งสองเครื่องหมายโมเมนต์ เหล็กชั้นใดอยู่ในแรงดึงก็ใช้ตาม strain; ไม่ให้กำลังเหล็กรับอัดที่ยังไม่ได้ยืนยัน restraint |
| One-way shear | 5.7.3.3–5.7.3.4, 5.12.8.6.2 | ใช้ Nu/Mu/Vu และเหล็กด้านรับแรงดึงในทิศทางเดียวกัน; เหล็กทั้งสองชั้นใช้พิจารณาระยะ crack-control layer ที่เข้าเงื่อนไข; Vs=Vp=0 สำหรับพื้น RC ซึ่งยังไม่ได้ยืนยันเหล็กรับเฉือนตั้งฉากพื้น |
| Flexural shear tie | 5.7.3.5 | ตรวจเหล็กด้านรับแรงดึงของ strip ใช้ φf จากกำลังโมเมนต์ที่ Nu เดียวกัน แทนการใช้ 0.90 ทุกสภาวะ; ไม่บวกแรงเฉือนเต็มจำนวนให้ทั้งสองผิว |
| Flexural minimum | 5.6.3.3 | ตรวจ Mr≥min(1.33Mu,Mcr). ใช้กำลังโมเมนต์ที่ Nu เดียวกัน สำหรับ Nu≠0 ใช้หลักฐานเพียงพอ 1.33Mu; สำหรับ Nu=0 เพิ่ม Mcr ที่ γ3=1 ซึ่งเป็นขอบเขตบนของ fy/fu. หากผ่านขอบเขตที่เข้มกว่าถือว่าพิสูจน์ขั้นต่ำได้ หากไม่ผ่านเป็น REVIEW เพื่อหาสาขา Mcr/gamma3 จริง ไม่รายงาน FAIL จากค่าที่สมมติ |
| Temperature / spacing | 5.10.6, 5.10.3.2 | แยกแต่ละผิวและแต่ละทิศ รวม 4 กลุ่ม ใช้ b→∞ เป็นขอบเขต As ขั้นต่ำที่อนุรักษ์นิยม; ตรวจ spacing รวมข้อจำกัดพื้นหนามาก |
| Required development length | 5.10.8.2.1 | คำนวณ ld ของเหล็กพื้นตรงจาก db/fy/fc และตำแหน่งหล่อ ใช้ขอบเขต coating 1.2/1.5 ตาม cover/spacing เมื่อไม่ทราบ coating, ผลคูณ location×coating ไม่เกิน 1.7; ไม่ลดจาก confinement หรือเหล็กเกิน; ไม่น้อยกว่า 12 นิ้ว. ยังไม่รับรองระยะฝัง/ต่อทาบ/ตะขอที่มีจริง |

คำว่า longitudinal reinforcement ในข้อเฉือนหมายถึงเหล็กตามแนว strip ที่กำลังตรวจ ดังนั้น strip ตามขวางสะพานใช้เหล็กขวางพื้น ไม่ใช่หยิบเหล็กยาวสะพานมาใช้ทุกทิศ

เหล็กตะแกรงบน+ล่างและขา U-dowel ไม่ถูกนับรวมเป็น Vs อัตโนมัติ การใช้ U-dowel ใน interface shear เป็นอีกกลไกหนึ่งซึ่งต้องตรวจแรงข้ามรอยต่อและ anchorage

## หน้าตัดตรวจแรงเฉือน

- I-girder: ใช้หน้าปีกบนกว้าง **600 mm** จาก Project JSON โดยสมมติการสัมผัสรองรับเต็มความกว้าง
- Diaphragm: อ่านความหนาจาก native shell overwrite: end **400 mm**, intermediate **300 mm**; จำกัดแนวตามความยาวจริง ไม่ต่อแนวออกสู่ overhang
- ใช้หน้ารองรับเป็นฐานอนุรักษ์นิยม ไม่สมมติสิทธิลด/ย้ายไป dv จากหน้าเมื่อยังไม่มีเงื่อนไขการลงแรงครบ
- ค่าที่หน้ารองรับเป็น linear interpolation บนขอบ FE เดียวกัน ของแรงครบ 8 องค์ประกอบใน case/step เดียวกันและความหนาเดียวกันตามเรขาคณิต ไม่ใช่การเฉลี่ยข้าม elements/cases หรือการย้ายจุดอ้างอิงแรง
- บริเวณภายใน footprint ของรองรับเก็บผล native เดิมไว้เป็น local-support REVIEW สำหรับ shear/tie; Direct N–M และขั้นต่ำยังตรวจตาม scope จุดเดิม ไม่ถือว่าบริเวณนี้ผ่าน
- จุดหน้าตัดเป้าหมายที่อยู่ในขอบเขตตรวจ แต่ต้องใช้ source corner ที่เคยถูกละเว้น จะเป็น REVIEW ไม่ดึง peak หรือจุดรอยต่อกลับมาใช้ และไม่ให้ PASS ข้างเคียงกลบผลที่ขาด
- Diaphragm face ในตัวอย่างนี้ยังไม่สามารถให้ค่าตัวเลขได้ เพราะต้อง interpolate ผ่าน source nodes ที่ถูกละเว้นไว้ จุดเหล่านี้ยังคงแสดง REVIEW ต้องมีผลที่หน้าตัดจริงหรือ mesh/output ที่อยู่นอกบริเวณละเว้นเพื่อปิดประเด็น

การแยก footprint ตามเรขาคณิตทำให้ตัวเลข shear envelope มีขอบเขตต่างจาก AASHTO62 จึงไม่ใช่หลักฐานว่ากำลังพื้นเพิ่มขึ้นหรือว่าตัดแรงสูงแล้วพื้นผ่าน

## ผลตัวอย่างจาก JSON32 และ Excel เดิม

| การตรวจรายองค์ประกอบ | Max known D/C | ผลเฉพาะขอบเขต |
|---|---:|---|
| Shear transverse | 1.490332 | FAIL + มีหน้าตัด REVIEW |
| Shear longitudinal | 3.001741 | FAIL + มีหน้าตัด REVIEW |
| Direct N–M transverse | 0.441277 | PASS เฉพาะ Ny/My |
| Direct N–M longitudinal | 0.366523 | PASS เฉพาะ Nx/Mx |
| Flexural minimum transverse | 0.536328 | ผ่านหลักฐานเพียงพอ |
| Flexural minimum longitudinal | 0.586723 | ผ่านหลักฐานเพียงพอ |
| Flexural shear tie transverse | 1.235121 | FAIL + มีหน้าตัด REVIEW |
| Flexural shear tie longitudinal | 2.077051 | FAIL + มีหน้าตัด REVIEW |
| Temperature minimum | 0.333392 | PASS ทั้ง 4 กลุ่ม |
| Bar spacing | 0.666667 | PASS ทั้ง 4 กลุ่ม |

เหล็กตามยาวบน DB16@200, กลุ่มอื่น DB16@150, fy390 MPa, fc35 MPa. Cover เหล็กยาว56 mm, เหล็กขวาง40 mm; ระยะศูนย์กลางจากผิว64/48 mm ตามลำดับ

ใช้ Top Slab ต้นฉบับ **146,432 แถว**; geometry/end exclusions **26,240** และ isolated-peak exclusions **6,960** ตาม REVIEW61 เดิม คง native rows ที่ตรวจ **113,232** แถวครบ ไม่เปลี่ยนแรง/keys/เครื่องหมาย/แกนอ้างอิงต้นฉบับ

มี support-face samples **21,632**: คำนวณได้ **12,136**, เป้าหมายใน scope แต่ข้อมูลต้นทางถูกละเว้น **6,456**, เป้าหมายอยู่นอก scope ตาม geometry/end exclusions **3,040**. Sample ที่คำนวณไม่ได้ไม่มี D/C ตัวเลข

## ขอบเขตที่ยังไม่ใช่ full deck acceptance

**สถานะรวมยังเป็น REVIEW REQUIRED และมี component FAIL**. การคำนวณเพิ่มในรุ่นนี้ไม่ได้ปิดการตรวจ Nxy/Mxy, simultaneous biaxial shear ตาม 5.7.3.1, local D-regions/load paths, punching ตาม 5.12.8.6, interface shear ตาม 5.7.4, ระยะฝัง/ต่อทาบจริง, fatigue และ SLS. ตำแหน่ง/ขนาดพื้นที่ลงแรงหรือ reaction สำหรับ punching ไม่สามารถนิยามได้จาก shell corner force table เพียงอย่างเดียว

ผล N–M ที่เขียวไม่ได้พิสูจน์ระบบ shell ทั้งชุดว่าผ่าน แรงเฉือนที่แดงก็ยังต้องตีความร่วมกับหน้าตัดและกลไกถ่ายแรงที่ถูกต้อง ไม่ใช่ข้อสรุปทันทีว่าพื้นจริงล้มเหลว

## การตรวจสอบ

- Focused/regression tests ที่เกี่ยวข้อง **146 passed**; ไม่ได้รันทั้ง repository
- ตรวจสูตร US/SI, N–M equilibrium, fixed-Nu moment capacity, minimum sufficient proof, φf, ld, four-mat roles, interpolation ทั้ง 8 องค์ประกอบ และ missing/excluded source guards
- อ่าน native Excel เต็มใหม่ ตรวจแรง 8 องค์ประกอบและ source keys ไม่เปลี่ยน รวม mask ตรงกับฐานเดิม
- AppTest กับไฟล์เต็ม: 10 views และ case filter, 1 solver call, 0 exceptions, ไม่มี export CSV หนักโดยอัตโนมัติ; ตรวจ numerical envelope เพิ่มครบ 50 คู่ view/case
- ส่งออก PNG 6 ภาพที่ 1440×720 และตรวจด้วยสายตา: mesh ครบ 4,576 elements, ไม่มี legend/title/axis ซ้อนหรือตัด
- ไม่มี manual live-browser screenshot QA; ใช้ Streamlit AppTest และภาพ export
- การผ่าน software tests ไม่ได้พิสูจน์ว่าตรวจข้อกำหนดทางวิศวกรรมครบทั้งระบบ

สูตร girder ULS/SLS และพฤติกรรม Project JSON เดิมคงไว้ ไม่มีการเพิ่ม result-cache persistence ผล shell ยังคงเป็น session inputs/results
