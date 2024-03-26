from django.shortcuts import get_object_or_404
from django.db.models import Count, Prefetch

from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView # its combine with listmodelmixin and createmodelmixin
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet # just list and retrive
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, DestroyModelMixin
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend


from .models import Comment, OrderItem, Product, Category, Cart, CartItem, Customer, Order
from .serializers import OrderForAdminSerializer, OrderItemSerializer, OrderSerializer, ProductSerializer, CategorySerializer, CommentSerializer, CartSerializer, CartItemSerializer, AddCartItemSerializer, UpdateCartItemSerializer, CustomerSerializer, OrderCreateSerializer, OrderUpdateSerializer
from .filters import ProductFilter
from .paginations import DefaultPagination
from .permissions import IsAdminUserOrReadOnly, SendPrivateEmailToCustomerPermission, CustomDjangoModelPermissions
from .signals import order_created

class ProductViewSet(ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['name', 'unit_price', 'inventory']
    search_fields = ['name', 'category__title']
    pagination_class = DefaultPagination
    # filterset_fields = ['category_id', 'inventory']
    filterset_class = ProductFilter
    permission_classes = [CustomDjangoModelPermissions]

    # def get_queryset(self):
    #     queryset = Product.objects.all()
    #     category_id_parameter = self.request.query_params.get('category_id')  # query_params is everything in url
    #     if category_id_parameter is not None:
    #         queryset = queryset.filter(category_id=category_id_parameter)
    #     return queryset

    def get_serializer_context(self):
        return {'request':self.request}

    def destroy(self, request, pk):
        product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
        if product.order_items.count() > 0:
            return Response({'error':'There is some order items including this product. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class CategoryViewSet(ModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.prefetch_related('products').all()
    permission_classes = [IsAdminUserOrReadOnly]

    def delete(self, request, pk):
        category = get_object_or_404(Category.objects.prefetch_related('products'), pk=pk)
        if category.products.count() > 0:
            return Response({'error':'They are many products for this category. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentViewSet(CreateModelMixin,RetrieveModelMixin,GenericViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        product_pk = self.kwargs['product_pk']
        return Comment.objects.filter(product_id=product_pk).all()
    
    def get_serializer_context(self):
        return {'product_pk': self.kwargs['product_pk']}
    
    # def my_comment(self, request):
    #     user_id = request.user.id 
    #     customer = Customer.objects.get(user_id=user_id)
    

class CartViewSet(ModelViewSet):
    serializer_class = CartSerializer
    queryset = Cart.objects.prefetch_related('items__product').all()
    lookup_value_regex = '[0-9a-fA-F]{8}\-?[0-9a-fA-F]{4}\-?[0-9a-fA-F]{4}\-?[0-9a-fA-F]{4}\-?[0-9a-fA-F]{12}'  # regex: its a string format that check the data is this format or not


class CartItemViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        cart_pk = self.kwargs['cart_pk']
        return CartItem.objects.select_related('product').filter(cart_id=cart_pk).all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddCartItemSerializer
        elif self.request.method == 'PATCH':
            return UpdateCartItemSerializer
        return CartItemSerializer
    
    def get_serializer_context(self):
        return {'cart_pk': self.kwargs['cart_pk']}
    

class OrderViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'options', 'head']
    # permission_classes = [IsAuthenticated] # its classes so just class name

    def get_permissions(self): # its permissions so we should classname()
        if self.request.method in ['PATCH', 'DELETE']: # its better that admin dont have permission to delete too.
            return [IsAdminUser()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        queryset = Order.objects \
                    .prefetch_related(
                        Prefetch( # in normal prefetch we dont use select_related or more but use complicate quesrt. --> query in prefetch
                            'items', # our query will minimum
                            queryset=OrderItem.objects.select_related('product'),
                        )
                    ) \
                    .select_related('customer__user') \
                    .all()
        
        user = self.request.user

        if user.is_staff:
            return queryset
        return queryset.filter(customer__user_id=user.id)
    

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        
        if  self.request.method == 'PATCH':
            return OrderUpdateSerializer

        if self.request.user.is_staff:
            return OrderForAdminSerializer
        return OrderSerializer
    
    def get_serializer_context(self):
        return {'user_id': self.request.user.id}
    
    def create(self, request, *args, **kwargs): # when order was created we want to show it. data is return to view so we should overight create
        create_order_serializer = OrderCreateSerializer(data=request.data, context={'user_id': self.request.user.id})
        create_order_serializer.is_valid(raise_exception=True)  
        created_order = create_order_serializer.save()

        order_created.send_robust(self.__class__, order=created_order)

        serializer = OrderSerializer(created_order)
        return Response(serializer.data)
        
        

        



class CustomerViewSet(ModelViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['GET','PUT'], permission_classes=[IsAuthenticated]) # we dont need id for myself
    def me(self, request):
        user_id = request.user.id
        customer = Customer.objects.get(user_id=user_id)
        if request.method == 'GET':
            serializer = CustomerSerializer(customer)
            return Response(serializer.data)
        elif request.method == 'PUT':
            serializer = CustomerSerializer(customer, data=request.data)
            serializer.is_valid()
            serializer.save()
            return Response(serializer.data)

    @action(detail=True, permission_classes=[SendPrivateEmailToCustomerPermission])
    def send_private_email(self, request, pk):
        return Response(f'Email was sending successfully to user {pk=}!')
    
# APIView
# class ProductList(ListCreateAPIView): # the get and post method in listcreateapiview 
#     serializer_class = ProductSerializer
#     queryset = Product.objects.select_related('category').all()
#     # def get_serializer_class(self):
#     #     return ProductSerializer   
#     # def get_queryset(self):
#     #     return Product.objects.select_related('category').all()

#     def get_serializer_context(self):
#         return {'request':self.request}


# CBV
# class ProductList(APIView):
#     def get(self, request):
#         queryset = Product.objects.select_related('category').all()
#         serializer = ProductSerializer(queryset, many=True, context={'request':request})
#         return Response(serializer.data)
    
#     def post(self, request):
#         serializer = ProductSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

# Functional View
# @api_view(['GET', 'POST'])
# def product_list(request): # in normal mood the request and response is type Http but in DRF they are class request and response of DRF
#     if request.method == 'GET':
#         queryset = Product.objects.select_related('category').all()
#         serializer = ProductSerializer(queryset, many=True, context={'request':request})
#         return Response(serializer.data)
#     elif request.method == 'POST':
#         serializer = ProductSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_201_CREATED)
#     # if serializer.is_valid():
#         #     serializer.validated_data
#         #     return Response('Everything is OK')
#     # else:
#         #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


#-----------------------------------------------------------------------

# APIView
# class ProductDetail(RetrieveUpdateDestroyAPIView):
#     serializer_class = ProductSerializer
#     queryset = Product.objects.select_related('category').all()

#     def delete(self, request, pk):
#         product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
#         if product.order_items.count() > 0:
#             return Response({'error':'There is some order items including this product. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
#         product.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)

# CBV
# class ProductDetail(APIView):
#     def get(self, request, pk):
#         product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
#         serializer = ProductSerializer(product, context={'request':request})
#         return Response(serializer.data)
    
#     def put(self, request, pk):
#         product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
#         serializer = ProductSerializer(product, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data)
    
#     def delete(self, request, pk):
#         product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
#         if product.order_items.count() > 0:
#             return Response({'error':'There is some order items including this product. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
#         product.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)

# Functional view
# @api_view(['GET', 'PUT', 'DELETE'])
# def product_detail(request, pk):
#     product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
#     if request.method == 'GET':
#         serializer = ProductSerializer(product, context={'request':request})
#         return Response(serializer.data)
#     elif request.method == 'PUT':
#         serializer = ProductSerializer(product, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data)
#     elif request.method == 'DELETE':
#         if product.order_items.count() > 0:
#             return Response({'error':'There is some order items including this product. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
#         product.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)


#-----------------------------------------------------------------------

# APIView
# class CategoryList(ListCreateAPIView):
#     serializer_class = CategorySerializer
#     queryset = Category.objects.prefetch_related('products').all()


# CBV
# class CategoryList(APIView):
#     def get(self, request):
#         queryset = Category.objects.prefetch_related('products').all()
#         serializer = CategorySerializer(queryset, many=True)
#         return Response(serializer.data)
    
#     def post(self, request):
#         serializer = CategorySerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_201_CREATED)


# @api_view(['GET', 'POST'])
# def category_list(request):
#     if request.method == 'GET':
#         queryset = Category.objects.prefetch_related('products').all()
#         serializer = CategorySerializer(queryset, many=True)
#         return Response(serializer.data)
#     elif request.method == 'POST':
#         serializer = CategorySerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_201_CREATED)


#-----------------------------------------------------------------------

# APIView
# class CategoryDetail(RetrieveUpdateDestroyAPIView):
#     serializer_class = CategorySerializer
#     queryset = Category.objects.prefetch_related('products').all()

#     def delete(self, request, pk):
#         category = get_object_or_404(Category.objects.prefetch_related('products'), pk=pk)
#         if category.products.count() > 0:
#             return Response({'error':'They are many products for this category. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
#         category.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)

# CBV
# class CategoryDetail(APIView):
#     def get(self, request, pk):
#         category = get_object_or_404(Category.objects.prefetch_related('products'), pk=pk)
#         serializer = CategorySerializer(category)
#         return Response(serializer.data)
    
#     def put(self, request, pk):
#         category = get_object_or_404(Category.objects.prefetch_related('products'), pk=pk)
#         serializer = CategorySerializer(category, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data)
    
#     def delete(self, request, pk):
#         category = get_object_or_404(Category.objects.prefetch_related('products'), pk=pk)
#         if category.products.count() > 0:
#             return Response({'error':'They are many products for this category. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
#         category.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)

# Functional view
# @api_view(['GET', 'PUT', 'DELETE'])
# def category_detail(request, pk):
#     category = get_object_or_404(Category.objects.prefetch_related('products'), pk=pk)
#     if request.method == 'GET':
#         serializer = CategorySerializer(category)
#         return Response(serializer.data)
#     elif request.method == 'PUT':
#         serializer = CategorySerializer(category, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data)
#     elif request.method == 'DELETE':
#         if category.products.count() > 0:
#             return Response({'error':'They are many products for this category. Please remove them first.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
#         category.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)
