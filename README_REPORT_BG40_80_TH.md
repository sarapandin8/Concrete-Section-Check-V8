# REPORT.BG40.80

รุ่นนี้พัฒนาจาก concrete-section-pro_SLAB-PUNCHLOCAL79.zip
เพื่อเพิ่มรายการคำนวณ I-girder ในรูปแบบ BG40_Final_Complete_R10.docx

## ใช้งาน

1. เปิดโครงการ I-girder ตั้งค่าและนำเข้าแรงตามขั้นตอนเดิม
2. คำนวณ checks ที่ต้องการในหน้า Analysis
3. ไปที่ Report / QA > Structural Design Calculation Report
4. ดู Report chapter preview; ใส่ชื่อโครงการ ผู้จัดทำ ผู้ตรวจ และ revision ใน Report details
5. กด Build Calculation Report แล้วดาวน์โหลด Word หรือ Report and Source Evidence ZIP

ไม่ต้องยืนยันแรงซ้ำเพื่อสร้างรายงาน ไม่มีการคำนวณกำลังหรือความเค้นซ้ำในหน้า Report

## รูปแบบ

ใช้แม่แบบจาก Word ต้นฉบับโดยตรง คง page setup, styles, theme, ฟอนต์ Tahoma
ระยะขอบ หัวบท ตาราง และหัว–ท้ายกระดาษเดิม เปลี่ยนเฉพาะข้อมูลชื่อโครงการ
และเนื้อหาคำนวณ Revision และวันจัดทำแสดงในส่วนข้อมูลรายงาน
ตารางมีหน่วยและแหล่งข้อมูล พร้อมหัวตารางซ้ำเมื่อข้ามหน้า
สมการ Word แบบ OMML แก้ไขได้ แสดงข้ออ้างอิง สมการ แทนค่า และผล
ใช้โครงสร้างรายงานดังนี้

1. Design Criteria Design Loads and Load Combinations
2. Structural System and Analysis Model
3. Section Properties
4. Prestress Losses
5. Analysis Results
6. ULS Flexural Design
7. ULS Shear and Torsion Design
8. SLS Stress Check
9. Deflection Check
10. Deck Slab Reinforcement and Punching Review

เก็บค่าแรงของแต่ละ source row/case ไว้ด้วยกัน ไม่สร้างแรง Vmax + Tmax ขึ้นใหม่
ตารางเต็มและค่าความละเอียดเดิมอยู่ใน evidence ZIP พร้อม Source_Register.csv
และ Calculations.json พร้อม ProjectInputSnapshot.json, Figure_Register.json
และ PNG ต้นฉบับของรูปที่ฝังใน Word

รูปประกอบแยกตามบท ได้แก่ แนวอ้างอิงช่วงคานและแนว debonding,
หน้าตัด precast/composite พร้อม dimension และเหล็ก/ลวด, กราฟแรงนำเข้า,
หน้าตัดที่จุดควบคุมพร้อม stress block/neutral axis หรือ closed hoop,
กราฟ ULS demand–capacity และ V–T D/C, SLS stress ตลอดช่วงและตามความลึก,
deflection/camber, หน้าตัดเหล็กพื้น 4 mats และ Plan/profile ของผลตรวจพื้น
กราฟ loss และ loaded-area perimeters แสดงเมื่อมีข้อมูลนั้นรองรับ
รูปแต่ละรูปมีกรณีแรง ตำแหน่ง หน่วย และคำอธิบายที่เกี่ยวข้อง

## ที่มาและขอบเขต

BG40 R10 เป็นแหล่งรูปแบบและลำดับเนื้อหา ไม่ใช่แหล่งตัวเลขออกแบบของ I-girder
ใช้วัสดุ หน้าตัด เหล็ก ลวด แรง และผลคำนวณจากโครงการที่เปิดจริง
ใช้สมการและ code basis ของ stored result ไม่คัดลอกวิธี external/unbonded
ของ box girder มาแทน strain compatibility ของ pretensioned I-girder

ข้อมูลผลตรวจที่ไม่ตรงกับ input/version ปัจจุบันจะไม่ถูกนำไปออกเป็นผลใหม่
เมื่อ input, stored result, metadata หรือ export options เปลี่ยน ปุ่มดาวน์โหลด
รายงานเดิมจะถูกซ่อนจนสร้างรายงานใหม่

บท Prestress แสดง force states และ loss audits ที่มีอยู่ ส่วน loss audit เดิม
ไม่มี input fingerprint จึงแสดง REVIEW เพื่อให้ผู้ตรวจยืนยันที่มา
บท Punching คง Local D/C และ REVIEW ของ physical perimeter ตามรุ่น 79
ไม่อ้างว่า Local D/C ต่ำกว่า 1 เป็นการผ่าน punching ครบแล้ว
บท SLS แสดงเฉพาะ girder ที่คำนวณไว้ใน runtime ปัจจุบัน
นิยาม load combinations/dynamic factors ที่ไม่มีในข้อมูลนำเข้าไม่ถูกสมมติขึ้น
หน้าตัด polygon ในบท 3 เป็น gross geometry ไม่ใช่ transformed composite properties

ระบบรายงานเดิมและรายงาน Crossbeam ยังคงทำงานตามเดิม รุ่นนี้เพิ่มรายงาน
รูปแบบ BG40 ใน workflow parametric I-girder

## Verification

104 targeted and regression tests passed.
ครอบคลุม source fidelity, current/stale bindings, multi-member ULS,
SLS stress, deflection, local punching, Word structure, editable equations,
complete evidence ZIP, Streamlit build and stale-download behavior.
ตรวจว่า styles.xml และ theme เดิมไม่เปลี่ยน และระยะขอบตรงกับแม่แบบทุกค่า

ตรวจเอกสารจากการ render Word เป็นภาพแล้ว
ไม่พบการเปลี่ยนค่าผลคำนวณจากส่วน Report
ไม่ได้อ้างว่าทุกโมดูลของแอปผ่านการรับรองการออกแบบครบถ้วน

