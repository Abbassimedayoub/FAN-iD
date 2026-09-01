from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered

APP_LABELS = ["identity", "organizing", "catalog", "ordering", "core"]

for app_label in APP_LABELS:
    app_config = apps.get_app_config(app_label)

    for model in app_config.get_models():
        try:
            class AutoAdmin(admin.ModelAdmin):
                list_per_page = 50

                def get_readonly_fields(self, request, obj=None):
                    fields = []
                    if any(f.name == "password" for f in self.model._meta.fields):
                        fields.append("password")
                    return fields

            admin.site.register(model, AutoAdmin)
        except AlreadyRegistered:
            pass
