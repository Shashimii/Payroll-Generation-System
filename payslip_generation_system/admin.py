from django.contrib import admin
from django.contrib.auth.models import User
from .models import UserRole, Employee

# Simple registration for UserRole
admin.site.register(UserRole)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('fullname', 'birthdate', 'user')
    actions = ['generate_user_accounts']

    def generate_user_accounts(self, request, queryset):
        created_count = 0
        skipped_count = 0

        for emp in queryset:
            # Skip if already linked to a user
            if emp.user:
                skipped_count += 1
                continue

            # username: fullname with spaces removed (no lowercase)
            username = emp.fullname.replace(" ", "")

            # password: birthdate as string, or defaultpass
            if emp.birthdate:
                password = str(emp.birthdate).strip()   # e.g. "2002-02-22"
            else:
                password = "defaultpass"

            # avoid duplicate usernames
            if User.objects.filter(username=username).exists():
                username = f"{username}{emp.id}"

            # create user
            user = User.objects.create(username=username)
            user.set_password(password)  # hashes the password
            user.save()

            # link to employee
            emp.user = user
            emp.save()

            # create UserRole (default to "employee")
            UserRole.objects.create(user=user, role="employee")

            created_count += 1

        # summary message
        msg = f"✅ {created_count} user(s) created."
        if skipped_count:
            msg += f" ⏭️ {skipped_count} employee(s) already had accounts."
        self.message_user(request, msg)

    generate_user_accounts.short_description = "Generate User accounts + roles for selected employees"
