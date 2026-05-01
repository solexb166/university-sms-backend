from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Avg
from django.utils import timezone
from functools import wraps
from .models import Student, Lecturer, Department
from accounts.models import CustomUser
from courses.models import Enrollment, Course, ModuleSelection
from fees.models import FeePayment, PaymentSubmission
from results.models import Result

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
@role_required('admin', 'registry')
def students_list(request):
    search = request.GET.get('search', '')
    students = Student.objects.select_related('department', 'user').filter(is_active=True)
    if search:
        students = students.filter(full_name__icontains=search) | students.filter(student_id__icontains=search)
    return render(request, 'students/list.html', {'students': students, 'search': search})

@login_required
@role_required('admin', 'registry')
def student_register(request):
    departments = Department.objects.all()
    otp_info = None
    if request.method == 'POST':
        username = request.POST.get('username')
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'students/register.html', {'departments': departments})
        user = CustomUser.objects.create_user(
            username=username,
            password='temp_unused_password_123',
            email=request.POST.get('email', ''),
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            role='student'
        )
        otp = user.generate_otp()
        dept = get_object_or_404(Department, id=request.POST.get('department'))
        student = Student.objects.create(
            user=user,
            student_id=request.POST.get('student_id'),
            full_name=request.POST.get('full_name'),
            program=request.POST.get('program'),
            department=dept,
            semester_in_program=request.POST.get('semester_in_program', 1),
            gender=request.POST.get('gender', ''),
            phone=request.POST.get('phone', ''),
            student_type=request.POST.get('student_type', 'local'),
            tuition_amount=request.POST.get('tuition_amount', 0),
            currency=request.POST.get('currency', 'UGX'),
        )
        otp_info = {
            'student_name': student.full_name,
            'username': username,
            'otp': otp,
            'student_id': student.student_id,
        }
        return render(request, 'students/register.html', {
            'departments': departments,
            'otp_info': otp_info,
        })
    return render(request, 'students/register.html', {'departments': departments})

@login_required
@role_required('admin', 'registry')
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    enrollments = Enrollment.objects.filter(student=student).select_related('course')
    selections = ModuleSelection.objects.filter(student=student).select_related('course')
    results = Result.objects.filter(student=student).select_related('course')
    payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
    total_paid = payments.aggregate(t=Sum('amount_paid'))['t'] or 0
    avg_marks = results.aggregate(avg=Avg('marks'))['avg']
    return render(request, 'students/detail.html', {
        'student': student,
        'enrollments': enrollments,
        'selections': selections,
        'results': results,
        'payments': payments,
        'total_paid': total_paid,
        'avg_marks': avg_marks,
    })

@login_required
@role_required('admin', 'registry')
def departments_list(request):
    departments = Department.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        if Department.objects.filter(code=code).exists():
            messages.error(request, 'Department code already exists.')
        else:
            Department.objects.create(
                name=name, code=code,
                head_of_dept=request.POST.get('head_of_dept', ''),
            )
            messages.success(request, f'Department {name} created successfully.')
        return redirect('departments_list')
    return render(request, 'students/departments.html', {'departments': departments})

# ---- STUDENT PORTAL ----

