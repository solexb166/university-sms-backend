import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Avg, Count
from students.models import Student
from fees.models import FeePayment
from courses.models import Enrollment, Course, ExamDocket
from results.models import Result
import urllib.request
import urllib.error


def get_finance_data():
    """Collect all finance data to send to AI"""
    students = Student.objects.filter(is_active=True).select_related('department')
    data = {
        'total_students': students.count(),
        'total_collected': float(FeePayment.objects.aggregate(t=Sum('amount_paid'))['t'] or 0),
        'clearance_summary': {
            'exam_cleared': 0,
            'cat2_cleared': 0,
            'cat1_cleared': 0,
            'enrolled': 0,
            'not_enrolled': 0,
        },
        'students': []
    }

    for student in students:
        pct = student.payment_percentage
        payments = FeePayment.objects.filter(student=student)
        total_paid = payments.aggregate(t=Sum('amount_paid'))['t'] or 0
        latest = payments.order_by('-payment_date').first()
        balance = float(latest.balance) if latest else float(student.tuition_amount)

        if pct >= 100:
            status = 'Exam Cleared'
            data['clearance_summary']['exam_cleared'] += 1
        elif pct >= 75:
            status = 'CAT 2 Cleared'
            data['clearance_summary']['cat2_cleared'] += 1
        elif pct >= 50:
            status = 'CAT 1 Cleared'
            data['clearance_summary']['cat1_cleared'] += 1
        elif pct >= 30:
            status = 'Enrolled'
            data['clearance_summary']['enrolled'] += 1
        else:
            status = 'Not Enrolled'
            data['clearance_summary']['not_enrolled'] += 1

        data['students'].append({
            'name': student.full_name,
            'id': student.student_id,
            'program': student.program,
            'year': student.year_of_study,
            'currency': student.currency,
            'tuition': float(student.tuition_amount),
            'total_paid': float(total_paid),
            'balance': balance,
            'percentage': round(pct, 1),
            'status': status,
        })

    return data


def get_exam_office_data():
    """Collect exam office data"""
    students = Student.objects.filter(is_active=True)
    data = {
        'total_students': students.count(),
        'dockets_generated': ExamDocket.objects.filter(academic_year='2025/2026').count(),
        'clearance': {
            'exam_cleared': [],
            'not_cleared': [],
        }
    }
    for student in students:
        pct = student.payment_percentage
        entry = {
            'name': student.full_name,
            'id': student.student_id,
            'program': student.program,
            'percentage': round(pct, 1),
        }
        if pct >= 100:
            data['clearance']['exam_cleared'].append(entry)
        else:
            entry['shortfall'] = round(
                (float(student.tuition_amount) - float(
                    FeePayment.objects.filter(student=student).aggregate(
                        t=Sum('amount_paid'))['t'] or 0)), 2)
            data['clearance']['not_cleared'].append(entry)
    return data


def build_system_prompt(role, data):
    """Build system prompt with real data for AI"""
    if role == 'finance':
        return f"""You are a smart AI assistant for the Finance Office at Cavendish University Uganda.
You have access to real-time fee payment data. Here is the current data:

SUMMARY:
- Total Students: {data['total_students']}
- Total Fees Collected: UGX {data['total_collected']:,.0f}
- Exam Cleared (100%): {data['clearance_summary']['exam_cleared']} students
- CAT 2 Cleared (75%+): {data['clearance_summary']['cat2_cleared']} students
- CAT 1 Cleared (50%+): {data['clearance_summary']['cat1_cleared']} students
- Enrolled (30%+): {data['clearance_summary']['enrolled']} students
- Not Enrolled (<30%): {data['clearance_summary']['not_enrolled']} students

CLEARANCE THRESHOLDS:
- Enrollment: 30% of tuition
- CAT 1: 50% of tuition
- CAT 2: 75% of tuition
- Final Exam: 100% of tuition

STUDENT DATA:
{json.dumps(data['students'], indent=2)}

Your job is to:
1. Answer questions about fee payments and clearance
2. Generate clearance lists when asked
3. Identify students who need to pay more
4. Give smart financial summaries
5. Flag students below any threshold when asked

Be concise, professional and helpful. Use actual student names and numbers from the data above.
Format lists clearly. Always refer to real data — never make up information."""

    elif role == 'exam_office':
        cleared = data['clearance']['exam_cleared']
        not_cleared = data['clearance']['not_cleared']
        return f"""You are a smart AI assistant for the Exam Office at Cavendish University Uganda.
You have access to real-time clearance data. Here is the current data:

SUMMARY:
- Total Students: {data['total_students']}
- Exam Dockets Generated: {data['dockets_generated']}
- Students Cleared for Exam (100%): {len(cleared)}
- Students NOT Cleared: {len(not_cleared)}

CLEARED STUDENTS (100% paid):
{json.dumps(cleared, indent=2)}

NOT CLEARED STUDENTS:
{json.dumps(not_cleared, indent=2)}

Your job is to:
1. Answer questions about exam clearance
2. List cleared and not cleared students
3. Tell staff who can and cannot sit exams
4. Help generate and manage exam dockets
5. Provide clearance statistics

Be concise, professional and helpful. Always use real data. Never make up information."""

    return "You are a helpful university assistant."


@login_required
@csrf_exempt
def chatbot_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if request.user.role not in ['finance', 'exam_office', 'admin']:
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()
        history = body.get('history', [])

        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Get real data based on role
        role = request.user.role
        if role == 'finance' or role == 'admin':
            data = get_finance_data()
        else:
            data = get_exam_office_data()

        system_prompt = build_system_prompt(role, data)

        # Build messages for Claude API
        messages = []
        for h in history[-10:]:  # Last 10 messages for context
            messages.append({'role': h['role'], 'content': h['content']})
        messages.append({'role': 'user', 'content': user_message})

        # Call Claude API
        payload = json.dumps({
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 1000,
            'system': system_prompt,
            'messages': messages,
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01',
            },
            method='POST'
        )

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            ai_response = result['content'][0]['text']

        return JsonResponse({'response': ai_response})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
