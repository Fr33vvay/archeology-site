"""Отправка еженедельного отчёта на почту."""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from accounts.weekly_report import collect_stats, format_report


class Command(BaseCommand):
    help = "Отправляет еженедельный отчёт за прошлую календарную неделю (MSK)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Отправить даже при нулевых метриках",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Не отправлять письмо, только вывести текст",
        )

    def handle(self, *args, **options):
        stats = collect_stats()
        body = format_report(stats)
        if options["dry_run"]:
            self.stdout.write(body)
            if not stats.has_activity and not options["force"]:
                self.stdout.write(self.style.WARNING("Активности нет — в обычном режиме письмо не уйдёт."))
            return

        if not stats.has_activity and not options["force"]:
            self.stdout.write("Активности нет — письмо не отправлено.")
            return

        recipients = list(getattr(settings, "WEEKLY_REPORT_RECIPIENTS", []) or [])
        if not recipients:
            self.stderr.write(self.style.ERROR("WEEKLY_REPORT_RECIPIENTS пуст."))
            return

        from datetime import timedelta

        last_day = stats.end - timedelta(seconds=1)
        subject = (
            f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '')}"
            f"Еженедельный отчёт {stats.start.strftime('%d.%m')}–"
            f"{last_day.strftime('%d.%m')}"
        )
        send_mail(
            subject=subject.strip(),
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        self.stdout.write(self.style.SUCCESS(f"Отчёт отправлен: {', '.join(recipients)}"))
