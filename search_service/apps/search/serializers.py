from rest_framework import serializers


class IndexRequestSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_image_id = serializers.IntegerField(required=False, allow_null=True)
    image = serializers.ImageField(required=True)


class SearchRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=20, default=5)
    score_threshold = serializers.FloatField(required=False, allow_null=True)


class SearchMatchSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_image_id = serializers.IntegerField(required=False, allow_null=True)
    qdrant_id = serializers.CharField()
    score = serializers.FloatField()
