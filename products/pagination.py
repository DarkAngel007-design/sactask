from rest_framework.pagination import PageNumberPagination


class ProductPagination(PageNumberPagination):
    """Page-number pagination: ?page=2&page_size=25

    Responses look like:
        {"count": 42, "next": "...?page=3", "previous": "...?page=1",
         "results": [ ... ]}
    """

    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
