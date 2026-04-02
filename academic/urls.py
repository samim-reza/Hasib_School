from django.urls import path
from . import views

app_name = 'academic'
urlpatterns = [
    path('', views.home_view, name='home'),
    path('health/', views.health_check, name='health_check'),
    path('logout/', views.account_logout, name='account_logout'),
    path('teacher/login/', views.teacher_login, name='teacher_login'),
    path('super_admin/', views.super_admin_login, name='super_admin_login'),
    path('super_admin/dashboard/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('super_admin/logout/', views.super_admin_logout, name='super_admin_logout'),
    path('teacher/', views.teacher_portal, name='teacher_portal'),
    path('teacher/change-password/', views.teacher_change_password, name='teacher_change_password'),
    path('teacher/attendance-history/', views.attendance_history, name='attendance_history'),
    path('teacher/manage-teachers/', views.teacher_management, name='teacher_management'),
    path('teacher/manage-teachers/<int:teacher_id>/update-name/', views.teacher_update_name, name='teacher_update_name'),
    path('teacher/manage-teachers/<int:teacher_id>/update-username/', views.teacher_update_username, name='teacher_update_username'),
    path('teacher/manage-teachers/<int:teacher_id>/remove/', views.teacher_remove, name='teacher_remove'),
    path('teacher/admin-account/', views.admin_account_settings, name='admin_account_settings'),
    path('teacher/admissions/', views.admission_portal, name='admission_portal'),
    path('teacher/admissions/new/', views.admission_create, name='admission_create'),
    path('teacher/admissions/<int:admission_id>/edit/', views.admission_edit, name='admission_edit'),
    path('teacher/admissions/<int:admission_id>/print/', views.admission_print, name='admission_print'),
    path('teacher/take_attendance/', views.take_attendance, name='take_attendance'),
    path('teacher/add_student/', views.add_student, name='add_student'),
    path('teacher/remove_student/<int:student_id>/', views.remove_student, name='remove_student'),
]
