# coding: utf-8

"""
Test data factories for core module

@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django.contrib.contenttypes.models import ContentType

from factory.django import DjangoModelFactory
import factory
import factory.fuzzy

from core.models import TagCategory, Tag, TaggedItem
from leads.models import Lead
from people.models import Consultant


class TagFactory(DjangoModelFactory):
    name = factory.Faker("word")
    category = factory.fuzzy.FuzzyChoice(TagCategory.objects.all())
    class Meta:
        model = "core.Tag"


class TaggedLeadFactory(DjangoModelFactory):
    tag = factory.fuzzy.FuzzyChoice(Tag.objects.all())
    content_type = ContentType.objects.get(model='Lead')
    object_id = factory.fuzzy.FuzzyChoice(Lead.objects.all().values_list('id', flat=True))
    class Meta:
        model = "core.TaggedItem"

class TaggedConsultantFactory(DjangoModelFactory):
    tag = factory.fuzzy.FuzzyChoice(Tag.objects.all())
    content_type = ContentType.objects.get(model='Consultant')
    object_id = factory.fuzzy.FuzzyChoice(Consultant.objects.all().values_list('id', flat=True))
    level = factory.fuzzy.FuzzyChoice([i[0] for i in TaggedItem.TAG_LEVEL_TYPES])
    nature = factory.fuzzy.FuzzyChoice([i[0] for i in TaggedItem.TAG_NATURE_TYPES])
    class Meta:
        model = "core.TaggedItem"
