from django.db import models
from students.models import Student
from courses.models import Course

class Result(models.Model):
    GRADE_CHOICES = [
        ('A', 'A - Excellent (80-100)'),
        ('B', 'B - Good (70-79)'),
        ('C', 'C - Average (60-69)'),
        ('D', 'D - Pass (50-59)'),
        ('F', 'F - Fail (0-49)'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='results')
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True)
    academic_year = models.CharField(max_length=10, default='2025/2026')
    remarks = models.TextField(blank=True)
    recorded_by = models.CharField(max_length=100, blank=True)
    date_recorded = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_year')

    def save(self, *args, **kwargs):
        m = float(self.marks)
        if m >= 80: self.grade = 'A'
        elif m >= 70: self.grade = 'B'
        elif m >= 60: self.grade = 'C'
        elif m >= 50: self.grade = 'D'
        else: self.grade = 'F'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.course} - {self.grade}"
