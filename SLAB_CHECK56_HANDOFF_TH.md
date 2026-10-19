# SLAB.CHECK56 — ตรวจเหล็กพื้นจาก shell results

พัฒนาต่อจาก SLAB.IMPORT55 เพิ่มตัวคำนวณและแผนที่ผลในหน้าเดิม ใช้เหล็กยาว/ขวาง บน/ล่างที่กรอกไว้แล้ว ไม่เพิ่มแบบฟอร์มเหล็กซ้ำ

## วิธีใช้

1. เปิด Project JSON และตรวจวัสดุพื้นกับเหล็กทั้ง 4 กลุ่มใน Section Builder / Slab mesh ให้ตรงกับแบบ
2. ไป **Loads → Slab Shell Results** เลือก Excel ทั้งชุดเดิม แล้วกด **Import & validate shell data** เก็บทุก worksheet และแถวหน่วยจาก CSI
3. เปิด **Analysis → Slab Reinforcement** กด **Calculate Slab Reinforcement** ครั้งเดียว
4. เลือก **Result to review** เป็น Overall section, เหล็กแต่ละกลุ่ม, Concrete compression หรือ One-way shear แล้วเลือก LC ที่ต้องการดู
5. ชี้ที่แผนที่เพื่อดู LC / Max–Min / corner ที่ควบคุม เปิด **Calculation trace / Equations** เมื่อต้องการตรวจตัวเลข เปิด **Source audit / Export results** เพื่อดาวน์โหลด CSV

กราฟเปลี่ยนตามตัวเลือกโดยไม่เรียก solver ซ้ำ บนจอแคบเลื่อนเฉพาะแผนที่ในแนวนอนได้ สถานะด้านบนและตารางเหล็ก 4 กลุ่มยังเป็นผลจากทุกกรณีที่นำเข้า ไม่ถูกลดขอบเขตตาม LC ที่เลือกดู

## วิธีอ่านผล

- **Preview PASS**: ผ่านเฉพาะรายการตรวจที่ตัวคำนวณรุ่นนี้รองรับและมีข้อมูลครบ ไม่ใช่การยืนยันออกแบบพื้นครบทุกข้อ
- **Preview FAIL**: มีค่าตรวจที่ทราบแล้วเกิน 1
- **REVIEW / สีเทา**: เงื่อนไขตรวจแรงเฉือนยังยืนยันไม่ได้ หรือชุด corner/case ไม่ครบ ไม่ถูกแทนด้วยศูนย์หรือแสดงผ่าน
- แผนที่แสดงค่าสูงสุดของ source corner/case ต่อ element ไม่เฉลี่ยข้าม corner หรือ LC และไม่ตัดพีก
- สีใช้ระยะเชิงลอการิทึมเพื่ออ่านพีกกับค่ารอบ D/C = 1 พร้อมกัน แต่ scale / hover แสดง D/C จริง
- ค่า As required เป็นค่าจาก field ที่เลือก พร้อม shear-tie screen และ shrinkage minimum ไม่ใช่คำยืนยันว่าเป็นปริมาณเหล็กต่ำสุดหรือเป็น bar schedule ที่นำไปก่อสร้างได้ทันที

บริเวณจุดรองรับ/ถ่ายแรงที่มีพีกสูงต้องประเมินเป็นบริเวณก่อนจัดเหล็กจริง แอปคงแรงต้นทางไว้ให้ตรวจสอบ

## หลักคำนวณที่เพิ่ม

- ตรวจ N–M พร้อมกันทั้ง 6 องค์ประกอบในแต่ละแถวตามฐานข้อมูลแรงร่วมของโครงการที่ผู้ใช้ยืนยัน
- เปลี่ยนเฉพาะแกน shell ไปเป็นแกนเหล็กจริง ไม่มีการย้ายจุดอ้างอิงแรงจาก shell midsurface
- หาทิศตามแนวสะพานจาก BridgeObj / BOSpan / StartSta / EndSta ในไฟล์ที่มีอยู่แล้ว ไม่ต้อง export ไฟล์เพิ่ม
- ใช้ Thick1..4 กับลำดับมุม Area เดิม อินเตอร์โพเลตความหนาถึง analysis corner แล้วใช้ตำแหน่งเหล็กจริงทั้ง 4 ชั้น
- เหล็กขวางอยู่ชั้นนอก เหล็กยาวอยู่ด้านในตามข้อกำหนดเดิมของโครงการ
- concrete รับอัด เหล็กรับดึงใน sandwich field ตรวจสมดุลย้อนกลับทั้ง 6 องค์ประกอบทุกแถว
- ใช้ AASHTO LRFD 9th Edition เป็นฐาน component limits พร้อมแยก conservative shear screens และ shear-tie demand
- Wood–Armer แสดงใน trace เป็น bending reference ไม่ใช้แทนแรงเมมเบรนร่วมดัด

