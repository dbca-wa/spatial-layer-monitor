from django.contrib import admin
from django.db.models import OuterRef, Subquery
from .models import SpatialMonitor, SpatialMonitorHistory, SpatialQueue, RequestAuthentication, GeoServer


class SpatialMonitorHistoryInline(admin.TabularInline):
    model = SpatialMonitorHistory
    extra = 0
    fields = ('hash', 'created_at', 'synced_at', 'image_tag', 'purge_retry_count', 'purge_status', 'last_purge_attempt_at')
    ordering = ('-id',)
    readonly_fields = ('created_at', 'image_tag',)

    def get_queryset(self, request):
        """
        Override to limit the number of displayed entries to 5."""
        ordering = self.get_ordering(request)
        subquery = SpatialMonitorHistory.objects.filter(
            layer=OuterRef('layer')
        ).order_by('-id')[:100].values('pk')
        
        qs = super().get_queryset(request).filter(pk__in=Subquery(subquery))
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


class PurgeStatusFilter(admin.SimpleListFilter):
    title = 'purge status'
    parameter_name = 'purge_state'

    def lookups(self, request, model_admin):
        return (
            ('synced', 'Synced (Success)'),
            ('failed', 'Failed (Error/Retrying)'),
            ('pending', 'Pending (Not started)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'synced':
            return queryset.filter(synced_at__isnull=False)
        if self.value() == 'failed':
            return queryset.filter(synced_at__isnull=True, last_purge_attempt_at__isnull=False)
        if self.value() == 'pending':
            return queryset.filter(synced_at__isnull=True, last_purge_attempt_at__isnull=True)
        return queryset


@admin.register(SpatialMonitor)
class SpatialMonitorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'kmi_layer_name', 'url', 'last_checked', 'created_at', 'authentication')
    list_filter = ('last_checked', 'created_at', 'authentication')
    search_fields = ('name', 'kmi_layer_name', 'url')
    inlines = [SpatialMonitorHistoryInline]

@admin.register(SpatialMonitorHistory)
class SpatialMonitorHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer', 'hash', 'created_at', 'synced_at', 'purge_retry_count', 'purge_status', 'last_purge_attempt_at', 'purge_processing_at')
    list_filter = ('created_at', 'synced_at', PurgeStatusFilter)
    search_fields = ('id', 'layer__name','layer__kmi_layer_name' , 'hash', 'layer__url')
    ordering = ('-id',)
    # readonly_fields = ('purge_status', 'purge_retry_count', 'last_purge_attempt_at', 'purge_processing_at')


@admin.register(RequestAuthentication)
class RequestAuthenticationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'username', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'username')

    fields = ('name', 'username', 'password', 'description')

    def password(self, obj):
        return '*** CLASSIFIED *** {}'.format(obj.password)

@admin.register(GeoServer)
class GeoServerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'geoserver_group', 'endpoint_url','enabled','created_at')
    list_filter = ('geoserver_group','enabled',)

admin.site.register(SpatialQueue)
