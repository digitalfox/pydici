# -*- coding: UTF-8 -*-

"""
Use Apache http authentication to login with Django auth system
Stolen from patch http://code.djangoproject.com/ticket/689
Will be included in Django 1.1
"""

from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend

class RemoteUserAuthMiddleware(object):
    def process_request(self, request):
        from django.contrib.auth import authenticate, login
        # AuthenticationMiddleware is required to create request.user
        error = """The Django RemoteUserAuth middleware requires authentication middleware to be installed. Edit your MIDDLEWARE_CLASSES
setting to insert 'django.contrib.auth.middleware.AuthenticationMiddleware' *before* the RemoteUserMiddleware class."""
        assert hasattr(request, 'user'), error
        if request.user.is_anonymous():
            user = None
            try:
                user = authenticate(username=request.META['REMOTE_USER'])
            except KeyError:
                pass # No remote user available
            if user is not None:
                request.user = user    # set request.user to the authenticated user
                login(request, user)   # auto-login the user to Django
        return None

class RemoteUserAuthBackend(ModelBackend):

    def authenticate(self, username, password=None):
        """
        Authenticate user - RemoteUserAuth middleware passes REMOTE_USER
        as username.
        """
        if password is not None:
            return None
        user = None
        if username:
            username = self.parse_user(username)
            try:
                user = User.objects.get(username=username)
		file("/tmp/log", "w").write("coucou")
            except User.DoesNotExist:
                user = self.unknown_user(username)
                user = self.configure_user(user)
        return user

    def parse_user(self, username):
        """ Parse the provided username.
        Override this method if you need to do special things with the
        username, like stripping @realm or cleaning something like
        cn=x,dc=sas,etc.
        """
        return username

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def unknown_user(self, username):
        """Auto-create user. Called only if User object doesn't already exist
        for username.
        """
        user = User.objects.create_user(username, '')
        user.is_staff = False
        user.save()
        return user

    def configure_user(self, user):
        """ Configure a user after login.
        i.e: to read group membership from LDAP and so on.
        Called only if user User object has just been created."
        """
        return user
