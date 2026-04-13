from django.conf import settings
from django.db import models  # pyright: ignore[reportMissingImports]

# 1. Даатгалын бүтээгдэхүүний каталог

class InsuranceProduct(models.Model):
    category = models.CharField(max_length=100, help_text="Жишээ нь: Тээврийн хэрэгсэл")
    name = models.CharField(max_length=200, help_text="Жишээ нь: КАСКО даатгал")
    icon = models.CharField(max_length=10, blank=True, null=True, help_text="Жишээ нь: 🚗")
    is_active = models.BooleanField(default=True, help_text="Идэвхтэй зардаг эсэх")

    def __str__(self):
        return f"{self.category} - {self.name}"

    class Meta:
        db_table = "support_insuranceproduct"
class Intent(models.Model):
    # intentid: PK (Django 'id' гэж автоматаар үүсгэнэ)
    intent_name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.intent_name

# 2-р хүснэгт: Дэлгэрэнгүй мэдээлэл (Хүү)
class IntentDetail(models.Model):
    # detailid: PK (Django 'id' гэж автоматаар үүсгэнэ)
    # intentid: FK (Intent хүснэгттэй холбож байна)
    intent = models.ForeignKey(Intent, on_delete=models.CASCADE, related_name="details")
    
    answer = models.TextField()  # PDF-ээс олж авсан хариулт
    alternative_intent = models.JSONField(default=list, blank=True) # JSON бүтэц
    
    # PDF-ийн мэдээллээ хадгалах хэсэг
    source_pdf = models.CharField(max_length=255, blank=True, null=True)
    class Meta:
        indexes = [
            models.Index(fields=['alternative_intent']), # 👈 Ингэж индекс нэмдэг
        ]
    def __str__(self):
        return f"Detail for {self.intent.intent_name}"
# 2. Хэрэглэгчийн гэрээний үлдэгдэл болон хугацаа
class CustomerBalance(models.Model):
    contract_number = models.CharField(max_length=50, unique=True)
    contract_balance = models.DecimalField(max_digits=10, decimal_places=2)
    # Төлбөрт хамаарах даатгалын хугацаа
    coverage_start = models.DateField(help_text="Даатгал эхлэх огноо")
    coverage_end = models.DateField(help_text="Даатгал дуусах огноо")
    last_payment_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.contract_number}: {self.contract_balance}"

    class Meta:
        db_table = "customer_balance"

# 3. Тусгай зорилго болон хариултууд (Intent Management)
class CustomerIntent(models.Model):
    intent = models.CharField(max_length=255, unique=True)
    answer = models.TextField()

    def __str__(self) -> str:
        return self.intent

# 4. Чатны түүх хадгалах (Session State)
class ConversationState(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    history = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Session: {self.session_id}"


class ApartmentLead(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"

    owner_name = models.CharField(max_length=120)
    owner_phone = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    bedrooms = models.PositiveIntegerField(default=1)
    area_sqm = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apartment_leads",
    )
    agent_name = models.CharField(max_length=120, blank=True)
    agent_phone = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    class Meta:
        ordering = ["-created_at"]