from django.test import TestCase, Client
from django.contrib.auth.models import User
from main.models import Profile, Subject, SubjectSelection, MatchRoom
import json

class MatchmakingTestCase(TestCase):
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')
        self.user3 = User.objects.create_user(username='user3', password='password123')
        
        # Create profiles and set them online
        self.profile1 = Profile.objects.create(user=self.user1, is_online=True)
        self.profile2 = Profile.objects.create(user=self.user2, is_online=True)
        self.profile3 = Profile.objects.create(user=self.user3, is_online=True)
        
        # Create subjects
        self.subject_math = Subject.objects.create(name='Mathematics')
        
        # Set up subject selections - all beginners to test exact matching
        SubjectSelection.objects.create(student=self.profile1, subject=self.subject_math, level='beginner')
        SubjectSelection.objects.create(student=self.profile2, subject=self.subject_math, level='beginner')
        SubjectSelection.objects.create(student=self.profile3, subject=self.subject_math, level='beginner')

    def test_matchmaking_isolation_for_three_users(self):
        client1 = Client()
        client1.login(username='user1', password='password123')
        
        client2 = Client()
        client2.login(username='user2', password='password123')
        
        client3 = Client()
        client3.login(username='user3', password='password123')

        # 1. User 1 requests a match for Mathematics
        response1 = client1.post(
            '/api/match/',
            data=json.dumps({'subject': 'Mathematics', 'level': 'beginner'}),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()
        self.assertIn('room_id', data1)
        # matched with user2 or user3 (since both are beginners and online).
        # Let's check who they matched with.
        partner1 = data1['partner']
        self.assertIn(partner1, ['user2', 'user3'])
        room1_id = data1['room_id']

        # 2. The matched partner requests a match to join the room
        partner_client = client2 if partner1 == 'user2' else client3
        partner_username = 'user2' if partner1 == 'user2' else 'user3'
        
        response2 = partner_client.post(
            '/api/match/',
            data=json.dumps({'subject': 'Mathematics', 'level': 'beginner'}),
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2['room_id'], room1_id)
        self.assertEqual(data2['partner'], 'user1')

        # Verify database has exactly 1 room
        self.assertEqual(MatchRoom.objects.count(), 1)

        # 3. The third user (who is not in the room yet) requests a match.
        third_client = client3 if partner1 == 'user2' else client2
        third_username = 'user3' if partner1 == 'user2' else 'user2'

        # Previously, Step 7 would make the third user join the existing room because
        # their partner (e.g., user1 or user2) already had an active room.
        # With our fix, it should create a brand new room.
        response3 = third_client.post(
            '/api/match/',
            data=json.dumps({'subject': 'Mathematics', 'level': 'beginner'}),
            content_type='application/json'
        )
        self.assertEqual(response3.status_code, 200)
        data3 = response3.json()
        self.assertIn('room_id', data3)
        room3_id = data3['room_id']

        # Verify that the third user's room is DIFFERENT from the first room
        self.assertNotEqual(room3_id, room1_id)
        
        # Verify that there are now exactly 2 rooms in the database
        self.assertEqual(MatchRoom.objects.count(), 2)

        # Verify that room 3 is between the third user and one of the other users
        new_room = MatchRoom.objects.get(id=room3_id)
        participants = {new_room.student1.username, new_room.student2.username}
        self.assertIn(third_username, participants)
