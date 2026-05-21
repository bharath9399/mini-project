import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'study_partner_backend.settings')
django.setup()

from django.contrib.auth.models import User
from main.models import Profile, Subject, Task

def seed():
    print("Seeding subjects...")
    subjects = ["Mathematics", "Physics", "Computer Science", "History", "Literature"]
    for name in subjects:
        Subject.objects.get_or_create(name=name)
    
    print("Creating demo users...")
    users_data = [
        ("alex_pro", "Alex", "Johnson", "pro"),
        ("sarah_int", "Sarah", "Kennedy", "intermediate"),
        ("mike_int", "Mike", "Ross", "intermediate"),
        ("lily_beg", "Lily", "Evans", "beginner"),
    ]
    
    for username, first, last, level in users_data:
        user, created = User.objects.get_or_create(username=username, first_name=first, last_name=last)
        if created:
            user.set_password("password123")
            user.save()
            Profile.objects.get_or_create(user=user, level=level, role="student")
            print(f"Created user: {username}")

    print("Seed completed successfully.")

if __name__ == "__main__":
    seed()
