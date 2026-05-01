from django.db import models
from students.models import Student, Department, Lecturer

SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]

class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    lecturer = models.ForeignKey(Lecturer, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    credits = models.IntegerField(default=3)
    semester_in_program = models.IntegerField(choices=SEMESTER_CHOICES, default=1)
    max_enrollment = models.IntegerField(default=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.course_code} - {self.name}"

    @property
    def year_of_study(self):
        return (self.semester_in_program + 1) // 2

    @property
    def enrolled_count(self):
        return self.enrollments.filter(status='enrolled').count()

class ModuleSelection(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('enrolled', 'Enrolled'),
        ('dropped', 'Dropped'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='module_selections')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='selections')
    academic_year = models.CharField(max_length=10, default='2025/2026')
    semester_in_program = models.IntegerField(choices=SEMESTER_CHOICES, default=1)
    mode_of_study = models.CharField(max_length=20, default='day')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    date_selected = models.DateTimeField(auto_now_add=True)
    date_enrolled = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_year')

    def __str__(self):
        return f"{self.student} - {self.course} ({self.status})"

class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('dropped', 'Dropped'),
        ('completed', 'Completed'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.CharField(max_length=10, default='2025/2026')
    semester_in_program = models.IntegerField(choices=SEMESTER_CHOICES, default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enrolled')
    date_enrolled = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_year')

    def __str__(self):
        return f"{self.student} - {self.course}"

class ExamDocket(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_dockets')
    academic_year = models.CharField(max_length=10, default='2025/2026')
    semester_in_program = models.IntegerField(choices=SEMESTER_CHOICES, default=1)
    date_generated = models.DateTimeField(auto_now_add=True)
    generated_by = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, default='generated')

    def __str__(self):
        return f"Docket - {self.student} - Sem {self.semester_in_program}"
