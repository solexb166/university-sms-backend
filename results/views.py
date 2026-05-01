from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg
from functools import wraps
from .models import Result
from students.models import Student, Lecturer
from courses.models import Course, Enrollment

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
@role_required('admin', 'lecturer')
def results_list(request):
    search = request.GET.get('search', '')
    selected_course = request.GET.get('course', '')

    # If lecturer — only show their courses
    if request.user.role == 'lecturer':
        try:
            lecturer = request.user.lecturer_profile
            courses = Course.objects.filter(lecturer=lecturer, is_active=True)
        except:
            courses = Course.objects.none()
    else:
        courses = Course.objects.filter(is_active=True)

    results = Result.objects.select_related('student', 'course').filter(
        course__in=courses
    )
    if search:
        results = results.filter(student__full_name__icontains=search) | results.filter(student__student_id__icontains=search)
    if selected_course:
        results = results.filter(course_id=selected_course)

    students = Student.objects.filter(is_active=True)
    return render(request, 'results/list.html', {
        'results': results,
        'courses': courses,
        'students': students,
        'search': search,
        'selected_course': selected_course,
    })

@login_required
@role_required('admin', 'lecturer')
def course_students(request, course_id):
    """Lecturer sees all students enrolled in a specific course"""
    course = get_object_or_404(Course, id=course_id)
    # Check lecturer owns this course
    if request.user.role == 'lecturer':
        try:
            lecturer = request.user.lecturer_profile
            if course.lecturer != lecturer:
                messages.error(request, 'You do not have access to this course.')
                return redirect('results_list')
        except:
            messages.error(request, 'Lecturer profile not found.')
            return redirect('dashboard')

    enrollments = Enrollment.objects.filter(
        course=course, status='enrolled'
    ).select_related('student')
    results = Result.objects.filter(course=course).select_related('student')
    results_dict = {r.student_id: r for r in results}

    return render(request, 'results/course_students.html', {
        'course': course,
        'enrollments': enrollments,
        'results_dict': results_dict,
    })

@login_required
@role_required('admin', 'lecturer')
def record_result(request):
    if request.method == 'POST':
        student = get_object_or_404(Student, id=request.POST.get('student'))
        course = get_object_or_404(Course, id=request.POST.get('course'))
        marks = float(request.POST.get('marks', 0))
        Result.objects.update_or_create(
            student=student, course=course, academic_year='2025/2026',
            defaults={
                'marks': marks,
                'remarks': request.POST.get('remarks', ''),
                'recorded_by': request.user.get_full_name() or request.user.username,
            }
        )
        messages.success(request, f'Result recorded for {student.full_name}.')
        # Redirect back to course students if came from there
        next_url = request.POST.get('next', 'results_list')
        return redirect(next_url)
    students = Student.objects.filter(is_active=True)
    if request.user.role == 'lecturer':
        try:
            lecturer = request.user.lecturer_profile
            courses = Course.objects.filter(lecturer=lecturer, is_active=True)
        except:
            courses = Course.objects.none()
    else:
        courses = Course.objects.filter(is_active=True)
    return render(request, 'results/record.html', {'students': students, 'courses': courses})
