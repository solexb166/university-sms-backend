from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from functools import wraps
from .models import FeePayment, PaymentSubmission
from students.models import Student

def role_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission.')
                return redirect('dashboard')
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

@login_required
@role_required('admin', 'finance')
def fees_list(request):
    students = Student.objects.filter(is_active=True).select_related('department')
    filter_status = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    student_data = []
    for student in students:
        if search and search.lower() not in student.full_name.lower() and search.lower() not in student.student_id.lower():
            continue
        payments = FeePayment.objects.filter(student=student)
        total_paid = payments.aggregate(t=Sum('amount_paid'))['t'] or 0
        latest = payments.order_by('-payment_date').first()
        balance = float(latest.balance) if latest else float(student.tuition_amount)
        pct = student.payment_percentage

        if pct >= 100:
            status = 'Exam Cleared'
        elif pct >= 75:
            status = 'CAT 2 Cleared'
        elif pct >= 50:
            status = 'CAT 1 Cleared'
        elif pct >= 30:
            status = 'Enrolled'
        else:
            status = 'Not Enrolled'

        if filter_status != 'all' and status != filter_status:
            continue
        student_data.append({
            'student': student,
            'total_paid': total_paid,
            'balance': balance,
            'payment_count': payments.count(),
            'status': status,
            'percentage': round(pct, 1),
        })

    # Pending submissions count for badge
    pending_count = PaymentSubmission.objects.filter(status='pending').count()
    return render(request, 'fees/list.html', {
        'student_data': student_data,
        'filter_status': filter_status,
        'search': search,
        'pending_count': pending_count,
    })

@login_required
@role_required('admin', 'finance')
def pending_payments(request):
    submissions = PaymentSubmission.objects.filter(status='pending').select_related('student').order_by('-date_submitted')
    return render(request, 'fees/pending_payments.html', {'submissions': submissions})

@login_required
@role_required('admin', 'finance')
def approve_payment(request, pk):
    submission = get_object_or_404(PaymentSubmission, pk=pk)
    if request.method == 'POST':
        import uuid
        receipt = f"RCP-{uuid.uuid4().hex[:8].upper()}"
        student = submission.student
        total_paid_so_far = student.total_paid + float(submission.amount_paid)
        balance = max(0, float(student.tuition_amount) - total_paid_so_far)

        FeePayment.objects.create(
            student=student,
            submission=submission,
            amount_paid=submission.amount_paid,
            payment_method='bank',
            receipt_number=receipt,
            semester_in_program=submission.semester_in_program,
            academic_year=submission.academic_year,
            balance=balance,
            recorded_by=request.user.get_full_name() or request.user.username,
        )
        submission.status = 'approved'
        submission.verified_by = request.user.get_full_name() or request.user.username
        submission.date_verified = timezone.now()
        submission.save()

        pct = student.payment_percentage
        if pct >= 30:
            messages.success(request, f'Payment approved. {student.full_name} is now enrolled ({round(pct, 1)}% paid). Modules automatically enrolled.')
        else:
            messages.success(request, f'Payment approved. Student has paid {round(pct, 1)}% — needs 30% to enroll.')
        return redirect('pending_payments')
    return render(request, 'fees/approve_payment.html', {'submission': submission})

@login_required
@role_required('admin', 'finance')
def reject_payment(request, pk):
    submission = get_object_or_404(PaymentSubmission, pk=pk)
    if request.method == 'POST':
        submission.status = 'rejected'
        submission.verified_by = request.user.get_full_name() or request.user.username
        submission.date_verified = timezone.now()
        submission.rejection_reason = request.POST.get('reason', '')
        submission.save()
        messages.warning(request, f'Payment rejected for {submission.student.full_name}.')
        return redirect('pending_payments')
    return render(request, 'fees/approve_payment.html', {'submission': submission, 'rejecting': True})
