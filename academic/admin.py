from django.contrib import admin
from .models import Student, Teacher, Attendance, AdmissionRecord, TeacherActivityLog

admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Attendance)


@admin.register(AdmissionRecord)
class AdmissionRecordAdmin(admin.ModelAdmin):
	list_display = ('student', 'section', 'admission_fee', 'paid_in_cash', 'admitted_by_signature', 'created_at')
	list_filter = ('section', 'paid_in_cash', 'created_at')
	search_fields = ('student__name', 'student__roll_no', 'guardian_name', 'admitted_by_signature')


@admin.register(TeacherActivityLog)
class TeacherActivityLogAdmin(admin.ModelAdmin):
	list_display = ('created_at', 'actor', 'action_type', 'student', 'class_name', 'note')
	list_filter = ('action_type', 'class_name', 'created_at')
	search_fields = ('actor__username', 'student__name', 'student__roll_no', 'note')
