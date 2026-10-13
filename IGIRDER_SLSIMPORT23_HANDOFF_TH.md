# IGIRDER.SLSIMPORT23 — นำเข้าแรง SLS จาก CSiBridge แบบง่าย

พัฒนาต่อจาก baseline ที่ยอมรับแล้ว `concrete-section-pro_IGIRDER-ENDSIMPLE22.zip`

Baseline SHA-256: `5f32f4c35a22ac9bf4e2ae2d3eaef7dce4616fa4c319ec51072220f189c42524`

## วิธีใช้ตามปกติ

1. เปิด **Loads → SLS Loads** ใน Bridge Precast I-Girder
2. อัปโหลด Excel ที่ช่อง **Upload CSiBridge SLS girder forces**
3. กด **Import SLS loads**
4. เลือก **SLS girder** แล้วกด **Open SLS analysis**
5. ใน Service stage เลือก load case ที่ต้องการตรวจจาก **Service stage diagram load case**

ขั้นตอนนำเข้าไม่ต้องติ๊กยืนยัน ไม่ต้องกรอก Source basis และไม่ต้องเปิด More SLS import options สำหรับข้อมูลปกติ การอัปโหลด/เปิดดูตัวอย่างเพียงอย่างเดียวยังไม่แทนข้อมูลเดิม ต้องกด Import SLS loads ก่อน

แอปยอมรับคำประกาศของผู้ใช้ในงานนี้ว่าไฟล์เป็น CSiBridge Correspondence ซึ่งเก็บแรงที่เกิดพร้อมกันในแต่ละ load case และบันทึกที่มาไว้ในข้อมูล ไม่มีการนำ maxima ของแรงต่างเคสมาประกอบเป็นแถวใหม่ ทั้งนี้คำประกาศดังกล่าวไม่ใช่การตรวจ export setting ภายใน CSiBridge โดยอัตโนมัติ

## ค่าปกติและตัวเลือกเพิ่มเติม

ค่าเริ่มต้นคือ **Service stage / Total external SLS loads**: ใช้แรงรวมภายนอกจาก CSI โดยไม่เพิ่ม DL/SDL อัตโนมัติซ้ำ และเพิ่ม Pe จากข้อมูล Prestress ของแอปตามขั้นตอนเดิม

เปิด **More SLS import options** เฉพาะเมื่อไฟล์เป็น stage อื่น หรือมีองค์ประกอบแรงต่างจากค่าเริ่มต้น:

| Load content | DL/SDL ที่แอปเพิ่ม | Pe ที่แอปเพิ่ม |
|---|---|---|
| Total SLS external loads; app adds prestress | ไม่เพิ่ม | เพิ่มตามข้อมูล Prestress |
| Total SLS loads including CSI prestress | ไม่เพิ่ม | ไม่เพิ่ม เพราะรวมอยู่ในแรง CSI แล้ว |
| LL+IM only; app adds dead loads and prestress | เพิ่มตามการตั้งค่าเดิม | เพิ่มตามข้อมูล Prestress |

ตัวเลือกนี้ระบุองค์ประกอบแรง ไม่ใช่การยืนยันว่าแรงเกิดพร้อมกัน การนำเข้า stage ใหม่แทนเฉพาะ collection ของ stage นั้นและเก็บ stage อื่นไว้ ตารางแก้ไขและ template เดิมอยู่ใน **Stage load tables and templates** ส่วนการตั้งค่าโหลดอัตโนมัติอยู่ใน **Automatic stage load settings**

## การจับคู่ข้อมูล

| CSiBridge | แอป SLS |
|---|---|
| Distance | Station x (m) |
| P | N = −P (แอปใช้แรงอัดเป็นบวก) |
| M3 | Mx |
| M2 | My |
| V2 | Vy |
| V3 | Vx |
| T | T |

แปลงหน่วยตามแถวหน่วยของ CSI เป็น m, kN และ kN-m ก่อนจัดเก็บ ค่าแรงอีกห้าองค์ประกอบคงเครื่องหมายไว้ เก็บค่าดิบ รวม P เดิม หน่วยชื่อเคส/girder/BridgeObj/section cut/Before–After/StepType/เลขแถว/hash ไฟล์ไว้ใน Note

Max, Min, blank static StepType, Before/After และแถวซ้ำที่เป็น physical source rows ยังคงอยู่ โดย Case Name แยก series/occurrence ไม่ตัดแถวหรือสร้าง force envelope ใหม่ Blank StepType สำหรับ static combinations อนุญาตเฉพาะเส้นทาง SLS ใหม่นี้ เส้นทางตรวจ ULS เดิมคงกติกาเดิม

อ้างอิงเครื่องหมายแรงของ CSI:

