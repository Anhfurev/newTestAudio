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


class ConversationState(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    awaiting_contract = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.session_id} (awaiting_contract={self.awaiting_contract})"


# Model for PDF uploads
class PDFUpload(models.Model):
    file = models.FileField(upload_to="pdfs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
