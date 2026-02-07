-- =====================================================
-- Seed Data for Organization Types and Organizations
-- Usage: psql <database> -f seed_organizations.sql
-- Or from Python: use psycopg2 or SQLAlchemy to execute
-- =====================================================

-- =====================================================
-- 1. ORGANIZATION TYPES
-- =====================================================

-- Insert or update organization types
INSERT INTO organization_types
          (id, name_en, name_th, is_user_defined)
VALUES
          (1, 'Hospital', 'โรงพยาบาล', false),
          (2, 'Clinic', 'คลินิก', false),
          (3, 'Laboratory', 'ห้องปฏิบัติการ', false),
          (4, 'University', 'มหาวิทยาลัย', false),
          (5, 'Research Institute', 'สถาบันวิจัย', false),
          (6, 'Government Agency', 'หน่วยงานราชการ', false),
          (7, 'Private Company', 'บริษัทเอกชน', false),
          (8, 'NGO', 'องค์กรพัฒนาเอกชน', false),
          (9, 'Pharmacy', 'ร้านขายยา', false),
          (10, 'Healthcare Center', 'ศูนย์สุขภาพ', false)
ON CONFLICT
(id) DO
UPDATE SET
    name_en = EXCLUDED.name_en,
    name_th = EXCLUDED.name_th,
    is_user_defined = EXCLUDED.is_user_defined;

-- Reset sequence if needed
SELECT setval('organization_types_id_seq', (SELECT MAX(id)
          FROM organization_types));

-- =====================================================
-- 2. CLIENT ORGANIZATIONS (comhealth_orgs)
-- =====================================================

-- Insert client organizations (for Type ID 7 and 1)
INSERT INTO comhealth_orgs
          (name)
VALUES
          -- Universities
          ('มหาวิทยาลัยมหิดล'),
          ('จุฬาลงกรณ์มหาวิทยาลัย'),
          ('มหาวิทยาลัยธรรมศาสตร์'),
          ('มหาวิทยาลัยเกษตรศาสตร์'),
          ('มหาวิทยาลัยขอนแก่น'),
          ('มหาวิทยาลัยเชียงใหม่'),
          ('มหาวิทยาลัยสงขลานครินทร์'),

          -- Hospitals
          ('โรงพยาบาลรามาธิบดี'),
          ('โรงพยาบาลศิริราช'),
          ('โรงพยาบาลจุฬาลงกรณ์'),
          ('โรงพยาบาลภูมิพลอดุลยเดช'),
          ('โรงพยาบาลพระมงกุฎเกล้า'),
          ('โรงพยาบาลตำรวจ'),

          -- Research Institutes
          ('สถาบันวิจัยจุฬาภรณ์'),
          ('สถาบันบำราศนราดูร'),
          ('สถาบันวิจัยวิทยาศาสตร์สาธารณสุข'),

          -- Government Agencies
          ('กรมวิทยาศาสตร์การแพทย์'),
          ('กรมควบคุมโรค'),
          ('สำนักงานคณะกรรมการอาหารและยา'),
          ('กรมสนับสนุนบริการสุขภาพ'),
          ('สำนักงานหลักประกันสุขภาพแห่งชาติ'),

          -- Private Companies (Energy & Oil)
          ('บริษัท ไทยออยล์ จำกัด (มหาชน)'),
          ('บริษัท ปตท. จำกัด (มหาชน)'),
          ('บริษัท บางจากปิโตรเลียม จำกัด (มหาชน)'),
          ('บริษัท ไออาร์พีซี จำกัด (มหาชน)'),
          ('บริษัท พีทีที โกลบอล เคมิคอล จำกัด (มหาชน)'),

          -- Private Companies (Banking & Finance)
          ('ธนาคารกรุงเทพ จำกัด (มหาชน)'),
          ('ธนาคารไทยพาณิชย์ จำกัด (มหาชน)'),
          ('ธนาคารกสิกรไทย จำกัด (มหาชน)'),
          ('ธนาคารกรุงไทย จำกัด (มหาชน)'),
          ('ธนาคารทหารไทยธนชาต จำกัด (มหาชน)'),

          -- Private Companies (Retail)
          ('บริษัท ซีพี ออลล์ จำกัด (มหาชน)'),
          ('บริษัท เซ็นทรัล รีเทล คอร์ปอเรชั่น จำกัด (มหาชน)'),
          ('บริษัท โฮม โปรดักส์ เซ็นเตอร์ จำกัด (มหาชน)'),
          ('บริษัท เดอะมอลล์ กรุ๊ป จำกัด'),

          -- Private Companies (Utilities)
          ('การไฟฟ้าฝ่ายผลิตแห่งประเทศไทย'),
          ('การไฟฟ้านครหลวง'),
          ('การประปานครหลวง'),
          ('การประปาส่วนภูมิภาค'),

          -- Private Companies (Telecommunications)
          ('บริษัท ทรู คอร์ปอเรชั่น จำกัด (มหาชน)'),
          ('บริษัท แอดวานซ์ อินโฟร์ เซอร์วิส จำกัด (มหาชน)'),
          ('บริษัท ทริปเปิล ที บรอดแบนด์ จำกัด (มหาชน)'),

          -- Private Hospitals
          ('โรงพยาบาลกรุงเทพ'),
          ('โรงพยาบาลบำรุงราษฎร์'),
          ('โรงพยาบาลสมิติเวช'),
          ('โรงพยาบาลพญาไท'),
          ('โรงพยาบาลเซนต์หลุยส์'),
          ('โรงพยาบาลบีเอ็นเอช'),
          ('โรงพยาบาลแพทย์รังสิต'),

          -- Manufacturing
          ('บริษัท ไทยยูเนี่ยน โฟรเซ่น โปรดักส์ จำกัด (มหาชน)'),
          ('บริษัท เจริญโภคภัณฑ์อาหาร จำกัด (มหาชน)'),
          ('บริษัท ไทยเบฟเวอเรจ จำกัด (มหาชน)'),
          ('บริษัท ซีพี ออลล์ จำกัด (มหาชน)'),

          -- Technology & Services
          ('บริษัท เอสซีจี แพคเกจจิ้ง จำกัด (มหาชน)'),
          ('บริษัท พรีเซียส ชิพปิ้ง จำกัด (มหาชน)'),
          ('สถาบันวิทยาศาสตร์และเทคโนโลยีแห่งประเทศไทย'),
          ('สำนักงานพัฒนาวิทยาศาสตร์และเทคโนโลยีแห่งชาติ')

