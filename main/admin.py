from django.contrib import admin
from .models import Profile, Subject, SubjectSelection, MatchRoom, ChatMessage, SharedFile, FriendRequest, Task

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(SubjectSelection)
class SubjectSelectionAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'level')

@admin.register(MatchRoom)
class MatchRoomAdmin(admin.ModelAdmin):
    list_display = ('student1', 'student2', 'subject', 'is_active', 'created_at')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('room', 'sender', 'timestamp')

@admin.register(SharedFile)
class SharedFileAdmin(admin.ModelAdmin):
    list_display = ('message', 'file_type')

@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'status', 'created_at')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'completed')
    list_filter = ('completed',)
