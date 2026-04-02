from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_("ইউজার"))
    name = models.CharField(_("নাম"), max_length=150)
    phone = models.CharField(_("মোবাইল নম্বর"), max_length=20)
    subject = models.CharField(_("বিষয়"), max_length=100)
    
    class Meta:
        verbose_name = _("শিক্ষক")
        verbose_name_plural = _("শিক্ষকবৃন্দ")
        
    def __str__(self):
        return self.name

class Student(models.Model):
    name = models.CharField(_("শিক্ষার্থীর নাম"), max_length=150)
    roll_no = models.CharField(_("রোল নম্বর"), max_length=20, unique=True)
    class_name = models.CharField(_("শ্রেণী"), max_length=50)
    guardian_phone = models.CharField(_("অভিভাবকের মোবাইল"), max_length=20)
    is_active = models.BooleanField(_("অধ্যয়নরত"), default=True)

    class Meta:
        verbose_name = _("শিক্ষার্থী")
        verbose_name_plural = _("শিক্ষার্থীবৃন্দ")
        ordering = ['class_name', 'roll_no']

    def __str__(self):
        return f"{self.name} - {self.class_name} ({self.roll_no})"

class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name=_("শিক্ষার্থী"))
    date = models.DateField(_("তারিখ"), auto_now_add=True)
    is_present = models.BooleanField(_("উপস্থিত"), default=False)
    taken_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, verbose_name=_("শিক্ষক"))

    class Meta:
        verbose_name = _("উপস্থিতি")
        verbose_name_plural = _("উপস্থিতি রেকর্ড")
        unique_together = ('student', 'date')

    def __str__(self):
        return f"{self.student.name} - {self.date}"


class AdmissionRecord(models.Model):
    SECTION_NAZERA = 'nazera'
    SECTION_HIFZ = 'hifz'
    SECTION_CLASS_1 = 'class_1'
    SECTION_CLASS_2 = 'class_2'
    SECTION_CLASS_3 = 'class_3'
    SECTION_CLASS_4 = 'class_4'
    SECTION_CLASS_5 = 'class_5'
    SECTION_CLASS_6 = 'class_6'
    SECTION_CLASS_7 = 'class_7'
    SECTION_CLASS_8 = 'class_8'
    SECTION_CLASS_9 = 'class_9'
    SECTION_CLASS_10 = 'class_10'
    SECTION_CHOICES = (
        (SECTION_NAZERA, _('নাযেরা বিভাগ')),
        (SECTION_HIFZ, _('হিফয বিভাগ')),
        (SECTION_CLASS_1, _('প্রথম শ্রেণী')),
        (SECTION_CLASS_2, _('দ্বিতীয় শ্রেণী')),
        (SECTION_CLASS_3, _('তৃতীয় শ্রেণী')),
        (SECTION_CLASS_4, _('চতুর্থ শ্রেণী')),
        (SECTION_CLASS_5, _('পঞ্চম শ্রেণী')),
        (SECTION_CLASS_6, _('ষষ্ঠ শ্রেণী')),
        (SECTION_CLASS_7, _('সপ্তম শ্রেণী')),
        (SECTION_CLASS_8, _('অষ্টম শ্রেণী')),
        (SECTION_CLASS_9, _('নবম শ্রেণী')),
        (SECTION_CLASS_10, _('দশম শ্রেণী')),
    )

    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='admission_record',
        verbose_name=_('শিক্ষার্থী')
    )
    section = models.CharField(_('বিভাগ'), max_length=20, choices=SECTION_CHOICES)
    guardian_name = models.CharField(_('অভিভাবকের নাম'), max_length=150)
    address = models.TextField(_('ঠিকানা'), blank=True)
    admission_fee = models.DecimalField(_('ভর্তি ফি (টাকা)'), max_digits=10, decimal_places=2)
    paid_in_cash = models.BooleanField(_('ক্যাশে পরিশোধ'), default=True)
    admitted_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('ভর্তি কার্যক্রম পরিচালনাকারী শিক্ষক')
    )
    admitted_by_signature = models.CharField(_('শিক্ষকের স্বাক্ষর (নাম)'), max_length=150)
    remarks = models.TextField(_('মন্তব্য'), blank=True)
    created_at = models.DateTimeField(_('ভর্তির সময়'), auto_now_add=True)
    updated_at = models.DateTimeField(_('সর্বশেষ আপডেট'), auto_now=True)

    class Meta:
        verbose_name = _('ভর্তি রেকর্ড')
        verbose_name_plural = _('ভর্তি রেকর্ডসমূহ')
        ordering = ['-created_at']

    def __str__(self):
        section_label = dict(self.SECTION_CHOICES).get(self.section, self.section)
        return f"{self.student.name} - {section_label}"


class TeacherActivityLog(models.Model):
    ACTION_ADD_STUDENT = 'add_student'
    ACTION_REMOVE_STUDENT = 'remove_student'
    ACTION_ATTENDANCE = 'attendance'

    ACTION_CHOICES = (
        (ACTION_ADD_STUDENT, _('শিক্ষার্থী যুক্ত')),
        (ACTION_REMOVE_STUDENT, _('শিক্ষার্থী মুছে ফেলা')),
        (ACTION_ATTENDANCE, _('উপস্থিতি নেওয়া')),
    )

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('ব্যবহারকারী'))
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('শিক্ষার্থী'))
    action_type = models.CharField(_('কার্যক্রম'), max_length=20, choices=ACTION_CHOICES)
    class_name = models.CharField(_('শ্রেণী'), max_length=50, blank=True)
    note = models.CharField(_('বিস্তারিত'), max_length=255, blank=True)
    created_at = models.DateTimeField(_('সময়'), auto_now_add=True)

    class Meta:
        verbose_name = _('শিক্ষক কার্যক্রম')
        verbose_name_plural = _('শিক্ষক কার্যক্রমসমূহ')
        ordering = ['-created_at', '-id']

    def __str__(self):
        action_label = dict(self.ACTION_CHOICES).get(self.action_type, self.action_type)
        actor_name = self.actor.username if self.actor else 'Unknown'
        return f"{actor_name} - {action_label}"
