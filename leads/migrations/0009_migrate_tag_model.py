from django.db import migrations


def migrate_tags(apps, schema_editor):
    """Migrate from old taggit default model to new custom one"""
    LegacyTaggedItem = apps.get_model('taggit', 'TaggedItem')
    Tag = apps.get_model('core', 'Tag')
    TaggedItem = apps.get_model('core', 'TaggedItem')

    for legacy_tagged_item in LegacyTaggedItem.objects.all():
        tag, created = Tag.objects.get_or_create(name=legacy_tagged_item.tag.name, slug=legacy_tagged_item.tag.slug)
        TaggedItem.objects.get_or_create(content_type=legacy_tagged_item.content_type, object_id=legacy_tagged_item.object_id, tag=tag)

def empty_old_tag_tables(apps, schema_editor):
    LegacyTaggedItem = apps.get_model('taggit', 'TaggedItem')
    LegacyTag = apps.get_model('taggit', 'Tag')

    LegacyTaggedItem.objects.all().delete()
    LegacyTag.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0008_alter_lead_tags'),
    ]

    operations = [
        migrations.RunPython(migrate_tags),
        migrations.RunPython(empty_old_tag_tables)
    ]
