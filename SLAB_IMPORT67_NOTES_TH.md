# SLAB.IMPORT67 — รับผล Static ที่ไม่มี StepType

## สาเหตุ

ตัวนำเข้ารุ่นก่อนกำหนดให้ header `StepType` ต้องอยู่ในตาราง Element Forces - Area Shells เสมอ จึงปฏิเสธไฟล์ static equivalent train load ที่ส่งมา แม้แรงทั้งแปดองค์ประกอบจะมีครบ กรณีที่มีคอลัมน์แต่ช่องข้อมูลว่างเคยรองรับแล้ว ส่วนคอลัมน์ที่หายไปทั้งคอลัมน์เป็นข้อบกพร่องที่แก้ในรุ่นนี้

## การแก้ไข

- ยอมรับ `StepType` ที่ไม่มีใน native CSI export โดยเก็บเป็นช่องว่างในข้อมูลภายใน ไม่แก้ไฟล์ต้นฉบับ
- คง Max/Min และ StepNum ตามที่ export จริง ไม่มีการสร้าง envelope หรือตั้งชื่อ step เพิ่ม
- คงแรงทั้งแปด หน่วย ชื่อ case ลำดับแถว และการจับคู่ Area/AreaElem/Joint
- ตรวจแถวซ้ำตาม case/corner/step เหมือนเดิม หากไม่มี step และมีแถวซ้ำกำกวม ยังคงปฏิเสธข้อมูล
- ข้อความ error ของตารางที่รู้จักระบุเฉพาะ required columns ที่ขาดจริง
- คำแนะนำในหน้า Import และไฟล์ checklist อธิบาย StepType แบบ optional โดยไม่เพิ่มช่องกรอกหรือขั้นตอนยืนยัน

## วิธีใช้

1. ใช้โค้ดจาก ZIP SLAB.IMPORT67 และเริ่มแอปใหม่
2. เปิด Project JSON แล้วไป Loads → Slab Shell Results
3. เลือกสี่ชุด export ตามเดิม กด Import & validate shell data โดยใช้ไฟล์ Excel ต้นฉบับได้เลย
4. ไป Analysis → Slab Reinforcement → Calculate Top slab

ยังคงใช้สมการและกระบวนการคำนวณ DESIGN66 / AASHTO63 เดิม รวมทั้ง source exclusions, ขั้นตอนกราฟ, Summary/Report แบบอ่านผลที่มีอยู่ และ Project JSON แบบบันทึกข้อมูลนำเข้า

## การตรวจไฟล์จริง

ไฟล์ Element Forces - Area Shells(1).xlsx ไม่มี StepType จริง มี 127,680 แถว และข้อมูล Top Slab 109,824 แถว จาก S1A, S1C, U1A, U1B, U2A และ U2B จับคู่กับ geometry อีกสามชุดเดิมได้ครบ การตรวจอ่าน workbook แยกจากตัวนำเข้ายืนยันว่าแรงทั้งแปดและ record keys ตรงทุกแถว

โปรแกรมเก็บชื่อ case ทั้งหมดตามต้นฉบับ ไม่เดาประเภท ULS/SLS จากชื่อ การนำเข้าสำเร็จและคำนวณกราฟได้ไม่ได้หมายความว่าผลออกแบบผ่าน ให้ดูสถานะกำลังของหน้าตัดในหน้าผลคำนวณตามขอบเขตเดิม รายละเอียดการตรวจอยู่ใน SLAB_IMPORT67_VERIFICATION.json และ qa/evidence/slab_import67/
