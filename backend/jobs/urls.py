"""URL routing for the jobs app."""

from rest_framework.routers import DefaultRouter

from .views import JobExecutionViewSet, JobViewSet

router = DefaultRouter()
router.register(r"jobs", JobViewSet, basename="job")
router.register(r"executions", JobExecutionViewSet, basename="execution")

urlpatterns = router.urls
