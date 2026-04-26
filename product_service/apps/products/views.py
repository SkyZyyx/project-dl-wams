from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product, ProductImage
from .permissions import ProductOwnerOrAdminPermission, SellerOrAdminWritePermission
from .serializers import (
    CategorySerializer,
    ProductImageSerializer,
    ProductImageUploadSerializer,
    ProductSerializer,
)


class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [SellerOrAdminWritePermission]


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [SellerOrAdminWritePermission]


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [SellerOrAdminWritePermission]

    def get_queryset(self):
        queryset = Product.objects.select_related("category").prefetch_related("images")
        ids = self.request.query_params.get("ids")
        if ids:
            id_list = [int(value) for value in ids.split(",") if value.strip().isdigit()]
            if id_list:
                queryset = queryset.filter(id__in=id_list)
        return queryset


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [ProductOwnerOrAdminPermission]

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("images")


class ProductImageListCreateView(APIView):
    permission_classes = [SellerOrAdminWritePermission]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk):
        product = get_object_or_404(Product.objects.prefetch_related("images"), pk=pk)
        serializer = ProductImageSerializer(product.images.all(), many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        checker = ProductOwnerOrAdminPermission()
        if not checker.has_object_permission(request, self, product):
            return Response({"detail": "You do not have permission to modify this product."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProductImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save(product=product)
        output = ProductImageSerializer(image, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)
