from django.conf import settings


def ops_links(_request):
    return {
        'flower_url': getattr(settings, 'FLOWER_URL', ''),
        'enable_allauth': getattr(settings, 'ENABLE_ALLAUTH', False),
    }