รายละเอียดสมการ การใช้ phi ขอบเขต และ hand benchmarks อยู่ใน **SLAB_CHECK56_METHOD.md**

## ขอบเขตที่ยังแยกตรวจ

รุ่นนี้เป็น **section preview** ที่มีสมดุล N–M ไม่ใช่ full 3D N–M–V model ที่ตรวจยืนยันครบ และยังไม่ใช่ complete deck code acceptance การนำ component limits ของ AASHTO มาใช้ใน field ไม่เท่ากับยืนยัน STM ทั้งระบบ

ยังแยกตรวจ anchorage/development, nodal/load-transfer regions, flexural minimum reinforcement, cover/exposure requirements, fatigue, punching/local wheel effects และ SLS cracking พื้นต้องเป็น normal-weight nonprestressed monolithic slab ใช้สะพานแนวตรงและความกว้างคงที่ มี planar four-corner shells; geometry นอกขอบเขตจะแจ้งเหตุ ไม่เดาทิศเหล็ก

ค่าตรวจแรงเฉือนที่ไม่เข้าเงื่อนไขจะคง REVIEW แม้ส่วน N–M ผ่าน ไม่อาศัยการยืนยันจากผู้ใช้เพื่อเปลี่ยนสถานะเป็นผ่าน

## การเก็บข้อมูลและการใช้งานต่อ

ใช้ Project JSON เดิมได้ โครงสร้างไฟล์ input เดิมไม่เปลี่ยน Excel และผลพื้นใหม่เป็น session-only จึงต้องนำเข้า Excel อีกครั้งหลังเปิด Project JSON หรือเริ่มแอปใหม่ การแก้ข้อมูลเหล็ก/วัสดุหรือเปลี่ยนชุดไฟล์จะซ่อนผลเก่าจนคำนวณใหม่

ผล preview ไม่เขียนทับผลคานใน Result Summary / Report และไม่ได้แก้สมการ ULS / SLS ของ I-girder

## ผลตรวจรุ่นนี้

- 99 selected engine, UI, navigation, SLS และ cover regression tests ผ่าน
- ใช้ไฟล์จริงครบ 170,240 แถวแรง เลือกพื้น 146,432 แถว / 4,576 elements / 276 Areas
- ตัดเฉพาะ non-slab 23,808 แถวออกจากการตรวจพื้น โดยเก็บใน source package
- ชุดพื้นมี corner ครบทุก LC / Max–Min ที่นำเข้า ความหนา 200–350 มม.
- solver 6.00 วินาทีในเครื่อง QA; Calculate จน render แผนที่ 10.02 วินาที ตัวเลขนี้ไม่รวมขั้นตอนอ่าน Excel
- ทดสอบจริงใน browser ที่ความกว้าง 1,280 / 1,768 / 390 px ไม่มี browser errors หรือ page overflow; จอเล็กเลื่อนแผนที่ภายในกรอบ
- เปลี่ยน view / LC แล้ว solver ยังถูกเรียกเพียงครั้งเดียว ส่งออก CSV ได้ 4,576 แถว พร้อม original eight CSI components
- normalized equilibrium residual สูงสุด 8.53e-14 ต่ำกว่าเกณฑ์ 1e-7

ผลจาก JSON ตัวอย่างที่มีอยู่กับไฟล์แรงจริงยังมีทั้ง Preview FAIL และ REVIEW โดย D/C สูงสุดประมาณ 19.73 ผลนี้ไม่ใช่การสรุปว่ารายละเอียดโครงการปัจจุบันผ่าน และไม่ควรนำพีกนี้ไปจัดเหล็กโดยไม่มี regional assessment

## Repo summary

Add a coupled slab N–M section preview using existing top/bottom reinforcement, native CSI axes and local thicknesses. Include conservative shear screens, required/provided steel, a governing-element D/C map, calculation traces and CSV export. Reuse calculations across filters and retain explicit scope/REVIEW gates. Verify 99 selected tests and the full 146,432-record browser flow; preserve existing girder checks.
