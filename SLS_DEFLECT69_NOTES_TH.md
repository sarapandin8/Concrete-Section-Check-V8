# SLS.DEFLECT69 — กราฟ deflection แยก stage และเส้นเกณฑ์

วันที่ส่งมอบ: 21 ตุลาคม 2026 · พัฒนาจาก SLAB.REVIEW68

เปิด **Analysis → SLS Deflection / Camber** แล้วกด **Calculate deflection / camber** เพียงครั้งเดียว เลือก Transfer / Construction / Service เพื่อสลับกราฟจากผลที่เก็บไว้ การเปิด Result Summary และ Report / QA ไม่สั่งคำนวณใหม่

## สิ่งที่ตรวจพบและแก้ไข

- L/360 เดิมถูกใช้เป็นเกณฑ์เดียวทุก stage และตรวจเฉพาะการแอ่นลงสุทธิ ทำให้ camber จาก prestress บดบังการตรวจ live-load deflection ได้ รุ่นนี้ตรวจ **LL+IM increment** แยกจาก net camber
- โมเดล generated bridge stage loads ของ JSON32 มี DL/SDL แต่ไม่มี LL component เส้น Service ทั้งสามจึงซ้อนกัน ไม่ใช่หลักฐานว่ารถไฟทำให้ deflection เป็นศูนย์ รุ่นนี้แจ้ง **SOURCE MISSING / REVIEW** แทน PASS
- เส้น completion กับ sustained เดิมเป็นผล elastic เดียวกัน ไม่มี creep/shrinkage เพิ่ม รุ่นนี้แสดงเพียงเส้นเดียวชื่อ Sustained · elastic และแยก long-term เป็น NOT CALCULATED / REVIEW
- กราฟเต็มช่วง 0–L เก็บจุดหัวท้าย ไม่ smooth ผล ใช้ legend สั้นด้านล่างและ marker ณ จุดควบคุม ตรวจหน้าจอ 1440 และ 1280 px แล้ว
- บันทึกเฉพาะตัวเลือกและข้อมูลนำเข้าใหม่ใน project JSON ผล runtime ไม่ถูกบันทึกกลับเข้า JSON และจะถูกล้างเมื่อโหลดโครงการ

## ผลจาก JSON32 เดิมโดยไม่แก้ข้อมูล

| Stage | การโก่งขึ้นสูงสุด (มม.) | ตำแหน่ง x (ม.) | ขอบเขต |
|---|---:|---:|---|
| Transfer | 18.754 | 10.000 | Net elastic response |
| Construction / wet slab | 13.820 | 10.000 | Net elastic response |
| Service sustained | 9.912 | 10.000 | Net elastic response |
| Service LL+IM | ไม่มีข้อมูล | — | REVIEW |

ค่าข้างต้นตรงกับรูปที่ส่งมา สูตรสร้าง stage curves เดิมและข้อมูล prestress/geometry ไม่ได้เปลี่ยน ค่าบวกเป็นการโก่งขึ้น ไม่ควรนำไปเทียบเป็น LL deflection หรือสรุปผ่านทั้งระบบ

## เส้น limit ใช้อย่างไร

เปิดแถบพับ **Deflection criteria / Live-load source**:

1. **Railway project · min(L/1500, 30 mm)** ให้ 13.333 มม. สำหรับ L = 20 ม. เป็นตัวเลือกเกณฑ์โครงการในรุ่นนี้ ต้องยืนยันกับข้อกำหนดของเจ้าของงานก่อนใช้ตัดสินงานรถไฟ ไม่ใช่ข้อกำหนดรถไฟสากลของ AASHTO
2. **AASHTO highway · LL+IM L/800** ให้ 25.000 มม. สำหรับ L = 20 ม. เป็น optional highway criterion ตาม 2.5.2.6.2 และต้องใช้โหลดตาม 3.6.1.3.2 ใช้กับโครงการรถไฟโดยอัตโนมัติไม่ได้
3. **Custom LL limit** ใช้เกณฑ์ LL ของโครงการ หรือเลือก Review only เมื่อต้องการดู response ก่อน
4. **Transfer / Construction |δ| tolerance** เป็นตัวเลือก ไม่ต้องกรอกหากไม่มีเกณฑ์โครงการ เมื่อกำหนดจะแสดงเส้น ±tolerance และตรวจขนาด response ทั้งโก่งขึ้นและแอ่นลง ไม่มีการสมมติเกณฑ์ code camber เดียวให้ทุก stage

