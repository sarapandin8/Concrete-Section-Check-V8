# Repo summary — IGIRDER.REFERENCE43

Separate the source-defined embedded-steel cracking parameter from the concrete
torsion law; add strict and declared-extension profiles, low-load strain
continuation, exact material-boundary termination, independent mechanics tests
and a three-profile 16-case audit. Keep unmatched reproduction and full composite
production acceptance explicit.

ฐาน: delivered IGIRDER.REFERENCE42-DEV ZIP; retained files are byte-identical.

- `concrete_pmm_pro/analysis/igird_reference43.py`: nonlinear reference kernel
- `tools/run_igird_reference43.py`: repeatable offline audit and material trace
- `tests/test_igird_reference43.py`: 36 new checks
- `docs/IGIRDER_REFERENCE43_METHOD.md`: source definitions, equations and scope
- `qa/evidence/igird_reference43/`: numerical comparison and regression evidence

ผลตรวจซอฟต์แวร์ที่เลือก: 552 passed, 7 warnings; ไม่ได้รันทั้ง repository
ผลเทียบที่เกณฑ์ 1%: strict 0/16 และ reject นอกขอบเขต 8 กรณี;
declared extension 5/16. Full composite Vn / Tn / V–T ยังไม่ผ่านการยืนยัน
และยังไม่เชื่อมเป็นกำลังออกแบบในหน้าผู้ใช้
