from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User as AuthUser
from .models import Student, Teacher, Attendance, AdmissionRecord, TeacherActivityLog

admin.site.register(Student)
admin.site.register(Attendance)


class TeacherAdminForm(forms.ModelForm):
	username = forms.CharField(label='ইউজারনেম', max_length=150, help_text='শিক্ষকের লগইন ইউজারনেম (ইউনিক হতে হবে)।')

	class Meta:
		model = Teacher
		fields = ('name', 'phone', 'subject')

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance and self.instance.pk and self.instance.user_id:
			self.fields['username'].initial = self.instance.user.username

	def clean_username(self):
		username = self.cleaned_data['username'].strip().lower()
		queryset = AuthUser.objects.filter(username=username)
		if self.instance and self.instance.pk and self.instance.user_id:
			queryset = queryset.exclude(pk=self.instance.user_id)
		if queryset.exists():
			raise ValidationError('এই ইউজারনেম ইতোমধ্যে ব্যবহৃত হয়েছে।')
		return username


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
	form = TeacherAdminForm
	fields = ('username', 'name', 'phone', 'subject')
	list_display = ('name', 'username_display', 'phone', 'subject')
	search_fields = ('name', 'phone', 'subject', 'user__username')
	list_select_related = ('user',)

	@admin.display(description='ইউজারনেম')
	def username_display(self, obj: Teacher) -> str:
		return obj.user.username

	def save_model(self, request, obj: Teacher, form, change):
		username = form.cleaned_data['username']
		if change:
			user = obj.user
			user.username = username
			user.first_name = obj.name
			user.is_staff = True
			user.save(update_fields=['username', 'first_name', 'is_staff'])
		else:
			user = AuthUser.objects.create_user(
				username=username,
				password='default123',
				first_name=obj.name,
				is_staff=True,
				is_active=True,
			)
			obj.user = user

		super().save_model(request, obj, form, change)

		if not change:
			self.message_user(request, f'শিক্ষক তৈরি হয়েছে। ইউজার: {username}, ডিফল্ট পাসওয়ার্ড: default123')


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
