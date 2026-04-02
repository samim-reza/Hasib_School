from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as AuthUser
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum, Count
from django.utils.http import url_has_allowed_host_and_scheme
from typing import Optional, cast
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from .models import Student, Attendance, Teacher, AdmissionRecord, TeacherActivityLog
from core.models import Notice, AdmissionHeadline
from finance.models import Transaction
from datetime import date, datetime


SECTION_LABELS = dict(AdmissionRecord.SECTION_CHOICES)
TRANSACTION_TYPE_LABELS = dict(Transaction.TRANSACTION_TYPES)
TRANSACTION_CATEGORY_LABELS = dict(Transaction.CATEGORY_CHOICES)


def health_check(request: HttpRequest) -> HttpResponse:
    return HttpResponse('ok', content_type='text/plain')


def _is_teacher_or_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return getattr(user, 'teacher', None) is not None
    except ObjectDoesNotExist:
        return False


def _ensure_teacher_or_admin(request: HttpRequest) -> Optional[HttpResponse]:
    if not _is_teacher_or_admin(request.user):
        messages.error(request, 'এই পেজে প্রবেশের অনুমতি নেই।')
        return redirect('academic:teacher_login')

    check_password = getattr(request.user, 'check_password', None)
    try:
        has_teacher_profile = getattr(request.user, 'teacher', None) is not None
    except ObjectDoesNotExist:
        has_teacher_profile = False

    if has_teacher_profile and not request.user.is_superuser and callable(check_password):
        change_password_url = reverse('academic:teacher_change_password')
        if request.path != change_password_url and check_password('default123'):
            messages.warning(request, 'প্রথম লগইনে ডিফল্ট পাসওয়ার্ড পরিবর্তন করুন।')
            return redirect('academic:teacher_change_password')

    return None


def _ensure_admin(request: HttpRequest) -> Optional[HttpResponse]:
    if not request.user.is_authenticated or not request.user.is_superuser:
        messages.error(request, 'শুধুমাত্র অ্যাডমিন এই পেজ ব্যবহার করতে পারবেন।')
        return redirect('academic:teacher_portal')
    return None


def _ensure_super_admin(request: HttpRequest) -> Optional[HttpResponse]:
    if not request.user.is_authenticated or not request.user.is_superuser:
        messages.error(request, 'শুধুমাত্র সুপার অ্যাডমিন এই পেজ ব্যবহার করতে পারবেন।')
        return redirect('academic:super_admin_login')
    return None


def _get_user_display_name(request: HttpRequest) -> str:
    full_name_getter = getattr(request.user, 'get_full_name', None)
    full_name = str(full_name_getter()) if callable(full_name_getter) else ''
    username = str(getattr(request.user, 'username', ''))
    return full_name or username


def _log_activity(
    request: HttpRequest,
    action_type: str,
    student: Optional[Student] = None,
    class_name: str = '',
    note: str = '',
) -> None:
    TeacherActivityLog.objects.create(
        actor=request.user,
        student=student,
        action_type=action_type,
        class_name=class_name,
        note=note,
    )


def super_admin_login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('academic:super_admin_dashboard')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip().lower()
        password = request.POST.get('password') or ''

        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_superuser:
            login(request, user)
            messages.success(request, 'সুপার অ্যাডমিন হিসেবে সফলভাবে লগইন হয়েছে।')
            return redirect('academic:super_admin_dashboard')

        messages.error(request, 'লগইন তথ্য সঠিক নয় বা এটি সুপার অ্যাডমিন অ্যাকাউন্ট নয়।')

    return render(request, 'academic/super_admin_login.html')


def teacher_login(request: HttpRequest) -> HttpResponse:
    if _is_teacher_or_admin(request.user):
        return redirect('academic:teacher_portal')

    next_url = request.POST.get('next') or request.GET.get('next') or reverse('academic:teacher_portal')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse('academic:teacher_portal')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip().lower()
        password = request.POST.get('password') or ''

        user = authenticate(request, username=username, password=password)
        if user is not None and _is_teacher_or_admin(user):
            login(request, user)
            messages.success(request, 'সফলভাবে লগইন হয়েছে।')
            return redirect(next_url)

        messages.error(request, 'ইউজারনেম বা পাসওয়ার্ড সঠিক নয়।')

    return render(request, 'academic/teacher_login.html', {'next_url': next_url})


