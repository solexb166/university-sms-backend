from django.contrib.auth.models import AbstractUser
from django.db import models
import random
import string

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('registry', 'Registry Staff'),
        ('finance', 'Finance Staff'),
        ('lecturer', 'Lecturer'),
        ('exam_office', 'Exam Office'),
        ('student', 'Student'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(default=False)
    otp = models.CharField(max_length=20, blank=True)

    def generate_otp(self):
        otp = ''.join(random.choices(string.digits, k=6))
        self.otp = otp
        self.must_change_password = True
        self.save()
        return otp

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
