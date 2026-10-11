# Concrete Section Pro — IGIRDER.VTCHART16

พัฒนาต่อจาก `concrete-section-pro_IGIRDER-ALLCASE15.zip` โดยตรวจ JSON และหน้าแอป Shear+Torsion(9).pdf ที่ผู้ใช้ส่งล่าสุด ผลคำนวณของไฟล์นี้ตรงกับค่าที่แสดงใน PDF แต่กราฟองค์ประกอบเดิมมีชื่อเส้นที่คลาดเคลื่อนและแสดงเกณฑ์ไม่ครบ จึงแก้การแสดงผลและเพิ่มการตรวจสอบย้อนกลับ

## เปรียบเทียบกับ ALLCASE15

| รายการ | ALLCASE15 | VTCHART16 |
|---|---|---|
| เส้นตรวจขีดจำกัดแรงเฉือน | ชื่อ Veff D/C แม้ใช้ actual Vu | ชื่อ Shear limit D/C ตรงกับสมการที่ใช้ |
| องค์ประกอบในกราฟ V+T | Shear / Transverse / Longitudinal | เพิ่ม Spacing D/C = s/smax |
| ที่มาของเหล็กปลอกบนเส้นกราฟ | แสดงกรณีและตำแหน่ง | เพิ่ม Zone และ spacing ที่ใช้จริงใน hover |
| จุดควบคุมในรายละเอียด | แสดงค่าควบคุม | เพิ่มชื่อ Zone พร้อม spacing ที่ให้และที่ยอมให้ |
| สูตร Vn, Tn และ V+T | สูตรจากฐานเดิม | ไม่เปลี่ยนสูตร ผลทุกตารางก่อน–หลังเท่ากัน |
| การสลับ All / single case | อ่านผลที่คำนวณไว้ | คงเดิม ทดสอบว่าไม่เรียก solver และไม่แก้ข้อมูล |

ไฟล์ production ที่แก้: `analysis_page.py`, `igird_case_review.py`, `igird_vt_workspace.py`, `igird_combined_vt.py` ภายใต้ `concrete_pmm_pro/ui/` เท่านั้น

## ผลจาก JSON ล่าสุด

ไฟล์ `I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck350(1).json` มี SHA256 `f6f2fec89ba4e7cdbe46da189b7b88582dd19789dc443ac95192b1724584db68` ขนาด 48,305,045 bytes; ไม่แก้ไขไฟล์ต้นฉบับ

| คาน | จุดควบคุม | Shear limit D/C | Transverse D/C | Longitudinal D/C | Overall |
|---|---:|---:|---:|---:|---:|
| Left Exterior Girder | 14.000 m | 0.077 | 1.420 | 0.691 | FAIL |
| Interior Girder 2 | 14.000 m | 0.240 | 2.369 | 1.071 | FAIL |

ค่าตารางนี้ตรงกับ PDF ที่ส่งมาเมื่อปัดทศนิยม 3 ตำแหน่ง ผลละเอียด 320 แถวต่อคาน รวม 640 แถว คานริมมี FAIL 60 / REVIEW 260 แถว คานภายในมี FAIL 96 / REVIEW 224 แถว; แถว FAIL ก็ยังมีเงื่อนไขที่ต้อง REVIEW แยกต่างหากได้

JSON ล่าสุดมีเหล็กปลอกครบช่วง 0–20 m: 0–1.5 @70, 1.5–6 @100, 6–14 @200, 14–18.5 @100, 18.5–20 @70 (DB12, 2 legs, fy 390 MPa) จึงไม่พบช่วงขาด Zone แบบข้อมูลเก่า ณ x=14 ซึ่งเป็นรอยต่อ Zone ระบบเลือก Midspan @200 ตามลำดับ Zone เดิม ส่วน x=15 อยู่ใน Right transition @100 จึงเกิดยอดและการลดลงของกราฟจริง เวอร์ชันนี้แสดงที่มาชัดเจนและไม่เปลี่ยนการเลือก Zone หรือปรับเหล็กเพื่อให้ผลผ่าน

