from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _, ugettext

from accounts.models import User
from contacts.models import Organization, Person
from tools.formats import local_date_format, pretty_due, markdownify
from tools.models import SearchQuerySet, Model
from tools.urls import model_urls


class ProjectQuerySet(SearchQuerySet):
    pass


@model_urls()
class Project(Model):
    ACQUISITION = 10
    WORK_IN_PROGRESS = 20
    FINISHED = 30
    DECLINED = 40

    STATUS_CHOICES = (
        (ACQUISITION, _('Acquisition')),
        (WORK_IN_PROGRESS, _('Work in progress')),
        (FINISHED, _('Finished')),
        (DECLINED, _('Declined')),
    )

    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_('customer'),
        related_name='+')
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('contact'),
        related_name='+')

    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('owned by'),
        related_name='+')

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=ACQUISITION)

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    invoicing = models.BooleanField(
        _('invoicing'),
        default=True,
        help_text=_('This project is eligible for invoicing.'))
    maintenance = models.BooleanField(
        _('maintenance'),
        default=False,
        help_text=_('This project is used for maintenance work.'))

    _code = models.IntegerField(_('code'))

    objects = models.Manager.from_queryset(ProjectQuerySet)()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('project')
        verbose_name_plural = _('projects')

    def __str__(self):
        return self.title

    def __html__(self):
        return format_html(
            '<small>{}</small> {}',
            self.code,
            self.title)

    @property
    def code(self):
        return '%s-%04d' % (
            self.created_at.year,
            self._code)

    def save(self, *args, **kwargs):
        if not self.pk:
            self._code = RawSQL(
                'SELECT COALESCE(MAX(_code), 0) + 1 FROM projects_project'
                ' WHERE EXTRACT(year FROM created_at) = %s',
                (timezone.now().year,),
            )
        super().save(*args, **kwargs)
    save.alters_data = True

    def status_css(self):
        return {
            self.ACQUISITION: 'success',
            self.WORK_IN_PROGRESS: 'info',
            self.FINISHED: 'default',
            self.DECLINED: 'warning',
        }[self.status]

    @cached_property
    def overview(self):
        # Avoid circular imports
        from logbook.models import LoggedHours
        from offers.models import Service

        return {
            'logged': LoggedHours.objects.filter(
                task__project=self,
            ).order_by().aggregate(h=Sum('hours'))['h'] or Decimal(),
            'approved': sum(
                (service.approved_hours for service in Service.objects.filter(
                    offer__project=self)),
                Decimal()),
        }

    def pretty_status(self):
        parts = [self.get_status_display()]
        if not self.invoicing:
            parts.append(ugettext('no invoicing'))
        if self.maintenance:
            parts.append(ugettext('maintenance'))
        return ', '.join(parts)


@model_urls()
class Task(Model):
    INBOX = 10
    BACKLOG = 20
    IN_PROGRESS = 30
    READY_FOR_TEST = 40
    DONE = 50

    STATUS_CHOICES = (
        (INBOX, _('Inbox')),
        (BACKLOG, _('Backlog')),
        (IN_PROGRESS, _('In progress')),
        (READY_FOR_TEST, _('Ready for test')),
        (DONE, _('Done')),
    )

    TASK = 'task'
    BUG = 'bug'
    ENHANCEMENT = 'enhancement'
    QUESTION = 'question'

    TYPE_CHOICES = (
        (TASK, _('Task')),
        (BUG, _('Bug')),
        (ENHANCEMENT, _('Enhancement')),
        (QUESTION, _('Question')),
    )

    BLOCKER = 50
    HIGH = 40
    NORMAL = 30
    LOW = 20

    PRIORITY_CHOICES = (
        (BLOCKER, _('Blocker')),
        (HIGH, _('High')),
        (NORMAL, _('Normal')),
        (LOW, _('Low')),
    )

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('created by'),
        related_name='+')

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_('project'),
        related_name='tasks')
    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    type = models.CharField(
        _('type'),
        max_length=20,
        choices=TYPE_CHOICES,
        default=TASK,
    )
    priority = models.PositiveIntegerField(
        _('priority'),
        choices=PRIORITY_CHOICES,
        default=NORMAL,
    )
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('owned by'),
        related_name='+')

    service = models.ForeignKey(
        'offers.Service',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('service'),
        related_name='tasks',
    )

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=INBOX)
    closed_at = models.DateTimeField(
        _('closed at'),
        blank=True,
        null=True)

    due_on = models.DateField(
        _('due on'),
        blank=True,
        null=True,
        help_text=_('This field should be left empty most of the time.'))

    position = models.PositiveIntegerField(_('position'), default=0)
    _code = models.IntegerField(_('code'))

    class Meta:
        ordering = ('pk',)
        verbose_name = _('task')
        verbose_name_plural = _('tasks')

    def __str__(self):
        return self.title

    def __html__(self):
        return format_html(
            '<small>{}</small> {}',
            self.code,
            self.title,
        )

    @property
    def code(self):
        return '#%s' % self._code

    def save(self, *args, **kwargs):
        if not self.pk:
            self._code = RawSQL(
                'SELECT COALESCE(MAX(_code), 0) + 1 FROM projects_task'
                ' WHERE project_id=%s',
                (self.project_id,),
            )
        super().save(*args, **kwargs)
    save.alters_data = True

    def description_html(self):
        return markdownify(self.description) if self.description else '–'

    def pretty_status(self):
        if self.status == self.DONE:
            return _('Done since %(closed_on)s') % {
                'closed_on': local_date_format(self.closed_at, 'd.m.Y'),
            }

        elif self.due_on:
            return _('%(status)s (%(pretty_due)s)') % {
                'status': self.get_status_display(),
                'pretty_due': pretty_due(self.due_on),
            }

        return self.get_status_display()

    def type_css(self):
        return {
            self.TASK: '',
            self.BUG: 'glyphicon glyphicon-exclamation-sign icon-red',
            self.ENHANCEMENT: 'glyphicon glyphicon-plus-sign icon-green',
            self.QUESTION: 'glyphicon glyphicon-question-sign icon-blue',
        }[self.type]

    def priority_css(self):
        return {
            self.BLOCKER: 'label label-danger',
            self.HIGH: 'label label-warning',
            self.NORMAL: 'label label-info',
            self.LOW: 'label label-default',
        }[self.priority]

    @cached_property
    def overview(self):
        from logbook.models import LoggedHours
        if not self.service:
            return {}

        hours_per_task = {
            row['task']: row['hours__sum']
            for row in LoggedHours.objects.filter(
                task__service=self.service,
            ).order_by().values('task').annotate(Sum('hours'))
        }

        return {
            'logged_this': hours_per_task.get(self.pk),
            'logged_tasks': sum(hours_per_task.values(), Decimal()),
            'approved': self.service.approved_hours,
        }


class Attachment(Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('task'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    title = models.CharField(
        _('title'),
        max_length=200,
        blank=True,
    )
    file = models.FileField(
        _('file'),
        upload_to='attachments/%Y/%m',
    )

    class Meta:
        ordering = ('created_at',)
        verbose_name = _('attachment')
        verbose_name_plural = _('attachments')

    def __str__(self):
        return self.title or self.file.name


@model_urls(default='update')
class Comment(Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('task'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('created by'),
        related_name='+')
    notes = models.TextField(
        _('notes'),
    )

    class Meta:
        ordering = ('created_at',)
        verbose_name = _('comment')
        verbose_name_plural = _('comments')

    def notes_html(self):
        return markdownify(self.notes)

    def __str__(self):
        return self.notes[:30] + '...'
