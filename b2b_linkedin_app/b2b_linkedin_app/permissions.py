from django.contrib import admin

class PaidPermissionAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser or getattr(request.user, "is_paid", False)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, "is_paid", False)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def get_model_perms(self, request):
        """
        Убирает кнопку "Add" справа в админке, если нет прав на добавление
        """
        perms = super().get_model_perms(request)
        if not self.has_add_permission(request):
            perms['add'] = False
        return perms