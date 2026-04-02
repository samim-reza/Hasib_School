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
from django.utils.http import url_has_allowed_host_and_scheme
from typing import Optional, cast
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from .models import Student, Attendance, Teacher, AdmissionRecord, TeacherActivityLog
from core.models import Notice, AdmissionHeadline
from datetime import date


SECTION_LABELS = dict(AdmissionRecord.SECTION_CHOICES)


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
    }
    return render(request, 'academic/super_admin_dashboard.html', context)

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
