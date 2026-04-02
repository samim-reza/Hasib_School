from django.db import models
from django.utils.translation import gettext_lazy as _

class Notice(models.Model):
    title = models.CharField(_("শিরোনাম"), max_length=255)
    description = models.TextField(_("বিবরণ"))
    document = models.FileField(_("ফাইল/ছবি"), upload_to='notices/', null=True, blank=True)
    created_at = models.DateTimeField(_("প্রকাশের সময়"), auto_now_add=True)
    is_active = models.BooleanField(_("সক্রিয়"), default=True)

    class Meta:
        verbose_name = _("নোটিশ")
        verbose_name_plural = _("নোটিশসমূহ")
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class AdmissionHeadline(models.Model):
    headline = models.CharField(_('হেডলাইন'), max_length=255, default='ভর্তি চলছে - নাযেরা বিভাগ ও হিফয বিভাগে ভর্তি চলছে')
    subheadline = models.CharField(_('সাব-হেডলাইন'), max_length=255, blank=True)
    is_active = models.BooleanField(_('সক্রিয়'), default=True)
    updated_at = models.DateTimeField(_('সর্বশেষ আপডেট'), auto_now=True)

    class Meta:
        verbose_name = _('ভর্তি বিজ্ঞাপন')
        verbose_name_plural = _('ভর্তি বিজ্ঞাপনসমূহ')
        ordering = ['-updated_at']

    def __str__(self):
        return self.headline
