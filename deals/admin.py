from django.contrib import admin

import reversion

from deals.models import Funnel, Deal


class DealAdmin(reversion.VersionAdmin):
    list_display = (
        'funnel', 'title', 'owned_by', 'estimated_value', 'status',
        'created_at')
    list_display_links = ('title',)
    list_filter = ('funnel', 'status')
    raw_id_fields = ('owned_by',)
    search_fields = ('title', 'description')


admin.site.register(Funnel)
admin.site.register(Deal, DealAdmin)
