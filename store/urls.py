from django.urls import path, include
from rest_framework_nested import routers

from . import views


router = routers.DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('carts', views.CartViewSet, basename='cart')
router.register('customers', views.CustomerViewSet, basename='customer')
router.register('orders', views.OrderViewSet, basename='order')

# Nested: url haye to dar to
products_router = routers.NestedDefaultRouter(router, 'products', lookup='product') # localhost:8000/store/products/1(product-pk)/
products_router.register('comments', views.CommentViewSet, basename='product-comments')

cart_item_router = routers.NestedDefaultRouter(router, 'carts', lookup='cart')
cart_item_router.register('items', views.CartItemViewSet, basename='cart-items')

urlpatterns = router.urls + products_router.urls + cart_item_router.urls

# urlpatterns = [
#     path('', include(router.urls))
# ]


# urlpatterns = [
#     path('products/', views.ProductList.as_view(), name='product_list'),
#     path('products/<int:pk>/', views.ProductDetail.as_view(), name='product_detail'),
#     path('categories/', views.CategoryList.as_view(), name='category_list'),
#     path('categories/<int:pk>/', views.CategoryDetail.as_view(), name='category_detail'),
# ]