ON CONFLICT
(name) DO NOTHING;

-- =====================================================
-- 3. REGULAR ORGANIZATIONS (organizations table)
-- =====================================================

-- Insert regular organizations with their types
INSERT INTO organizations
          (name, organization_type_id, country, is_user_defined)
VALUES
          -- Hospitals (Type 1)
          ('Ramathibodi Hospital', 1, 'Thailand', false),
          ('Siriraj Hospital', 1, 'Thailand', false),
          ('BNH Hospital', 1, 'Thailand', false),
          ('MedPark Hospital', 1, 'Thailand', false),
          ('Bumrungrad International Hospital', 1, 'Thailand', false),
          ('Samitivej Hospital', 1, 'Thailand', false),

          -- Clinics (Type 2)
          ('Bangkok Health Clinic', 2, 'Thailand', false),
          ('Sukhumvit Medical Center', 2, 'Thailand', false),
          ('Thonglor Wellness Clinic', 2, 'Thailand', false),
          ('Pattaya International Clinic', 2, 'Thailand', false),

          -- Laboratories (Type 3)
          ('National Reference Laboratory', 3, 'Thailand', false),
          ('Central Lab Services', 3, 'Thailand', false),
          ('Bangkok Medical Laboratory', 3, 'Thailand', false),
          ('Chulalongkorn Medical Laboratory', 3, 'Thailand', false),

          -- Universities (Type 4)
          ('Mahidol University', 4, 'Thailand', false),
          ('Chulalongkorn University', 4, 'Thailand', false),
          ('Thammasat University', 4, 'Thailand', false),
          ('Kasetsart University', 4, 'Thailand', false),
          ('Khon Kaen University', 4, 'Thailand', false),
          ('Prince of Songkla University', 4, 'Thailand', false),

          -- Research Institutes (Type 5)
          ('National Science and Technology Development Agency', 5, 'Thailand', false),
          ('Thailand Institute of Scientific and Technological Research', 5, 'Thailand', false),
          ('National Center for Genetic Engineering and Biotechnology', 5, 'Thailand', false),

          -- Government Agencies (Type 6)
          ('Ministry of Public Health', 6, 'Thailand', false),
          ('Department of Medical Sciences', 6, 'Thailand', false),
          ('Food and Drug Administration', 6, 'Thailand', false),
          ('Department of Disease Control', 6, 'Thailand', false),
          ('National Health Security Office', 6, 'Thailand', false),

          -- NGOs (Type 8)
          ('Thai Red Cross Society', 8, 'Thailand', false),
          ('Foundation for AIDS Rights', 8, 'Thailand', false),
          ('Population and Community Development Association', 8, 'Thailand', false),
          ('Ramathibodi Foundation', 8, 'Thailand', false),

          -- Pharmacies (Type 9)
          ('Fascino Pharmacy', 9, 'Thailand', false),
          ('Boots Pharmacy Thailand', 9, 'Thailand', false),
          ('Watsons Pharmacy', 9, 'Thailand', false),
          ('Matsumoto Kiyoshi Thailand', 9, 'Thailand', false),

          -- Healthcare Centers (Type 10)
          ('Community Health Center Bangkok', 10, 'Thailand', false),
          ('Pattaya Health Center', 10, 'Thailand', false),
          ('Chiang Mai Community Health', 10, 'Thailand', false),
          ('Phuket Health Promotion Center', 10, 'Thailand', false)

ON CONFLICT
(name) DO NOTHING;

-- =====================================================
-- Summary & Verification Queries
-- =====================================================

-- Show counts
          SELECT 'Organization Types' as table_name, COUNT(*) as count
          FROM organization_types
UNION ALL
          SELECT 'Client Organizations', COUNT(*)
          FROM comhealth_orgs
UNION ALL
          SELECT 'Regular Organizations', COUNT(*)
          FROM organizations;

-- Show organization types with counts
SELECT
          ot.id,
          ot.name_en,
          ot.name_th,
          COUNT(o.id) as org_count
FROM organization_types ot
          LEFT JOIN organizations o ON o.organization_type_id = ot.id
GROUP BY ot.id, ot.name_en, ot.name_th
ORDER BY ot.id;

-- Show sample client organizations
SELECT id, name
FROM comhealth_orgs
ORDER BY name LIMIT 10;

-- Show sample regular organizations by type
SELECT 
    o.id,
    o.name
,
    ot.name_en as org_type,
    o.country
FROM organizations o
LEFT JOIN organization_types ot ON ot.id = o.organization_type_id
ORDER BY o.organization_type_id, o.name
LIMIT 20;
