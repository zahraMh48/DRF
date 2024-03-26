from rest_framework import permissions
import copy

class IsAdminUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.method in permissions.SAFE_METHODS or (request.user and request.user.is_staff))
        # we have 3 safe methods: GET, HEAD, OPTIONS
    
class SendPrivateEmailToCustomerPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.has_perm('store.send_private_email'))

class CustomDjangoModelPermissions(permissions.DjangoModelPermissions):
    def __init__(self):
        self.perms_map = copy.deepcopy(self.perms_map) # DjangoModelPermissions doesent change in real path
        self.perms_map['GET'] = ['%(app_label)s.view_%(model_name)s']

