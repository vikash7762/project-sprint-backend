from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from random import randint
from pydantic import BaseModel

import os
import smtplib
from email.message import EmailMessage

from database import otps_collection, users_collection
from models import SignupPayload, SendOtpPayload
from security import create_access_token

router = APIRouter()

# -------- Email config --------
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)


def send_otp_email(to_email: str, code: str):
    """
    Send OTP to user via SMTP.
    """
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM]):
        # Fail fast if email is not configured
        print("Email config missing, cannot send OTP email")
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Project Sprint OTP code"
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(f"Your OTP code is {code}. It will expire in 10 minutes.")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"OTP email sent to {to_email}")
    except Exception as e:
        # Do not break the API if email fails; just log the error
        print("Error sending OTP email:", repr(e))


class SendOtpRequest(BaseModel):
    email: str


@router.post("/send-otp")
async def send_otp(payload: SendOtpRequest):
    email = payload.email
    identifier = email
    otp = str(randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    otps_collection.insert_one(
        {
            "identifier": identifier,
            "code": otp,
            "expiresAt": expires_at,
            "attempts": 0,
            "used": False,
        }
    )

    print("send_otp endpoint hit")
    print(f"OTP for {identifier}: {otp}")

    # NEW: actually send the email
    send_otp_email(identifier, otp)

    return {"message": "OTP generated and email (attempted) to be sent"}


@router.post("/verify-otp")
async def verify_otp(identifier: str, code: str):
    otp = otps_collection.find_one(
        {
            "identifier": identifier,
            "code": code,
            "expiresAt": {"$gt": datetime.utcnow()},
            "used": False,
        }
    )

    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if otp["attempts"] >= 3:
        raise HTTPException(status_code=400, detail="Too many attempts")

    otps_collection.update_one(
        {"_id": otp["_id"]},
        {"$set": {"used": True}},
    )

    # Check if user exists
    query = {"email": identifier} if "@" in identifier else {"phone": identifier}
    user = users_collection.find_one(query)

    if not user:
        # frontend should now redirect to signup with this identifier
        return {"new_user": True, "identifier": identifier}

    # update last login time
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"lastLoginAt": datetime.utcnow()}},
    )

    # create JWT token for logged-in user
    token = create_access_token(
        {"sub": str(user["_id"]), "role": user["role"]}
    )

    return {
        "message": "Login successful",
        "new_user": False,
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/signup")
async def signup(payload: SignupPayload):
    """
    Complete onboarding for a new user after OTP verification.
    Stores full profile in MongoDB.
    """
    identifier = payload.identifier

    # Check if user already exists
    query = {"email": identifier} if "@" in identifier else {"phone": identifier}
    existing = users_collection.find_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_doc = {
        "fullName": payload.fullName,
        "email": identifier if "@" in identifier else None,
        "phone": identifier if "@" not in identifier else None,
        "collegeOrCompany": payload.collegeOrCompany,
        "skills": payload.skills,
        "role": payload.role,  # "USER" or "ADMIN"
        "city": payload.city,
        "signupAt": datetime.utcnow(),
        "lastLoginAt": datetime.utcnow(),
    }

    users_collection.insert_one(user_doc)

    return {"message": "Signup completed"}
