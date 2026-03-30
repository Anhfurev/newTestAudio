import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agentapp.settings")
django.setup()

from support.models import CustomerIntent, Product, CustomerBalance

# Add intents
CustomerIntent.objects.get_or_create(
    intent="үлдэгдэл",
    answer="Таны гэрээний үлдэгдэл мэдээллийг шалгаж байна."
)
CustomerIntent.objects.get_or_create(
    intent="гэрээ",
    answer="Гэрээний дугаараа оруулна уу."
)
CustomerIntent.objects.get_or_create(
    intent="нөхөн төлбөр",
    answer="Нөхөн төлбөрийн мэдээлэл авах бол гэрээний дугаараа оруулна уу."
)

# Add a product
product, _ = Product.objects.get_or_create(
    name="Автомашины даатгал",
    description="Автомашины бүрэн болон хариуцлагын даатгал"
)

# Add a contract balance
CustomerBalance.objects.get_or_create(
    contract_number="12345",
    contract_balance=1500000.00
)

print("Seed data inserted!")
