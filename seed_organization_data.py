#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Seed script for Organization Types and Client Organizations
Usage: python seed_organization_data.py
"""

import sys
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize minimal Flask app
app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db
db = SQLAlchemy(app)

# Import models after db is initialized
from app.continuing_edu.models import OrganizationType, Organization
from app.comhealth.models import ComHealthOrg


def seed_organization_types():
    """Seed Organization Types data"""
    print("\n" + "="*60)
    print("🏢 Seeding Organization Types")
    print("="*60)
    
    organization_types = [
        {'id': 1, 'name_en': 'Hospital', 'name_th': 'โรงพยาบาล'},
        {'id': 2, 'name_en': 'Clinic', 'name_th': 'คลินิก'},
        {'id': 3, 'name_en': 'Laboratory', 'name_th': 'ห้องปฏิบัติการ'},
        {'id': 4, 'name_en': 'University', 'name_th': 'มหาวิทยาลัย'},
        {'id': 5, 'name_en': 'Research Institute', 'name_th': 'สถาบันวิจัย'},
        {'id': 6, 'name_en': 'Government Agency', 'name_th': 'หน่วยงานราชการ'},
        {'id': 7, 'name_en': 'Private Company', 'name_th': 'บริษัทเอกชน'},
        {'id': 8, 'name_en': 'NGO', 'name_th': 'องค์กรพัฒนาเอกชน'},
        {'id': 9, 'name_en': 'Pharmacy', 'name_th': 'ร้านขายยา'},
        {'id': 10, 'name_en': 'Healthcare Center', 'name_th': 'ศูนย์สุขภาพ'},
    ]
    
    added = 0
    updated = 0
    skipped = 0
    
    for org_type_data in organization_types:
        try:
            existing = OrganizationType.query.filter_by(id=org_type_data['id']).first()
            
            if existing:
                # Update existing record
                existing.name_en = org_type_data['name_en']
                existing.name_th = org_type_data['name_th']
                existing.is_user_defined = False
                updated += 1
                print(f"  ✏️  Updated: {org_type_data['name_en']} ({org_type_data['name_th']})")
            else:
                # Create new record
                org_type = OrganizationType(
                    id=org_type_data['id'],
                    name_en=org_type_data['name_en'],
                    name_th=org_type_data['name_th'],
                    is_user_defined=False
                )
                db.session.add(org_type)
                added += 1
                print(f"  ➕ Added: {org_type_data['name_en']} ({org_type_data['name_th']})")
                
        except IntegrityError as e:
            db.session.rollback()
            print(f"  ⚠️  Skipped (duplicate): {org_type_data['name_en']}")
            skipped += 1
            continue
    
    db.session.commit()
    
    print(f"\n📊 Organization Types Summary:")
    print(f"   ➕ Added: {added}")
    print(f"   ✏️  Updated: {updated}")
    print(f"   ⚠️  Skipped: {skipped}")
    print(f"   📦 Total: {OrganizationType.query.count()}")


def seed_client_organizations():
    """Seed Client Organizations (ComHealthOrg) data"""
    print("\n" + "="*60)
    print("🏥 Seeding Client Organizations (comhealth_orgs)")
    print("="*60)
    
    # Sample client organizations - adjust these based on your actual data
    client_orgs = [
        'มหาวิทยาลัยมหิดล',
        'จุฬาลงกรณ์มหาวิทยาลัย',
        'มหาวิทยาลัยธรรมศาสตร์',
        'โรงพยาบาลรามาธิบดี',
        'โรงพยาบาลศิริราช',
        'โรงพยาบาลจุฬาลงกรณ์',
        'สถาบันวิจัยจุฬาภรณ์',
        'สถาบันบำราศนราดูร',
        'กรมวิทยาศาสตร์การแพทย์',
        'กรมควบคุมโรค',
        'สำนักงานคณะกรรมการอาหารและยา',
        'บริษัท ไทยออยล์ จำกัด (มหาชน)',
        'บริษัท ปตท. จำกัด (มหาชน)',
        'บริษัท บางจากปิโตรเลียม จำกัด (มหาชน)',
        'บริษัท ไออาร์พีซี จำกัด (มหาชน)',
        'ธนาคารกรุงเทพ จำกัด (มหาชน)',
        'ธนาคารไทยพาณิชย์ จำกัด (มหาชน)',
        'บริษัท ซีพี ออลล์ จำกัด (มหาชน)',
        'บริษัท เซ็นทรัล รีเทล คอร์ปอเรชั่น จำกัด (มหาชน)',
        'การไฟฟ้าฝ่ายผลิตแห่งประเทศไทย',
        'การไฟฟ้านครหลวง',
        'การประปานครหลวง',
        'บริษัท ทรู คอร์ปอเรชั่น จำกัด (มหาชน)',
        'บริษัท แอดวานซ์ อินโฟร์ เซอร์วิส จำกัด (มหาชน)',
        'โรงพยาบาลกรุงเทพ',
        'โรงพยาบาลบำรุงราษฎร์',
        'โรงพยาบาลสมิติเวช',
        'โรงพยาบาลพญาไท',
        'โรงพยาบาลเซนต์หลุยส์',
        'สถาบันวิทยาศาสตร์และเทคโนโลยีแห่งประเทศไทย',
    ]
    
    added = 0
    updated = 0
    skipped = 0
    
    for org_name in client_orgs:
        try:
            existing = ComHealthOrg.query.filter_by(name=org_name).first()
            
            if existing:
                skipped += 1
                print(f"  ⏭️  Exists: {org_name}")
            else:
                # Create new record
                org = ComHealthOrg(name=org_name)
                db.session.add(org)
                added += 1
                print(f"  ➕ Added: {org_name}")
                
        except IntegrityError as e:
            db.session.rollback()
            print(f"  ⚠️  Error: {org_name} - {str(e)}")
            skipped += 1
            continue
    
    db.session.commit()
    
    print(f"\n📊 Client Organizations Summary:")
    print(f"   ➕ Added: {added}")
    print(f"   ⏭️  Already exists: {skipped}")
    print(f"   📦 Total: {ComHealthOrg.query.count()}")


def seed_sample_regular_organizations():
    """Seed sample regular organizations linked to types"""
    print("\n" + "="*60)
    print("🏢 Seeding Sample Regular Organizations")
    print("="*60)
    
    # Sample organizations with their types
    sample_orgs = [
        {'name': 'Ramathibodi Hospital', 'type_id': 1},  # Hospital
        {'name': 'Siriraj Hospital', 'type_id': 1},  # Hospital
        {'name': 'BNH Hospital', 'type_id': 1},  # Hospital
        {'name': 'MedPark Hospital', 'type_id': 1},  # Hospital
        {'name': 'Bangkok Health Clinic', 'type_id': 2},  # Clinic
        {'name': 'Sukhumvit Medical Center', 'type_id': 2},  # Clinic
        {'name': 'National Reference Laboratory', 'type_id': 3},  # Laboratory
        {'name': 'Central Lab Services', 'type_id': 3},  # Laboratory
        {'name': 'Mahidol University', 'type_id': 4},  # University
        {'name': 'Chulalongkorn University', 'type_id': 4},  # University
        {'name': 'Thammasat University', 'type_id': 4},  # University
        {'name': 'National Science and Technology Development Agency', 'type_id': 5},  # Research
        {'name': 'Thailand Institute of Scientific Research', 'type_id': 5},  # Research
        {'name': 'Ministry of Public Health', 'type_id': 6},  # Government
        {'name': 'Department of Medical Sciences', 'type_id': 6},  # Government
        {'name': 'Food and Drug Administration', 'type_id': 6},  # Government
        {'name': 'Thai Red Cross Society', 'type_id': 8},  # NGO
        {'name': 'Foundation for AIDS Rights', 'type_id': 8},  # NGO
        {'name': 'Fascino Pharmacy', 'type_id': 9},  # Pharmacy
        {'name': 'Boots Pharmacy Thailand', 'type_id': 9},  # Pharmacy
        {'name': 'Watsons Pharmacy', 'type_id': 9},  # Pharmacy
        {'name': 'Community Health Center Bangkok', 'type_id': 10},  # Healthcare Center
        {'name': 'Pattaya Health Center', 'type_id': 10},  # Healthcare Center
    ]
    
    added = 0
    skipped = 0
    
    for org_data in sample_orgs:
        try:
            existing = Organization.query.filter_by(name=org_data['name']).first()
            
            if existing:
                skipped += 1
                print(f"  ⏭️  Exists: {org_data['name']}")
            else:
                # Create new record
                org = Organization(
                    name=org_data['name'],
                    organization_type_id=org_data['type_id'],
                    country='Thailand',
                    is_user_defined=False
                )
                db.session.add(org)
                added += 1
                print(f"  ➕ Added: {org_data['name']} (Type ID: {org_data['type_id']})")
                
        except IntegrityError as e:
            db.session.rollback()
            print(f"  ⚠️  Error: {org_data['name']} - {str(e)}")
            skipped += 1
            continue
    
    db.session.commit()
    
    print(f"\n📊 Regular Organizations Summary:")
    print(f"   ➕ Added: {added}")
    print(f"   ⏭️  Already exists: {skipped}")
    print(f"   📦 Total: {Organization.query.count()}")


def main():
    """Main execution function"""
    print("\n" + "🌱 " + "="*56 + " 🌱")
    print("   SEED DATA SCRIPT - ORGANIZATIONS")
    print("🌱 " + "="*56 + " 🌱\n")
    
    with app.app_context():
        try:
            # Seed all data
            seed_organization_types()
            seed_client_organizations()
            seed_sample_regular_organizations()
            
            print("\n" + "✅ " + "="*56 + " ✅")
            print("   ALL DATA SEEDED SUCCESSFULLY!")
            print("✅ " + "="*56 + " ✅\n")
            
            # Summary
            print("📈 Final Database Statistics:")
            print(f"   • Organization Types: {OrganizationType.query.count()}")
            print(f"   • Client Organizations (comhealth_orgs): {ComHealthOrg.query.count()}")
            print(f"   • Regular Organizations: {Organization.query.count()}")
            print()
            
        except Exception as e:
            print(f"\n❌ Error during seeding: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            sys.exit(1)


if __name__ == '__main__':
    main()
