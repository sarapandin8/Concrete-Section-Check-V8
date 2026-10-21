# SLS.DEFLECT70 — Service deflection จาก CSI envelope ราย girder

วันที่ส่งมอบ: 21 ตุลาคม 2026 · พัฒนาจาก SLS.DEFLECT69

## วิธีใช้

เปิด **Analysis → SLS Deflection / Camber** แล้วอัปโหลด **Envelope SLS Girder Deflection (.xlsx)** กด **Calculate deflection / camber** ครั้งเดียว จากนั้นเลือก Stage และเลือก **Service girder** เพื่อดูกราฟของคานที่ต้องการ การสลับ stage/girder หรือเปิด Result Summary / Report ไม่สั่งคำนวณใหม่

- **Transfer / Construction:** คำนวณจาก section model, prestress และ generated stage loads เดิมของ I-girder หนึ่งตัว ชื่อกราฟระบุ single I-girder / calculated อย่างชัดเจน ไม่ได้ใช้ความแข็งสะพานทั้ง 6 คานรวมกัน และไม่ได้เปลี่ยนตาม sheet ที่เลือกดู Service
- **Service:** แสดงเฉพาะผลนำเข้าของ girder ที่เลือก ชื่อกราฟระบุชื่อ girder + WebTop Vert + Imported SLS envelope ไม่มี generated Service fallback ไม่มีช่องใส่ LL UDL สำหรับ Service ในเส้นทาง bridge นี้
- ข้อมูลนำเข้าและเกณฑ์ตรวจถูกเก็บใน project JSON เพื่อไม่ต้องนำเข้าซ้ำ ผลคำนวณ runtime และ widget state ไม่ถูกบันทึกเป็น analysis cache

## รูปแบบไฟล์ที่รับ

ใช้แบบเดียวกับไฟล์ตัวอย่างที่ส่งมาได้เลย ไม่ต้องแก้ spreadsheet หรือติ๊กยืนยัน:

| รายการ | ข้อกำหนด |
|---|---|
| ไฟล์ | .xlsx ของ Envelope SLS Girder Deflection |
| Worksheet | หนึ่ง girder ต่อหนึ่ง sheet ใช้ชื่อ sheet เป็นชื่อ girder |
| Girder Distance | ระยะตามยาวของ girder ตั้งแต่ 0 ถึง L |
| ItemType | มี Max และ Min ครบทุกสถานี |
| WebTop Vert | displacement แนวดิ่งที่ต้องการใช้ |
| แถวหน่วยใต้ header | จำเป็นสำหรับ Girder Distance และ WebTop Vert |

Layout Line Distance, WebTop Tran, WebTop Long และ WebTop RLong ไม่ถูกใช้ในการคำนวณนี้ แถวหน่วยยอมรับ m / mm / cm / ft / in และแปลงระยะเป็นเมตรกับ displacement เป็นมิลลิเมตรเพียงครั้งเดียว

แอปตรวจ Max/Min จับคู่กัน สถานีซ้ำ ค่าไม่เป็นตัวเลข หน่วยที่ขาด และช่วงระยะที่ไม่ตรงกับ span ปัจจุบัน ไฟล์ single-case/step, force/stress table และ entire bridge section ไม่ใช่อินพุตของเส้นทางนี้ การอัปโหลดทดแทนที่ผิดจะไม่เขียนทับ input bank เดิม แต่ผล Service เดิมจะไม่ถูกใช้แทนไฟล์ที่ผิด หากกด X ลบไฟล์นำเข้าจะล้าง Service input

รูปแบบตัวอย่างไม่มีชื่อ load case หรือ definition ของ load combination แอปใช้การระบุ **SLS envelope** ของผู้ใช้เป็นขอบเขตนำเข้า และตรวจรูปแบบ Max/Min โดยไม่สร้างชื่อ case หรืออ้างว่าตรวจ load factors จากไฟล์นี้ได้

## ผลตรวจเทียบไฟล์จริง

Workbook SHA-256: `4beac1fa04c5ad73f43a24c654826ac34362dfdac28be7e62fc1830969a7d536`

มี 2 girders รวม 96 แถว WebTop Vert: แต่ละตัวมี 24 สถานี × Max/Min ทั้งสองสาขา โดยใช้ Girder Distance ตาม export และเก็บจุดหัวท้ายครบ ไม่ smooth หรือตัด peak ของ displacement

