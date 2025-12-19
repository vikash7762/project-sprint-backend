from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from jose import jwt, JWTError
from bson import ObjectId
from pydantic import BaseModel  # <-- added

from auth import router as auth_router
from database import users_collection
from security import SECRET_KEY, ALGORITHM

app = FastAPI(title="ProjectSprint")

# Read token from "Authorization" header, e.g. "Bearer eyJ..."
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])


def get_current_user(auth_header: str = Depends(api_key_header)):
    # Expect header: Authorization: Bearer <token>
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = auth_header.split(" ", 1)[1]

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_exception
    return user


@app.get("/home")
async def home(current_user: dict = Depends(get_current_user)):
    return {
        "message": f"Welcome {current_user['fullName']}",
        "role": current_user["role"],
        "profile": {
            "email": current_user.get("email"),
            "phone": current_user.get("phone"),
            "collegeOrCompany": current_user["collegeOrCompany"],
            "skills": current_user["skills"],
            "city": current_user["city"],
        },
    }


# ---- NEW: update profile ----

class ProfileUpdate(BaseModel):
    fullName: str | None = None
    collegeOrCompany: str | None = None
    skills: list[str] | None = None
    city: str | None = None
    phone: str | None = None


@app.put("/profile")
async def update_profile(
    payload: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    update_data: dict = {}

    if payload.fullName is not None:
        update_data["fullName"] = payload.fullName
    if payload.collegeOrCompany is not None:
        update_data["collegeOrCompany"] = payload.collegeOrCompany
    if payload.skills is not None:
        update_data["skills"] = payload.skills
    if payload.city is not None:
        update_data["city"] = payload.city
    if payload.phone is not None:
        update_data["phone"] = payload.phone

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    users_collection.update_one(
        {"_id": current_user["_id"]},
        {"$set": update_data},
    )

    return {"message": "Profile updated successfully"}
# ------------------------------


@app.get("/")
async def root():
    return {"message": "ProjectSprint API is running"}
