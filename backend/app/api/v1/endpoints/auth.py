from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Household, HouseholdMember, User
from app.schemas.auth import Token, UserCreate, UserLogin, UserOut
from app.services.household_utils import new_invite_code, parse_json_list

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        dietary_requirements=parse_json_list(u.dietary_requirements),
        health_conditions=parse_json_list(u.health_conditions),
        daily_calorie_target=u.daily_calorie_target,
    )


@router.post("/register", response_model=Token)
def register(body: UserCreate, db: Session = Depends(get_db)):
    email_l = body.email.strip().lower()
    if db.query(User).filter(User.email == email_l).first():
        raise HTTPException(400, "Email already registered")
    user = User(email=email_l, hashed_password=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.flush()
    code = body.join_code.strip().upper()
    if code:
        hh = db.query(Household).filter(Household.invite_code == code).first()
        if not hh:
            db.rollback()
            raise HTTPException(400, "Invalid invite code")
        db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="member"))
    else:
        hh = Household(name=body.household_name.strip() or "My Household", invite_code=new_invite_code())
        db.add(hh)
        db.flush()
        db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    db.commit()
    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    return Token(access_token=create_access_token(user.id))
