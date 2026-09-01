"""
Routes du contexte `organizing`.

Aucune barre oblique finale, par coherence avec le reste de l API.
"""

from django.urls import path

from .reactivation_views import OrganizerReactivationRequestView
from .scanner_archive_views import OrganizerScannerBulkArchiveView
from .scanner_credential_views import OrganizerScannerPasswordReissueView, ScannerPasswordHelpRequestView
from .scanner_invitation_views import OrganizerScannerInvitationResendView
from .scanner_leave_views import (
    OrganizerScannerLeaveDecisionView,
    ScannerLeaveRequestView,
    ScannerLeaveSecurityCodeView,
)
from .scanner_security_views import OrganizerScannerSecurityCodeView
from .scanner_views import (
    OrganizerArchivedScannerCollectionView,
    OrganizerScannerCollectionView,
    OrganizerScannerDetailView,
)
from .views import OrganizerApplyView, OrganizerMeView

app_name = "organizing"

urlpatterns = [
    path(
        "me/scanners/<uuid:scanner_id>/security-code",
        OrganizerScannerSecurityCodeView.as_view(),
        name="organizer-scanner-security-code",
    ),
    path(
        "scanner-leave/security-code",
        ScannerLeaveSecurityCodeView.as_view(),
        name="scanner-leave-security-code",
    ),
    path(
        "scanner-leave/request",
        ScannerLeaveRequestView.as_view(),
        name="scanner-leave-request",
    ),
    path(
        "scanner-password-help/request",
        ScannerPasswordHelpRequestView.as_view(),
        name="scanner-password-help-request",
    ),
    path("apply", OrganizerApplyView.as_view(), name="organizer-apply"),
    path("me", OrganizerMeView.as_view(), name="organizer-me"),
    path(
        "me/reactivation-request",
        OrganizerReactivationRequestView.as_view(),
        name="organizer-me-reactivation-request",
    ),
    path(
        "me/scanners",
        OrganizerScannerCollectionView.as_view(),
        name="organizer-me-scanners",
    ),
    path(
        "me/scanners/archived",
        OrganizerArchivedScannerCollectionView.as_view(),
        name="organizer-me-scanners-archived",
    ),
    path(
        "me/scanners/archive",
        OrganizerScannerBulkArchiveView.as_view(),
        name="organizer-me-scanners-archive",
    ),
    path(
        "me/scanners/<uuid:scanner_id>",
        OrganizerScannerDetailView.as_view(),
        name="organizer-me-scanner-detail",
    ),
    path(
        "me/scanners/<uuid:scanner_id>/leave-request",
        OrganizerScannerLeaveDecisionView.as_view(),
        name="organizer-scanner-leave-decision",
    ),
    path(
        "me/scanners/<uuid:scanner_id>/resend-invitation",
        OrganizerScannerInvitationResendView.as_view(),
        name="organizer-scanner-invitation-resend",
    ),
    path(
        "me/scanners/<uuid:scanner_id>/temporary-password",
        OrganizerScannerPasswordReissueView.as_view(),
        name="organizer-scanner-password-reissue",
    ),
]
