from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.contrib import admin, messages
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
	list_display = ("title", "transaction_type", "category", "amount", "date")
	list_filter = ("transaction_type", "category", "date")
	date_hierarchy = "date"
	search_fields = ("title", "description")
	change_list_template = "admin/finance/transaction/change_list.html"

	def get_urls(self):
		urls = super().get_urls()
		custom_urls = [
			path(
				"history-report/",
				self.admin_site.admin_view(self.history_report_view),
				name="finance_transaction_history_report",
			),
		]
		return custom_urls + urls

	def _get_filtered_queryset(self, request):
		queryset = self.get_queryset(request).order_by("-date", "-id")
		start_date = None
		end_date = None

		start_raw = request.GET.get("start_date")
		end_raw = request.GET.get("end_date")

		if start_raw:
			try:
				start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
				queryset = queryset.filter(date__gte=start_date)
			except ValueError:
				messages.error(request, "শুরুর তারিখ সঠিক ফরম্যাটে দিন (YYYY-MM-DD)।")

		if end_raw:
			try:
				end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
				queryset = queryset.filter(date__lte=end_date)
			except ValueError:
				messages.error(request, "শেষের তারিখ সঠিক ফরম্যাটে দিন (YYYY-MM-DD)।")

		return queryset, start_date, end_date

	def _summary(self, queryset):
		income = sum((tx.amount for tx in queryset if tx.transaction_type == "income"), Decimal("0.00"))
		expense = sum((tx.amount for tx in queryset if tx.transaction_type == "expense"), Decimal("0.00"))
		category_totals = {}
		for tx in queryset:
			label = tx.get_category_display()
			category_totals[label] = category_totals.get(label, Decimal("0.00")) + tx.amount
		return {
			"income": income,
			"expense": expense,
			"balance": income - expense,
			"count": queryset.count(),
			"category_totals": category_totals,
		}

	def history_report_view(self, request):
		queryset, start_date, end_date = self._get_filtered_queryset(request)
		summary = self._summary(queryset)

		if request.GET.get("export") == "pdf":
			return self._export_pdf(queryset, summary, start_date, end_date)

		context = {
			**self.admin_site.each_context(request),
			"opts": self.model._meta,
			"title": "Financial History Report",
			"transactions": queryset,
			"start_date": start_date,
			"end_date": end_date,
			"summary": summary,
		}
		return TemplateResponse(request, "admin/finance/transaction/history_report.html", context)

	def _export_pdf(self, queryset, summary, start_date, end_date):
		date_label = timezone.localdate().strftime("%Y-%m-%d")
		response = HttpResponse(content_type="application/pdf")
		response["Content-Disposition"] = f'attachment; filename="financial-history-{date_label}.pdf"'

		buffer = BytesIO()
		doc = Canvas(buffer, pagesize=A4)
		page_width, page_height = A4
		y = page_height - 20 * mm

		def write_line(text, x=18 * mm, size=10, dy=7 * mm):
			nonlocal y
			doc.setFont("Helvetica", size)
			doc.drawString(x, y, text)
			y -= dy

		write_line("Hasib International Islamic Academy", size=14, dy=8 * mm)
		write_line("Financial History Report", size=12)

		range_text = "Date Range: All"
		if start_date and end_date:
			range_text = f"Date Range: {start_date} to {end_date}"
		elif start_date:
			range_text = f"Date Range: From {start_date}"
		elif end_date:
			range_text = f"Date Range: Up to {end_date}"
		write_line(range_text)
		write_line(f"Generated On: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}")
		y -= 3 * mm

		write_line(f"Total Transactions: {summary['count']}")
		write_line(f"Total Income: BDT {summary['income']}")
		write_line(f"Total Expense: BDT {summary['expense']}")
		write_line(f"Balance: BDT {summary['balance']}")

		y -= 2 * mm
		doc.line(15 * mm, y, page_width - 15 * mm, y)
		y -= 6 * mm

		doc.setFont("Helvetica-Bold", 9)
		doc.drawString(18 * mm, y, "Date")
		doc.drawString(45 * mm, y, "Type")
		doc.drawString(75 * mm, y, "Category")
		doc.drawString(112 * mm, y, "Title")
		doc.drawString(160 * mm, y, "Amount")
		y -= 5 * mm
		doc.setFont("Helvetica", 9)

		for tx in queryset:
			if y < 22 * mm:
				doc.showPage()
				y = page_height - 20 * mm
				doc.setFont("Helvetica-Bold", 9)
				doc.drawString(18 * mm, y, "Date")
				doc.drawString(45 * mm, y, "Type")
				doc.drawString(75 * mm, y, "Category")
				doc.drawString(112 * mm, y, "Title")
				doc.drawString(160 * mm, y, "Amount")
				y -= 5 * mm
				doc.setFont("Helvetica", 9)

			title = tx.title if len(tx.title) <= 24 else f"{tx.title[:21]}..."
			category = tx.get_category_display()
			doc.drawString(18 * mm, y, tx.date.strftime("%Y-%m-%d"))
			doc.drawString(45 * mm, y, tx.get_transaction_type_display())
			doc.drawString(75 * mm, y, category)
			doc.drawString(112 * mm, y, title)
			doc.drawRightString(196 * mm, y, f"BDT {tx.amount}")
			y -= 5 * mm

		doc.showPage()
		doc.save()
		response.write(buffer.getvalue())
		buffer.close()
		return response
