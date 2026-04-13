from django.contrib import admin
from .models import ApartmentLead, ConversationState, CustomerBalance, Intent, IntentDetail

# 1. IntentDetail-ийг Intent дотор нь харагдуулах (Inline)
class IntentDetailInline(admin.TabularInline):
    model = IntentDetail
    extra = 1  # Шинээр нэмэх 1 хоосон мөр үргэлж харуулна
    fields = ("answer", "alternative_intent", "source_pdf")

# 2. Үндсэн Intent Admin
@admin.register(Intent)
class IntentAdmin(admin.ModelAdmin):
    list_display = ("id", "intent_name", "created_date")
    search_fields = ("intent_name",)
    inlines = [IntentDetailInline] # Энэ мөрөөр 2 хүснэгтийг нэг цонхонд харуулна

# 3. Бусад моделиуд (Хэвээрээ)
@admin.register(CustomerBalance)
class CustomerBalanceAdmin(admin.ModelAdmin):
    list_display = ("contract_number", "contract_balance")
    search_fields = ("contract_number",)

@admin.register(ConversationState)
class ConversationStateAdmin(admin.ModelAdmin):
    # 'updated_at' гэдгийг хасаж, зөвхөн 'session_id'-г үлдээнэ
    list_display = ("session_id",) 
    search_fields = ("session_id",)


@admin.register(ApartmentLead)
class ApartmentLeadAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_name", "status", "agent_name", "created_at")
    search_fields = ("title", "owner_name", "owner_phone", "location")
    list_filter = ("status", "created_at")