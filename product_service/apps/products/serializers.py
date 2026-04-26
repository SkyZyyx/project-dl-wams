from rest_framework import serializers

from .models import Category, Product, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")
        extra_kwargs = {"slug": {"required": False}}


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = (
            "id",
            "image_url",
            "thumbnail_b64",
            "is_primary",
            "indexed",
            "qdrant_id",
            "uploaded_at",
        )

    def get_image_url(self, obj):
        request = self.context.get("request")
        if not obj.image:
            return None
        url = obj.image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    seller_username = serializers.CharField(read_only=True)
    image_files = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "description",
            "price",
            "category",
            "category_id",
            "created_at",
            "seller_username",
            "images",
            "image_files",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        image_files = attrs.get("image_files") or []
        if self.instance is None and len(image_files) < 5:
            raise serializers.ValidationError({"image_files": "Provide at least 5 images when creating a product."})
        return attrs

    def create(self, validated_data):
        image_files = validated_data.pop("image_files", [])
        request = self.context.get("request")
        username = ""
        if request is not None and getattr(request.user, "is_authenticated", False):
            username = str(getattr(request.user, "username", "") or "")
            if not username:
                token = getattr(request.user, "token", None)
                if token is not None:
                    username = str(token.get("username", "") or "")
        product = Product.objects.create(seller_username=username, **validated_data)
        for index, image_file in enumerate(image_files):
            ProductImage.objects.create(product=product, image=image_file, is_primary=index == 0)
        return product


class ProductImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("image", "is_primary")
