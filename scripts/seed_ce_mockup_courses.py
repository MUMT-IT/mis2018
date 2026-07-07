"""
สคริปต์สำหรับสร้างข้อมูล mockup ของหลักสูตร continuing education
เพื่อทดสอบการแสดงผล

รันด้วย: FLASK_APP=app.main:app flask seed-ce-courses
"""
from datetime import datetime, timedelta

from app.main import app, db
from app.continuing_edu.models import (
    CEEventEntity, 
    CEEntityCategory,
    CEEventSpeaker,
    CEEventAgenda,
    CEEventRegistrationFee,
    CEMemberType,
)
from app.staff.models import StaffAccount


def create_mockup_courses():
    """สร้างข้อมูล mockup 5 courses"""
    
    # ตรวจสอบว่ามี category อยู่แล้วหรือไม่
    category = CEEntityCategory.query.first()
    if not category:
        print("กำลังสร้าง category ใหม่...")
        category = CEEntityCategory(
            name_th="การพัฒนาวิชาชีพ",
            name_en="Professional Development",
            description="Professional development courses",
            entity_category_code="prof_dev"
        )
        db.session.add(category)
        db.session.commit()
    
    # หา staff account สำหรับกำหนดเป็นผู้สร้าง
    staff = StaffAccount.query.first()
    if not staff:
        print("⚠️  ไม่พบ staff account ในระบบ กำลังข้ามการกำหนด staff_id")
        staff_id = None
    else:
        staff_id = staff.id
    
    # ข้อมูล mockup courses
    courses_data = [
        {
            "course_code": "CE2026-001",
            "title_en": "Advanced Clinical Laboratory Techniques",
            "title_th": "เทคนิคห้องปฏิบัติการทางคลินิกขั้นสูง",
            "description_en": "Learn advanced laboratory techniques for clinical diagnostics and research applications.",
            "description_th": "เรียนรู้เทคนิคห้องปฏิบัติการขั้นสูงสำหรับการวินิจฉัยทางคลินิกและการวิจัย",
            "long_description_en": "This comprehensive course covers cutting-edge laboratory techniques including molecular diagnostics, flow cytometry, and advanced microscopy. Students will gain hands-on experience with state-of-the-art equipment and learn best practices for quality control and laboratory management.",
            "long_description_th": "หลักสูตรที่ครอบคลุมเทคนิคห้องปฏิบัติการที่ทันสมัย รวมถึงการวินิจฉัยระดับโมเลกุล flow cytometry และกล้องจุลทรรศน์ขั้นสูง ผู้เรียนจะได้รับประสบการณ์ตรงในการใช้อุปกรณ์ที่ทันสมัยและเรียนรู้แนวทางปฏิบัติที่ดีสำหรับการควบคุมคุณภาพและการจัดการห้องปฏิบัติการ",
            "duration_en": "40 hours",
            "duration_th": "40 ชั่วโมง",
            "format_en": "Hybrid (Online + On-site)",
            "format_th": "แบบผสม (ออนไลน์ + ปฏิบัติที่สถานที่จริง)",
            "location_en": "Faculty of Medical Technology, Mahidol University",
            "location_th": "คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล",
            "certificate_name_en": "Certificate in Advanced Clinical Laboratory Techniques",
            "certificate_name_th": "ใบรับรองการผ่านหลักสูตรเทคนิคห้องปฏิบัติการทางคลินิกขั้นสูง",
            "continue_education_score": 4.0,
            "price": 12000,
        },
        {
            "course_code": "CE2026-002",
            "title_en": "Medical Microbiology and Infectious Diseases",
            "title_th": "จุลชีววิทยาทางการแพทย์และโรคติดเชื้อ",
            "description_en": "Comprehensive study of medical microbiology, pathogenic organisms, and infectious disease management.",
            "description_th": "ศึกษาจุลชีววิทยาทางการแพทย์ เชื้อโรค และการจัดการโรคติดเชื้ออย่างครอบคลุม",
            "long_description_en": "This course provides in-depth knowledge of bacterial, viral, fungal, and parasitic infections. Topics include diagnostic methods, antimicrobial resistance, infection control, and emerging infectious diseases. Ideal for laboratory professionals and healthcare workers.",
            "long_description_th": "หลักสูตรนี้ให้ความรู้เชิงลึกเกี่ยวกับการติดเชื้อแบคทีเรีย ไวรัส เชื้อรา และปรสิต หัวข้อรวมถึงวิธีการวินิจฉัย ความต้านทานต่อยาต้านจุลชีพ การควบคุมการติดเชื้อ และโรคติดเชื้อที่กำลังเกิดขึ้นใหม่ เหมาะสำหรับนักวิทยาศาสตร์การแพทย์และบุคลากรทางสาธารณสุข",
            "duration_en": "30 hours",
            "duration_th": "30 ชั่วโมง",
            "format_en": "Online",
            "format_th": "ออนไลน์",
            "location_en": "Online Platform",
            "location_th": "แพลตฟอร์มออนไลน์",
            "certificate_name_en": "Certificate in Medical Microbiology",
            "certificate_name_th": "ใบรับรองการผ่านหลักสูตรจุลชีววิทยาทางการแพทย์",
            "continue_education_score": 3.0,
            "price": 8000,
        },
        {
            "course_code": "CE2026-003",
            "title_en": "Clinical Biochemistry and Laboratory Medicine",
            "title_th": "ชีวเคมีคลินิกและเวชศาสตร์ห้องปฏิบัติการ",
            "description_en": "Study clinical biochemistry principles and their applications in disease diagnosis and monitoring.",
            "description_th": "ศึกษาหลักการชีวเคมีคลินิกและการประยุกต์ใช้ในการวินิจฉัยและติดตามโรค",
            "long_description_en": "Covers biochemical tests, interpretation of laboratory results, quality assurance, and the role of laboratory medicine in patient care. Topics include enzyme analysis, hormone assays, lipid profiles, and tumor markers.",
            "long_description_th": "ครอบคลุมการตรวจทางชีวเคมี การแปลผลการตรวจทางห้องปฏิบัติการ การประกันคุณภาพ และบทบาทของเวชศาสตร์ห้องปฏิบัติการในการดูแลผู้ป่วย หัวข้อรวมถึงการวิเคราะห์เอนไซม์ การตรวจฮอร์โมน lipid profile และ tumor markers",
            "duration_en": "35 hours",
            "duration_th": "35 ชั่วโมง",
            "format_en": "On-site",
            "format_th": "ปฏิบัติที่สถานที่จริง",
            "location_en": "Faculty of Medical Technology, Mahidol University",
            "location_th": "คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล",
            "certificate_name_en": "Certificate in Clinical Biochemistry",
            "certificate_name_th": "ใบรับรองการผ่านหลักสูตรชีวเคมีคลินิก",
            "continue_education_score": 3.5,
            "price": 10000,
        },
        {
            "course_code": "CE2026-004",
            "title_en": "Molecular Diagnostics and Genomics",
            "title_th": "การวินิจฉัยระดับโมเลกุลและจีโนมิกส์",
            "description_en": "Learn cutting-edge molecular diagnostic techniques including PCR, sequencing, and genetic analysis.",
            "description_th": "เรียนรู้เทคนิคการวินิจฉัยระดับโมเลกุลที่ทันสมัย รวมถึง PCR การลำดับดีเอ็นเอ และการวิเคราะห์ทางพันธุกรรม",
            "long_description_en": "This advanced course explores molecular biology techniques used in modern diagnostics. Students will learn about PCR methods, next-generation sequencing, CRISPR applications, and personalized medicine. Includes practical laboratory sessions and case studies.",
            "long_description_th": "หลักสูตรขั้นสูงนี้สำรวจเทคนิคชีววิทยาโมเลกุลที่ใช้ในการวินิจฉัยสมัยใหม่ ผู้เรียนจะได้เรียนรู้เกี่ยวกับวิธีการ PCR การลำดับดีเอ็นเอรุ่นใหม่ การประยุกต์ใช้ CRISPR และการแพทย์เฉพาะบุคคล รวมถึงการปฏิบัติในห้องปฏิบัติการและกรณีศึกษา",
            "duration_en": "45 hours",
            "duration_th": "45 ชั่วโมง",
            "format_en": "Hybrid (Online + On-site)",
            "format_th": "แบบผสม (ออนไลน์ + ปฏิบัติที่สถานที่จริง)",
            "location_en": "Faculty of Medical Technology, Mahidol University",
            "location_th": "คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล",
            "certificate_name_en": "Certificate in Molecular Diagnostics",
            "certificate_name_th": "ใบรับรองการผ่านหลักสูตรการวินิจฉัยระดับโมเลกุล",
            "continue_education_score": 4.5,
            "price": 15000,
        },
        {
            "course_code": "CE2026-005",
            "title_en": "Laboratory Quality Management and Accreditation",
            "title_th": "การจัดการคุณภาพห้องปฏิบัติการและการรับรอง",
            "description_en": "Master quality management systems, ISO standards, and laboratory accreditation processes.",
            "description_th": "เชี่ยวชาญระบบการจัดการคุณภาพ มาตรฐาน ISO และกระบวนการรับรองห้องปฏิบัติการ",
            "long_description_en": "This course covers ISO 15189 requirements, quality management principles, internal audits, and preparation for laboratory accreditation. Topics include document control, staff competency assessment, equipment management, and continuous improvement strategies.",
            "long_description_th": "หลักสูตรนี้ครอบคลุมข้อกำหนด ISO 15189 หลักการจัดการคุณภาพ การตรวจสอบภายใน และการเตรียมตัวสำหรับการรับรองห้องปฏิบัติการ หัวข้อรวมถึงการควบคุมเอกสาร การประเมินสมรรถนะบุคลากร การจัดการอุปกรณ์ และกลยุทธ์การปรับปรุงอย่างต่อเนื่อง",
            "duration_en": "25 hours",
            "duration_th": "25 ชั่วโมง",
            "format_en": "Online",
            "format_th": "ออนไลน์",
            "location_en": "Online Platform",
            "location_th": "แพลตฟอร์มออนไลน์",
            "certificate_name_en": "Certificate in Laboratory Quality Management",
            "certificate_name_th": "ใบรับรองการผ่านหลักสูตรการจัดการคุณภาพห้องปฏิบัติการ",
            "continue_education_score": 2.5,
            "price": 6000,
        },
    ]
    
    print("\n🎓 กำลังสร้างข้อมูล mockup courses...\n")
    
    # ข้อมูล speaker ตัวอย่างสำหรับใช้ใน course
    speakers_data = [
        {
            "title_en": "Assoc. Prof. Dr.",
            "title_th": "รศ.ดร.",
            "name_en": "Somchai Jaidee",
            "name_th": "สมชาย ใจดี",
            "email": "somchai@example.com",
            "institution_en": "Faculty of Medical Technology, Mahidol University",
            "institution_th": "คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล",
            "position_en": "Associate Professor",
            "position_th": "รองศาสตราจารย์",
            "bio_th": "ผู้เชี่ยวชาญด้านเทคนิคการแพทย์มีประสบการณ์มากกว่า 20 ปี",
            "bio_en": "Medical Technology Expert with over 20 years of experience"
        },
        {
            "title_en": "Asst. Prof. Dr.",
            "title_th": "ผศ.ดร.",
            "name_en": "Somying Witthayakan",
            "name_th": "สมหญิง วิทยาการ",
            "email": "somying@example.com",
            "institution_en": "Faculty of Medical Technology, Mahidol University",
            "institution_th": "คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล",
            "position_en": "Assistant Professor",
            "position_th": "ผู้ช่วยศาสตราจารย์",
            "bio_th": "นักวิจัยด้านจุลชีววิทยาและโรคติดเชื้อ",
            "bio_en": "Microbiology and Infectious Disease Researcher"
        },
    ]
    
    # หา member types สำหรับการกำหนดค่าธรรมเนียม
    member_types = CEMemberType.query.all()
    
    # สร้าง courses
    created_count = 0
    for idx, course_data in enumerate(courses_data, 1):
        # ตรวจสอบว่ามี course code นี้อยู่แล้วหรือไม่
        existing = CEEventEntity.query.filter_by(course_code=course_data["course_code"]).first()
        if existing:
            print(f"⏭️  ข้าม: {course_data['course_code']} - {course_data['title_th']} (มีอยู่แล้ว)")
            continue
        
        # เพิ่ม early bird registration
        now = datetime.now()
        early_bird_start = now
        early_bird_end = now + timedelta(days=30)
        
        # สร้าง course
        course = CEEventEntity(
            event_type="course",
            course_code=course_data["course_code"],
            title_en=course_data["title_en"],
            title_th=course_data["title_th"],
            description_en=course_data["description_en"],
            description_th=course_data["description_th"],
            long_description_en=course_data["long_description_en"],
            long_description_th=course_data["long_description_th"],
            duration_en=course_data["duration_en"],
            duration_th=course_data["duration_th"],
            format_en=course_data["format_en"],
            format_th=course_data["format_th"],
            location_en=course_data["location_en"],
            location_th=course_data["location_th"],
            certificate_name_en=course_data["certificate_name_en"],
            certificate_name_th=course_data["certificate_name_th"],
            continue_education_score=course_data["continue_education_score"],
            category_id=category.id,
            staff_id=staff_id,
            creating_institution="คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล",
            department_or_unit="ภาควิชาเทคนิคการแพทย์",
            early_bird_start=early_bird_start,
            early_bird_end=early_bird_end,
        )
        
        db.session.add(course)
        db.session.flush()  # เพื่อให้ได้ course.id
        
        # เพิ่ม speaker ให้กับ course (เลือกจาก list วนกัน)
        if idx <= len(speakers_data):
            speaker_data = speakers_data[(idx - 1) % len(speakers_data)]
            event_speaker = CEEventSpeaker(
                event_entity_id=course.id,
                title_en=speaker_data["title_en"],
                title_th=speaker_data["title_th"],
                name_en=speaker_data["name_en"],
                name_th=speaker_data["name_th"],
                email=speaker_data["email"],
                phone="02-123-4567",
                institution_en=speaker_data["institution_en"],
                institution_th=speaker_data["institution_th"],
                position_en=speaker_data["position_en"],
                position_th=speaker_data["position_th"],
                bio_en=speaker_data["bio_en"],
                bio_th=speaker_data["bio_th"],
            )
            db.session.add(event_speaker)
        
        # เพิ่ม registration fees
        base_price = float(course_data["price"])
        early_bird_price = base_price * 0.85  # ส่วนลด 15% สำหรับ early bird
        
        if member_types:
            for member_type in member_types:
                # ค่าธรรมเนียมพร้อม early bird discount
                fee = CEEventRegistrationFee(
                    event_entity_id=course.id,
                    member_type_id=member_type.id,
                    price=base_price,
                    early_bird_price=early_bird_price
                )
                db.session.add(fee)
        
        # เพิ่ม agenda ตัวอย่าง
        agenda_items = [
            {
                "title_en": "Introduction and Course Overview",
                "title_th": "บทนำและภาพรวมของหลักสูตร",
                "description_en": "Introduction to course objectives and learning outcomes",
                "description_th": "แนะนำวัตถุประสงค์และผลการเรียนรู้ของหลักสูตร",
                "order": 1,
                "start_time": now.replace(hour=9, minute=0),
                "end_time": now.replace(hour=10, minute=30),
            },
            {
                "title_en": "Core Concepts and Theory",
                "title_th": "แนวคิดหลักและทฤษฎี",
                "description_en": "Fundamental theories and concepts",
                "description_th": "ทฤษฎีและแนวคิดพื้นฐาน",
                "order": 2,
                "start_time": now.replace(hour=10, minute=45),
                "end_time": now.replace(hour=12, minute=0),
            },
            {
                "title_en": "Practical Applications",
                "title_th": "การประยุกต์ใช้งานจริง",
                "description_en": "Hands-on practice and case studies",
                "description_th": "การปฏิบัติจริงและกรณีศึกษา",
                "order": 3,
                "start_time": now.replace(hour=13, minute=0),
                "end_time": now.replace(hour=15, minute=0),
            },
        ]
        
        for agenda_data in agenda_items:
            agenda = CEEventAgenda(
                event_entity_id=course.id,
                **agenda_data
            )
            db.session.add(agenda)
        
        created_count += 1
        print(f"✅ สร้างแล้ว: {course_data['course_code']} - {course_data['title_th']}")
        print(f"   ราคา: ฿{int(base_price):,} (Early Bird: ฿{int(early_bird_price):,})")
        print(f"   คะแนน CE: {course_data['continue_education_score']}")
        print()
    
    # Commit ทั้งหมด
    db.session.commit()
    
    print(f"\n🎉 สร้างข้อมูล mockup เสร็จสิ้น!")
    print(f"📊 สร้างหลักสูตรใหม่: {created_count} หลักสูตร")
    print(f"📋 รวมทั้งหมดในระบบ: {CEEventEntity.query.filter_by(event_type='course').count()} หลักสูตร")
    print("\n💡 คุณสามารถดูหลักสูตรที่สร้างได้ที่หน้าเว็บ continuing education\n")


# สร้าง Flask CLI command
@app.cli.command('seed-ce-courses')
def seed_ce_courses_command():
    """สร้างข้อมูล mockup courses สำหรับ continuing education"""
    print("=" * 70)
    print("  🎓 Continuing Education Mockup Course Generator")
    print("=" * 70)
    create_mockup_courses()


if __name__ == "__main__":
    print("=" * 70)
    print("  🎓 Continuing Education Mockup Course Generator")
    print("=" * 70)
    with app.app_context():
        create_mockup_courses()
