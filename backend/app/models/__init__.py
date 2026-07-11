# models package initialization

from app.models.gov24 import Gov24ServiceDetail, Gov24ServiceList, Gov24SupportCondition  # noqa: F401
from app.models.policy import PolicyAnnouncement, PolicyAttachment, PolicyProgramPage  # noqa: F401

# 신규 추가된 테이블 ORM 모델들 등록 (Base.metadata 자동 감지용)
from app.models.user import User, UserProfile  # noqa: F401
from app.models.normalized_policy import NormalizedPolicy, AttachmentFile, PolicyAttachmentLink, PolicyDocument  # noqa: F401
from app.models.chat import PolicyChunk  # noqa: F401
from app.models.recommend import RecommendationVector  # noqa: F401
from app.models.review import ReviewVector, ReviewUpload  # noqa: F401
from app.models.prep import PrepVector  # noqa: F401
