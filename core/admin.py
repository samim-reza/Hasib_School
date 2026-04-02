from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from .models import Notice, AdmissionHeadline

admin.site.register(Notice)

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
	list_display = ('username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active')
	list_editable = ('first_name', 'last_name')
	search_fields = ('username', 'first_name', 'last_name', 'email')


@admin.register(AdmissionHeadline)
class AdmissionHeadlineAdmin(admin.ModelAdmin):
	list_display = ('headline', 'is_active', 'updated_at')
	list_filter = ('is_active', 'updated_at')
	search_fields = ('headline', 'subheadline')
