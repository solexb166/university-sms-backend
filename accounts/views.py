from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser
from courses.models import Course
import datetime

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.must_change_password:
                return redirect('change_password')
            return redirect('dashboard')
        # Try OTP login
        try:
            user_obj = CustomUser.objects.get(username=username)
            if user_obj.otp and user_obj.otp == password:
                login(request, user_obj)
                return redirect('change_password')
        except CustomUser.DoesNotExist:
            pass
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html', {'current_year': datetime.datetime.now().year})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def change_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/change_password.html')
        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'accounts/change_password.html')
        request.user.set_password(new_password)
        request.user.must_change_password = False
        request.user.otp = ''
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Password changed successfully. Welcome!')
        return redirect('dashboard')
    return render(request, 'accounts/change_password.html')

@login_required
def users_list(request):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    users = CustomUser.objects.all().order_by('role', 'username')
    try:
        from courses.models import Course
        courses = Course.objects.filter(is_active=True)
    except Exception:
        courses = []
    return render(request, 'accounts/users.html', {'users': users, 'courses': courses})

@login_required
def create_user(request):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        role = request.POST.get('role', 'registry')
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('users_list')
        user = CustomUser.objects.create_user(
            username=username,
            password=request.POST.get('password'),
            email=request.POST.get('email', ''),
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            role=role,
            phone=request.POST.get('phone', ''),
        )
        # If lecturer — create profile and assign courses
        if role == 'lecturer':
            from students.models import Lecturer, Department
            dept_id = request.POST.get('department')
            dept = Department.objects.filter(id=dept_id).first() if dept_id else None
            lecturer_id = f"LEC{user.id:04d}"
            lecturer = Lecturer.objects.create(
                user=user,
                lecturer_id=lecturer_id,
                full_name=f"{request.POST.get('first_name', '')} {request.POST.get('last_name', '')}".strip(),
                department=dept,
                specialization=request.POST.get('specialization', ''),
            )
            # Assign courses to lecturer
            course_ids = request.POST.getlist('courses')
            for cid in course_ids:
                course = Course.objects.filter(id=cid).first()
                if course:
                    course.lecturer = lecturer
                    course.save()
        messages.success(request, f'User {username} created successfully.')
        return redirect('users_list')
    return redirect('users_list')
