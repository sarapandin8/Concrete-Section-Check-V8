# SLAB.IMPORT55 — เมนูและการนำเข้าข้อมูลพื้นจาก CSiBridge

พัฒนาจาก IGIRDER.SLS54 รอบนี้เพิ่มเมนูและตัวตรวจข้อมูลนำเข้า ไม่ใช่ตัวคำนวณกำลังพื้น

## ตำแหน่งโมดูล

- **Loads → Slab Shell Results**: คู่มือไฟล์ ตัวเลือก Excel หลายไฟล์ ปุ่ม Import & validate และรายการตารางที่ขาด
- **Analysis → Slab Reinforcement**: ข้อมูล shell ที่นำเข้า สถานะ NOT CALCULATED และเหล็กพื้นบน–ล่างทั้งสองทิศทางจากโครงการ
- Loads เดิมของ Bridge Beam / Girder ใช้ชื่อ **Girder Forces**; ขั้นตอนนำเข้าแรงคานเดิมยังใช้ได้
- เมนูใหม่อยู่ใน workflow Bridge Beam / Girder เท่านั้น

## ไฟล์ที่ใช้

ชื่อไฟล์เป็นตัวอย่างตามไฟล์จริงที่ได้รับ แอปตรวจจากหัวตารางภายใน เปลี่ยนชื่อหรือรวมตารางทั้งหมดใน workbook เดียวได้ ไม่ต้องลบ sheet อื่น

| ไฟล์ | ตารางที่ต้องมี |
|---|---|
| Element Forces - Area Shells.xlsx | Element Forces - Area Shells |
| TABLE Objects And Elements - Areas(1).xlsx | Objects And Elements - Areas; Objects And Elements - Joints |
| Area Assigment.xlsx | Area Bridge Object Flags; Area Overwrites - Thickness; Area Section Assignments; Area Local Axes Assignments 1 - Typical; Area Local Axes Assignments 2 - Advanced เมื่อ AdvanceAxes = Yes |
| Connectivity Data.xlsx | Connectivity - Area; Joint Coordinates |

ชื่อ worksheet ของ Local Axes อาจไม่มีคำว่า Assignments เพราะ CSI จำกัดความยาวชื่อ sheet แอปใช้ schema ของคอลัมน์ในการตรวจด้วย

เก็บ Program Control, Frames, Links, Auto Mesh และ Edge Constraints ไว้ได้ ไม่ต้องแนบ Objects And Elements - Areas รุ่นเก่าที่มีเฉพาะ Areas ซ้ำ และไม่ต้องเพิ่มไฟล์ stress / นิยาม load combination / การตั้งค่า moving load ใน workflow นี้

## วิธีใช้

1. เปิด Project JSON และใช้ workflow Bridge Beam / Girder
2. Export จาก CSiBridge เป็น Excel หน่วย kN, m โดยเก็บชื่อคอลัมน์และแถวหน่วยเดิมครบ
3. เลือก Excel ทั้งชุดพร้อมกันใน Loads → Slab Shell Results แล้วกด **Import & validate shell data**
4. หากมีตารางขาด แอประบุชื่อและ export set; หากข้อมูลขัดกัน แอปไม่แสดงเป็นข้อมูลพร้อมใช้
5. กด **Open Slab Reinforcement** เพื่อดูชุดข้อมูลและเหล็กเดิม ไม่ต้องกรอกข้อมูลเหล็กซ้ำในหน้านี้

นำเข้าครั้งเดียวแล้วเปลี่ยนหน้าได้โดยไม่อ่าน Excel ซ้ำ การเลือกไฟล์ชุดอื่นทำให้ชุดเดิมเป็น STALE จนกด Import ใหม่ ข้อมูล Excel เป็น session input; เปิด Project JSON ใหม่หรือเริ่มแอปใหม่ให้แนบ Excel อีกครั้ง

## ข้อมูลที่เก็บและตรวจ

- เก็บ F11, F22, F12, M11, M22, M12, V13, V23 รวมคอลัมน์เพิ่มเติมและทุกแถวที่นำเข้าจากตารางแรง
- ใช้แรงที่อยู่ในแต่ละแถวเป็นชุดแรงร่วมตามฐานข้อมูลโครงการที่ผู้ใช้ยืนยัน ไม่ประกอบ component envelope ใหม่ขณะนำเข้า
- เก็บ U1A/U1B/U2A/U2B และ Max/Min ไม่รวมแถวข้าม LC/step
- ตรวจหน่วย ค่าตัวเลข key ซ้ำ การจับคู่ Area / AreaElem / Joint และพิกัด generated ~ joints
- เลือก CompType = Top Slab อัตโนมัติ ข้อมูล diaphragm ยังอยู่ในตารางต้นทาง แต่แยกออกจากชุดพื้น
- เก็บ Thick1..4 และลำดับ Joint1..4 ของ Area ต้นฉบับ ไม่แทนพื้นทั้งหมดด้วยความหนา 350 มม.
- แสดง inventory เหล็กยาว/ขวาง บน/ล่างจากข้อมูลเดิม พร้อม cover; ไม่ผูกกับ flag การนับเหล็กพื้นใน Mn ของคาน
- ไม่แทนข้อมูลเหล็กที่ขาดด้วยเหล็กสมมติหรือค่า 0

## ขอบเขต

สถานะ IMPORTED หมายถึงตารางและความสัมพันธ์ข้อมูลผ่านการตรวจนำเข้า ไม่ใช่ผลกำลังหรือการยืนยันแกน shell สำหรับการออกแบบ

ยังไม่ได้คำนวณกำลังพื้น, As required, D/C, แผนที่ผลกำลัง หรือ PASS/FAIL ตัวคำนวณถัดไปต้องตรวจแรงเมมเบรนร่วมดัดจาก F/M ทั้ง 6 องค์ประกอบ และ V13/V23 ตามขอบเขตมาตรฐานที่เลือก ไม่ควรใช้ข้อมูล ULS ไปสรุปผล SLS cracking

No engineering resistance equations changed. No girder ULS/SLS calculation logic changed. No Project JSON schema change or result-cache persistence was added. Opening a Project JSON clears the new session-only shell package to prevent reuse of another model's exports.

## Verification

- 69 targeted and navigation/SLS/cover regression tests passed, including 19 shell-import tests
- Supplied complete exports: 170,240 force rows, 5,320 shell elements, 5,733 analysis joints
- Selected Top Slab: 146,432 records, 4,576 elements, 276 Areas
- Non-slab records excluded from slab view: 23,808
- Top Slab corner thicknesses: 200–350 mm
- No missing required tables or failed record joins in the supplied exports
- Read-only real-file import measured about 16 seconds in the QA runtime; runtime on other machines may differ
- Browser inspection uses a loopback-only server and blocks external browser requests

## Repo summary

Add bridge-scoped Slab Reinforcement navigation and a native CSiBridge shell import workflow with a four-file export guide, automatic table matching, Top Slab filtering, input validation and reuse of existing slab reinforcement. Keep slab resistance explicitly not calculated and preserve existing girder design checks.