คานทั้งสองยังไม่ผ่าน Transverse และคานภายในยังมี Longitudinal D/C > 1 ที่จุดดังกล่าว การเปลี่ยนระยะปลอกอาจเปลี่ยนการแบ่งกำลัง Vs และแรงตามยาวที่ต้องการด้วย ต้อง Calculate ใหม่ด้วยรายละเอียดที่เลือกก่อนสรุปผล ไม่รับรองว่าลด spacing อย่างเดียวแล้วทุกเกณฑ์จะผ่าน

## หลักคำนวณและขอบเขตการตรวจ

- ใช้ AASHTO LRFD 9th Edition: General Procedure สำหรับ β/θ, ตรวจแรงเฉือนตาม 5.7.3.3-2, เหล็กขวางร่วมตาม 5.7.3.6.1 และแรงตามยาวตาม 5.7.3.6.3-1
- Shear limit D/C ใช้ actual |Vu|; Veff ใช้ตามบทบาทใน strain และมี conservative screen แยกที่คงสถานะ REVIEW โดยไม่รวมเป็น code-component D/C
- ผลชุดนี้ระบุ Section basis = FINAL COMPOSITE และใช้ dv จากหน้าตัดประกอบ; พารามิเตอร์ torsion Ao/ph มาจากแนวเหล็กปลอกปิดที่กำหนด ไม่เท่ากับการถือว่าพื้น deck ทั้งหมดเป็นพื้นที่ในปลอก
- ตรวจแทนค่าอิสระ 11 ค่า/แถว รวม 7,040 ค่า โดยใช้ geometry, strain และ developed resistance ที่บันทึกไว้ ความคลาดเคลื่อนแบบ scaled สูงสุด 2.67e-14; เป็นการตรวจสมการในขอบเขตโครงการนี้ ไม่ใช่การยืนยัน geometry/development ทุกกรณีโดย solver อิสระ
- เทียบผลก่อน–หลังแก้แบบ exact ทุก DataFrame ของทั้งสองคาน และตรวจ 42 จุดของกราฟ overview กับผลควบคุมจริง
- ไม่เพิ่มค่า D/C ปลายคานที่ไม่มี source row และไม่ต่อเส้นข้ามค่าที่ขาด กรณี source set 2 มีเฉพาะ 19 stations จึงไม่แต่งค่าที่ x=0/20

ข้อมูล CSI ยังคงเป็น ENVELOPE — REVIEW ทั้ง 640 แถว จึงต้องยืนยันความพร้อมกันของแรงก่อนรับรอง combined design; effective deck width ยังไม่ยืนยัน, support bearing face ยังไม่มีข้อมูลครบ และ Interface Shear ต้องคำนวณ/ตรวจแยกตามสถานะปัจจุบัน ระบบไม่ได้ติ๊กยืนยันแทนผู้ใช้

## การทดสอบและวิธีใช้งาน

ทดสอบ regression 200 tests ผ่าน (109 ด้าน V+T/กราฟ + 91 ด้านกราฟร่วม/Project IO/CSI import/member charts) พร้อม actual app.py review แบบ automatic → all → single → all ของสองคาน โดยไม่เรียก solver และไม่เปลี่ยน input/cache; ตรวจ browser ที่ความกว้าง 1440 และ 1100 px และ compile ไฟล์ที่เกี่ยวข้อง

แตก ZIP เป็นโฟลเดอร์ใหม่ ใช้วิธีเปิดแอปเดิม โหลด JSON ล่าสุด แล้วกด Calculate Shear + Torsion — all 2 girders เปิด Girder และ Combined components / individual cases เพื่อดูกราฟ 4 เกณฑ์ ชี้เมาส์ที่ x=14 เพื่อดู Midspan และ spacing 200 mm

ZIP เป็นแอปเต็ม เก็บไฟล์เดิมจาก ALLCASE15 ครบ ไม่รวม runtime checkpoint หรือ browser screenshot ใหม่ หลักฐานการทดสอบอยู่ใน `qa/evidence/igird_vtchart16/`; SHA256 และจำนวนไฟล์จริงระบุในเอกสาร release validation ที่ส่งคู่กัน

Repo summary: Correct combined shear–torsion chart labels, show spacing utilization and reinforcement sources, and verify unchanged calculations against the supplied project.
