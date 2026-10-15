# IGIRDER.INPUT30 — ลดข้อมูลซ้ำและเตรียมข้อมูลคานประกอบ

รุ่นนี้ปรับขั้นตอนนำเข้าและ UI ของรอยต่อให้ใช้ข้อมูลโครงการเดิมได้มากขึ้น **ยังไม่ได้เพิ่มกำลัง dowel เข้า Girder Tn หรือ full composite V–T** และยังไม่ได้พัฒนา nonlinear coupled resistance solver ตามเป้าหมายระยะถัดไป การมีข้อมูลครบไม่ทำให้สถานะกำลังร่วมเป็น PASS

ฐานพัฒนาคือ JOINT29 ที่ส่งมอบก่อนหน้านี้ SHA-256 `a281a917df728b69cb33b5f8b27c60d0d9739c02465b3c65f860588755764f7f` ไม่ได้ย้อนกลับไปใช้ SLSIMPORT23 หรือแอป Segmental Box Girder

**สิ่งที่เปลี่ยน**

| ส่วนใช้งาน | ผลใน INPUT30 |
|---|---|
| นำเข้า CSiBridge | ตรวจชีต Girder รายตัวได้ในเส้นทางปกติ ไม่ต้องเลือกชีตหรือกำหนดชื่อคานซ้ำสำหรับไฟล์ที่ตรวจรูปแบบได้ |
| Beam / Slab | อ่านจากไฟล์เดียวกันและเก็บเป็น inputs ใน Project JSON ไม่เพิ่มเข้า Loads เป็นคานอีกตัว |
| Entire Bridge Section | ไม่นำยอดรวมทั้งสะพานไปใช้เป็นแรงของ Girder ตัวหนึ่ง |
| Dowel layout | หน้าเริ่มต้นแสดง Zone, Start, End และ Spacing; ขนาดเหล็ก จำนวนขา และ fy ที่มีอยู่ยังถูกเก็บครบ เปิดแก้ได้ใน Bar properties |
| Dowel detail | รวมมิติจริงที่ยังขาดไว้ในแผงพับเดียว ใช้ cover ที่บันทึกไว้เดิมเมื่อไม่มีค่าเฉพาะ dowel และยังแก้ค่าให้ตรงเหล็กจริงได้ |
| Interface options | พับ manual width และ anchorage declaration เดิมไว้ ไม่เพิ่มช่องยืนยันใหม่ |
| Joint forces | ไม่แสดงตารางกรอกแรงเองในหน้าเริ่มต้น การกรอกแรงรอยต่อเองเป็นการตรวจแบบ advanced เท่านั้น |
| Inputs reused / still missing | แยกข้อมูลที่ใช้ซ้ำ ข้อมูลจริงที่ยังต้องเติม และขั้นคำนวณที่ยังอยู่ระหว่างพัฒนา |

การนำเข้าใหม่มีผลเมื่อกด Import loads เท่านั้น การเปิดหน้า แก้ force-source selector หรือกลับมาอ่านไฟล์เดิมไม่แทนที่ Loads โดยอัตโนมัติ หากชื่อชีตไม่ชัดเจนจะยังใช้เส้นทาง mapping เดิม หากชีต Girder ที่ระบุชื่อชัดเจนเสีย header หรือมีแรงไม่ครบ จะไม่ยอมให้นำเข้าเป็นชุดที่ดูเหมือนครบ

**การใช้ไฟล์โครงการที่แนบ**

1. แตก ZIP แล้วรัน `streamlit run app.py`
2. เปิด `I_Girder_20m_INPUT30_DRAFT.json` ซึ่งมีข้อมูลต้นทาง Girder/Beam/Slab ของ DL และ U2A ที่ส่งมาแล้ว ไม่ต้องอัปโหลดสองไฟล์นี้ซ้ำเพื่อเก็บตารางต้นทาง
3. ใน Loads ใช้วิธีนำเข้าเดิมสำหรับข้อมูลใหม่: เลือกไฟล์ → Force source → Import loads
4. ใน Analysis → ULS Strength → Final — Composite เปิดรายละเอียดของ Flexure แล้วใช้แผง Dowel layout / Dowel detail เมื่อมีข้อมูลจริงเพิ่ม
5. Inputs reused / still missing ใช้ดูว่าค่าใดมีแล้ว ค่าที่ไม่ทราบยังว่าง การคำนวณ joint เดิมยังต้องกด Calculate U-dowel Joint และเป็น REVIEW ตามขอบเขตเดิม

การเพิ่ม reference source inputs ใน JSON ไม่ได้นำ DL ไปแทน ULS และไม่ได้เปลี่ยนตาราง Loads ที่ใช้ออกแบบปัจจุบัน การเปลี่ยนชุด Loads ยังต้องนำเข้าผ่านหน้า Loads ตามปกติ

**ข้อมูลจริงของคุณที่ใช้ต่อ**

