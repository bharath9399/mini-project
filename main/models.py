from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    LEVEL_CHOICES = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('pro', 'Pro'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_online = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class Subject(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class SubjectSelection(models.Model):
    student = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='subject_selections')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    level = models.CharField(max_length=20, choices=Profile.LEVEL_CHOICES, default='beginner')

    def __str__(self):
        return f"{self.student.user.username} - {self.subject.name} ({self.level})"

class MatchRoom(models.Model):
    student1 = models.ForeignKey(User, related_name='rooms_as_student1', on_delete=models.CASCADE)
    student2 = models.ForeignKey(User, related_name='rooms_as_student2', on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Room: {self.student1.username} & {self.student2.username}"

class ChatMessage(models.Model):
    room = models.ForeignKey(MatchRoom, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.text[:20]}"

class SharedFile(models.Model):
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE, related_name='shared_file')
    file = models.FileField(upload_to='chat_files/')
    file_type = models.CharField(max_length=50) # 'pdf', 'image', etc.

class FriendRequest(models.Model):
    sender = models.ForeignKey(User, related_name='sent_requests', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=(('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')), default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
