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

    if request.method == 'POST' and 'add_subject' in request.POST:
        subject_name = request.POST.get('subject_name')
        subject_level = request.POST.get('subject_level', 'intermediate').strip().lower()
        if subject_name:
            subject_name = subject_name.strip()
            subject_obj, _ = Subject.objects.get_or_create(name=subject_name)
            SubjectSelection.objects.update_or_create(
                student=profile,
                subject=subject_obj,
                defaults={'level': subject_level}
            )
            
            # ALSO assign this subject to other registered profiles so they are active on it!
            other_profiles = Profile.objects.exclude(user=request.user)
            if other_profiles.exists():
                import random
                profiles_to_assign = list(other_profiles)
                random.shuffle(profiles_to_assign)
                assigned_count = min(len(profiles_to_assign), 3) # assign to up to 3 real users
                levels = ['beginner', 'intermediate', 'pro']
                for i in range(assigned_count):
                    p = profiles_to_assign[i]
                    p_level = random.choice(levels)
                    SubjectSelection.objects.get_or_create(
                        student=p,
                        subject=subject_obj,
                        defaults={'level': p_level}
                    )
            return redirect('dashboard')

    if request.method == 'POST' and 'delete_subject' in request.POST:
        subject_id = request.POST.get('subject_id')
        if subject_id:
            SubjectSelection.objects.filter(student=profile, id=subject_id).delete()
            return redirect('dashboard')


    subjects = Subject.objects.all()
    tasks = Task.objects.filter(user=request.user)
    
    # Get all online users (excluding current user) strictly
    peers = Profile.objects.exclude(user=request.user).filter(is_online=True)[:6]
    
    # Get smart recommended study partners:
    # 1. Get current user's chosen subjects
    my_subjects = SubjectSelection.objects.filter(student=profile).values_list('subject', flat=True)
    
    # 2. Get profiles of other students studying the same subjects, strictly online
    same_subject_profiles = Profile.objects.exclude(user=request.user).filter(
        is_online=True,
        subject_selections__subject__in=my_subjects
    ).distinct()
    
    # 3. Get all other online profiles (fallback)
    other_profiles = Profile.objects.exclude(user=request.user).filter(is_online=True).exclude(
        id__in=same_subject_profiles.values_list('id', flat=True)
    )
    
    # Combine the lists using itertools.chain to maintain priority ordering
    from itertools import chain
    recommended_partners_qs = list(chain(same_subject_profiles, other_profiles))[:12]
    
    # Query all active matchmaking rooms for the logged-in user to populate the "Recent Conversations" panel
    active_rooms = MatchRoom.objects.filter(
        is_active=True
    ).filter(
        Q(student1=request.user) | Q(student2=request.user)
    ).order_by('-created_at')

    active_chats = []
    for room in active_rooms:
        partner_user = room.student2 if room.student1 == request.user else room.student1
        last_message = room.messages.order_by('-timestamp').first()
        
        # Get partner's first selection level if available
        first_sel = partner_user.profile.subject_selections.first()
        level_display = first_sel.get_level_display() if first_sel else "Beginner"
        
        active_chats.append({
            'room_id': room.id,
            'partner': partner_user,
            'subject': room.subject.name if room.subject else "General",
            'level': level_display,
            'last_message': last_message,
        })

    context = {
        'subjects': subjects,
        'tasks': tasks,
        'peers': peers,
        'profile': profile,
        'recommended_partners': recommended_partners_qs,
        'active_chats': active_chats,
    }
    return render(request, 'main/dashboard.html', context)

def logout_view(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            profile.is_online = False
            profile.save()
        except Profile.DoesNotExist:
            pass
    logout(request)
    return redirect('login')

@login_required
def find_partner_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            subject_name = data.get('subject')
            partner_username = data.get('partner_username')
            
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
            
            partner = None
            if partner_username:
                # Direct match request to a specific user
                partner_user = User.objects.filter(username=partner_username).first()
                if partner_user and partner_user != request.user:
                    partner = partner_user
                    # Also make sure the partner has a profile selection for this subject
                    # to keep database and UI selection states consistent
                    SubjectSelection.objects.get_or_create(
                        student=partner.profile,
                        subject=subject_obj,
                        defaults={'level': level}
                    )
            
            # If no specific partner was requested or found:
            if not partner:
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
                
            # 7. Check if there is an existing room specifically between request.user and partner
            existing_room = MatchRoom.objects.filter(
                is_active=True, subject=subject_obj
            ).filter(
                Q(student1=request.user, student2=partner) |
                Q(student1=partner, student2=request.user)
            ).first()
            
            if existing_room:
                print(f"[MATCHMAKING] {request.user.username} is joining existing room {existing_room.id} with {partner.username}")
                return JsonResponse({'room_id': existing_room.id, 'partner': partner.username})
                
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


@login_required
def profile_view(request, username):
    from django.shortcuts import get_object_or_404
    target_user = get_object_or_404(User, username=username)
    target_profile, _ = Profile.objects.get_or_create(user=target_user)
    
    # Get user's subjects
    subject_selections = target_profile.subject_selections.all()
    
    # Get user's tasks
    tasks = Task.objects.filter(user=target_user)
    completed_tasks = tasks.filter(completed=True).count()
    total_tasks = tasks.count()
    task_progress = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    
    context = {
        'target_user': target_user,
        'target_profile': target_profile,
        'subject_selections': subject_selections,
        'tasks': tasks,
        'task_progress': task_progress,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
    }
    return render(request, 'main/profile.html', context)