def super_admin_logout(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        logout(request)
    messages.success(request, 'সুপার অ্যাডমিন লগআউট সম্পন্ন হয়েছে।')
    return redirect('academic:super_admin_login')


def account_logout(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        logout(request)
    messages.success(request, 'লগআউট সম্পন্ন হয়েছে।')
    return redirect('academic:home')


def super_admin_dashboard(request: HttpRequest) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    context = {
        'teachers_count': Teacher.objects.count(),
        'active_students_count': Student.objects.filter(is_active=True).count(),
        'admissions_count': AdmissionRecord.objects.count(),
        'attendance_count': Attendance.objects.count(),
        'notices_count': Notice.objects.count(),
        'active_notices_count': Notice.objects.filter(is_active=True).count(),
        'admission_headlines_count': AdmissionHeadline.objects.count(),
        'active_admission_headlines_count': AdmissionHeadline.objects.filter(is_active=True).count(),
        'transactions_count': Transaction.objects.count(),
    }
    return render(request, 'academic/super_admin_dashboard.html', context)


def super_admin_notice_board(request: HttpRequest) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    edit_notice: Optional[Notice] = None
    edit_id = (request.GET.get('edit') or '').strip()
    if edit_id:
        if edit_id.isdigit():
            edit_notice = get_object_or_404(Notice, id=int(edit_id))
        else:
            messages.error(request, 'নোটিশ এডিট করার জন্য সঠিক আইডি দিন।')
            return redirect('academic:super_admin_notice_board')

    if request.method == 'POST':
        notice_id = (request.POST.get('notice_id') or '').strip()
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        is_active = request.POST.get('is_active') == 'on'
        document = request.FILES.get('document')
        remove_document = request.POST.get('remove_document') == 'on'

        if not title or not description:
            messages.error(request, 'শিরোনাম এবং বিবরণ বাধ্যতামূলক।')
            if notice_id:
                return redirect(f"{reverse('academic:super_admin_notice_board')}?edit={notice_id}")
            return redirect('academic:super_admin_notice_board')

        if notice_id:
            notice = get_object_or_404(Notice, id=int(notice_id))
            notice.title = title
            notice.description = description
            notice.is_active = is_active

            if remove_document and notice.document:
                notice.document.delete(save=False)
                setattr(notice, 'document', None)

            if document:
                if notice.document:
                    notice.document.delete(save=False)
                setattr(notice, 'document', document)

            notice.save()
            messages.success(request, 'নোটিশ সফলভাবে আপডেট হয়েছে।')
        else:
            Notice.objects.create(
                title=title,
                description=description,
                is_active=is_active,
                document=document,
            )
            messages.success(request, 'নতুন নোটিশ প্রকাশ করা হয়েছে।')

        return redirect('academic:super_admin_notice_board')

    notices = Notice.objects.order_by('-created_at')
    return render(
        request,
        'academic/super_admin_notice_board.html',
        {
            'notices': notices,
            'edit_notice': edit_notice,
        },
    )


def super_admin_notice_toggle(request: HttpRequest, notice_id: int) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:super_admin_notice_board')

    notice = get_object_or_404(Notice, id=notice_id)
    notice.is_active = not notice.is_active
    notice.save(update_fields=['is_active'])
    status_text = 'সক্রিয়' if notice.is_active else 'নিষ্ক্রিয়'
    messages.success(request, f'নোটিশ {status_text} করা হয়েছে।')
    return redirect('academic:super_admin_notice_board')


def super_admin_notice_delete(request: HttpRequest, notice_id: int) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:super_admin_notice_board')

    notice = get_object_or_404(Notice, id=notice_id)
    if notice.document:
        notice.document.delete(save=False)
    notice.delete()
    messages.success(request, 'নোটিশ মুছে ফেলা হয়েছে।')
    return redirect('academic:super_admin_notice_board')


def super_admin_admission_ads(request: HttpRequest) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    edit_headline: Optional[AdmissionHeadline] = None
    edit_id = (request.GET.get('edit') or '').strip()
    if edit_id:
        if edit_id.isdigit():
            edit_headline = get_object_or_404(AdmissionHeadline, id=int(edit_id))
        else:
            messages.error(request, 'ভর্তি বিজ্ঞাপনের সঠিক আইডি দিন।')
            return redirect('academic:super_admin_admission_ads')

    if request.method == 'POST':
        headline_id = (request.POST.get('headline_id') or '').strip()
        headline = (request.POST.get('headline') or '').strip()
        subheadline = (request.POST.get('subheadline') or '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if not headline:
            messages.error(request, 'হেডলাইন বাধ্যতামূলক।')
            if headline_id:
                return redirect(f"{reverse('academic:super_admin_admission_ads')}?edit={headline_id}")
            return redirect('academic:super_admin_admission_ads')

        if headline_id:
            admission_headline = get_object_or_404(AdmissionHeadline, id=int(headline_id))
            admission_headline.headline = headline
            admission_headline.subheadline = subheadline
            admission_headline.is_active = is_active
            admission_headline.save()
            messages.success(request, 'ভর্তি বিজ্ঞাপন আপডেট হয়েছে।')
        else:
            AdmissionHeadline.objects.create(
                headline=headline,
                subheadline=subheadline,
                is_active=is_active,
            )
            messages.success(request, 'নতুন ভর্তি বিজ্ঞাপন যুক্ত হয়েছে।')

        return redirect('academic:super_admin_admission_ads')

    headlines = AdmissionHeadline.objects.order_by('-updated_at')
    return render(
        request,
        'academic/super_admin_admission_ads.html',
        {
            'headlines': headlines,
            'edit_headline': edit_headline,
        },
    )


def super_admin_admission_ads_toggle(request: HttpRequest, headline_id: int) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:super_admin_admission_ads')

    headline = get_object_or_404(AdmissionHeadline, id=headline_id)
    headline.is_active = not headline.is_active
    headline.save(update_fields=['is_active'])
    status_text = 'সক্রিয়' if headline.is_active else 'নিষ্ক্রিয়'
    messages.success(request, f'ভর্তি বিজ্ঞাপন {status_text} করা হয়েছে।')
    return redirect('academic:super_admin_admission_ads')


def super_admin_admission_ads_delete(request: HttpRequest, headline_id: int) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:super_admin_admission_ads')

    headline = get_object_or_404(AdmissionHeadline, id=headline_id)
    headline.delete()
    messages.success(request, 'ভর্তি বিজ্ঞাপন মুছে ফেলা হয়েছে।')
    return redirect('academic:super_admin_admission_ads')


def super_admin_finance_management(request: HttpRequest) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    edit_transaction: Optional[Transaction] = None
    edit_id = (request.GET.get('edit') or '').strip()
    if edit_id:
        if edit_id.isdigit():
            edit_transaction = get_object_or_404(Transaction, id=int(edit_id))
        else:
            messages.error(request, 'লেনদেন এডিট করার জন্য সঠিক আইডি দিন।')
            return redirect('academic:super_admin_finance_management')

    if request.method == 'POST':
        transaction_id = (request.POST.get('transaction_id') or '').strip()
        title = (request.POST.get('title') or '').strip()
        amount_raw = (request.POST.get('amount') or '').strip()
        transaction_type = (request.POST.get('transaction_type') or '').strip()
        category = (request.POST.get('category') or '').strip()
        description = (request.POST.get('description') or '').strip()
        receipt = request.FILES.get('receipt')
        remove_receipt = request.POST.get('remove_receipt') == 'on'

        if not title:
            messages.error(request, 'শিরোনাম বাধ্যতামূলক।')
            if transaction_id:
                return redirect(f"{reverse('academic:super_admin_finance_management')}?edit={transaction_id}")
            return redirect('academic:super_admin_finance_management')

        if transaction_type not in TRANSACTION_TYPE_LABELS:
            messages.error(request, 'আয়/ব্যয়ের ধরন সঠিকভাবে নির্বাচন করুন।')
            return redirect('academic:super_admin_finance_management')

        if category not in TRANSACTION_CATEGORY_LABELS:
            messages.error(request, 'ক্যাটাগরি সঠিকভাবে নির্বাচন করুন।')
            return redirect('academic:super_admin_finance_management')

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, 'পরিমাণ সঠিক সংখ্যায় লিখুন।')
            return redirect('academic:super_admin_finance_management')

        if amount <= Decimal('0'):
            messages.error(request, 'পরিমাণ অবশ্যই ০-এর বেশি হতে হবে।')
            return redirect('academic:super_admin_finance_management')

        if transaction_id:
            transaction = get_object_or_404(Transaction, id=int(transaction_id))
            transaction.title = title
            transaction.amount = amount
            transaction.transaction_type = transaction_type
            transaction.category = category
            transaction.description = description

            if remove_receipt and transaction.receipt:
                transaction.receipt.delete(save=False)
                setattr(transaction, 'receipt', None)

            if receipt:
                if transaction.receipt:
                    transaction.receipt.delete(save=False)
                setattr(transaction, 'receipt', receipt)

            transaction.save()
            messages.success(request, 'লেনদেন আপডেট হয়েছে।')
        else:
            Transaction.objects.create(
                title=title,
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                description=description,
                receipt=receipt,
            )
            messages.success(request, 'নতুন লেনদেন যুক্ত হয়েছে।')

        return redirect('academic:super_admin_finance_management')

    transactions = Transaction.objects.order_by('-date', '-id')

    selected_type = (request.GET.get('transaction_type') or '').strip()
    selected_category = (request.GET.get('category') or '').strip()
    start_date_raw = (request.GET.get('start_date') or '').strip()
    end_date_raw = (request.GET.get('end_date') or '').strip()

    if selected_type in TRANSACTION_TYPE_LABELS:
        transactions = transactions.filter(transaction_type=selected_type)

    if selected_category in TRANSACTION_CATEGORY_LABELS:
        transactions = transactions.filter(category=selected_category)

    if start_date_raw:
        try:
            start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
            transactions = transactions.filter(date__gte=start_date)
        except ValueError:
            messages.error(request, 'শুরুর তারিখ সঠিক ফরম্যাটে দিন (YYYY-MM-DD)।')

    if end_date_raw:
        try:
            end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date()
            transactions = transactions.filter(date__lte=end_date)
        except ValueError:
            messages.error(request, 'শেষের তারিখ সঠিক ফরম্যাটে দিন (YYYY-MM-DD)।')

    income_total = (
        transactions.filter(transaction_type='income').aggregate(total=Sum('amount')).get('total')
        or Decimal('0.00')
    )
    expense_total = (
        transactions.filter(transaction_type='expense').aggregate(total=Sum('amount')).get('total')
        or Decimal('0.00')
    )
    balance_total = income_total - expense_total

    category_breakdown_raw = (
        transactions.values('category')
        .annotate(total=Sum('amount'), items=Count('id'))
        .order_by('category')
    )
    category_breakdown = [
        {
            'label': TRANSACTION_CATEGORY_LABELS.get(item['category'], item['category']),
            'total': item['total'] or Decimal('0.00'),
            'items': item['items'],
        }
        for item in category_breakdown_raw
    ]

    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'edit_transaction': edit_transaction,
        'transaction_type_choices': Transaction.TRANSACTION_TYPES,
        'category_choices': Transaction.CATEGORY_CHOICES,
        'selected_type': selected_type,
        'selected_category': selected_category,
        'start_date': start_date_raw,
        'end_date': end_date_raw,
        'income_total': income_total,
        'expense_total': expense_total,
        'balance_total': balance_total,
        'category_breakdown': category_breakdown,
    }
    return render(request, 'academic/super_admin_finance_management.html', context)


def super_admin_finance_delete(request: HttpRequest, transaction_id: int) -> HttpResponse:
    denied = _ensure_super_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:super_admin_finance_management')

    transaction = get_object_or_404(Transaction, id=transaction_id)
    if transaction.receipt:
        transaction.receipt.delete(save=False)
    transaction.delete()
    messages.success(request, 'লেনদেন মুছে ফেলা হয়েছে।')
    return redirect('academic:super_admin_finance_management')

def home_view(request: HttpRequest) -> HttpResponse:
    notices = Notice.objects.filter(is_active=True)
    admission_headline = AdmissionHeadline.objects.filter(is_active=True).first()
    paginator = Paginator(notices, 5) # 5 notices per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        'academic/home.html',
        {
            'page_obj': page_obj,
            'admission_headline': admission_headline,
        }
    )

