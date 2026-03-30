from django.db import models


class CustomerIntent(models.Model):
    intent = models.CharField(max_length=255, unique=True)
    answer = models.TextField()

    def __str__(self) -> str:
        return self.intent


class CustomerBalance(models.Model):
    contract_number = models.CharField(max_length=50, unique=True)
    contract_balance = models.DecimalField(max_digits=10, decimal_places=2)


    def __str__(self) -> str:
        return f"{self.contract_number}: {self.contract_balance}"

    class Meta:
        db_table = "customer_balance"
class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Бүтээгдэхүүний нэр")
    description = models.TextField(verbose_name="Дэлгэрэнгүй", blank=True)

    def __str__(self):
        return self.name

from django.db import models

class Contract(models.Model):
    contract_number = models.CharField(max_length=100, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return self.contract_number

from django.db import models

class ConversationState(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    # Add this JSON field to store the OpenAI message array
    history = models.JSONField(default=list, blank=True) 
    
    # You can delete the old fields like `awaiting_contract` if you want!


# Model for PDF uploads
from django.db import models

class ProductCertificate(models.Model):
    # Product Info
    product_name = models.CharField(max_length=255, verbose_name="Бүтээгдэхүүний нэр")
    
    # Dates (Erhiin hugatsaa)
    start_date = models.DateField(verbose_name="Эхэлсэн огноо")
    end_date = models.DateField(verbose_name="Эрх дуусах огноо")
    
    # Company Data (Extracted from PDF)
    company_name = models.CharField(max_length=255, verbose_name="Компанийн нэр")
    company_register = models.CharField(max_length=50, blank=True, null=True, verbose_name="Регистрийн дугаар")
    
    # Optional: Keep a record of the original file
    source_pdf = models.FileField(upload_to='certificates/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} - {self.company_name}"