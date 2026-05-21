from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Profile, Subject, SubjectSelection, MatchRoom, ChatMessage, Task
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
import json

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if not remember:
                request.session.set_expiry(0) # Browser close session
            else:
                request.session.set_expiry(1209600) # 2 weeks
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'main/login.html')

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        level = request.POST.get('level')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name)
            Profile.objects.create(user=user, is_online=True)
            login(request, user)
            return redirect('dashboard')
    return render(request, 'main/signup.html')

@login_required
def dashboard_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    profile.is_online = True
    profile.save()
    
    if request.method == 'POST' and 'add_task' in request.POST:
        title = request.POST.get('task_title')
        if title:
            Task.objects.create(user=request.user, title=title)
            return redirect('dashboard')

    subjects = Subject.objects.all()
    tasks = Task.objects.filter(user=request.user)
    
    # Get all online users as potential peers for now
    peers = Profile.objects.filter(is_online=True).exclude(user=request.user).distinct()[:6]
    
    context = {
        'subjects': subjects,
        'tasks': tasks,
        'peers': peers,
        'profile': profile
    }
    return render(request, 'main/dashboard.html', context)

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def find_partner_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            subject_name = data.get('subject')
            
            # Extract the pure subject name if it's passed with level (e.g. 'Mathematics • Intermediate')
            if '•' in subject_name:
                parts = subject_name.split('•')
                subject_name = parts[0].strip()
                level = parts[1].strip().lower()
            else:
                level = data.get('level', 'beginner').lower()
            
            subject_obj, _ = Subject.objects.get_or_create(name=subject_name)
            
            # Update user's subject selection so they are registered as studying this subject
            SubjectSelection.objects.update_or_create(
                student=request.user.profile,
                subject=subject_obj,
                defaults={'level': level}
            )
            
            # 1. Check if the user is already part of an active MatchRoom for this subject
            existing_room = MatchRoom.objects.filter(
                is_active=True, subject=subject_obj
            ).filter(
                Q(student1=request.user) | Q(student2=request.user)
            ).first()
            
            if existing_room:
                partner_user = existing_room.student2 if existing_room.student1 == request.user else existing_room.student1
                print(f"[MATCHMAKING] {request.user.username} joined existing room {existing_room.id} with {partner_user.username}")
                return JsonResponse({'room_id': existing_room.id, 'partner': partner_user.username})
                
            # 2. If no room exists, find online users
            online_users = User.objects.filter(profile__is_online=True).exclude(id=request.user.id)
            
            # 3. Match Exact Subject and Level
            exact_matches = online_users.filter(
                profile__subject_selections__subject__name__icontains=subject_name,
                profile__subject_selections__level=level
            )
            
            partner = None
            if exact_matches.exists():
                import random
                partner = random.choice(list(exact_matches))
            else:
                # 4. Match Nearby Level (same subject, different level)
                nearby_matches = online_users.filter(
                    profile__subject_selections__subject__name__icontains=subject_name
                )
                if nearby_matches.exists():
                    import random
                    partner = random.choice(list(nearby_matches))
                else:
                    # 5. Fallback: Just match ANY online user (useful for local testing)
                    any_online = online_users.all()
                    if any_online.exists():
                        import random
                        partner = random.choice(list(any_online))
            
            # 6. If absolutely nobody is online, return an error
            if not partner:
                print(f"[MATCHMAKING] No partner found for {request.user.username}")
                return JsonResponse({'error': 'No study partner available right now'}, status=404)
                
            # 7. Check if THAT partner already has a room we should just join
            partner_room = MatchRoom.objects.filter(
                is_active=True, subject=subject_obj
            ).filter(
                Q(student1=partner) | Q(student2=partner)
            ).first()
            
            if partner_room:
                print(f"[MATCHMAKING] {request.user.username} is joining partner's existing room {partner_room.id}")
                # We can just update student2 if it was empty, but since we created it with student2=partner originally,
                # if A created Room(A, B), partner_room has student1=A, student2=B.
                # B is now searching, picks A. partner_room is found!
                # We simply return partner_room.id so B connects to it!
                return JsonResponse({'room_id': partner_room.id, 'partner': partner.username})
                
            room = MatchRoom.objects.create(
                student1=request.user,
                student2=partner,
                subject=subject_obj
            )
            print(f"[MATCHMAKING] {request.user.username} created new room {room.id} with {partner.username}")
            
            return JsonResponse({'room_id': room.id, 'partner': partner.username})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def upload_file_view(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        room_id = request.POST.get('room_id')
        
        try:
            room = MatchRoom.objects.get(id=room_id)
            # Create a placeholder message for the file
            msg = ChatMessage.objects.create(room=room, sender=request.user, text="[Shared a file]")
            from .models import SharedFile
            # Simple check for file type
            file_type = 'image' if file.content_type.startswith('image/') else 'pdf'
            
            shared = SharedFile.objects.create(message=msg, file=file, file_type=file_type)
            
            return JsonResponse({
                'success': True, 
                'file_url': shared.file.url, 
                'file_name': file.name,
                'file_type': file_type
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)