| Girder | แอ่นลงสูงสุด (มม.) | x (ม.) | Branch | D/C เทียบ project limit 13.333 มม. |
|---|---:|---:|---|---:|
| Left Exterior Girder | 9.227 | 10.45714 | Min | 0.692025 |
| Interior Girder 2 | 9.160 | 10.45714 | Min | 0.687000 |

ค่าดิบเป็น −0.009227 และ −0.009160 ม. ตามลำดับ แอปคงเครื่องหมายไว้ในกราฟ ค่า Demand ในตารางเป็น max(|Max|, |Min|) ผล Preview PASS ข้างต้นเป็นการตรวจ component เทียบเกณฑ์โครงการ ไม่ใช่การรับรองทั้งระบบ SLS

Transfer / Construction จาก JSON32 เดิมยังมี camber สูงสุด 18.754 / 13.820 มม. ตามลำดับ สมการต้นทางเดิมไม่เปลี่ยน

## เกณฑ์และขอบเขตการคำนวณ

- **Railway project min(L/1500, 30 mm)** ให้ 13.333 มม. สำหรับ 20 ม. เป็นตัวเลือก project criterion สำหรับ |WebTop Vert| envelope ต้องยืนยันกับข้อกำหนดเจ้าของงาน จะแสดงเส้น ±limit
- **Custom SLS envelope limit** ใช้ขนาดการเคลื่อนตัวสูงสุดทั้งสองเครื่องหมายเทียบกับ limit ที่กำหนด
- **AASHTO highway L/800 / immediate LL L/360** ยังคงเป็น reference-only ในการนำเข้า envelope นี้ เพราะรูปแบบไฟล์ไม่มีข้อมูลยืนยันว่าผลเป็น LL-only demand สถานะคง REVIEW แม้มีตัวเลขอัตราส่วนให้พิจารณา
- Transfer / Construction ใช้ project tolerance ที่ระบุ หรือคง response-only REVIEW หากเว้นว่าง

Service ใช้ **WebTop Vert ตามที่ CSI export** เท่านั้น ไม่มีการย้ายจุดอ้างอิงไป centroid ไม่มีการบวก camber, LL, impact/load factor หรือ creep ซ้ำ ไม่หักเส้นเชื่อม displacement ที่ bearing และไม่บังคับ displacement หัวท้ายเป็นศูนย์ ข้อมูล source และการแปลงหน่วยดูได้ในแถบ **Calculation trace / Equations / Source audit** และ Download deflection audit

Max/Min เป็นขอบเขตของผลรายสถานี สองเส้นไม่ได้หมายถึงรูปทรงการเสียรูปของ load configuration เดียวกันทั้งเส้น การรวม DL/LL/prestress หรือผลระยะยาวขึ้นอยู่กับโมเดลและ SLS envelope ที่ผู้ใช้เลือกใน CSI แอปไม่สมมติว่าผลใดรวมอยู่แล้วและไม่เติมผลเพิ่มให้เอง จึงคง full deflection acceptance = false

ตามเอกสาร CSI displacement ใช้แกนของ bridge layout line ซึ่งรวม grade/superelevation และมีตัวเลือกระยะตาม individual girder เส้นทางนี้เก็บ WebTop Vert และ Girder Distance เดิมไว้ ไม่แปลงเป็น global-Z component หรือเปลี่ยนแกนให้เอง:
https://docs.csiamerica.com/help-files/csibridge/Home_tab/Display_panel/Show_Bridge_Forces_Stresses.htm

Building-girder route ของ DEFLECT69 และโมดูล slab / strength / prestress losses เดิมไม่เปลี่ยน ส่วน banner ที่อ้าง ULS imported girder ถูกซ่อนเฉพาะหน้า Deflection เพื่อไม่ให้สับสนกับ Service girder ที่เลือกจากไฟล์นี้

หลักฐานทดสอบ: SLS_DEFLECT70_VERIFICATION.json และ qa/evidence/sls_deflect70/ ตัวอย่าง Excel ใน tests/fixtures/sls_deflect70/ เป็นสำเนาไฟล์ต้นฉบับที่ไม่แก้ข้อมูล
