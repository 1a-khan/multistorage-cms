from django.db.models import Q

from .models import ProjectHub


def user_hubs(request):
    if not request.user.is_authenticated:
        return {'nav_hubs': []}

    hubs = ProjectHub.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct().order_by('name')
    return {'nav_hubs': hubs}
