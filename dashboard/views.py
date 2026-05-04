from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, Count
from students.models import Student
from courses.models import Course, Enrollment
from fees.models import FeePayment, PaymentSubmission
from results.models import Result

def get_fees_display():
    ugx = FeePayment.objects.filter(student__currency='UGX').aggregate(t=Sum('amount_paid'))['t'] or 0
    usd = FeePayment.objects.filter(student__currency='USD').aggregate(t=Sum('amount_paid'))['t'] or 0
    parts = []
    if ugx: parts.append(f"UGX {ugx:,.0f}")
    if usd: parts.append(f"USD {usd:,.0f}")
    return " + ".join(parts) if parts else "UGX 0"

@login_required
def dashboard(request):
    user = request.user
    if user.must_change_password:
        return redirect('change_password')
    if user.role == 'student':
        return redirect('my_dashboard')
    if user.role == 'exam_office':
        return redirect('exam_office_dashboard')

    context = {}

    if user.role == 'admin':
        context['total_students'] = Student.objects.filter(is_active=True).count()
        context['total_courses'] = Course.objects.filter(is_active=True).count()
        context['total_enrollments'] = Enrollment.objects.filter(status='enrolled').count()
        context['total_fees'] = get_fees_display()
        context['pending_payments'] = PaymentSubmission.objects.filter(status='pending').context['ugx_fees'] = FeePayment.objects.filter(student__currency='UGX').aggregate(t=Sum('amount_paid'))['t'] or 0
        context['ugx_fees'] = FeePayment.objects.filter(student__currency='UGX').aggregate(t=Sum('amount_paid'))['t'] or 0
        context['usd_fees'] = FeePayment.objects.filter(student__currency='USD').aggregate(t=Sum('amount_paid'))['t'] or 0

    elif user.role == 'registry':
        context['total_students'] = Student.objects.filter(is_active=True).count()
        context['total_courses'] = Course.objects.filter(is_active=True).count()
        context['total_enrollments'] = Enrollment.objects.filter(status='enrolled').count()

    elif user.role == 'finance':
        students = Student.objects.filter(is_active=True)
        exam_cleared = cat2 = cat1 = enrolled = not_enrolled = 0
        for s in students:
            pct = s.payment_percentage
            if pct >= 100: exam_cleared += 1
            elif pct >= 75: cat2 += 1
            elif pct >= 50: cat1 += 1
            elif pct >= 30: enrolled += 1
            else: not_enrolled += 1
        context['exam_cleared'] = exam_cleared
        context['cat2_cleared'] = cat2
        context['cat1_cleared'] = cat1
        context['enrolled'] = enrolled
        context['not_enrolled'] = not_enrolled
        context['total_fees'] = get_fees_display()
        context['pending_payments'] = PaymentSubmission.objects.filter(status='pending').count()
        context['ugx_fees'] = FeePayment.objects.filter(student__currency='UGX').aggregate(t=Sum('amount_paid'))['t'] or 0
        context['usd_fees'] = FeePayment.objects.filter(student__currency='USD').aggregate(t=Sum('amount_paid'))['t'] or 0

    elif user.role == 'lecturer':
        try:
            lecturer = user.lecturer_profile
            my_courses = Course.objects.filter(lecturer=lecturer, is_active=True)
            context['my_courses'] = my_courses
            context['total_courses'] = my_courses.count()
            context['total_students'] = Enrollment.objects.filter(
                course__in=my_courses, status='enrolled'
            ).values('student').distinct().count()
            context['results_entered'] = Result.objects.filter(course__in=my_courses).count()
        except:
            context['my_courses'] = []
            context['total_courses'] = 0
            context['total_students'] = 0
            context['results_entered'] = 0

    return render(request, 'dashboard.html', context)

@login_required
def reports(request):
    if request.user.role not in ['admin', 'finance']:
        return redirect('dashboard')
    total_students = Student.objects.filter(is_active=True).count()
    total_courses = Course.objects.filter(is_active=True).count()
    total_enrollments = Enrollment.objects.filter(status='enrolled').count()
    total_results = Result.objects.count()
    avg_marks = Result.objects.aggregate(avg=Avg('marks'))['avg'] or 0
    grade_dist = Result.objects.values('grade').annotate(count=Count('grade')).order_by('grade')
    return render(request, 'reports.html', {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'total_fees': get_fees_display(),
        'total_results': total_results,
        'avg_marks': f"{avg_marks:.1f}",
        'grade_dist': grade_dist,
    })