เส้นแดงที่ Service อยู่ด้านลบและใช้เทียบกับ **LL+IM increment** เท่านั้น กรณี LL source ขาดยังวาดเส้นเกณฑ์ให้เห็นได้ แต่ไม่มีเส้น LL หรือ D/C ที่สมมติขึ้น

ช่อง **Service LL+IM per girder (kN/m)** เป็นทางเลือกสำหรับแบบจำลอง uniform service line load ของคานที่กำลังตรวจ รวม impact เพียงครั้งเดียว ไม่ใช้ค่า ULS factored หรือแรงดันรวมของทั้งสะพาน/ทั้งราง หากโมเดลเดิมมี LL component ที่ทราบค่าจะใช้ค่านั้นได้โดยไม่ต้องกรอกซ้ำ ช่องว่างกับค่า 0 มีความหมายต่างกัน: ว่างหมายถึงไม่มี source ส่วน 0 คือผู้ใช้ระบุว่าไม่มี LL ในกรณีนั้นอย่างชัดเจน

## วิธีคำนวณและข้อจำกัดที่ยังต้องทราบ

กราฟมาจาก **generated stage loads** ในแอป ไม่ใช่ CSI displacements ที่นำเข้าหรือการอินทิเกรต M/EI ของ CSI สูตรเดิมใช้คานช่วงเดียว EI คงที่ และแรง prestress/eccentricity เทียบเท่าที่กลางช่วง โหลดก่อน composite ใช้ precast EI และโหลดเพิ่มหลัง composite ใช้ transformed composite EI

LL UDL ใหม่คำนวณด้วย δ(x) = −wx(L³−2Lx²+x³)/(24EcIcomp); ที่กลางช่วงมีขนาด 5wL⁴/(384EcIcomp) โดย kN/m = N/mm, x/L เป็นมม., Ec เป็น MPa และ I เป็นมม.⁴ ไม่คูณ dynamic allowance หรือ load factor ซ้ำ

AASHTO LRFD Ninth Edition (2020) **5.6.3.5.2** ให้พิจารณาผล DL, LL, prestressing, erection, creep, shrinkage และ relaxation ตามที่เกี่ยวข้อง รุ่นนี้ยังไม่เพิ่มตัววิเคราะห์ stage Ec, Pe(x) จาก debonding, nonprismatic end EI, cracked stiffness, creep/shrinkage หรือการตอบสนองราง ดังนั้นแม้ LL instantaneous component เป็น Preview PASS ก็ยังไม่รับรอง full deflection acceptance และไม่มีเส้น long-term ที่สร้างขึ้นแทนการวิเคราะห์

## แหล่งตรวจสอบ

- AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), 5.6.3.5.2 และ 5.9.3.6: ตรวจจาก Section 5 ที่ผู้ใช้ให้
- FHWA, Prefabricated Steel Bridge Systems, Chapter 6, deflection check under LRFD 2.5.2.6.2: https://www.fhwa.dot.gov/bridge/prefab/psbsreport07.cfm
- MnDOT LRFD Bridge Design Manual, Section 5, deflection/camber: https://www.dot.state.mn.us/bridge/pdf/lrfdmanual/section05.pdf

หลักฐานตรวจซอฟต์แวร์อยู่ใน SLS_DEFLECT69_VERIFICATION.json และ qa/evidence/sls_deflect69/ ผล explicit LL = 20 kN/m ใน browser QA เป็นกรณีทดสอบแยก ไม่ใช่โหลดรถไฟจริงของ JSON32
