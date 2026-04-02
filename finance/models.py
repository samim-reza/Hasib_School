from django.db import models
from django.utils.translation import gettext_lazy as _

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('income', _('আয়')),
        ('expense', _('ব্যয়')),
    )
    CATEGORY_CHOICES = (
        ('boarding', _('বোর্ডিং')),
        ('student_fees', _('স্টুডেন্ট ফি')),
        ('admission_fees', _('ভর্তি ফি')),
        ('salary', _('বেতন')),
        ('furniture', _('ফার্নিচার')),
        ('bills', _('বিল')),
        ('maintenance', _('রক্ষণাবেক্ষণ')),
        ('others', _('অন্যান্য')),
    )
    
    title = models.CharField(_("শিরোনাম"), max_length=200)
    amount = models.DecimalField(_("পরিমাণ (টাকা)"), max_digits=10, decimal_places=2)
    transaction_type = models.CharField(_("ধরন"), max_length=10, choices=TRANSACTION_TYPES)
    category = models.CharField(_("ক্যাটাগরি"), max_length=20, choices=CATEGORY_CHOICES, default='others')
    date = models.DateField(_("তারিখ"), auto_now_add=True)
    description = models.TextField(_("বিস্তারিত"), blank=True, null=True)
    receipt = models.FileField(_("রসিদ"), upload_to='receipts/', blank=True, null=True)

    class Meta:
        verbose_name = _("লেনদেন")
        verbose_name_plural = _("লেনদেনসমূহ")
        ordering = ['-date', '-id']

    def __str__(self):
        transaction_label = dict(self.TRANSACTION_TYPES).get(self.transaction_type, self.transaction_type)
        category_label = dict(self.CATEGORY_CHOICES).get(self.category, self.category)
        return f"{self.title} - {transaction_label} ({category_label}) : {self.amount} ৳"
