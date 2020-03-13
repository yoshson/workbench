from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User


class NoteQuerySet(models.QuerySet):
    def for_content_object(self, content_object):
        return self.filter(
            content_type=ContentType.objects.get_for_model(content_object),
            object_id=content_object.pk,
        )


class Note(models.Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("created by"),
        related_name="notes",
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"))

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    objects = NoteQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("note")
        verbose_name_plural = _("notes")

    def __str__(self):
        return self.title