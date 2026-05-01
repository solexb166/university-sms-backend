from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from functools import wraps
from .models import Course, Enrollment, ModuleSelection, ExamDocket
from students.models import Student, Department, Lecturer

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
@role_required('admin', 'registry', 'lecturer')
def courses_list(request):
    if request.user.role == 'lecturer':
        try:
            lecturer = request.user.lecturer_profile
            courses = Course.objects.filter(lecturer=lecturer, is_active=True).select_related('department', 'lecturer')
        except:
            courses = Course.objects.none()
    else:
        courses = Course.objects.select_related('department', 'lecturer').filter(is_active=True).order_by('semester_in_program', 'course_code')
    return render(request, 'courses/list.html', {'courses': courses})

@login_required
@role_required('admin', 'registry')
def course_create(request):
    departments = Department.objects.all()
    lecturers = Lecturer.objects.all()
    if request.method == 'POST':
        dept = get_object_or_404(Department, id=request.POST.get('department'))
        lecturer_id = request.POST.get('lecturer')
        lecturer = Lecturer.objects.filter(id=lecturer_id).first() if lecturer_id else None
        Course.objects.create(
            course_code=request.POST.get('course_code'),
            name=request.POST.get('name'),
            department=dept,
            lecturer=lecturer,
            credits=request.POST.get('credits', 3),
            semester_in_program=request.POST.get('semester_in_program', 1),
            max_enrollment=request.POST.get('max_enrollment', 50),
        )
        messages.success(request, 'Course created successfully.')
        return redirect('courses_list')
    return render(request, 'courses/create.html', {'departments': departments, 'lecturers': lecturers})

@login_required
@role_required('admin', 'registry')
def enrollments_list(request):
    enrollments = Enrollment.objects.select_related('student', 'course').all().order_by('-date_enrolled')
    students = Student.objects.filter(is_active=True)
    courses = Course.objects.filter(is_active=True)
    return render(request, 'courses/enrollments.html', {
        'enrollments': enrollments,
        'students': students,
        'courses': courses,
    })

@login_required
@role_required('admin', 'registry')
def enroll_student(request):
    if request.method == 'POST':
        student = get_object_or_404(Student, id=request.POST.get('student'))
        course = get_object_or_404(Course, id=request.POST.get('course'))
        _, created = Enrollment.objects.get_or_create(
            student=student, course=course, academic_year='2025/2026',
            defaults={'semester_in_program': course.semester_in_program, 'status': 'enrolled'}
        )
        if created:
            messages.success(request, f'{student.full_name} enrolled in {course.name}.')
        else:
            messages.warning(request, 'Student is already enrolled in this course.')
        return redirect('enrollments_list')
    return redirect('enrollments_list')

@login_required
@role_required('admin', 'exam_office')
def exam_office_dashboard(request):
    all_students = Student.objects.filter(is_active=True)
    cleared = [s for s in all_students if s.exam_cleared]
    not_cleared = [s for s in all_students if not s.exam_cleared]
    dockets = ExamDocket.objects.filter(academic_year='2025/2026').count()
    return render(request, 'exam_office/dashboard.html', {
        'cleared_count': len(cleared),
        'not_cleared_count': len(not_cleared),
        'dockets_generated': dockets,
        'total_students': all_students.count(),
    })

@login_required
@role_required('admin', 'exam_office')
def generate_dockets(request):
    if request.method == 'POST':
        academic_year = '2025/2026'
        generated = 0
        for student in Student.objects.filter(is_active=True):
            if student.exam_cleared:
                _, created = ExamDocket.objects.get_or_create(
                    student=student, academic_year=academic_year,
                    defaults={
                        'semester_in_program': student.semester_in_program,
                        'generated_by': request.user.get_full_name() or request.user.username,
                    }
                )
                if created:
                    generated += 1
        messages.success(request, f'{generated} exam docket(s) generated.')
        return redirect('exam_office_dashboard')
    return redirect('exam_office_dashboard')

@login_required
@role_required('admin', 'exam_office')
def clearance_list(request):
    clearance_type = request.GET.get('type', 'enrollment')
    thresholds = {'enrollment': 30, 'cat1': 50, 'cat2': 75, 'exam': 100}
    labels = {
        'enrollment': 'Enrollment Clearance (30%)',
        'cat1': 'CAT 1 Clearance (50%)',
        'cat2': 'CAT 2 Clearance (75%)',
        'exam': 'Final Exam Clearance (100%)',
    }
    threshold = thresholds.get(clearance_type, 30)
    label = labels.get(clearance_type, 'Enrollment')
    cleared = []
    not_cleared = []
    for student in Student.objects.filter(is_active=True):
        pct = student.payment_percentage
        if pct >= threshold:
            cleared.append({'student': student, 'percentage': round(pct, 1)})
        else:
            shortfall = (threshold / 100 * float(student.tuition_amount)) - student.total_paid
            not_cleared.append({
                'student': student,
                'percentage': round(pct, 1),
                'shortfall': max(0, shortfall),
            })
    return render(request, 'exam_office/clearance_list.html', {
        'cleared': cleared,
        'not_cleared': not_cleared,
        'clearance_type': clearance_type,
        'label': label,
        'threshold': threshold,
    })

@login_required
@role_required('admin', 'lecturer')
def course_students(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.user.role == 'lecturer':
        try:
            lecturer = request.user.lecturer_profile
            if course.lecturer != lecturer:
                messages.error(request, 'Access denied.')
                return redirect('results_list')
        except:
            return redirect('dashboard')
    enrollments = Enrollment.objects.filter(course=course, status='enrolled').select_related('student')
    from results.models import Result
    results = {r.student_id: r for r in Result.objects.filter(course=course)}
    return render(request, 'results/course_students.html', {
        'course': course,
        'enrollments': enrollments,
        'results_dict': results,
    })
