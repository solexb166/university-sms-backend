from django.db import models
from students.models import Student

class PaymentSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    BANK_CHOICES = [
        ('stanbic', 'Stanbic Bank'),
        ('dtb', 'Diamond Trust Bank'),
        ('uba', 'United Bank for Africa'),
        ('dfcu', 'DFCU Bank'),
        ('other', 'Other'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payment_submissions')
    bank_name = models.CharField(max_length=20, choices=BANK_CHOICES, default='stanbic')
    bank_reference = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default='UGX')
    semester_in_program = models.IntegerField(default=1)
    academic_year = models.CharField(max_length=10, default='2025/2026')
    date_submitted = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    verified_by = models.CharField(max_length=100, blank=True)
    date_verified = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student} - {self.bank_reference} ({self.status})"

class FeePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('bank', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    submission = models.OneToOneField(PaymentSubmission, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='bank')
    receipt_number = models.CharField(max_length=50, unique=True)
    semester_in_program = models.IntegerField(default=1)
    academic_year = models.CharField(max_length=10, default='2025/2026')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recorded_by = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._auto_enroll()

    def _auto_enroll(self):
        from django.utils import timezone
        from courses.models import ModuleSelection, Enrollment
        student = self.student
        if student.payment_percentage >= 30:
            pending = ModuleSelection.objects.filter(
                student=student, status='pending',
                academic_year=self.academic_year
            )
            for sel in pending:
                Enrollment.objects.get_or_create(
                    student=student, course=sel.course,
                    academic_year=self.academic_year,
                    defaults={
                        'semester_in_program': sel.semester_in_program,
                        'status': 'enrolled'
                    }
                )
                sel.status = 'enrolled'
                sel.date_enrolled = timezone.now()
                sel.save()

    def __str__(self):
        return f"{self.student} - {self.receipt_number}"
