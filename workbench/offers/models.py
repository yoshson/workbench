from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User
from workbench.projects.models import Project
from workbench.tools.formats import currency, local_date_format
from workbench.tools.models import ModelWithTotal, SearchQuerySet, Z
from workbench.tools.urls import model_urls


class OfferQuerySet(SearchQuerySet):
    pass


@model_urls
class Offer(ModelWithTotal):
    IN_PREPARATION = 10
    OFFERED = 20
    ACCEPTED = 30
    REJECTED = 40
    REPLACED = 50

    STATUS_CHOICES = (
        (IN_PREPARATION, _("In preparation")),
        (OFFERED, _("Offered")),
        (ACCEPTED, _("Accepted")),
        (REJECTED, _("Rejected")),
        (REPLACED, _("Replaced")),
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_("project"),
        related_name="offers",
    )

    offered_on = models.DateField(_("offered on"), blank=True, null=True)
    closed_on = models.DateField(_("closed on"), blank=True, null=True)

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("owned by"), related_name="+"
    )

    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=IN_PREPARATION
    )

    postal_address = models.TextField(_("postal address"), blank=True)
    _code = models.IntegerField(_("code"))

    objects = OfferQuerySet.as_manager()

    class Meta:
        ordering = ("-offered_on",)
        verbose_name = _("offer")
        verbose_name_plural = _("offers")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.project.urls["services"]

    def save(self, *args, **kwargs):
        new = False
        if not self.pk:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM offers_offer"
                " WHERE project_id = %s",
                (self.project_id,),
            )
            new = True
        super().save(*args, **kwargs)
        if new:
            self.refresh_from_db()

    save.alters_data = True

    @property
    def code(self):
        return "%s-o%02d" % (self.project.code, self._code)

    def _calculate_total(self):
        self.subtotal = sum(
            (service.service_cost for service in self.services.all()), Z
        )
        super()._calculate_total()

    def clean(self):
        super().clean()

        if self.status in (self.OFFERED, self.ACCEPTED, self.REJECTED):
            if not self.offered_on:
                raise ValidationError(
                    {"status": _("Offered on date missing for selected state.")}
                )

    def pretty_status(self):
        if self.status == self.IN_PREPARATION:
            return _("In preparation since %(created_at)s") % {
                "created_at": local_date_format(self.created_at, "d.m.Y")
            }
        elif self.status == self.OFFERED:
            return _("Offered on %(offered_on)s") % {
                "offered_on": local_date_format(self.offered_on, "d.m.Y")
            }
        elif self.status in (self.ACCEPTED, self.REJECTED):
            return _("%(status)s on %(closed_on)s") % {
                "status": self.get_status_display(),
                "closed_on": local_date_format(self.closed_on, "d.m.Y"),
            }
        return self.get_status_display()

    def status_css(self):
        return {
            self.IN_PREPARATION: "info",
            self.OFFERED: "success",
            self.ACCEPTED: "default",
            self.REJECTED: "danger",
            self.REPLACED: "",
        }[self.status]

    @property
    def total_title(self):
        return _("total CHF incl. tax") if self.liable_to_vat else _("total CHF")

    def short_total_excl(self):
        parts = [gettext("%s excl. tax") % currency(self.total_excl_tax)]
        if self.discount:
            parts.append(" - %s %s" % (currency(self.discount), gettext("discount")))
        return "".join(parts)