- I-girder ลึก 1500 mm, flange บน 600 mm, web หลัก 200 mm
- Slab ที่จัดให้ Girder กว้าง 1200 mm หนา 350 mm
- เหล็ก slab ตามยาวเดิม DB16@200 ด้านบน และ DB16@150 ด้านล่าง ไม่มีการนำ DB20 แนวขวางในรูปไปเขียนทับเหล็กตามยาว
- Dowel DB12 จำนวน 2 ขาต่อชุด ระยะ C/D/E เท่ากับ 70/150/200 mm ตาม inputs เดิม
- ช่วงเริ่ม–สิ้นสุด C/D/E ยังไม่ทราบและไม่คัดลอกช่วงปลอก I มาแทน
- ระยะขา U, ระยะฝังตรง, มิติ hook/tail และ coating/anchorage region ที่ยังไม่ทราบยังคงเป็น unknown/null
- มิติอ้างอิง 250/220 mm จากรูปไม่ถูกใช้แทนระยะขา U หรือ development length ที่ตรวจสอบแล้ว

**ผลทดสอบไฟล์จริง**

| ไฟล์ | Girder | แถว Loads ที่ตรวจพบ | แถว component inputs |
|---|---:|---:|---:|
| DL — Girder/Beam/Slab | 6 | 276 | 828 |
| U2A — Girder/Beam/Slab | 6 | 552 | 1656 |

Component inputs เก็บทั้งหกองค์ประกอบและ source fields/units/signs เดิม เป็นข้อมูลต้นทางเท่านั้น ไม่มีการ fit offsets หรือสร้างแรงรอยต่อไว้ใน metadata นี้ สำหรับ U2A ที่เป็น Max/Min ยังแสดง State pairing required แม้มี Girder/Beam/Slab ครบ เพื่อไม่รวม extrema คนละสถานะเป็นเวกเตอร์เดียว

**การตรวจสอบซอฟต์แวร์**

- ชุดทดสอบที่เลือก 271 กรณีผ่านทั้งหมด ไม่มี failure/error/skip รวม 20 กรณีใหม่ของ INPUT30; เวลา 43.386 s มี 7 warnings ในขอบเขตชุดนี้ ไม่ได้อ้างว่ารันทั้ง repository ผ่าน
- ตรวจ syntax ของ app และไฟล์ที่แก้/เพิ่มแล้ว
- Streamlit AppTest ใช้ไฟล์ DL จริงผ่านหน้า import: ไม่มี text-input จับคู่สมาชิกหรือ multiselect เลือกชีตในเส้นทางปกติ และไม่มี confirmation checkbox ใหม่
- Full app.py AppTest: เปิดหน้าไม่คำนวณเอง; กด Calculate U-dowel Joint เรียกหนึ่งครั้ง; ไม่มี joint actions จริงจึงไม่เรียก mechanism solver; ผล ULS เดิมไม่ถูกเปลี่ยน
- บันทึก/เปิด Project JSON กลับมาได้ครบสำหรับ component inputs; raw Loads ไม่เปลี่ยน; solver witness ไม่ถูกบันทึก; Summary และ Report ไม่เรียก solver ซ้ำ
- เทียบไฟล์ analysis modules กับ JOINT29 แล้ว bytes เหมือนเดิม สูตรกำลังและพฤติกรรม ULS/SLS เดิมไม่เปลี่ยน
- ยังไม่ได้ตรวจภาพหน้าจอใน browser จริง: environment ไม่มี browser executable และการดาวน์โหลด browser ไม่ได้ archive ที่ใช้งานได้ จึงไม่อ้างว่า visual browser QA ผ่าน การตรวจ UI รอบนี้เป็น AppTest และตรวจองค์ประกอบ/พฤติกรรม

**งานกำลังร่วมที่ยังต้องทำ**

การ recover interface reactions จาก component states และการคำนวณกำลังร่วมของทั้ง Girder ยังเป็นงานพัฒนาของแอป ไม่ได้ผลักภาระให้ผู้ใช้ต้องคำนวณ qx/qy/n/mx มาใส่ในเส้นทางปกติ รุ่นนี้เก็บข้อมูลให้พร้อมใช้ในงานนั้น แต่ยังไม่คำนวณแรงรอยต่อให้อัตโนมัติ

ขั้นถัดไปต้องมี paired load state, จุดอ้างอิงของ component และสมดุล free-body ที่รวมแรงภายนอก พร้อมแบบจำลองการเสียรูปร่วมของคาน/slab/interface ต้องตรวจการใช้เหล็กร่วม การวิบัติของ slab การฝังยึด splitting และพฤติกรรมใกล้ diaphragm/จุดรองรับ ก่อนให้ผลเข้า production Tn/V–T เป้าหมายดังกล่าวยังไม่เสร็จใน INPUT30

ฐานแนวทางที่ค้นไว้คือ [Bairán–Marí: nonlinear coupled sectional approach](https://link.springer.com/article/10.1007/s11831-007-9007-5) และ [การแยก B-regions / D-regions](https://www.ctresources.info/ccp/paper.html?id=5797) การเพิ่มรอยต่อ U-dowel ของโครงการเป็นส่วนที่ต้องพัฒนาและพิสูจน์เพิ่ม งานเหล่านี้ไม่ได้รับรองรายละเอียดรอยต่อปัจจุบันโดยตรง

**Repo summary**

```text
IGIRDER.INPUT30: Simplify dowel UI and named-sheet CSI imports; retain Beam/Slab source inputs in Project JSON. Preserve Loads and resistance equations; full composite Tn/V–T remains unimplemented.
```
