from django.db import models
from accounts.models import CustomUser

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    head_of_dept = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name

class Student(models.Model):
    STUDENT_TYPE_CHOICES = [
        ('local', 'Local'),
        ('international', 'International'),
    ]
    MODE_CHOICES = [
        ('day', 'Day'),
        ('distance', 'Distance Learning'),
        ('weekend', 'Weekend'),
    ]
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    program = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    semester_in_program = models.IntegerField(choices=SEMESTER_CHOICES, default=1)
    student_type = models.CharField(max_length=20, choices=STUDENT_TYPE_CHOICES, default='local')
    mode_of_study = models.CharField(max_length=20, choices=MODE_CHOICES, default='day')
    admission_date = models.DateField(auto_now_add=True)
    tuition_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=5, default='UGX')
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"

    @property
    def year_of_study(self):
        return (self.semester_in_program + 1) // 2

    @property
    def total_paid(self):
        from django.db.models import Sum
        return float(self.payments.aggregate(total=Sum('amount_paid'))['total'] or 0)

    @property
    def payment_percentage(self):
        if float(self.tuition_amount) == 0:
            return 0
        return (self.total_paid / float(self.tuition_amount)) * 100

    @property
    def is_enrolled(self):
        return self.payment_percentage >= 30

    @property
    def cat1_cleared(self):
        return self.payment_percentage >= 50

    @property
    def cat2_cleared(self):
        return self.payment_percentage >= 75

    @property
    def exam_cleared(self):
        return self.payment_percentage >= 100

class Lecturer(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='lecturer_profile')
    lecturer_id = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    specialization = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.lecturer_id} - {self.full_name}"