@login_required
def my_dashboard(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        enrollments = Enrollment.objects.filter(student=student, status='enrolled').select_related('course')
        results = Result.objects.filter(student=student)
        payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
        avg_marks = results.aggregate(avg=Avg('marks'))['avg']
        latest = payments.first()
        balance = float(latest.balance) if latest else float(student.tuition_amount)
        pending_submissions = PaymentSubmission.objects.filter(student=student, status='pending').count()
    except:
        student = enrollments = results = None
        avg_marks = balance = pending_submissions = 0
        payments = []
    return render(request, 'students/my_dashboard.html', {
        'student': student,
        'enrollments': enrollments,
        'results': results,
        'avg_marks': avg_marks,
        'balance': balance,
        'pending_submissions': pending_submissions,
    })

@login_required
def upload_photo(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        if request.method == 'POST' and request.FILES.get('photo'):
            student.photo = request.FILES['photo']
            student.save()
            messages.success(request, 'Profile photo updated successfully.')
    except:
        messages.error(request, 'Student profile not found.')
    return redirect('my_dashboard')

@login_required
def select_modules(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
    except:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

    academic_year = '2025/2026'
    sem = student.semester_in_program

    # Get courses for this semester
    available_courses = Course.objects.filter(
        semester_in_program=sem,
        is_active=True,
    ).select_related('department', 'lecturer').order_by('course_code')

    # Already selected or enrolled
    selected_ids = list(ModuleSelection.objects.filter(
        student=student, academic_year=academic_year,
        semester_in_program=sem
    ).values_list('course_id', flat=True))

    enrolled_ids = list(Enrollment.objects.filter(
        student=student, academic_year=academic_year,
        semester_in_program=sem
    ).values_list('course_id', flat=True))

    if request.method == 'POST':
        course_ids = request.POST.getlist('courses')
        if not course_ids:
            messages.error(request, 'Please select at least one module.')
            return render(request, 'students/select_modules.html', {
                'available_courses': available_courses,
                'selected_ids': selected_ids,
                'enrolled_ids': enrolled_ids,
                'student': student,
                'sem': sem,
            })
        # Remove old pending selections
        ModuleSelection.objects.filter(
            student=student, academic_year=academic_year,
            semester_in_program=sem, status='pending'
        ).delete()
        # Create new selections
        for cid in course_ids:
            try:
                course = Course.objects.get(id=cid)
                if int(cid) not in enrolled_ids:
                    ModuleSelection.objects.get_or_create(
                        student=student, course=course,
                        academic_year=academic_year,
                        defaults={
                            'semester_in_program': sem,
                            'status': 'pending'
                        }
                    )
            except Course.DoesNotExist:
                pass
        messages.success(request, f'{len(course_ids)} module(s) selected successfully. Pay 30% of your tuition to confirm enrollment.')
        return redirect('my_courses')

    return render(request, 'students/select_modules.html', {
        'available_courses': available_courses,
        'selected_ids': selected_ids,
        'enrolled_ids': enrolled_ids,
        'student': student,
        'sem': sem,
    })

@login_required
def my_courses(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        enrollments = Enrollment.objects.filter(student=student, status='enrolled').select_related('course')
        selections = ModuleSelection.objects.filter(student=student, status='pending').select_related('course')
    except:
        student = enrollments = selections = None
    return render(request, 'students/my_courses.html', {
        'enrollments': enrollments,
        'selections': selections,
        'student': student,
    })

@login_required
def my_results(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        results = Result.objects.filter(student=student).select_related('course')
        avg = results.aggregate(avg=Avg('marks'))['avg']
    except:
        results = []
        avg = None
    return render(request, 'students/my_results.html', {'results': results, 'average': avg})

@login_required
def my_fees(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
        submissions = PaymentSubmission.objects.filter(student=student).order_by('-date_submitted')
        total_paid = student.total_paid
        latest = payments.first()
        balance = float(latest.balance) if latest else float(student.tuition_amount)
        pct = student.payment_percentage
    except:
        student = None
        payments = submissions = []
        total_paid = balance = pct = 0
    return render(request, 'students/my_fees.html', {
        'student': student,
        'payments': payments,
        'submissions': submissions,
        'total_paid': total_paid,
        'balance': balance,
        'payment_percentage': pct,
    })

@login_required
def submit_payment(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
    except:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')
    if request.method == 'POST':
        PaymentSubmission.objects.create(
            student=student,
            bank_name=request.POST.get('bank_name', 'other'),
            bank_reference=request.POST.get('bank_reference'),
            amount_paid=request.POST.get('amount_paid'),
            currency=student.currency,
            semester_in_program=student.semester_in_program,
            academic_year='2025/2026',
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Payment submitted. Finance will verify it shortly.')
        return redirect('my_fees')
    return render(request, 'students/submit_payment.html', {'student': student})

@login_required
def proof_of_registration(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        if not student.is_enrolled:
            messages.error(request, 'You need to pay at least 30% of your tuition to print proof of registration.')
            return redirect('my_fees')
        enrollments = Enrollment.objects.filter(student=student, status='enrolled').select_related('course')
        latest = FeePayment.objects.filter(student=student).order_by('-payment_date').first()
        balance = float(latest.balance) if latest else float(student.tuition_amount)
    except:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')
    return render(request, 'students/proof_of_registration.html', {
        'student': student,
        'enrollments': enrollments,
        'balance': balance,
        'today': timezone.now(),
    })

@login_required
def my_exam_docket(request):
    if request.user.role != 'student':
        return redirect('dashboard')
    try:
        student = request.user.student_profile
        from courses.models import ExamDocket
        docket = ExamDocket.objects.filter(student=student, academic_year='2025/2026').first()
        if not docket:
            messages.error(request, 'Your exam docket has not been generated yet.')
            return redirect('my_courses')
        if not student.exam_cleared:
            messages.error(request, 'You need to pay 100% of tuition to access your exam docket.')
            return redirect('my_fees')
        enrollments = Enrollment.objects.filter(student=student, status='enrolled').select_related('course')
    except:
        messages.error(request, 'Exam docket not found.')
        return redirect('dashboard')
    return render(request, 'students/exam_docket.html', {
        'student': student,
        'docket': docket,
        'enrollments': enrollments,
        'today': timezone.now(),
    })
