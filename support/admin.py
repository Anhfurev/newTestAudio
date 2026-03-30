from django.contrib import admin

from .models import ConversationState, CustomerBalance, CustomerIntent


@admin.register(CustomerIntent)
class CustomerIntentAdmin(admin.ModelAdmin):
    list_display = ("intent",)
    search_fields = ("intent",)


@admin.register(CustomerBalance)
class CustomerBalanceAdmin(admin.ModelAdmin):
    list_display = ("contract_number", "contract_balance")
    search_fields = ("contract_number",)


@admin.register(ConversationState)
class ConversationStateAdmin(admin.ModelAdmin):
    search_fields = ("session_id",)
