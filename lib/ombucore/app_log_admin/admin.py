from app_log.models import AppLogEntry, Subscription
from ombucore.admin.sites import site as admin_site
from ombucore.app_log_admin.modeladmin import AppLogEntryModelAdmin, SubscriptionModelAdmin

admin_site.register(AppLogEntry, AppLogEntryModelAdmin)
admin_site.register(Subscription, SubscriptionModelAdmin)
