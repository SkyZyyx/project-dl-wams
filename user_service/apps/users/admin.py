from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email")
    list_filter = ("role",)


admin.site.site_header = "Apex Motors User Control"
admin.site.site_title = "User Control"
admin.site.index_title = "User administration"
