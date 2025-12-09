#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Seed script using raw SQL to avoid circular imports
Usage: python seed_organizations_simple.py
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection from environment"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    # Fix for Heroku postgres URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return psycopg2.connect(database_url)

def seed_organization_types(conn):
    """Seed Organization Types"""
    print("\n" + "="*60)
    print("🏢 Seeding Organization Types")
    print("="*60)
    
    organization_types = [
        (1, 'Hospital', 'โรงพยาบาล'),
        (2, 'Clinic', 'คลินิก'),
        (3, 'Laboratory', 'ห้องปฏิบัติการ'),
        (4, 'University', 'มหาวิทยาลัย'),
        (5, 'Research Institute', 'สถาบันวิจัย'),
        (6, 'Government Agency', 'หน่วยงานราชการ'),
        (7, 'Private Company', 'บริษัทเอกชน'),
        (8, 'NGO', 'องค์กรพัฒนาเอกชน'),
        (9, 'Pharmacy', 'ร้านขายยา'),
        (10, 'Healthcare Center', 'ศูนย์สุขภาพ'),
    ]
    
    cursor = conn.cursor()
    added = 0
    updated = 0
    
    for org_id, name_en, name_th in organization_types:
        try:
            # Check if exists
            cursor.execute("SELECT id FROM organization_types WHERE id = %s", (org_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update
                cursor.execute("""
                    UPDATE organization_types 
                    SET name_en = %s, name_th = %s, is_user_defined = false 
                    WHERE id = %s
                """, (name_en, name_th, org_id))
                updated += 1
                print(f"  ✏️  Updated: {name_en} ({name_th})")
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO organization_types (id, name_en, name_th, is_user_defined) 
                    VALUES (%s, %s, %s, false)
                """, (org_id, name_en, name_th))
                added += 1
                print(f"  ➕ Added: {name_en} ({name_th})")
        except Exception as e:
            print(f"  ⚠️  Error with {name_en}: {str(e)}")
            conn.rollback()
            continue
    
    conn.commit()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM organization_types")
    total = cursor.fetchone()[0]
    
    print(f"\n📊 Organization Types Summary:")
    print(f"   ➕ Added: {added}")
    print(f"   ✏️  Updated: {updated}")
    print(f"   📦 Total: {total}")
    
    cursor.close()

def seed_client_organizations(conn):
    """Seed Client Organizations (ComHealthOrg)"""
    print("\n" + "="*60)
    print("🏥 Seeding Client Organizations (comhealth_orgs)")
    print("="*60)
    
    client_orgs = [
        # Universities
        'มหาวิทยาลัยมหิดล',
        'จุฬาลงกรณ์มหาวิทยาลัย',
        'มหาวิทยาลัยธรรมศาสตร์',
        'มหาวิทยาลัยเกษตรศาสตร์',
        'มหาวิทยาลัยขอนแก่น',
        'มหาวิทยาลัยเชียงใหม่',
        'มหาวิทยาลัยสงขลานครินทร์',
        
        # Hospitals
        'โรงพยาบาลรามาธิบดี',
        'โรงพยาบาลศิริราช',
        'โรงพยาบาลจุฬาลงกรณ์',
        'โรงพยาบาลภูมิพลอดุลยเดช',
        'โรงพยาบาลพระมงกุฎเกล้า',
        'โรงพยาบาลตำรวจ',
        
        # Research Institutes
        'สถาบันวิจัยจุฬาภรณ์',
        'สถาบันบำราศนราดูร',
        'สถาบันวิจัยวิทยาศาสตร์สาธารณสุข',
        
        # Government Agencies
        'กรมวิทยาศาสตร์การแพทย์',
        'กรมควบคุมโรค',
        'สำนักงานคณะกรรมการอาหารและยา',
        'กรมสนับสนุนบริการสุขภาพ',
        'สำนักงานหลักประกันสุขภาพแห่งชาติ',
        
        # Private Companies (Energy)
        'บริษัท ไทยออยล์ จำกัด (มหาชน)',
        'บริษัท ปตท. จำกัด (มหาชน)',
        'บริษัท บางจากปิโตรเลียม จำกัด (มหาชน)',
        'บริษัท ไออาร์พีซี จำกัด (มหาชน)',
        'บริษัท พีทีที โกลบอล เคมิคอล จำกัด (มหาชน)',
        
        # Private Companies (Banking)
        'ธนาคารกรุงเทพ จำกัด (มหาชน)',
        'ธนาคารไทยพาณิชย์ จำกัด (มหาชน)',
        'ธนาคารกสิกรไทย จำกัด (มหาชน)',
        'ธนาคารกรุงไทย จำกัด (มหาชน)',
        'ธนาคารทหารไทยธนชาต จำกัด (มหาชน)',
        
        # Private Companies (Retail)
        'บริษัท ซีพี ออลล์ จำกัด (มหาชน)',
        'บริษัท เซ็นทรัล รีเทล คอร์ปอเรชั่น จำกัด (มหาชน)',
        'บริษัท โฮม โปรดักส์ เซ็นเตอร์ จำกัด (มหาชน)',
        'บริษัท เดอะมอลล์ กรุ๊ป จำกัด',
        
        # Utilities
        'การไฟฟ้าฝ่ายผลิตแห่งประเทศไทย',
        'การไฟฟ้านครหลวง',
        'การประปานครหลวง',
        'การประปาส่วนภูมิภาค',
        
        # Telecommunications
        'บริษัท ทรู คอร์ปอเรชั่น จำกัด (มหาชน)',
        'บริษัท แอดวานซ์ อินโฟร์ เซอร์วิส จำกัด (มหาชน)',
        'บริษัท ทริปเปิล ที บรอดแบนด์ จำกัด (มหาชน)',
        
        # Private Hospitals
        'โรงพยาบาลกรุงเทพ',
        'โรงพยาบาลบำรุงราษฎร์',
        'โรงพยาบาลสมิติเวช',
        'โรงพยาบาลพญาไท',
        'โรงพยาบาลเซนต์หลุยส์',
        'โรงพยาบาลบีเอ็นเอช',
        'โรงพยาบาลแพทย์รังสิต',
        
        # Manufacturing
        'บริษัท ไทยยูเนี่ยน โฟรเซ่น โปรดักส์ จำกัด (มหาชน)',
        'บริษัท เจริญโภคภัณฑ์อาหาร จำกัด (มหาชน)',
        'บริษัท ไทยเบฟเวอเรจ จำกัด (มหาชน)',
        
        # Technology & Services
        'บริษัท เอสซีจี แพคเกจจิ้ง จำกัด (มหาชน)',
        'บริษัท พรีเซียส ชิพปิ้ง จำกัด (มหาชน)',
        'สถาบันวิทยาศาสตร์และเทคโนโลยีแห่งประเทศไทย',
        'สำนักงานพัฒนาวิทยาศาสตร์และเทคโนโลยีแห่งชาติ',
    ]
    
    cursor = conn.cursor()
    added = 0
    skipped = 0
    
    for org_name in client_orgs:
        try:
            # Check if exists
            cursor.execute("SELECT id FROM comhealth_orgs WHERE name = %s", (org_name,))
            existing = cursor.fetchone()
            
            if existing:
                skipped += 1
                print(f"  ⏭️  Exists: {org_name}")
            else:
                # Insert
                cursor.execute("INSERT INTO comhealth_orgs (name) VALUES (%s)", (org_name,))
                added += 1
                print(f"  ➕ Added: {org_name}")
        except Exception as e:
            print(f"  ⚠️  Error with {org_name}: {str(e)}")
            conn.rollback()
            continue
    
    conn.commit()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM comhealth_orgs")
    total = cursor.fetchone()[0]
    
    print(f"\n📊 Client Organizations Summary:")
    print(f"   ➕ Added: {added}")
    print(f"   ⏭️  Already exists: {skipped}")
    print(f"   📦 Total: {total}")
    
    cursor.close()

def main():
    """Main execution function"""
    print("\n" + "🌱 " + "="*56 + " 🌱")
    print("   SEED DATA SCRIPT - ORGANIZATIONS")
    print("🌱 " + "="*56 + " 🌱\n")
    
    try:
        conn = get_db_connection()
        print("✅ Connected to database successfully")
        
        # Seed all data
        seed_organization_types(conn)
        seed_client_organizations(conn)
        
        print("\n" + "✅ " + "="*56 + " ✅")
        print("   ALL DATA SEEDED SUCCESSFULLY!")
        print("✅ " + "="*56 + " ✅\n")
        
        # Summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM organization_types")
        org_types_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM comhealth_orgs")
        client_orgs_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM organizations")
        regular_orgs_count = cursor.fetchone()[0]
        cursor.close()
        
        print("📈 Final Database Statistics:")
        print(f"   • Organization Types: {org_types_count}")
        print(f"   • Client Organizations (comhealth_orgs): {client_orgs_count}")
        print(f"   • Regular Organizations: {regular_orgs_count}")
        print()
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
