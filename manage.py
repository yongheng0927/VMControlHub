#!/usr/bin/env python3
import sys
import argparse
from getpass import getpass
from app import create_app
from app.models import db, User

app = create_app()

def createsuperuser():
    """Create a superuser with the role of admin"""
    try:
        print('Start creating superuser...')
        
        username = input('Please enter username: ').strip()
        if not username:
            print('✗ Username cannot be empty')
            return
        
        with app.app_context():
            if User.query.filter_by(username=username).first():
                print(f'✗ User {username} already exists')
                return
        
        password = getpass('Please enter password: ')
        password2 = getpass('Please confirm password: ')
        
        if password != password2:
            print('✗ Passwords do not match')
            return
        
        if len(password) < 6:
            print('✗ Password must be at least 6 characters long')
            return
        
        with app.app_context():
            user = User(username=username, role='admin')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        
        print(f'✓ Superuser {username} created successfully!')
    except KeyboardInterrupt:
        print('\n✗ Operation cancelled by user')
        sys.exit(0)
    except Exception as e:
        print(f'✗ Creation failed: {str(e)}')
        sys.exit(1)

def changepassword():
    """Change password for specified user"""
    try:
        username = input('Please enter the username to change password: ').strip()
        if not username:
            print('✗ Username cannot be empty')
            return
        
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            if not user:
                print(f'✗ User {username} does not exist')
                return
        
        password = getpass('Please enter new password: ')
        password2 = getpass('Please confirm new password: ')
        
        if password != password2:
            print('✗ Passwords do not match')
            return
        
        if len(password) < 6:
            print('✗ Password must be at least 6 characters long')
            return
        
        with app.app_context():
            user.set_password(password)
            db.session.commit()
        
        print(f'✓ Password for user {username} changed successfully!')
    except KeyboardInterrupt:
        print('\n✗ Operation cancelled by user')
        sys.exit(0)
    except Exception as e:
        print(f'✗ Change failed: {str(e)}')
        sys.exit(1)


def main():
    try:
        parser = argparse.ArgumentParser(description='VM Control Hub CLI Manager')
        parser.add_argument('command', choices=['createsuperuser', 'changepassword'],
                            help='Available commands: createsuperuser, changepassword')
        
        args = parser.parse_args()
        
        if  args.command == 'createsuperuser':
            createsuperuser()
        elif args.command == 'changepassword':
            changepassword()
    except KeyboardInterrupt:
        print('\n✗ Operation cancelled by user')
        sys.exit(0)

if __name__ == '__main__':
    main()