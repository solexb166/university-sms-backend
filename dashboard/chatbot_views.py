import json
import os
import urllib.request
import urllib.error
import traceback
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Avg, Count
from students.models import Student
from fees.models import FeePayment
from courses.models import Enrollment, Course, ExamDocket
from results.models import Result


def get_finance_data():
    """Collect all finance data to send to AI"""
    students = Student.objects.filter(is_active=True).select_related('department')

    from fees.models import PaymentSubmission
    pending_submissions = PaymentSubmission.objects.filter(status='pending').select_related('student')
    pending_list = []
    for sub in pending_submissions:
        pending_list.append({
            'student_name': sub.student.full_name,
            'student_id': sub.student.student_id,
            'bank': sub.bank_name,
            'reference': sub.bank_reference,
            'amount': float(sub.amount_paid),
            'currency': sub.student.currency,
            'submitted': str(sub.date_submitted),
        })

    ugx_total = FeePayment.objects.filter(
        student__currency='UGX'
    ).aggregate(t=Sum('amount_paid'))['t'] or 0

    usd_total = FeePayment.objects.filter(
        student__currency='USD'
    ).aggregate(t=Sum('amount_paid'))['t'] or 0

    data = {
        'total_students': students.count(),
        'total_collected_ugx': float(ugx_total),
        'total_collected_usd': float(usd_total),
        'pending_submissions': len(pending_list),
        'pending_list': pending_list,
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
    if role == 'finance' or role == 'admin':
        return f"""You are the Finance AI Assistant built into the Cavendish University Uganda Student Records Management System. You are NOT a third party. You are part of this system and you have DIRECT ACCESS to the live database right now.

You already know everything about every student's payment status. Do not say things like "I don't have access to the database" or "you should check the system" or "I cannot verify". You ARE the system. Speak with confidence using the real data below.

LIVE DATA FROM DATABASE RIGHT NOW:
- Total Students: {data['total_students']}
- Total UGX Collected: UGX {data['total_collected_ugx']:,.0f}
- Total USD Collected: USD {data['total_collected_usd']:,.0f}
- Pending Payment Submissions: {data['pending_submissions']}
- Exam Cleared (100%): {data['clearance_summary']['exam_cleared']} students
- CAT 2 Cleared (75%+): {data['clearance_summary']['cat2_cleared']} students
- CAT 1 Cleared (50%+): {data['clearance_summary']['cat1_cleared']} students
- Enrolled (30%+): {data['clearance_summary']['enrolled']} students
- Not Enrolled (<30%): {data['clearance_summary']['not_enrolled']} students

PENDING SUBMISSIONS WAITING FOR YOUR APPROVAL:
{json.dumps(data['pending_list'], indent=2)}

ALL STUDENT PAYMENT RECORDS:
{json.dumps(data['students'], indent=2)}

CLEARANCE THRESHOLDS:
- 30% = Enrolled (can register modules and print Proof of Registration)
- 50% = CAT 1 Cleared
- 75% = CAT 2 Cleared
- 100% = Exam Cleared (can print Exam Docket)

RULES FOR HOW YOU RESPOND:
- Always speak as if you are looking at the live data right now
- Never say "I don't have access" or "please check the system" — you ARE the system
- When listing students, use their real names and real percentages from the data above
- When asked about pending payments, list them by name with their bank reference and amount
- Be direct, professional and concise
- Format responses clearly with names and numbers
- Do NOT use any Markdown formatting. No asterisks, no bold, no headers, no bullet symbols like * or #. Use plain text only. Use numbers like 1. 2. 3. for lists.
- If asked what action to take, guide the user to the right page in the system"""

    elif role == 'exam_office':
        cleared = data['clearance']['exam_cleared']
        not_cleared = data['clearance']['not_cleared']
        return f"""You are the Exam Office AI Assistant built into the Cavendish University Uganda Student Records Management System. You are NOT a third party. You are part of this system and you have DIRECT ACCESS to the live database right now.

Do not say things like "I don't have access" or "you should check the system". You ARE the system. Speak with full confidence using the real data below.

LIVE DATA FROM DATABASE RIGHT NOW:
- Total Students: {data['total_students']}
- Exam Dockets Generated: {data['dockets_generated']}
- Students Cleared for Exams (100% paid): {len(cleared)}
- Students NOT Cleared: {len(not_cleared)}

CLEARED STUDENTS — CAN SIT EXAMS:
{json.dumps(cleared, indent=2)}

NOT CLEARED STUDENTS — CANNOT SIT EXAMS:
{json.dumps(not_cleared, indent=2)}

RULES FOR HOW YOU RESPOND:
- Always speak as if you are looking at the live data right now
- Never say "I don't have access" or "please check the system" — you ARE the system
- Use real student names and real percentages from the data above
- Be direct, professional and concise
- If asked who can sit exams, list the cleared students by name
- If asked who cannot sit exams, list the not cleared students with their shortfall amounts
- Guide users to the right page when action is needed"""

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

        # Get API key from environment
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            print("CHATBOT ERROR: ANTHROPIC_API_KEY is not set in environment variables")
            return JsonResponse({'error': 'API key not configured'}, status=500)

        # Get real data based on role
        role = request.user.role
        if role in ['finance', 'admin']:
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
                'x-api-key': api_key,  # ✅ API KEY ADDED HERE
            },
            method='POST'
        )

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            ai_response = result['content'][0]['text']

        return JsonResponse({'response': ai_response})

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"CHATBOT HTTP ERROR {e.code}: {error_body}")
        return JsonResponse({'error': f'API error {e.code}: {error_body}'}, status=500)

    except urllib.error.URLError as e:
        print(f"CHATBOT URL ERROR: {e.reason}")
        return JsonResponse({'error': f'Connection error: {e.reason}'}, status=500)

    except Exception as e:
        print(f"CHATBOT ERROR: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
