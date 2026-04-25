from django.db import models


class Order(models.Model):
    user_id = models.BigIntegerField(db_index=True)
    user_username = models.CharField(max_length=150, blank=True)
    user_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Order {self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_id = models.BigIntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    product_description = models.TextField(blank=True)
    product_category_id = models.BigIntegerField(null=True, blank=True)
    product_category_name = models.CharField(max_length=255, blank=True)
    product_category_slug = models.SlugField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def __str__(self):
        return f"{self.order_id}:{self.product_id}"
