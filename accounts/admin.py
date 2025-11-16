from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'specialty', 'workplace')
    list_filter = ('role', 'specialty')
    search_fields = ('username', 'email', 'specialty', 'workplace')
