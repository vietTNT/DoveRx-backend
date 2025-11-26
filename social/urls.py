from rest_framework.routers import DefaultRouter
from .views import PostViewSet, CommentViewSet , NotificationViewSet

router = DefaultRouter()
router.register("posts", PostViewSet, basename="posts")
router.register("comments", CommentViewSet, basename="comments")
router.register("notifications", NotificationViewSet, basename="notifications")
urlpatterns = router.urls
