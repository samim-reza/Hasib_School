from django.db import models
from django.utils.translation import gettext_lazy as _

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('income', _('আয়')),
        ('expense', _('ব্যয়')),
    )
    
    title = models.CharField(_("শিরোনাম"), max_length=200)
    amount = models.DecimalField(_("পরিমাণ (টাকা)"), max_digits=10, decimal_places=2)
    transaction_type = models.CharField(_("ধরন"), max_length=10, choices=TRANSACTION_TYPES)
    date = models.DateField(_("তারিখ"), auto_now_add=True)
    description = models.TextField(_("বিস্তারিত"), blank=True, null=True)
    receipt = models.FileField(_("রসিদ"), upload_to='receipts/', blank=True, null=True)

    class Meta:
        verbose_name = _("লেনদেন")
        verbose_name_plural = _("লেনদেনসমূহ")
        ordering = ['-date', '-id']

    def __str__(self):
        transaction_label = dict(self.TRANSACTION_TYPES).get(self.transaction_type, self.transaction_type)
        return f"{self.title} - {transaction_label} : {self.amount} ৳"
