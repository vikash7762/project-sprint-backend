from pydantic import BaseModel, EmailStr
from typing import List, Optional


class SignupPayload(BaseModel):
    identifier: EmailStr | str  # email or phone
    fullName: str
    collegeOrCompany: str
    skills: List[str]
    role: str          # "USER" or "ADMIN"
    city: str


class SendOtpPayload(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
