#!/usr/bin/env python3
"""Quick script to check current members in database"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.continuing_edu.models import Member, db

with app.app_context():
    try:
        count = Member.query.count()
        print(f'Total members: {count}')
        
        recent = Member.query.order_by(Member.created_at.desc()).limit(5).all()
        print('\nRecent 5 members:')
        for m in recent:
            google_status = "Yes" if m.google_sub else "No"
            email = m.email or "No email"
            print(f'  ID: {m.id}, Username: {m.username}, Email: {email}, Google: {google_status}')
            
        # Check for test users
        print('\nExisting test users:')
        test_users = Member.query.filter(Member.username.like('test%')).all()
        if test_users:
            for tu in test_users:
                print(f'  - {tu.username} ({tu.email})')
        else:
            print('  No test users found')
            
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