@login_required
def teacher_portal(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied
        
    class_names = [label for _, label in AdmissionRecord.SECTION_CHOICES]
    selected_class = request.GET.get('class_name', '').strip()

    if selected_class in class_names:
        students = Student.objects.filter(is_active=True, class_name=selected_class)
    else:
        students = Student.objects.none()

    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    page_student_ids = [student.id for student in page_obj.object_list]
    present_ids = set(
        Attendance.objects.filter(
            student_id__in=page_student_ids,
            date=date.today(),
            is_present=True,
        ).values_list('student_id', flat=True)
    )
    for student in page_obj.object_list:
        student.is_present_today = student.id in present_ids

    activity_qs = TeacherActivityLog.objects.select_related('student', 'actor')
    if selected_class in class_names:
        activity_qs = activity_qs.filter(class_name=selected_class)
    if not request.user.is_superuser:
        activity_qs = activity_qs.filter(actor=request.user)
    recent_activities = activity_qs[:20]

    context = {
        'page_obj': page_obj,
        'class_choices': AdmissionRecord.SECTION_CHOICES,
        'is_admin': request.user.is_superuser,
        'class_names': class_names,
        'selected_class': selected_class,
        'recent_activities': recent_activities,
    }
    return render(request, 'academic/teacher_portal.html', context)


@login_required
def teacher_change_password(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    current_user = cast(AuthUser, request.user)

    if request.method == 'POST':
        form = PasswordChangeForm(current_user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'পাসওয়ার্ড সফলভাবে পরিবর্তন হয়েছে।')
            return redirect('academic:teacher_portal')
        messages.error(request, 'পাসওয়ার্ড পরিবর্তন করা যায়নি। অনুগ্রহ করে তথ্য ঠিক করুন।')
    else:
        form = PasswordChangeForm(current_user)

    return render(request, 'academic/teacher_change_password.html', {'form': form})


@login_required
def teacher_management(request: HttpRequest) -> HttpResponse:
    denied = _ensure_admin(request)
    if denied:
        return denied

    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        subject = request.POST.get('subject', '').strip()

        if not all([username, name, phone, subject]):
            messages.error(request, 'সবগুলো তথ্য পূরণ করুন।')
            return redirect('academic:teacher_management')

        if AuthUser.objects.filter(username=username).exists():
            messages.error(request, 'এই ইউজারনেম ইতোমধ্যে ব্যবহৃত হয়েছে।')
            return redirect('academic:teacher_management')

        user = AuthUser.objects.create_user(
            username=username,
            password='default123',
            first_name=name,
            is_staff=True,
            is_active=True,
        )
        Teacher.objects.create(user=user, name=name, phone=phone, subject=subject)
        messages.success(request, f'শিক্ষক তৈরি হয়েছে। ইউজার: {username}, ডিফল্ট পাসওয়ার্ড: default123')
        return redirect('academic:teacher_management')

    teachers = Teacher.objects.select_related('user').order_by('name')
    return render(request, 'academic/teacher_management.html', {'teachers': teachers})


@login_required
def teacher_update_name(request: HttpRequest, teacher_id: int) -> HttpResponse:
    denied = _ensure_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:teacher_management')

    teacher = get_object_or_404(Teacher, id=teacher_id)
    new_name = request.POST.get('name', '').strip()

    if not new_name:
        messages.error(request, 'নাম ফাঁকা রাখা যাবে না।')
        return redirect('academic:teacher_management')

    teacher.name = new_name
    teacher.save(update_fields=['name'])
    teacher.user.first_name = new_name
    teacher.user.save(update_fields=['first_name'])
    messages.success(request, 'শিক্ষকের নাম আপডেট হয়েছে।')
    return redirect('academic:teacher_management')


@login_required
def teacher_update_username(request: HttpRequest, teacher_id: int) -> HttpResponse:
    denied = _ensure_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:teacher_management')

    teacher = get_object_or_404(Teacher.objects.select_related('user'), id=teacher_id)
    new_username = request.POST.get('username', '').strip().lower()

    if not new_username:
        messages.error(request, 'ইউজারনেম ফাঁকা রাখা যাবে না।')
        return redirect('academic:teacher_management')

    exists = AuthUser.objects.filter(username=new_username).exclude(pk=teacher.user.pk).exists()
    if exists:
        messages.error(request, 'এই ইউজারনেম ইতোমধ্যে ব্যবহৃত হয়েছে।')
        return redirect('academic:teacher_management')

    teacher.user.username = new_username
    teacher.user.save(update_fields=['username'])
    messages.success(request, 'শিক্ষকের ইউজারনেম আপডেট হয়েছে।')
    return redirect('academic:teacher_management')


@login_required
def teacher_remove(request: HttpRequest, teacher_id: int) -> HttpResponse:
    denied = _ensure_admin(request)
    if denied:
        return denied

    if request.method != 'POST':
        return redirect('academic:teacher_management')

    teacher = get_object_or_404(Teacher.objects.select_related('user'), id=teacher_id)
    if teacher.user.is_superuser:
        messages.error(request, 'সুপারইউজার শিক্ষক মুছে ফেলা যাবে না।')
        return redirect('academic:teacher_management')

    username = teacher.user.username
    teacher.user.delete()
    messages.success(request, f'শিক্ষক {username} মুছে ফেলা হয়েছে।')
    return redirect('academic:teacher_management')


@login_required
def admin_account_settings(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    current_user = cast(AuthUser, request.user)

    if request.method == 'POST':
        new_username = request.POST.get('username', '').strip().lower()

        if not new_username:
            messages.error(request, 'ইউজারনেম ফাঁকা রাখা যাবে না।')
            return redirect('academic:admin_account_settings')

        exists = AuthUser.objects.filter(username=new_username).exclude(pk=current_user.pk).exists()
        if exists:
            messages.error(request, 'এই ইউজারনেম ইতোমধ্যে ব্যবহৃত হয়েছে।')
            return redirect('academic:admin_account_settings')

        current_user.username = new_username
        current_user.save(update_fields=['username'])
        messages.success(request, 'ইউজারনেম আপডেট হয়েছে।')
        return redirect('academic:admin_account_settings')

    return render(request, 'academic/admin_account_settings.html', {'current_username': current_user.username})


@login_required
def attendance_history(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    queryset = Attendance.objects.select_related('student', 'taken_by').order_by('-date', '-id')
    selected_class = request.GET.get('class_name', '').strip()
    selected_date = request.GET.get('date', '').strip()

    class_names = [label for _, label in AdmissionRecord.SECTION_CHOICES]

    if selected_class in class_names:
        queryset = queryset.filter(student__class_name=selected_class)

    if selected_date:
        queryset = queryset.filter(date=selected_date)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'class_names': class_names,
        'selected_class': selected_class,
        'selected_date': selected_date,
    }
    return render(request, 'academic/attendance_history.html', context)

@login_required
def take_attendance(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    if request.method == "POST":
        student_id = request.POST.get('student_id')
        selected_class = request.POST.get('class_name', '').strip()
        is_present = request.POST.get('is_present') == 'on'
        student = get_object_or_404(Student, id=student_id)
        
        teacher = getattr(request.user, 'teacher', None)
        
        Attendance.objects.update_or_create(
            student=student,
            date=date.today(),
            defaults={'is_present': is_present, 'taken_by': teacher}
        )
        status_text = 'উপস্থিত' if is_present else 'অনুপস্থিত'
        _log_activity(
            request,
            TeacherActivityLog.ACTION_ATTENDANCE,
            student=student,
            class_name=student.class_name,
            note=f"{student.name} ({student.roll_no}) - {status_text}",
        )
        return render(
            request,
            'academic/partials/attendance_row.html',
            {
                'student': student,
                'status': 'success',
                'is_present': is_present,
                'selected_class': selected_class or student.class_name,
            },
        )
    return redirect('academic:teacher_portal')

@login_required
def add_student(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect('academic:teacher_portal')

    name = (request.POST.get('name') or '').strip()
    roll_no = (request.POST.get('roll_no') or '').strip()
    class_name = (request.POST.get('class_name') or '').strip()
    guardian_phone = (request.POST.get('guardian_phone') or '').strip()

    class_labels = set(SECTION_LABELS.values())
    if class_name not in class_labels:
        messages.error(request, "ড্রপডাউন থেকে সঠিক শ্রেণী নির্বাচন করুন।")
        return redirect('academic:teacher_portal')

    if Student.objects.filter(roll_no=roll_no).exists():
        messages.error(request, "এই রোল নম্বরের শিক্ষার্থী ইতিমধ্যে আছে।")
    else:
        student = Student.objects.create(name=name, roll_no=roll_no, class_name=class_name, guardian_phone=guardian_phone)
        _log_activity(
            request,
            TeacherActivityLog.ACTION_ADD_STUDENT,
            student=student,
            class_name=class_name,
            note=f"{student.name} ({student.roll_no}) যুক্ত করা হয়েছে",
        )
        messages.success(request, "শিক্ষার্থী সফলভাবে যুক্ত করা হয়েছে।")

    query = urlencode({'class_name': class_name})
    return redirect(f"{reverse('academic:teacher_portal')}?{query}")

@login_required
def remove_student(request: HttpRequest, student_id: int) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    student = get_object_or_404(Student, id=student_id)
    class_name = student.class_name
    student_name = student.name
    student_roll = student.roll_no
    student.is_active = False
    student.save()
    _log_activity(
        request,
        TeacherActivityLog.ACTION_REMOVE_STUDENT,
        student=student,
        class_name=class_name,
        note=f"{student_name} ({student_roll}) মুছে ফেলা হয়েছে",
    )
    messages.success(request, "শিক্ষার্থী মুছে ফেলা হয়েছে।")

    selected_class = request.GET.get('class_name', '').strip()
    target_class = selected_class or class_name
    if target_class:
        query = urlencode({'class_name': target_class})
        return redirect(f"{reverse('academic:teacher_portal')}?{query}")
    return redirect('academic:teacher_portal')


@login_required
def admission_portal(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    admissions = AdmissionRecord.objects.select_related('student', 'admitted_by')
    paginator = Paginator(admissions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'academic/admission_portal.html', {'page_obj': page_obj, 'is_admin': request.user.is_superuser})


@login_required
def admission_create(request: HttpRequest) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    teacher = getattr(request.user, 'teacher', None)
    default_signature = teacher.name if teacher else _get_user_display_name(request)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        roll_no = request.POST.get('roll_no', '').strip()
        guardian_phone = request.POST.get('guardian_phone', '').strip()
        guardian_name = request.POST.get('guardian_name', '').strip()
        section = request.POST.get('section', '').strip()
        admission_fee_text = request.POST.get('admission_fee', '0').strip()
        address = request.POST.get('address', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        admitted_by_signature = request.POST.get('admitted_by_signature', '').strip() or default_signature

        if section not in SECTION_LABELS:
            messages.error(request, 'সঠিক বিভাগ নির্বাচন করুন।')
            return redirect('academic:admission_create')

        if not all([name, roll_no, guardian_phone, guardian_name]):
            messages.error(request, 'অনুগ্রহ করে বাধ্যতামূলক তথ্য পূরণ করুন।')
            return redirect('academic:admission_create')

        try:
            admission_fee = Decimal(admission_fee_text)
        except (InvalidOperation, ValueError):
            messages.error(request, 'ভর্তি ফি সঠিক সংখ্যায় দিন।')
            return redirect('academic:admission_create')

        if Student.objects.filter(roll_no=roll_no).exists():
            messages.error(request, 'এই রোল নম্বর ইতোমধ্যে ব্যবহৃত হয়েছে।')
            return redirect('academic:admission_create')

        student = Student.objects.create(
            name=name,
            roll_no=roll_no,
            class_name=SECTION_LABELS[section],
            guardian_phone=guardian_phone,
            is_active=True,
        )

        admission = AdmissionRecord.objects.create(
            student=student,
            section=section,
            guardian_name=guardian_name,
            address=address,
            admission_fee=admission_fee,
            paid_in_cash=True,
            admitted_by=teacher,
            admitted_by_signature=admitted_by_signature,
            remarks=remarks,
        )

        messages.success(request, 'ভর্তি তথ্য সফলভাবে সংরক্ষণ হয়েছে। এখন প্রিন্ট নিন।')
        admission_pk = admission.pk
        if admission_pk is None:
            messages.error(request, 'ভর্তি রেকর্ড পাওয়া যায়নি। আবার চেষ্টা করুন।')
            return redirect('academic:admission_portal')
        return redirect('academic:admission_print', admission_id=admission_pk)

    context = {
        'admission': None,
        'default_signature': default_signature,
        'section_choices': AdmissionRecord.SECTION_CHOICES,
    }
    return render(request, 'academic/admission_form.html', context)


@login_required
def admission_edit(request: HttpRequest, admission_id: int) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    admission = get_object_or_404(AdmissionRecord.objects.select_related('student'), id=admission_id)
    teacher = getattr(request.user, 'teacher', None)
    default_signature = admission.admitted_by_signature or (teacher.name if teacher else request.user.username)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        roll_no = request.POST.get('roll_no', '').strip()
        guardian_phone = request.POST.get('guardian_phone', '').strip()
        guardian_name = request.POST.get('guardian_name', '').strip()
        section = request.POST.get('section', '').strip()
        admission_fee_text = request.POST.get('admission_fee', '0').strip()
        address = request.POST.get('address', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        admitted_by_signature = request.POST.get('admitted_by_signature', '').strip() or default_signature

        if section not in SECTION_LABELS:
            messages.error(request, 'সঠিক বিভাগ নির্বাচন করুন।')
            return redirect('academic:admission_edit', admission_id=admission_id)

        try:
            admission_fee = Decimal(admission_fee_text)
        except (InvalidOperation, ValueError):
            messages.error(request, 'ভর্তি ফি সঠিক সংখ্যায় দিন।')
            return redirect('academic:admission_edit', admission_id=admission_id)

        conflict_exists = Student.objects.filter(roll_no=roll_no).exclude(pk=admission.student.pk).exists()
        if conflict_exists:
            messages.error(request, 'এই রোল নম্বর ইতোমধ্যে ব্যবহৃত হয়েছে।')
            return redirect('academic:admission_edit', admission_id=admission_id)

        admission.student.name = name
        admission.student.roll_no = roll_no
        admission.student.guardian_phone = guardian_phone
        admission.student.class_name = SECTION_LABELS[section]
        admission.student.save()

        admission.section = section
        admission.guardian_name = guardian_name
        admission.address = address
        admission.admission_fee = admission_fee
        admission.paid_in_cash = True
        admission.admitted_by = teacher if teacher else admission.admitted_by
        admission.admitted_by_signature = admitted_by_signature
        admission.remarks = remarks
        admission.save()

        messages.success(request, 'ভর্তি তথ্য সফলভাবে আপডেট হয়েছে।')
        return redirect('academic:admission_portal')

    context = {
        'admission': admission,
        'default_signature': default_signature,
        'section_choices': AdmissionRecord.SECTION_CHOICES,
    }
    return render(request, 'academic/admission_form.html', context)


@login_required
def admission_print(request: HttpRequest, admission_id: int) -> HttpResponse:
    denied = _ensure_teacher_or_admin(request)
    if denied:
        return denied

    admission = get_object_or_404(AdmissionRecord.objects.select_related('student', 'admitted_by'), id=admission_id)
    return render(request, 'academic/admission_print.html', {'admission': admission})
