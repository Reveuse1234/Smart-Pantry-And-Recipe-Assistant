import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    invite_code = Column(String(16), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    members = relationship("HouseholdMember", back_populates="household")
    pantry_items = relationship("PantryItem", back_populates="household")
    shopping_lists = relationship("ShoppingList", back_populates="household")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    health_conditions = Column(Text, default="[]")
    dietary_requirements = Column(Text, default="[]")
    daily_calorie_target = Column(Integer, nullable=True)
    ai_preferences = Column(Text, nullable=True)  # free text: tastes, dislikes, time constraints for AI
    favorite_cuisines = Column(Text, default="[]")  # JSON list e.g. ["Italian","Japanese"] for personalization
    cooking_mode = Column(String(16), default="solo")  # "solo" | "family" — portions & planning
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    memberships = relationship("HouseholdMember", back_populates="user")
    calorie_entries = relationship("DailyCalorieEntry", back_populates="user")


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id", name="uq_household_user"),)

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(32), default="member")

    household = relationship("Household", back_populates="members")
    user = relationship("User", back_populates="memberships")


class PantryItem(Base):
    __tablename__ = "pantry_items"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    name = Column(String(200), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(64), default="each")
    category = Column(String(80), default="general")
    expiration_date = Column(Date, nullable=True)
    barcode = Column(String(64), nullable=True)
    image_path = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    household = relationship("Household", back_populates="pantry_items")


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    cuisine = Column(String(80), nullable=False, index=True)
    instructions = Column(Text, nullable=False)
    prep_minutes = Column(Integer, default=30)
    calories_per_serving = Column(Integer, default=0)
    servings = Column(Integer, default=4)
    image_url = Column(String(512), nullable=False, default="")
    ingredients_json = Column(Text, nullable=False)
    diet_tags = Column(Text, default="[]")
    health_notes = Column(Text, default="[]")
    # Optional: Spoonacular analyzed steps (JSON list of strings), cached after first API match.
    structured_steps_json = Column(Text, nullable=True)
    # Optional: same match, JSON list of {number, instruction, ingredients[], equipment[]} per step.
    spoonacular_guide_json = Column(Text, nullable=True)
    spoonacular_recipe_id = Column(Integer, nullable=True)


class DailyCalorieEntry(Base):
    __tablename__ = "daily_calorie_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_date = Column(Date, nullable=False)
    calories = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="calorie_entries")


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    household = relationship("Household", back_populates="shopping_lists")
    items = relationship("ShoppingListItem", back_populates="shopping_list", cascade="all, delete-orphan")


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id = Column(Integer, primary_key=True, index=True)
    shopping_list_id = Column(Integer, ForeignKey("shopping_lists.id"), nullable=False)
    item_name = Column(String(200), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(64), default="each")
    is_checked = Column(Boolean, default=False)
    source_recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)

    shopping_list = relationship("ShoppingList", back_populates="items")


class ExpiryNotification(Base):
    __tablename__ = "expiry_notifications"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)
    pantry_item_id = Column(Integer, ForeignKey("pantry_items.id"), nullable=True)
    severity = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    dismissed = Column(Boolean, default=False)

    household = relationship("Household")
