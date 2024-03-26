from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.urls import reverse
from django.utils.http import urlencode

from . import models

class InventoryFilter(admin.SimpleListFilter):
    title = 'Critical Inventory Status'
    parameter_name = 'inventory'

    LESS_THAN_3 = '<3'
    BETWEEN_3_AND_10 = '3<=10'
    MOR_THAN_10 = '>10'
    
    def lookups(self, request, model_admin):
        return [
            (InventoryFilter.LESS_THAN_3, 'High'),
            (InventoryFilter.BETWEEN_3_AND_10, 'Medium'),
            (InventoryFilter.MOR_THAN_10, 'ok'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == InventoryFilter.LESS_THAN_3:
            return queryset.filter(inventory__lt=3)
        if self.value() == InventoryFilter.BETWEEN_3_AND_10:
            return queryset.filter(inventory__range=(3,10))
        if self.value() == InventoryFilter.MOR_THAN_10:
            return queryset.filter(inventory__gt=10)


@admin.register(models.Product)
class ProdcutAdmin(admin.ModelAdmin):

    list_display = ['id', 'name','inventory', 'unit_price', 'inventory_status', 'product_category', 'num_of_comments']
    list_per_page = 10
    list_editable = ['unit_price']
    list_select_related = ['category']
    list_filter = ['datetime_created', InventoryFilter]
    actions = ['clear_inventory']
    search_fields = ['name',]
    prepopulated_fields = {
        'slug':['name',]
    }

    def inventory_status(self, product):
        if product.inventory < 10:
            return 'Low'
        if product.inventory > 50:
            return 'High'
        return 'Medium'
    
    @admin.display(ordering='category__title')
    def product_category(self, product):
        return product.category.title
    
    def get_queryset(self, request):
        return super().get_queryset(request)\
                      .prefetch_related('comments')\
                      .annotate(comments_count=Count('comments'))
    
    @admin.display(ordering='comments_count', description='# comments')
    def num_of_comments(self, product):
        url = (
            reverse('admin:store_comment_changelist')
            +'?'
            +urlencode({
                'product_id':product.id,
            })
        )
        print(url)
        # return product.comments_count
        return format_html('<a href="{}">{}</a>', url, product.comments_count)

    @admin.action(description='Clear Inventory')
    def clear_inventory(self, request, queryset):
        update_count = queryset.update(inventory=0)
        self.message_user(
            request,
            f'{update_count} of products inventories cleared to zero',
        )


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


class OrderItemInline(admin.TabularInline):
    model = models.OrderItem
    fields = ['order', 'product', 'quantity', 'unit_price']
    min_num = 1
    

@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer','datetime_created', 'status', 'num_of_items']
    list_editable = ['status']
    list_per_page = 10
    ordering = ['datetime_created']
    inlines = [OrderItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request)\
                      .prefetch_related('items')\
                      .annotate(items_count=Count('items'))
        
    @admin.display(ordering='items_count', description='# items') # descriptin is show in db with name of description not with name of func
    def num_of_items(self, order):
        return order.items_count
    

@admin.register(models.Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'status']
    list_editable = ['status']
    list_per_page = 10
    autocomplete_fields = ['product',]
    # list_display_links = ['product']

@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email']
    list_per_page = 10
    ordering = ['user__last_name', 'user__first_name',]
    search_fields = ['user__first_name__istartswith', 'user__last_name__istartswith',]

    def first_name(self, customer):
        return customer.user.first_name
    
    def last_name(self, customer):
        return customer.user.last_name
    
    def email(self, customer):
        return customer.user.email


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price']
    autocomplete_fields = ['product']







class CartItemInline(admin.TabularInline):
    model = models.CartItem
    fields = ['cart', 'product', 'quantity']
    min_num = 1
    

@admin.register(models.Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at']
    inlines = [CartItemInline]
