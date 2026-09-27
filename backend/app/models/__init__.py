"""models __init__ - 必须在 database.Base 之后 import"""
from .user import User, DoctorProfile
from .case import Case
from .observation import Observation
from .treatment import TreatmentPlan
from .feedback import Feedback
from .friend import Friend
from .challenge import Challenge, Checkin
from .shop import ShopItem, ShopReview, ShopOrder

__all__ = [
    "User", "DoctorProfile",
    "Case", "Observation", "TreatmentPlan", "Feedback",
    "Friend", "Challenge", "Checkin",
    "ShopItem", "ShopReview", "ShopOrder",
]