- [CSiBridge Frame Element Internal Forces Output Conventions](https://docs.csiamerica.com/help-files/csibridge/Output_Conventions/Frame_Element_Internal_Forces_Output_Conventions.htm)
- [CSiBridge analysis axial convention](https://docs.csiamerica.com/help-files/csibridge/Advanced_tab/Define_panel/Section_Properties/Hinge_Properties/curve_interaction_surface_definition_for_property_name_form.htm)

## การเก็บข้อมูลและขอบเขตผล

- SLS มี collection/ตัวเลือก girder แยกจาก ULS การเปลี่ยน SLS ไม่แทนแรง ULS
- สลับ girder แล้วเก็บการแก้ไขไว้กับ girder เดิม JSON เก็บแรงและ SLS girder ที่เลือก
- ปฏิเสธไฟล์ซ้ำ/ข้อมูลไม่ครบก่อนเปลี่ยนข้อมูลในงานเดิม
- ไม่สร้าง station หรือแถวแรงศูนย์แทรกใน native cases แม้ไฟล์มี station เดียว
- ล้าง snapshot SLS ที่เกี่ยวข้องเมื่อเปลี่ยนอินพุต/เปลี่ยน girder ส่วน Result Summary และ Report / QA อ่านผลที่เก็บไว้โดยไม่เรียก solver
- ตารางผลระบุ Girder และ Source scope: ผลครอบคลุม girder และ diagram case ที่เลือก ไม่ใช่การรับรองทุก case ใน collection

## การคำนวณและข้อจำกัด

สูตร stress และ code limits เดิมยังใช้ต่อ แต่แก้การประกอบโหลด SLS ให้แรงรวม CSI ไม่ได้รับ auto DL/SDL ซ้ำ รวมถึงไม่บวก locked-in construction moment ซ้ำในตาราง Beam/CIP สำหรับข้อมูล total และมีตัวเลือกไม่เพิ่ม Pe เมื่อรวมอยู่ใน CSI แล้ว

ไฟล์แรงรวมเพียงชุดเดียวไม่สามารถแยกประวัติการลงโหลดก่อน/หลัง composite ได้ ผล total จึงเป็น stress จาก resultant บน section basis ที่เลือก ไม่ใช่การย้อนสร้าง staged construction history การเลือก profile/code limit ยังคงเป็นการตั้งค่า stage เดิม ไม่อนุมานชนิด SLS limit จากชื่อ S1A/S1C

SLS stress engine ปัจจุบันใช้ N/Mx ส่วน My/Vy/Vx/T เก็บไว้สำหรับ checks อื่นในอนาคต SLS/FE geometry ยังใช้ uniform section ตามขอบเขต baseline เดิม Deflection/camber ยังใช้ generated stage-load model ของแอป และไม่ได้เปลี่ยนเป็นการใช้ CSI SLS case ใน milestone นี้ โดยแสดงข้อความในหน้าแอป

แก้ runtime bug เดิมในกราฟ full-length SLS ที่อ้างชื่อ compression/tension trace ซึ่งไม่มีตัวแปรกำหนดไว้ ให้แสดง legend มาตรฐานเดิมได้

ไม่มีการเพิ่ม result-cache persistence ไม่มีการรัน CSiBridge ใหม่ ไม่มีการ deploy หรือ push repository และไม่มีการรับรองผลออกแบบสะพานทั้งโครงการ

## ผลทดสอบ

- Targeted + regression **298 passed / 0 failed / 0 errors / 0 skipped**, 19 test modules ใช้ Streamlit จริง
- Compile ผ่านสำหรับ app.py, production modules ที่แก้, tests และ QA script
- นำเข้า Excel จริงของผู้ใช้ครบ 240 แถว / 2 girders รวม Max/Min/static อย่างละ 80 แถว
- ตรวจ six-component vectors และ provenance กับ source reader ทุกแถว
- ส่งข้อมูลทั้งสอง girders รวม 240 แถวผ่าน production stress adapter: N/Mx ตรงกับต้นฉบับที่แปลงเครื่องหมาย/หน่วยแล้ว และ auto DL/SDL/locked-in moment ที่เพิ่มเป็นศูนย์สำหรับ total rows
- ทดสอบ member selection, JSON roundtrip, invalid/duplicate data, unit conversion, source isolation และ sparse stations
- Actual app.py: Upload → Import → เลือก girder → Open SLS analysis → Result Summary/Report → Loads ผ่าน ไม่มี Streamlit exception และไม่เรียก SLS solver จาก Loads/Summary/Report
- ตรวจ browser จริงที่ความกว้าง 1440 และ 1100 px รวมการเลือก Service tab จาก Open SLS analysis ไม่มี JavaScript/Streamlit error

ใช้ hypothetical reinforcement inputs ของ baseline สำหรับ software QA เท่านั้น ไม่ใช่การรับรองงานออกแบบจริง เป็นการทดสอบที่ระบุข้างต้น ไม่ใช่ full repository test suite

Source XLSX SHA-256: `368bad9008cde4d3562a62df017af26d906f0edf4fd709da4c1bfced2a9ef621`

ไม่มีการแก้ Excel ต้นฉบับ fixture JSON ใหม่เก็บเฉพาะ force sheet ไม่เก็บ Program Control/license fields ไม่บรรจุ screenshot browser ชุดใหม่หรือ checkpoint ชั่วคราวใน release

## Repo summary

Add simple CSiBridge SLS imports with separate girder cases, correct axial signs, and no duplicate dead-load or prestress effects.
