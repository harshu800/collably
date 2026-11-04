"""Model registry — importing this package registers every model on Base.metadata."""

from app.models.agreement import AgreementVersion
from app.models.application import ApplicationStatus, CampaignApplication
from app.models.audit_log import AuditLog
from app.models.brand_profile import BrandProfile
from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.models.collaboration import (
    Collaboration,
    CollaborationPayoutStatus,
    CollaborationStatus,
    FundingStatus,
)
from app.models.creator_profile import CreatorProfile
from app.models.deliverable import Deliverable, DeliverableKind, DeliverableStatus
from app.models.dispute import Dispute, DisputeResolution, DisputeStatus
from app.models.email_outbox import EmailOutbox
from app.models.file import File, FileVisibility
from app.models.notification import Notification
from app.models.payment import Payment, PaymentKind, PaymentStatus
from app.models.payout import Payout, PayoutStatus
from app.models.payout_method import CreatorPayoutMethod, PayoutMethodKind
from app.models.refund import Refund
from app.models.report import Report, ReportStatus, ReportTargetType
from app.models.revision import DeliverableRevision
from app.models.user import User, UserRole
from app.models.webhook_event import PaymentWebhookEvent

__all__ = [
    "AgreementVersion",
    "ApplicationStatus",
    "AuditLog",
    "BrandProfile",
    "Campaign",
    "CampaignApplication",
    "CampaignStatus",
    "CampaignType",
    "Collaboration",
    "CollaborationPayoutStatus",
    "CollaborationStatus",
    "CreatorPayoutMethod",
    "CreatorProfile",
    "Deliverable",
    "DeliverableKind",
    "DeliverableRevision",
    "DeliverableStatus",
    "Dispute",
    "DisputeResolution",
    "DisputeStatus",
    "EmailOutbox",
    "File",
    "FileVisibility",
    "FundingStatus",
    "Notification",
    "Payment",
    "PaymentKind",
    "PaymentStatus",
    "PaymentWebhookEvent",
    "Payout",
    "PayoutMethodKind",
    "PayoutStatus",
    "Refund",
    "Report",
    "ReportStatus",
    "ReportTargetType",
    "User",
    "UserRole",
]
