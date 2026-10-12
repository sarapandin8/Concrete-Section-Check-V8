# ENDSECTION18 — ผลตรวจ 12 ตุลาคม 2026

พัฒนาจาก AUTOLOAD17 และตรวจซ้ำหลังการกู้สภาพแวดล้อมแล้ว

| การตรวจ | ผล |
|---|---|
| Compile app.py/โมดูลที่แก้ | PASS |
| Regression สุดท้าย | 722 passed, 2 deselected |
| Targeted geometry/engineering/chart/import | 40 passed |
| แอปจริง: ช่องกรอก, taper preview, invalid overlap, JSON roundtrip | PASS |
| CSI 640 แถว / 2 girders / แรงทั้งหก | ค่าเดิมและสมาชิกถูกต้อง |
| Geometry samples x=1.625 ม. ของทั้งสอง girder | เส้น Vn/Tn ใช้ taper; diagram-only; D/C ว่าง |
| แก้หัวตันแล้วผล STALE; Summary/Report ไม่คำนวณซ้ำ | PASS |
| Browser 1440/1100 px และ slider เปลี่ยน polygon | PASS; ไม่มี JavaScript error |

2 tests เก่าที่ deselect ตรวจข้อความ UI/README ที่เปลี่ยนไปตั้งแต่ก่อนเวอร์ชันนี้ พบว่าล้มเหลวใน AUTOLOAD17 ที่ยังไม่ได้แก้เช่นกัน ดู baseline_known_failures.xml

หัวตัน 600×1500 มม. ใช้ Acp=900000 มม.², Pcp=4200 มม., Ao=495918.367 มม.² ปลอก DB12/cover40 ให้ ph=3832 มม. หน้าตัดกลาง taper ให้ bv=400 มม. และมีการตรวจแทนค่าสมการ Vn/Tn ใน targeted tests

Maximum numerical Combined D/C ของ Left Exterior Girder=1.375059 และ Interior Girder 2=1.749330 ยังเกิน 1 เพราะ governing อยู่ในช่วง I ผลกลางคานเท่าเดิม หัวตันช่วยเฉพาะเขตที่กำหนด

Native Max/Min ยังเป็น ENVELOPE / REVIEW และยังไม่ยืนยันรายละเอียดหัวตัน/ปลอก/เหล็กตามยาว/D-region หรือ moment reference ให้เอง SLS/deflection และ FE stiffness/self-weight ยังใช้โมเดลเดิม

อ่านคู่มือและตารางเปรียบเทียบใน IGIRDER_ENDSECTION18_HANDOFF_TH.md หลักฐานอยู่ใน qa/evidence/igird_endsection18/

Repo summary: Add station-based solid ends and tapers for I-girder ULS geometry and capacity checks.
