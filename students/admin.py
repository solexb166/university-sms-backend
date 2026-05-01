from django.contrib import admin
from .models import Student, Lecturer, Department
admin.site.register(Department)
admin.site.register(Student)
admin.site.register(Lecturer)
