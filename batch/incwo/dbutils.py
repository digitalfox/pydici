# -*- coding: UTF-8 -*-
"""
Database-related helper functions
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

def update_or_create(model, **kwargs):
    """
    Similar to get_or_create except it only uses the `id` key to locate
    existing object, and updates its fields from the kwargs if it exists.

    Returns the object and a boolean indicating whether it has been created,
    like get_or_create does.
    """
    created = False
    try:
        obj = model.objects.get(id=kwargs['id'])
        for key, value in kwargs.items():
            if key == 'id':
                continue
            setattr(obj, key, value)
    except model.DoesNotExist:
        obj = model(**kwargs)
        created = True
    obj.save()
    return obj, created


def get_list_or_create(model, **kwargs):
    """
    Create an object using kwargs if no objects match them. Similar to
    get_or_create, but does not fail if more than one object exists.

    If objects matched, returns a tuple of (object list, False)
    If no object matched, returns a tuple of ([new object], True)
    """
    lst = model.objects.filter(**kwargs)
    if lst:
        return lst, False
    obj = model(**kwargs)
    obj.save()
    return [obj], True
