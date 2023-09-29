# Встроенные модули Python
import asyncio
import io
import json
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from operator import and_
from typing import List, Optional, Dict, Tuple, Any
from urllib.parse import quote, unquote

# Модули для работы с SQL базами данных
import aiomysql
import jwt
import room
from fastapi.params import Path
from jose import JWTError
from jwt import PyJWTError
from sqlalchemy import  MetaData, Column, Integer, String, ForeignKey, PrimaryKeyConstraint, DateTime, \
    Table, func, LargeBinary, desc, or_, Boolean, BLOB, Text, Float, JSON, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.sync import update
from sqlalchemy.sql import select
from databases import Database


# Сторонние библиотеки для веб-фреймворков, безопасности и шаблонизации
from fastapi import  FastAPI, WebSocket, HTTPException, Depends, status, Form,  UploadFile, File

from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse, PlainTextResponse, Response, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect, WebSocketState

# Сторонние библиотеки для работы с файлами, датами и временем
from aiofile import async_open
from pytz import timezone
import pytz as pytz

# Сторонние библиотеки для безопасности и хеширования паролей
import bcrypt

# Другие сторонние библиотеки
from pydantic import BaseModel


import mimetypes
from pydantic.json import Union

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBearer()

# Устанавливаем URL базы данных
SQLALCHEMY_DATABASE_URL = "mysql://root:root@localhost/Chat"

# Инициализируем экземпляр базы данных
database = Database(SQLALCHEMY_DATABASE_URL)

# Инициализируем экземпляр FastAPI
app = FastAPI()

# Монтируем статические файлы
app.mount("/profile_pictures", StaticFiles(directory="profile_pictures"), name="profile_pictures")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Создаем сессию для взаимодействия с базой данных
engine = create_async_engine("mysql+aiomysql://root:root@localhost/chat")
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Устанавливаем метаданные и базовый класс для моделей SQLAlchemy
metadata = MetaData()
Base = declarative_base()

# Добавляем промежуточное ПО в приложение
app.add_middleware(SessionMiddleware, secret_key="root")

moscow_tz = timezone('Europe/Moscow')
MSK_TZ = timezone('Europe/Moscow')

# Определяем таблицы в базе данных
users = Table(
    "Users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("gender", String),
    Column("last_name", String),
    Column("first_name", String),
    Column("middle_name", String),
    Column("nickname", String),
    Column("phone_number", String, unique=True),
    Column("position", String),
    Column("email", String),
    Column("password", String),
    Column("last_online", DateTime(timezone=True)),
    Column("profile_picture", BLOB, default=None),
    Column("status", Text, default=None)
)

userchats = Table(
    "Userchats",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("chat_name", String),
    Column("owner_phone_number", String, ForeignKey('Users.phone_number')),
)

tokens = Table(
    "Tokens",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("token", String(length=512)),  # Указываем длину 512
    Column("expires_at", DateTime(timezone=True)),
    Column("user_id", Integer, ForeignKey("Users.id"))
)

refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("id", Integer, primary_key=True, index=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("token", String(length=255), unique=True, nullable=False),
    Column("expires_at", DateTime, nullable=False),
)

Polls = Table(
    "Polls",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("chat_id", Integer, ForeignKey('Userchats.id')),
    Column("creator_phone_number", String, ForeignKey('Users.phone_number')),
    Column("question", String),
    Column("options", String),
    Column("is_ended", Boolean, default=False),
    Column("voted_users", JSON)
)

PollOptions = Table(
    "PollOptions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("poll_id", Integer, ForeignKey('Polls.id')),
    Column("poll_option", String),
)

PollVotes = Table(
    "PollVotes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("poll_id", Integer, ForeignKey('Polls.id')),
    Column("option_id", Integer, ForeignKey('PollOptions.id')),
    Column("voter_phone_number", String, ForeignKey('Users.phone_number'))
)

PollResults = Table(
    "PollResults",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("poll_id", Integer, ForeignKey('Polls.id')),
    Column("option_id", Integer, ForeignKey('PollOptions.id')),
    Column("votes", Integer, default=0),
    Column("percentage", Float, default=0.0)
)

dialogs = Table(
    "Dialogs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user1_id", Integer, ForeignKey('Users.id')),
    Column("user2_id", Integer, ForeignKey('Users.id')),
    Column("created_at", DateTime(timezone=True), default=datetime.now(moscow_tz)),
    Column("user1_deleted", Boolean, default=False),
    Column("user2_deleted", Boolean, default=False),
)

dialog_messages = Table(
    "DialogMessages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dialog_id", Integer, ForeignKey('Dialogs.id')),
    Column("sender_id", Integer, ForeignKey('Users.id')),
    Column("message", String),
    Column("timestamp", DateTime(timezone=True), default=datetime.now(moscow_tz)),
    Column("delete_timestamp", DateTime),
)

chatmessages = Table(
    "ChatMessages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("chat_id", Integer, ForeignKey('Userchats.id')),
    Column("sender_phone_number", String, ForeignKey('Users.phone_number')),
    Column("message", String),
    Column("timestamp", DateTime, default=func.now()),
    Column("delete_timestamp", DateTime),
    Column("deleted_by_users", JSON),  # Новый столбец для хранения информации о удалении
    Column("message_type", String(255))  # Новый столбец для типа сообщения
)

ChatMembers = Table(
    "ChatMembers",
    metadata,
    Column("chat_id", Integer, ForeignKey('Userchats.id')),
    Column("user_phone_number", String, ForeignKey('Users.phone_number')),
    PrimaryKeyConstraint('chat_id', 'user_phone_number')
)

channels = Table(
    'channels', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String),
    Column('owner_phone_number', String, ForeignKey('Users.phone_number')),
    Column('creation_date', DateTime, default=func.now())
)

channel_members = Table(
    'channel_members', metadata,
    Column('id', Integer, primary_key=True),
    Column('channel_id', Integer, ForeignKey('channels.id')),
    Column('user_phone_number', String, ForeignKey('Users.phone_number'))
)

files = Table(
    "Files",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("phone_number", String, ForeignKey('Users.phone_number')),
    Column("file_path", String),
    Column("file", LargeBinary),
    Column("file_extension", String(255)),
)

channel_history = Table(
    "Channel_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("message", String),
    Column("timestamp", DateTime, default=lambda: datetime.now(MSK_TZ)),
    Column("channel_id", Integer, ForeignKey('channels.id')),
    Column("sender_phone_number", String, ForeignKey('Users.phone_number')),
    Column("file_id", Integer, ForeignKey('Files.id')),
    Column("file_name", String)
)

# Папка, где будут храниться фотографии профиля
PROFILE_PICTURES_FOLDER = "C:/Users/Программист/PycharmProjects/fastApiSpiritChat/profile_pictures"

# Определение исключения для проблем с аутентификацией
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

SECRET_KEY = "Bondar"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1800
REFRESH_TOKEN_EXPIRE_DAYS = 2

# Хранилище для аннулированных токенов
revoked_tokens = []


# Определяем модель пользователя
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    password = Column(String)


class UserInDB(BaseModel):
    id: int
    gender: str
    last_name: str
    first_name: str
    middle_name: str
    nickname: str
    phone_number: str
    position: str
    email: str
    password: str
    last_online: Optional[datetime]
    profile_picture: Optional[bytes]
    status: Optional[str]

    class Config:
        orm_mode = True


class MessageContent(BaseModel):
    message_text: str


class MessageType(str, Enum):
    CHAT = "chat"
    DIALOG = "dialog"
    CHANNEL = "channel"


class MyJinja2Templates(Jinja2Templates):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env.globals["time"] = time


templates = MyJinja2Templates(directory="templates")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    phone_number: str


# Извлекает информацию о пользователе из базы данных по номеру телефона.
async def get_user(phone_number: str):
    query = users.select().where(users.c.phone_number == phone_number)
    logging.info(f"Executing query: {query}")  # Debug info
    user = await database.fetch_one(query)
    logging.info(f"User from database in get_user function: {user}")  # Debug info
    return user

# Получает пользователя по номеру телефона.
async def get_user_by_phone(phone_number: str):
    logging.info(f'Getting user by phone: {phone_number}')
    query = users.select().where(users.c.phone_number == phone_number)
    user = await database.fetch_one(query)
    if user:
        logging.info(f'Found user: {user}')
        return UserInDB(**user)
    logging.info(f'No user found for phone: {phone_number}')
    return None

# Извлекает текущего пользователя из сессии.
async def get_current_user(request: Request):
    access_token = request.cookies.get("access_token")
    if access_token  is None:
        logging.warning("Token is missing.")
        return RedirectResponse(url="/login", status_code=303)

    try:
        if is_token_expired(access_token , SECRET_KEY):
            logging.warning("Token has expired.")
            # Для данного случая, вам нужно извлечь user_id из истекшего токена
            payload = jwt.decode(access_token , SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            user_id = payload.get("sub")

            new_token = await validate_and_refresh_token(request, user_id)
            if new_token:
                access_token = new_token
            else:
                logging.error("Failed to refresh the token.")
                return RedirectResponse(url="/login", status_code=303)

        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        phone_number: str = payload.get("sub")
        if phone_number is None:
            logging.error("Phone number not found in payload")
            raise credentials_exception

        user = await get_user_by_phone(phone_number)
        if user is None:
            logging.error("User not found by phone number")
            raise credentials_exception

        logging.info(f"User found: {user}")
        return user
    except PyJWTError as e:
        logging.error(f"JWT error: {e}")
        raise credentials_exception



# Добавим новую функцию для извлечения номера телефона по user_id
async def get_phone_number_by_user_id(user_id: int) -> Optional[str]:
    query = select([users.c.phone_number]).where(users.c.id == user_id)
    try:
        result = await database.fetch_one(query)
        if result:
            logging.info(f"Phone number found: {result.phone_number}")
            return result.phone_number
        else:
            logging.warning(f"No phone number found for user ID: {user_id}")
            return None
    except Exception as e:
        logging.error(f"An error occurred while fetching the phone number: {e}")
        return None


#функцию для извлечениz user_id из базы данных по токену:
async def get_user_id_by_token(access_token: str) -> Optional[int]:
    logging.info(f"Validating token: {access_token}")
    query = select([tokens.c.user_id]).where(tokens.c.token == access_token)
    result = await database.fetch_one(query)
    if result:
        logging.info(f"Token is valid, user_id: {result.user_id}")
        return result.user_id
    logging.warning("Token is invalid or not found in database.")
    return None


# Функция для проверки срока действия токена
def is_token_expired(access_token, SECRET_KEY):
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        expiration = payload.get("exp")
        if expiration:
            return datetime.utcfromtimestamp(expiration) < datetime.utcnow()
        return True
    except Exception as e:
        logging.error(f"Error in is_token_expired: {e}")
        return True



# Создание доступного токена
def create_access_token(data: dict, expires_delta: timedelta = None):
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logging.error(f"Error in create_access_token: {e}")
        return None

# Создание обновленного токена
def create_refresh_token(data: dict, expires_delta: timedelta = None):
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=7)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logging.error(f"Error in create_refresh_token: {e}")

# Получение токена из запроса
async def get_token(request: Request):
    logging.info('get_token called.')
    access_token = request.cookies.get("access_token")
    if access_token and is_token_expired(access_token, SECRET_KEY):
        logging.warning("Token has expired.")
        access_token = None  # Устанавливаем token в None, если он просрочен

    if access_token is None:
        phone_number = request.form.get("username")
        if phone_number:
            access_token = await get_token_from_db_by_phone_number(phone_number)
    return access_token

# Проверка и валидация токена
async def verify_and_validate_token(access_token: str):
    logging.info("Initiating process to verify and validate the token.")
    logging.info(f"Token to verify: {access_token}")

    if is_token_expired(access_token, SECRET_KEY):
        logging.warning("Token has expired.")
        return None, False

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        logging.info(f"Successfully decoded JWT payload: {payload}")

        phone_number = payload.get("sub")
        if phone_number:
            logging.info(f"Successfully retrieved phone_number from payload: {phone_number}")
            return phone_number, True
        else:
            logging.warning("Phone_number is missing from the payload.")
            return None, False

    except JWTError as e:
        logging.error(f"JWT Error while verifying the token: {e}")
        return None, False


@app.post("/token", response_model=Token)
async def login_for_access_token(response: Response, phone_number: str = Form(...), password: str = Form(...)):
    logging.info("Login endpoint called")
    user = await authenticate_user(phone_number, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.phone_number}, expires_delta=access_token_expires
    )
    access_expires_at = datetime.utcnow() + access_token_expires

    # Сохранение access_token в базе данных
    await save_token_to_db(database, user.id, access_token, access_expires_at)

    refresh_token = create_refresh_token(data={"sub": user.phone_number})
    refresh_expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Транзакция для сохранения обоих токенов
    async with database.transaction():
        await save_token_to_db(database, user.id, access_token, access_expires_at)
        await save_refresh_token_to_db(database, user.id, refresh_token, refresh_expires_at)

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite='Strict',
        max_age=3600  # установка срока действия кукиса в один час
    )

    response.set_cookie(
        key="refresh_token",  # добавьте эту строку
        value=f"Bearer {refresh_token}",  # и эту
        httponly=True,
        secure=True,
        samesite='Strict'
    )

    return {"access_token": access_token, "token_type": "bearer"}


# Обновление токена в базе данных
async def update_access_token_in_db(old_access_token: str, new_access_token: str):
    logging.info(f"Updating token in database: {old_access_token} to {new_access_token}")
    query = update(tokens).where(tokens.c.token == old_access_token).values(token=new_access_token)
    await database.execute(query)


# Функция для сохранения токена в базе данных
async def save_token_to_db(db: Database, user_id: int, access_token: str, expires_at: datetime):  # Изменен аргумент с 'token' на 'access_token'
    try:
        query = tokens.insert().values(user_id=user_id, token=access_token, expires_at=expires_at)
        await db.execute(query)
    except Exception as e:
        logging.error(f"An error occurred while saving token to database: {e}")
        raise HTTPException(status_code=500, detail="Could not save token to database")

# Функция для сохранения обновленного токена в базе данных
async def save_refresh_token_to_db(db: Database, user_id: int, refresh_token: str, expires_at: datetime):
    try:
        query = refresh_tokens.insert().values(user_id=user_id, token=refresh_token, expires_at=expires_at)
        await db.execute(query)
    except Exception as e:
        logging.error(f"An error occurred while saving refresh token to database: {e}")
        raise HTTPException(status_code=500, detail="Could not save refresh token to database")


@app.post("/token/refresh")
async def refresh_access_token(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found."
        )

    # Добавленная проверка: Проверка действительности refresh_token
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type."
            )
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token."
        )

    new_token = await validate_and_refresh_token(request, user_id)
    if new_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token or failed to refresh."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.utcnow() + access_token_expires
    await save_token_to_db(database, user_id, new_token, expires_at)

    response.set_cookie(
        key="access_token",
        value=f"Bearer {new_token}",
        httponly=True,
        secure=True,
        samesite='Strict'
    )
    logging.info(f"Refreshed access token: {new_token}")

    return {"access_token": new_token, "token_type": "bearer"}


@app.post("/token/revoke")
async def revoke_token(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"msg": "Tokens have been revoked"}


# Получение токена из базы данных
async def get_token_from_db(access_token: str) -> str:
    logging.info(f"Getting token from database: {access_token}")
    if is_token_expired(access_token, SECRET_KEY):
        logging.warning(f"Token has expired: {access_token}")
        return None
    query = select([tokens.c.token]).where(tokens.c.token == access_token)
    result = await database.fetch_one(query)
    if result:
        logging.info(f"Token found in database: {result.token}")
        return result.token
    else:
        logging.warning(f"Token not found in database: {access_token}")
        return None


async def is_token_in_db(phone_number: str) -> bool:
    logging.info(f"Checking if token is in database for phone number: {phone_number}")
    query = select([tokens.c.token]).join(users).where(users.c.phone_number == phone_number)
    result = await database.fetch_one(query)
    logging.info(f"Token for phone number {phone_number} found in database: {bool(result)}")
    return bool(result)

async def get_refresh_token_from_db_by_user_id(user_id: int) -> Optional[str]:
    logging.info(f"Getting refresh token from database by user ID: {user_id}")
    query = select([refresh_tokens.c.token]).where(refresh_tokens.c.user_id == user_id)
    result = await database.fetch_one(query)
    if result:
        logging.info(f"Refresh token found in database for user ID: {result.token}")
        return result.token
    else:
        logging.warning(f"Refresh token not found in database for user ID: {user_id}")
        return None


async def validate_and_refresh_token(connection: Union[WebSocket, Request], user_id: int, request_type: str = "websocket"):
    logging.info("=== Validating and Refreshing Token ===")
    logging.info(f"Validating and possibly refreshing token.")

    try:
        old_access_token = None
        if request_type == "websocket":
            old_access_token = await get_websocket_token(connection)
        elif request_type == "http":
            old_access_token = connection.cookies.get("access_token")
        else:
            logging.error("Invalid request_type specified")
            return None, False  # Added is_valid flag

        phone_number, is_valid = await verify_and_validate_token(old_access_token)

        if not is_valid:
            logging.warning(f"Token is invalid. Trying to refresh using refresh token for user {user_id}.")
            refresh_token = await get_refresh_token_from_db_by_user_id(user_id)  # Use user_id to fetch the refresh token

            if refresh_token:
                phone_number, is_valid = await verify_and_validate_token(refresh_token)

                if is_valid:
                    new_access_token = create_access_token({"sub": phone_number})
                    new_refresh_token = create_refresh_token({"sub": phone_number})

                    await update_access_token_in_db(old_access_token, new_access_token)
                    await update_refresh_token_in_db(refresh_token, new_refresh_token)

                    return new_access_token, True
                else:
                    logging.warning("Invalid refresh token. Deleting from database and closing connection.")
                    await delete_refresh_token_from_db(refresh_token)
                    if request_type == "websocket":
                        await connection.close(code=4001)
                    return None, False
            else:
                logging.warning("Invalid token and no refresh token found. Closing connection.")
                if request_type == "websocket":
                    await connection.close(code=4001)
                return None, False
        else:
            logging.info(f"Token is valid for user {user_id}.")
            return old_access_token, True

    except Exception as e:
        logging.error(f"An error occurred while validating and refreshing the token: {e}")
        if request_type == "websocket":
            await connection.close(code=4002)  # Custom close code for "internal error"
        return None, False


# Function to delete refresh token from database
async def delete_refresh_token_from_db(refresh_token: str):
    query = delete(refresh_tokens).where(refresh_tokens.c.token == refresh_token)
    await database.execute(query)


# Function to update refresh token in database
async def update_refresh_token_in_db(old_refresh_token: str, new_refresh_token: str):
    query = update(refresh_tokens).where(refresh_tokens.c.token == old_refresh_token).values(token=new_refresh_token)
    await database.execute(query)


async def send_heartbeat(websocket: WebSocket, user_id: int, interval: int = 30):
    logging.info(f"Starting heartbeat for WebSocket: {websocket}")
    while True:
        await asyncio.sleep(interval)

        # Проверка и возможное обновление токена
        new_token, is_valid = await validate_and_refresh_token(websocket, user_id)

        if not is_valid:
            await websocket.close(code=4001)  # Недействительный токен
            return

        if new_token:
            await websocket.send_text(json.dumps({"action": "new_token", "token": new_token}))

        await websocket.send_text(json.dumps({"action": "ping"}))
        logging.info(f"Sent heartbeat to WebSocket: {websocket}")


# На старте приложения подключаемся к базе данных
@app.on_event("startup")
async def startup():
    await database.connect()


# При остановке приложения отключаемся от базы данных
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


async def get_current_websocket(websocket: WebSocket):
    logging.info(f"Getting current WebSocket: {websocket}")
    return websocket

async def get_token_from_db_by_phone_number(phone_number: str) -> Optional[str]:
    logging.info(f"Getting token from database by phone number: {phone_number}")
    query = select([tokens.c.token]).join(users).where(users.c.phone_number == phone_number)
    result = await database.fetch_one(query)
    if result:
        logging.info(f"Token found in database for phone number: {result.token}")
        return result.token
    else:
        logging.warning(f"Token not found in database for phone number: {phone_number}")
        return None


async def get_current_user_from_websocket(websocket: WebSocket) -> Optional[UserInDB]:
    logging.info(f"Getting user from WebSocket: {websocket}")
    # Проверка состояния WebSocket
    logging.info(f"WebSocket state: {websocket.client_state}")

    access_token = websocket.cookies.get("access_token")
    if access_token is None:
        logging.warning("Access token not found in cookies.")
        return None

    logging.info(f"Access token found: {access_token}")

    user_id = await get_user_id_by_token(access_token)
    if user_id is None:
        logging.warning("User ID is None. Possibly invalid token.")
        return None

    phone_number = await get_phone_number_by_user_id(user_id)
    if phone_number is None:
        logging.error("Phone number not found for the user ID")
        return None

    new_access_token = await validate_and_refresh_token(websocket, user_id)
    if new_access_token is None:
        logging.warning("Invalid access token or failed to refresh.")
        return None

    if access_token != new_access_token:
        await websocket.send_text(json.dumps({"action": "refresh_token", "new_token": new_access_token}))

    user = await get_user_by_phone(phone_number)
    if user is None:
        logging.warning("User not found.")
        return None

    return user

# Проверяет, является ли хеш пароля действительным (соответствует формату bcrypt).
def is_password_hash_valid(password_hash: str):
    return password_hash.startswith(b'$2a$') or password_hash.startswith(b'$2b$') or password_hash.startswith(b'$2y$')


# Проверяет, соответствует ли введенный пароль хешу пароля пользователя.
def is_password_correct(password: str, password_hash: str):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash)


# Аутентифицирует пользователя, сравнивая введенный пароль с хешем пароля в базе данных.
async def authenticate_user(phone_number: str, password: str):
    user = await get_user_by_phone(phone_number)
    if user is None:
        return False

    password_hash = user.password.encode('utf-8')
    if not is_password_hash_valid(password_hash):
        logging.error(f"Invalid bcrypt hash for user {phone_number}")
        return False

    if not is_password_correct(password, password_hash):
        logging.error(f"Password incorrect for user {phone_number}")
        return False

    return user


# Добавляет нового пользователя в базу данных.
async def add_user(gender, last_name, first_name, middle_name, nickname, phone_number, position, email, password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    query = users.insert().values(gender=gender, last_name=last_name, first_name=first_name, middle_name=middle_name,
                                  nickname=nickname,
                                  phone_number=phone_number, position=position, email=email, password=hashed_password)
    logging.info(f"Executing query: {query}")  # Debug info
    result = await database.execute(query)
    logging.info(f"Result: {result}")  # Debug info
    return result


# Возвращает всех пользователей из базы данных.
async def get_all_users(search_query: str = "") -> List[dict]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()
    if search_query:
        search_query = "%" + search_query + "%"  # Форматируем запрос для использования в операторе LIKE
        await cur.execute(
            "SELECT id, first_name, last_name, phone_number FROM Users WHERE first_name LIKE %s OR last_name LIKE %s OR phone_number LIKE %s",
            (search_query, search_query, search_query),
        )
    else:
        await cur.execute(
            "SELECT id, first_name, last_name, phone_number FROM Users",
        )
    result = []
    async for row in cur:
        result.append({"id": row[0], "first_name": row[1], "last_name": row[2], "phone_number": row[3]})
    await cur.close()
    conn.close()
    return result


# Получает все сообщения из указанного чата.
async def get_chat_messages(chat_id: int):
    try:
        query = chatmessages.select().where(chatmessages.c.chat_id == chat_id).order_by(chatmessages.c.timestamp)
        chat_messages = await database.fetch_all(query)
        return chat_messages
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error getting chat messages")


async def get_user_chats(phone_number: str):
    try:
        # Выбираем идентификаторы чатов, в которых участвует пользователь
        query = ChatMembers.select().where(ChatMembers.c.user_phone_number == phone_number)
        user_chat_ids = await database.fetch_all(query)

        updated_user_chats = []  # Список для обновленных данных чатов

        # Для каждого идентификатора чата, получить информацию о чате
        for chat_id in user_chat_ids:
            query = userchats.select().where(userchats.c.id == chat_id['chat_id'])
            chat = await database.fetch_one(query)

            # Для каждого чата, получить последнее сообщение
            query = chatmessages.select().where(chatmessages.c.chat_id == chat_id['chat_id']).order_by(
                chatmessages.c.timestamp.desc()).limit(1)
            last_message = await database.fetch_one(query)

            updated_chat = dict(chat)  # Создаем новый словарь из данных chat
            if last_message:
                updated_chat['last_message'] = last_message['message']
                updated_chat['last_message_sender_phone'] = last_message[
                    'sender_phone_number']  # добавляем номер отправителя последнего сообщения
                updated_chat['last_message_timestamp'] = last_message['timestamp']

            updated_user_chats.append(updated_chat)  # Добавляем обновленный чат в список

        return updated_user_chats
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error getting user chats")


# Получает чат по идентификатору.
async def get_chat(chat_id: int):
    query = userchats.select().where(userchats.c.id == chat_id)
    chat = await database.fetch_one(query)
    return chat


# Получает всех участников определенного чата
async def get_chat_members(chat_id: int):
    try:
        query = ChatMembers.select().where(ChatMembers.c.chat_id == chat_id)
        chat_members = await database.fetch_all(query)

        # Преобразование результатов в словари
        chat_members = [dict(row) for row in chat_members]

        return chat_members
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error getting chat members")


# Маршрут к странице участников чата
@app.get("/chat/{chat_id}/members", response_class=HTMLResponse)
async def read_chat_members(request: Request, chat_id: int,
                            current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    # Этот маршрут отображает всех участников конкретного чата
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    members = await get_chat_members(chat_id)
    members_info = [await get_user(member['user_phone_number']) for member in members]
    # Отсортировать список участников так, чтобы владелец был первым
    members_info.sort(key=lambda member: member['phone_number'] != chat['owner_phone_number'])
    return templates.TemplateResponse("chatmembers.html", {"request": request, "chat": chat, "members": members_info,
                                                           "current_user": current_user})


# Исправленная функция, обращающаяся к БД
async def add_chat_member_db(chat_id: int, phone_number: str):
    try:
        query = ChatMembers.select().where(ChatMembers.c.chat_id == chat_id)
        members = await database.fetch_all(query)

        if len(members) >= 200:
            raise HTTPException(status_code=400, detail="The chat has reached the maximum number of members")

        query = ChatMembers.insert().values(chat_id=chat_id, user_phone_number=phone_number)
        await database.execute(query)

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error adding chat member")


@app.get("/chat/{chat_id}/members/add", response_class=HTMLResponse)
async def invite_to_chat(request: Request, chat_id: int, search_query: Optional[str] = None,
                         current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    print(f"Поисковый запрос: {search_query}")  # Логируем поисковый запрос

    chat = await get_chat(chat_id)
    members = await get_chat_members(chat_id)
    members_phone_numbers = [member['user_phone_number'] for member in members]

    if search_query:
        all_users = await search_users(search_query)
    else:
        all_users = await get_all_users()

    # Используем .phone_number вместо ['phone_number']
    inviteable_users = [user for user in all_users if
                        user['phone_number'] not in members_phone_numbers and user[
                            'phone_number'] != current_user.phone_number]

    return templates.TemplateResponse("addtochat.html", {"request": request, "chat": chat, "users": inviteable_users,
                                                         "current_user": current_user})


@app.post("/chat/{chat_id}/members/{phone_number}/add", response_class=RedirectResponse)
async def add_chat_member(request: Request, chat_id: int, phone_number: str,
                          current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    await add_chat_member_db(chat_id, phone_number)  # Исправленный вызов функции
    member_count = len(await get_chat_members(chat_id))
    await send_member_count_update(chat_id, member_count)
    return RedirectResponse(url=f"/chat/{chat_id}/members", status_code=303)


@app.get("/chat/{chat_id}/members/search", response_class=HTMLResponse)
async def search_chat_members(request: Request, chat_id: int, search_user: str,
                              current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    members = await get_chat_members(chat_id)
    members_info = [await get_user(member['user_phone_number']) for member in members]

    search_results = None
    if search_user:  # Проверка, что поисковый запрос не пустой
        # Поиск среди участников чата
        search_results = list(filter(
            lambda member: search_user.lower() in member['first_name'].lower() or search_user.lower() in member[
                'last_name'].lower() or search_user.lower() in member['nickname'].lower() or search_user in member[
                               'phone_number'], members_info))

    # Отсортировать список участников так, чтобы владелец был первым
    members_info.sort(key=lambda member: member['phone_number'] != chat['owner_phone_number'])

    # Возвращаем search_results только если поисковый запрос был выполнен
    return templates.TemplateResponse("chatmembers.html", {"request": request, "chat": chat, "members": members_info, "current_user": current_user,"search_results": search_results})


# Удаляет пользователя из чата.
async def delete_chat_member(chat_id: int, phone_number: str):
    try:
        query = ChatMembers.delete().where(
            and_(ChatMembers.c.chat_id == chat_id, ChatMembers.c.user_phone_number == phone_number))
        result = await database.execute(query)
        return result
    except SQLAlchemyError as e:
        print(str(e))  # line for debug
        raise HTTPException(status_code=500, detail="Error deleting chat member")


# Маршрут для удлаения частника из чата
@app.post("/chats/{chat_id}/members/{phone_number}/delete")
async def remove_chat_member(chat_id: int, phone_number: str,
                             current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    phone_number = unquote(phone_number)  # decode the phone number

    chat = await get_chat(chat_id)
    if not chat:
        print(f"Chat {chat_id} not found")  # line for debug
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.owner_phone_number != current_user.phone_number:
        raise HTTPException(status_code=403, detail="Only the chat owner can remove members")

    result = await delete_chat_member(chat_id, phone_number)
    if not result:
        print(f"Member {phone_number} not found in chat {chat_id}")  # line for debug
        raise HTTPException(status_code=404, detail="Member not found")

    member_count = len(await get_chat_members(chat_id))
    await send_member_count_update(chat_id, member_count)

    return RedirectResponse(url=f"/chat/{chat_id}/members", status_code=status.HTTP_303_SEE_OTHER)



async def create_poll(chat_id: int, creator_phone_number: str, question: str, options: List[str]):
    poll_query = Polls.insert().values(chat_id=chat_id, creator_phone_number=creator_phone_number, question=question)
    last_poll_id = await database.execute(poll_query)

    for option in options:
        option_query = PollOptions.insert().values(poll_id=last_poll_id, poll_option=option)
        await database.execute(option_query)

    return last_poll_id


def is_poll(message):
    # Если формат сообщения соответствует "Опрос: {id}", то это опрос
    if message.startswith("Опрос: "):
        return int(message.split(" ")[1])
    else:
        return None


async def get_poll(poll_id: int, current_user_phone_number: str):
    query = select([Polls]).where(Polls.c.id == poll_id)
    poll = await database.fetch_one(query)

    if poll is not None:
        # Создаем новый словарь с данными опроса
        poll_data = dict(poll)

        # Получаем варианты ответов для опроса
        options_query = select([PollOptions]).where(PollOptions.c.poll_id == poll_id)
        poll_options = await database.fetch_all(options_query)

        # Сохраняем варианты ответов в словаре
        poll_data['options'] = {option['id']: option['poll_option'] for option in poll_options}

        # Проверяем, голосовал ли текущий пользователь уже в этом опросе
        query = select([PollVotes]).where(PollVotes.c.poll_id == poll_id,
                                          PollVotes.c.voter_phone_number == current_user_phone_number)
        user_vote = await database.fetch_one(query)
        poll_data['user_voted'] = user_vote is not None

        return poll_data
    else:
        return None


@app.post("/chats/{chat_id}/create_poll")
async def create_poll_endpoint(chat_id: int, creator_phone_number: str = Form(...), question: str = Form(...),
                               options: List[str] = Form(...)):
    last_record_id = await create_poll(chat_id, creator_phone_number, question, options)

    # Добавляем опрос как сообщение в чат с особым форматированием или типом.
    message_content = f"Опрос: {last_record_id}"  # Используем идентификатор опроса
    message_query = chatmessages.insert().values(chat_id=chat_id, sender_phone_number=creator_phone_number,
                                                 message=message_content)
    await database.execute(message_query)

    # Перенаправляем пользователя обратно в чат после создания опроса
    return RedirectResponse(url=f"/chat/{chat_id}", status_code=status.HTTP_303_SEE_OTHER)


async def vote_on_poll(poll_id: int, option_id: int, voter_phone_number: str, chat_id: int):
    # Проверяем, голосовал ли пользователь уже в этом опросе
    query = select([PollVotes]).where(PollVotes.c.poll_id == poll_id,
                                      PollVotes.c.voter_phone_number == voter_phone_number)
    result = await database.fetch_one(query)
    if result is not None:
        raise HTTPException(status_code=400, detail="User has already voted in this poll")

    # Проверяем, существует ли опрос
    query = select([Polls]).where(Polls.c.id == poll_id)
    poll = await database.fetch_one(query)
    if poll is None:
        raise HTTPException(status_code=400, detail="The poll does not exist")

    # Проверяем, существует ли выбранный вариант ответа
    query = select([PollOptions]).where(PollOptions.c.poll_id == poll_id, PollOptions.c.id == option_id)
    option = await database.fetch_one(query)
    if option is None:
        raise HTTPException(status_code=400, detail="The option does not exist")

    # Добавляем голос в базу данных
    query = PollVotes.insert().values(poll_id=poll_id, option_id=option_id, voter_phone_number=voter_phone_number)
    await database.execute(query)

    # Получаем результаты голосования
    query = select([PollVotes.c.option_id, func.count(PollVotes.c.option_id)]).where(
        PollVotes.c.poll_id == poll_id).group_by(PollVotes.c.option_id)
    results = await database.fetch_all(query)

    total_votes = sum(result[1] for result in results)

    # Формируем результаты в виде словаря, где ключи - это option_id, а значения - это количество голосов и процент
    vote_results = {option_id: (count, count / total_votes * 100) for option_id, count in results}

    # Сохраняем результаты голосования в базе данных
    for option_id, (votes, percentage) in vote_results.items():
        query = PollResults.update().where(
            and_(PollResults.c.poll_id == poll_id, PollResults.c.option_id == option_id)).values(votes=votes,
                                                                                                 percentage=percentage)
        await database.execute(query)

    return vote_results


async def get_poll_results(poll_id: int) -> Dict[int, Tuple[int, float]]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    # Получаем все варианты ответа для опроса и инициализируем их нулевыми голосами
    await cur.execute("SELECT id FROM PollOptions WHERE poll_id = %s", (poll_id,))
    vote_counts = {option_id: 0 for option_id, in await cur.fetchall()}

    # Считаем голоса для каждого варианта
    await cur.execute("SELECT option_id FROM PollVotes WHERE poll_id = %s", (poll_id,))  # Use correct table name here
    for option_id, in await cur.fetchall():
        vote_counts[option_id] += 1

    await cur.close()
    conn.close()

    # Calculate the total number of votes
    total_votes = sum(vote_counts.values())

    # Calculate the percentage of votes for each option
    vote_counts = {option_id: (votes, votes / total_votes * 100) if total_votes > 0 else (votes, 0)
                   for option_id, votes in vote_counts.items()}

    return vote_counts


@app.post("/chats/{chat_id}/polls/{poll_id}/vote")
async def vote_on_poll_endpoint(poll_id: int, option_id: int = Form(...), voter_phone_number: str = Form(...),
                                chat_id: int = Path(...)):
    vote_results = await vote_on_poll(poll_id, option_id, voter_phone_number, chat_id)
    return RedirectResponse(url=f"/chat/{chat_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/chats/{chat_id}/polls/{poll_id}/results")
async def get_poll_results_endpoint(poll_id: int):
    results = await get_poll_results(poll_id)
    return results


async def delete_poll_data(poll_id: int):
    # Удалить сообщение, связанное с опросом
    message_content = f"Опрос: {poll_id}"
    message_query = chatmessages.delete().where(chatmessages.c.message == message_content)
    await database.execute(message_query)

    # Удалить все голоса для данного опроса
    query = PollVotes.delete().where(PollVotes.c.poll_id == poll_id)
    await database.execute(query)

    # Удалить все варианты ответа для данного опроса
    query = PollOptions.delete().where(PollOptions.c.poll_id == poll_id)
    await database.execute(query)

    # Удалить сам опрос
    query = Polls.delete().where(Polls.c.id == poll_id)
    await database.execute(query)


@app.post("/chats/{chat_id}/polls/{poll_id}/end")
async def end_poll(chat_id: int, poll_id: int, current_user_phone_number: str):
    # Получить опрос из базы данных
    poll = await get_poll(current_user_phone_number, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    # Установить поле `ended` в True
    poll_query = (
        Polls
        .update()
        .where(Polls.c.id == poll_id)
        .values(is_ended=True)
    )
    await database.execute(poll_query)

    # Вернуться обратно в чат
    return RedirectResponse(url=f"/chat/{chat_id}", status_code=status.HTTP_303_SEE_OTHER)


# Создает новое сообщение в чате.
async def create_message(chat_id: int, message_text: str, sender_phone_number: str):
    try:
        query = chatmessages.insert().values(
            message=message_text,
            chat_id=chat_id,
            sender_phone_number=sender_phone_number,
            timestamp=datetime.now()
        )
        await database.execute(query)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error creating message")


# Создает новый чат.
async def create_new_chat(chat_name: str, owner_phone_number: str, user_phone: str):
    try:
        query = userchats.insert().values(chat_name=chat_name, owner_phone_number=owner_phone_number)
        last_record_id = await database.execute(query)

        # Add the owner as a member of the chat
        await add_chat_member_db(last_record_id, owner_phone_number)

        # Add the user_phone as a member of the chat
        await add_chat_member_db(last_record_id, user_phone)

        return last_record_id
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error creating new chat")


# Возвращает файл по его идентификатору.
@app.get("/files/{file_id}")
async def get_file(file_id: int):
    logging.info(f"Fetching file with ID: {file_id} started")

    query = files.select().where(files.c.id == file_id)
    result = await database.fetch_one(query)

    logging.info(f"Fetching file with ID: {file_id} completed. Result: {result}")

    if result is None:
        logging.error(f"File with ID: {file_id} not found")
        raise HTTPException(status_code=404, detail="File not found")
    else:
        logging.info(f"File with ID: {file_id} found")

    # Get the original filename from the file_path
    original_filename = os.path.basename(result.file_path)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(original_filename)}"
    }

    return StreamingResponse(
        io.BytesIO(result.file),
        media_type=mimetypes.guess_type(f"dummy{result.file_extension}")[0],
        headers=headers
    )


# Сохраняет файл в базу данных.
async def save_file(phone_number: str, file_path: str, file_content: bytes, file_extension: str):
    query = files.insert().values(phone_number=phone_number, file_path=file_path, file=file_content,
                                  file_extension=file_extension)
    file_id = await database.execute(query)
    return file_id


# БЛОК УДАЛЕНИЯ СООБЩЕНИЙ ИЗ ЧАТА
# Получает сообщение по его идентификатору.
async def get_message_by_id(message_id: int):
    query = chatmessages.select().where(chatmessages.c.id == message_id)
    result = await database.fetch_one(query)
    return result


# Удаляет сообщение из базы данных.
async def delete_message_from_db(message_id: int):
    if message_id is None or message_id == 'undefined':
        return {"error": "Invalid message_id"}

    query = chatmessages.delete().where(chatmessages.c.id == message_id)
    await database.execute(query)
    return {"status": "message deleted"}


# Удаляет сообщение из чата, если текущий пользователь является автором этого сообщения.
@app.post("/chats/{chat_id}/messages/{message_id}/delete")
async def delete_message(
        chat_id: int,
        message_id: int,
        current_user: Union[str, RedirectResponse] = Depends(get_current_user)
):
    logging.info(f"Attempting to delete a message with ID: {message_id}")

    if message_id == 'undefined':
        logging.warning("Invalid message_id")
        raise HTTPException(status_code=400, detail="Invalid message_id")

    try:
        message_id = int(message_id)  # Преобразуем в целочисленный тип
    except ValueError:
        logging.error("Failed to convert message_id to integer")
        raise HTTPException(status_code=400, detail="Invalid message_id")

    if isinstance(current_user, RedirectResponse):
        return current_user

    message = await get_message_by_id(message_id)
    chat = await get_chat(chat_id)

    if message is None or message.chat_id != chat_id or (
            message.sender_phone_number != current_user.phone_number and chat[
        'owner_phone_number'] != current_user.phone_number):
        logging.error("Message not found or user is not the author or the chat admin")
        raise HTTPException(status_code=404, detail="Message not found or user is not the author or the chat admin")

    if message.message.startswith("Опрос: "):
        poll_id = int(message.message[7:])
        poll = await get_poll(poll_id, current_user.phone_number)
        if poll is not None:
            await delete_poll_data(poll_id)

    query = chatmessages.delete().where(chatmessages.c.id == message_id)
    logging.info(f"Executing query: {query}")

    try:
        await database.execute(query)
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url=f"/chats/{chat_id}", status_code=303)

# БЛОК МАРШРУТЫ
async def get_current_user_from_request(request: Request) -> Optional[UserInDB]:
    token = request.cookies.get("access_token")  # Извлечение токена из куки
    if token is None:
        logging.warning("Token is missing.")
        return None

    logging.info(f"Token extracted: {token}")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone_number: str = payload.get("sub")
        if phone_number is None:
            logging.error("Phone number not found in payload")
            raise credentials_exception

        user = await get_user_by_phone(phone_number)
        if user is None:
            logging.error("User not found by phone number")
            raise credentials_exception

        logging.info(f"User found: {user}")
        return user
    except PyJWTError as e:
        logging.error(f"JWT error: {e}")
        raise credentials_exception


# Маршрут к главной странице
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, current_user: Optional[User] = Depends(
    get_current_user_from_request)):  # Используем функцию для получения текущего пользователя из заголовка
    logging.info('Root route called')
    if current_user is None:
        logging.info('No current user, redirecting to login')
        return templates.TemplateResponse("login.html", {"request": request})
    else:
        logging.info(f'Current user: {current_user}, redirecting to home')
        return RedirectResponse(url="/home", status_code=303)


# Маршрут к странице входа в систему
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    # Этот маршрут отображает форму входа
    return templates.TemplateResponse('login.html', {"request": request})


# Маршрут для аутентификации пользователя
@app.post("/login")
async def login_user(request: Request, phone_number: str = Form(...), password: str = Form(...)):
    logging.info(f'Attempting to login user: {phone_number}')
    user = await authenticate_user(phone_number, password)
    if not user:
        logging.info(f'Failed to login user: {phone_number}')
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid login details"})
    else:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.phone_number}, expires_delta=access_token_expires
        )
        access_expires_at = datetime.utcnow() + access_token_expires

        # Сохранение access_token в базе данных
        await save_token_to_db(database, user.id, access_token, access_expires_at)

        refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token_data = {"sub": user.phone_number, "type": "refresh"}
        refresh_token = create_refresh_token(data=refresh_token_data, expires_delta=refresh_token_expires)

        # Store the refresh token in the database
        query = refresh_tokens.insert().values(user_id=user.id, token=refresh_token,
                                               expires_at=datetime.utcnow() + refresh_token_expires)
        logging.info(f"Inserting refresh token: {query}")
        await database.execute(query)

        logging.info(f'Generated access and refresh tokens for user: {phone_number}')

        # Redirect to the home page after successful login
        response_redirect = RedirectResponse(url="/home", status_code=303)
        response_redirect.set_cookie(key="access_token", value=access_token, httponly=True)
        return response_redirect



# Маршрут для выхода из системы
@app.get("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    # Delete the tokens from the database
    query = tokens.delete().where(tokens.c.user_id == current_user.id)
    await database.execute(query)

    query_refresh = refresh_tokens.delete().where(refresh_tokens.c.user_id == current_user.id)
    await database.execute(query_refresh)

    logging.info(f'User with ID {current_user.id} logged out. Redirecting to login page.')
    response_redirect = RedirectResponse(url="/login", status_code=303)
    response_redirect.delete_cookie(key="access_token")
    return response_redirect


# Маршрут к странице регистрации
@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    # Этот маршрут отображает форму регистрации
    return templates.TemplateResponse("register.html", {"request": request})


# Маршрут для регистрации пользователя
@app.post("/register")
async def register_user(gender: str = Form(...),
                        last_name: str = Form(...),
                        first_name: str = Form(...),
                        middle_name: str = Form(...),
                        nickname: str = Form(...),
                        phone_number: str = Form(...),
                        position: str = Form(...),
                        email: str = Form(...),
                        password: str = Form(...)):
    user_by_nickname = await get_user(nickname)
    user_by_phone = await get_user_by_phone(phone_number)
    if user_by_nickname:
        raise HTTPException(status_code=400, detail="Username already registered")
    if user_by_phone:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    await add_user(gender, last_name, first_name, middle_name, nickname, phone_number, position, email, password)
    token = create_access_token(data={"sub": phone_number})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/profile", response_class=HTMLResponse)
async def user_profile(request: Request):
    # Получаем токен из куки
    access_token = request.cookies.get("access_token")

    # Проверяем и обновляем токен, если нужно
    new_token, is_valid = await validate_and_refresh_token(request, None, request_type="http")

    if not is_valid:
        raise HTTPException(status_code=403, detail="You must be logged in to view the profile")

    # Извлекаем phone_number из токена
    payload = jwt.decode(new_token, SECRET_KEY, algorithms=[ALGORITHM])
    phone_number = payload.get("sub")

    # Извлекаем информацию о пользователе из базы данных
    user = await get_user_by_phone(phone_number)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Передаем информацию о пользователе в шаблон
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


@app.get("/profile/{phone_number}", response_class=HTMLResponse)
async def profile(request: Request, phone_number: str):
    user = await get_user_by_phone(phone_number)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


async def update_user_profile(phone_number, nickname, profile_picture, status):
    query = (
        update(users).
        where(users.c.phone_number == phone_number).
        values(nickname=nickname, profile_picture=profile_picture, status=status))
    await database.execute(query)


async def update_user_nickname(phone_number: str, new_nickname: str):
    query = users.update().where(users.c.phone_number == phone_number).values(nickname=new_nickname)
    logging.info(f"Updating field nickname for user with phone number: {phone_number} to {new_nickname}")
    result = await database.execute(query)
    logging.info(f"Field nickname updated successfully for user {phone_number}")
    return result


async def update_user_status(phone_number: str, new_status: str):
    query = users.update().where(users.c.phone_number == phone_number).values(status=new_status)
    logging.info(f"Updating field status for user with phone number: {phone_number} to {new_status}")
    result = await database.execute(query)
    logging.info(f"Field status updated successfully for user {phone_number}")
    return result


async def update_user_profile_picture(phone_number: str, new_profile_picture: str):
    query = users.update().where(users.c.phone_number == phone_number).values(profile_picture=new_profile_picture)
    logging.info(f"Updating field profile_picture for user with phone number: {phone_number} to {new_profile_picture}")
    result = await database.execute(query)
    logging.info(f"Field profile_picture updated successfully for user {phone_number}")
    return result


@app.get("/profile/picture/{phone_number}", response_class=FileResponse)
async def get_profile_picture(request: Request, phone_number: str):
    # Получаем токен из куки
    access_token = request.cookies.get("access_token")

    # Проверяем и обновляем токен, если нужно
    new_token, is_valid = await validate_and_refresh_token(request, None, request_type="http")

    if not is_valid:
        raise HTTPException(status_code=403, detail="You must be logged in to view the profile picture")
    user = await get_user_by_phone(phone_number)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.profile_picture is None or not os.path.exists(user.profile_picture.decode('utf-8')):
        default_image_path = os.path.join('images', 'default.jpg')
        if os.path.exists(default_image_path):
            return FileResponse(default_image_path)
        else:
            raise HTTPException(status_code=404, detail="Default image not found")

    profile_picture_path = user.profile_picture.decode('utf-8')
    return FileResponse(profile_picture_path)


async def save_profile_picture(profile_picture: UploadFile):
    try:
        # Если папка для фотографий профиля не существует, создаем ее
        if not os.path.exists(PROFILE_PICTURES_FOLDER):
            os.makedirs(PROFILE_PICTURES_FOLDER)

        # Создаем путь к файлу
        file_path = os.path.join(PROFILE_PICTURES_FOLDER, profile_picture.filename)

        # Записываем файл
        async with async_open(file_path, 'wb') as out_file:
            content = await profile_picture.read()  # Считываем содержимое
            await out_file.write(content)

        # Возвращаем путь к файлу как байты
        return str(file_path).encode('utf-8')

    except Exception as e:
        print(f"Unable to save profile picture. {e}")
        return None


@app.post("/profile/delete_picture")
async def delete_profile_picture(request: Request):
    # Получаем токен из куки
    access_token = request.cookies.get("access_token")

    # Проверяем и обновляем токен, если нужно
    new_token, is_valid = await validate_and_refresh_token(request, None, request_type="http")

    if not is_valid:
        raise HTTPException(status_code=403, detail="You must be logged in to delete the profile picture")

    # Извлекаем phone_number из токена
    payload = jwt.decode(new_token, SECRET_KEY, algorithms=[ALGORITHM])
    phone_number = payload.get("sub")

    await update_user_profile_picture(phone_number, "images/default.jpg")
    return RedirectResponse(url="/profile", status_code=303)



@app.post("/profile/update")
async def update_user_profile(request: Request,
                              nickname: str = Form(None),
                              status: str = Form(None),
                              profile_picture: UploadFile = File(None),
                              delete_picture: bool = Form(False)):
    # Получаем токен из куки
    access_token = request.cookies.get("access_token")

    # Проверяем и обновляем токен, если нужно
    new_token, is_valid = await validate_and_refresh_token(request, None, request_type="http")

    if not is_valid:
        raise HTTPException(status_code=403, detail="You must be logged in to edit the profile")

    # Извлекаем phone_number из токена
    payload = jwt.decode(new_token, SECRET_KEY, algorithms=[ALGORITHM])
    phone_number = payload.get("sub")

    # Остальная часть функции остается прежней
    user = await get_user_by_phone(phone_number)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if nickname:
        await update_user_nickname(phone_number, nickname)

    await update_user_status(phone_number, status)

    if delete_picture:
        await update_user_profile_picture(phone_number, "images/default.jpg")
    elif profile_picture:
        picture_path = await save_profile_picture(profile_picture)
        if picture_path is not None:
            await update_user_profile_picture(phone_number, picture_path)

    return RedirectResponse(url=f'/profile/{phone_number}', status_code=303)


async def update_user_field(phone_number: str, field: str, new_value: str):
    async with AsyncSession(engine) as session:
        print(f"Updating field {field} for user with phone number: {phone_number} to {new_value}")
        user = await session.execute(select(User).where(User.phone_number == phone_number))
        user = user.scalar_one_or_none()

        if user is None:
            raise ValueError("User not found")

        setattr(user, field, new_value)
        session.add(user)
        await session.commit()
        print(f"Field {field} updated successfully for user {phone_number}")


async def get_user_dialogs(current_user_id: int) -> list:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()
    await cur.execute("""
        SELECT 
            Dialogs.id,
            Users.id,
            Users.phone_number,
            Users.last_online
        FROM Dialogs
        JOIN Users ON (Dialogs.user1_id = Users.id OR Dialogs.user2_id = Users.id) AND Users.id != %s
        WHERE (Dialogs.user1_id = %s AND Dialogs.user1_deleted = 0) 
            OR (Dialogs.user2_id = %s AND Dialogs.user2_deleted = 0)
    """, (current_user_id, current_user_id, current_user_id))
    rows = await cur.fetchall()
    await cur.close()
    conn.close()

    dialogs = []
    for row in rows:
        dialog_id = row[0]
        # Запрос на последнее сообщение
        query = dialog_messages.select().where(dialog_messages.c.dialog_id == dialog_id).order_by(
            dialog_messages.c.timestamp.desc()).limit(1)
        last_message = await database.fetch_one(query)
        if last_message:
            dialogs.append({
                "id": row[0],
                "user_id": row[1],
                "interlocutor_phone_number": row[2],
                "last_online": row[3],
                "last_message": last_message['message'],
                "last_message_timestamp": last_message['timestamp']
            })
    return dialogs


async def get_subscribed_channels(user_phone_number: str):
    # Выборка из таблицы channel_members, где user_phone_number равен номеру телефона пользователя
    query = channel_members.select().where(channel_members.c.user_phone_number == user_phone_number)
    result = await database.fetch_all(query)

    # Создаем список для хранения информации о подписанных каналах
    subscribed_channels = []

    # Цикл по всем записям из выборки
    for record in result:
        # Выбираем информацию о канале по его ID из таблицы channels
        channel_query = channels.select().where(channels.c.id == record['channel_id'])
        channel_info = await database.fetch_one(channel_query)

        # Добавляем информацию о канале в список
        subscribed_channels.append(dict(channel_info))

    # Возвращаем список с информацией о подписанных каналах
    return subscribed_channels


@app.get("/home", response_class=HTMLResponse)
async def main_page(request: Request, current_user: User = Depends(get_current_user_from_request),
                    search_query: str = None):
    logging.info('Main page route called')

    # Добавляем логирование для токенов
    access_token = request.cookies.get("access_token")
    logging.info(f"Access token received in main_page: {access_token}")

    if current_user is None:
        logging.info('No current user, redirecting to login from main page')
        return RedirectResponse(url="/login", status_code=303)

    search_results_chats = []
    search_results_channels = []
    user_chats = await get_user_chats(current_user.phone_number)
    user_channels = await get_user_channels(current_user.phone_number)
    subscribed_channels = await get_subscribed_channels(current_user.phone_number)

    if search_query and search_query.strip():
        search_results_chats, search_results_channels = await search_chats_and_channels(search_query)

    # Получаем все доступные диалоги для текущего пользователя
    user_dialogs = await get_user_dialogs(current_user.id)

    # Выбираем первый доступный диалог, если он есть
    first_dialog = user_dialogs[0] if user_dialogs else None

    # Если есть доступный диалог, получаем его полные данные
    dialog = await get_dialog_by_id(first_dialog['id'], current_user.id) if first_dialog else None

    # Здесь мы создаем объект ответа и устанавливаем куки
    response = templates.TemplateResponse("chats.html", {
        "request": request,
        "chats": user_chats,
        "channels": user_channels,
        "current_user": current_user,
        "search_results_chats": search_results_chats,
        "search_results_channels": search_results_channels,
        "subscribed_channels": [channel['id'] for channel in subscribed_channels],
        "dialogs": user_dialogs,
        "search_query": search_query,
        "dialog": dialog,  # Добавляем dialog в контекст
    })

    # Устанавливаем куки для access_token
    response.set_cookie("access_token", access_token)
    return response


# Маршрут к странице чатов пользователя
@app.get("/chats", response_class=HTMLResponse)
async def read_chats(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chats = await get_user_chats(current_user.phone_number)
    channels = await get_user_channels(current_user.phone_number)
    left_chats = request.session.get('left_chats', [])  # получаем список покинутых чатов
    return templates.TemplateResponse("chats.html", {
        "request": request,
        "chats": chats,
        "channels": channels,
        "current_user": current_user,
        "left_chats": left_chats  # передаем список в шаблон
    })


async def is_member_of_chat(chat_id: int, phone_number: str):
    try:
        logging.info(f"Checking if user with phone_number {phone_number} is a member of chat {chat_id}")
        members = await get_chat_members(chat_id)
        logging.info(f"Members of chat {chat_id}: {members}")
        is_member = any(member['user_phone_number'] == phone_number for member in members)
        logging.info(f"Is user a member of chat {chat_id}: {is_member}")
        return is_member
    except Exception as e:
        logging.error(f"An error occurred while checking membership: {e}")
        return False


@app.get("/chat/{chat_id}", response_class=HTMLResponse)
async def read_chat(request: Request, chat_id: int,
                    current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    messages = await get_chat_messages(chat_id)
    members = await get_chat_members(chat_id)  # получение списка участников
    is_member = await is_member_of_chat(chat_id, current_user.phone_number)

    # Получение опросов
    polls = []
    poll_results = {}
    user_voted = False  # Инициализация user_voted
    for message in messages:
        if message.message.startswith('Опрос: '):
            poll_id_str = message.message.split(' ')[1].split('\n')[0]
            if poll_id_str.isdigit():
                poll_id = int(poll_id_str)
                poll = await get_poll(poll_id, current_user['phone_number'])
                if poll:
                    polls.append(poll)
                    poll_results[poll_id] = await get_poll_results(poll_id)
                    user_voted = bool(await database.fetch_one(
                        query="SELECT * FROM PollVotes WHERE poll_id = :poll_id AND voter_phone_number = :voter_phone_number",
                        values={"poll_id": poll_id, "voter_phone_number": current_user.phone_number}))

    return templates.TemplateResponse("chat.html", {"request": request, "chat": chat, "messages": messages, "polls": polls, "poll_results": poll_results, "user_voted": user_voted,  "current_user": current_user})


# Маршрут к странице создания нового чата
@app.get("/create_chat", response_class=HTMLResponse)
async def create_chat_page(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    # Этот маршрут отображает страницу создания нового чата
    if isinstance(current_user, RedirectResponse):
        return current_user
    users = await get_all_users()
    return templates.TemplateResponse("create_chat.html",
                                      {"request": request, "users": users, "current_user": current_user})


# Маршрут для создания нового чата
@app.post("/create_chat", response_class=HTMLResponse)
async def create_chat(request: Request, chat_name: str = Form(...), user_phone: str = Form(...),
                      current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Используем .phone_number вместо ['phone_number']
    chat_id = await create_new_chat(chat_name, current_user.phone_number, user_phone)

    return RedirectResponse(url=f"/chat/{chat_id}", status_code=303)  # перенаправление на страницу чата


# Маршрут отображает страницу конкретного чата и форму отправки нового сообщения
@app.get("/chats/{chat_id}", response_class=HTMLResponse)
async def chat_page(request: Request, chat_id: int,
                    current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = await get_chat_messages(chat_id)
    left_chats = request.session.get("left_chats", [])  # Получаем список покинутых чатов
    return templates.TemplateResponse("chat.html", {"request": request, "chat": chat, "messages": messages,
                                                    "current_user": current_user, "left_chats": left_chats})


# Маршрут для удаления чата
@app.post("/chats/{chat_id}/delete", response_class=HTMLResponse)
async def delete_chat(request: Request, chat_id: int,
                      current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Проверяем, является ли текущий пользователь владельцем чата
    chat = await get_chat(chat_id)
    if chat['owner_phone_number'] != current_user.phone_number:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this chat")

    try:
        # Удаляем результаты опросов в чате
        query = PollResults.delete().where(PollResults.c.poll_id == Polls.c.id).where(Polls.c.chat_id == chat_id)
        await database.execute(query)

        # Удаляем голоса в опросах
        query = PollVotes.delete().where(PollVotes.c.poll_id == Polls.c.id).where(Polls.c.chat_id == chat_id)
        await database.execute(query)

        # Удаляем варианты ответов в опросах
        query = PollOptions.delete().where(PollOptions.c.poll_id == Polls.c.id).where(Polls.c.chat_id == chat_id)
        await database.execute(query)

        # Удаляем опросы в чате
        query = Polls.delete().where(Polls.c.chat_id == chat_id)
        await database.execute(query)

        # Удаляем сообщения чата
        query = chatmessages.delete().where(chatmessages.c.chat_id == chat_id)
        await database.execute(query)

        # Удаляем участников чата
        query = ChatMembers.delete().where(ChatMembers.c.chat_id == chat_id)
        await database.execute(query)

        # Удаляем сам чат
        query = userchats.delete().where(userchats.c.id == chat_id)
        await database.execute(query)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error deleting the chat")

    return RedirectResponse(url="/chats", status_code=303)


async def get_chat_participants(chat_id: int):
    query = select([ChatMembers.c.user_phone_number]).where(ChatMembers.c.chat_id == chat_id)
    result = await database.fetch_all(query)
    return [row[0] for row in result]


@app.post("/chats/{chat_id}/send_message")
async def send_message_to_chat(chat_id: int, message_text: str = Form(None), file: UploadFile = File(None),
                               current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    # Проверка, является ли пользователь участником чата
    is_member = await is_member_of_chat(chat_id, current_user.phone_number)
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this chat")

    if isinstance(current_user, RedirectResponse):
        return current_user

    # Обрабатываем прикрепленный файл, если он есть
    file_id = None
    file_name = None
    if file and file.filename:
        file_content = await file.read()
        file_id = await save_file(current_user.phone_number, file.filename, file_content, os.path.splitext(file.filename)[1])
        file_name = file.filename

    # Преобразуем None в пустую строку, если пользователь не предоставил текст сообщения
    if message_text is None:
        message_text = ""

    # Если файл был загружен, добавьте информацию о файле в текст сообщения
    if file_id and file_name:
        file_info = f'[[FILE]]File ID: {file_id}, File Name: {file_name}[[/FILE]]'
        message_text = file_info if message_text is None else message_text + file_info

    try:
        await handle_chat_message(chat_id, message_text, current_user)
    except HTTPException:
        raise HTTPException(status_code=500, detail="Error sending message or uploading file")

    new_message = {
        "chat_id": chat_id,
        "sender_id": current_user.id,
        "message": message_text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "file_id": file_id,
        "file_name": file_name
    }

    # Отправляем сообщение через WebSocket
    room = f"chat_{chat_id}"
    #await manager.send_message_to_room(room, json.dumps({"action": "send_message", "message": new_message}))

    websocket = manager.get_connection(current_user.id, f"chat_{chat_id}")
    if websocket:
        await manager.send_message_to_room(f"chat_{chat_id}", json.dumps({"type": "new_message", "message": new_message}))
    else:
        logging.warning(f"No active connections found for room chat_{chat_id}")

    return RedirectResponse(url=f"/chats/{chat_id}", status_code=303)


# Этот маршрут обрабатывает действие "покинуть чат"
@app.post("/chats/{chat_id}/leave", response_class=RedirectResponse)
async def leave_chat(request: Request, chat_id: int,
                     current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    await delete_chat_member(chat_id, current_user['phone_number'])

    # Обновляем список покинутых чатов
    left_chats = request.session.get("left_chats", [])
    left_chats.append(chat_id)
    request.session["left_chats"] = left_chats

    return RedirectResponse(f"/chats", status_code=303)


# Этот маршрут обрабатывает действие "вернуться в чат"
@app.post("/chats/{chat_id}/return", response_class=RedirectResponse)
async def return_to_chat(request: Request, chat_id: int,
                         current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    await add_chat_member(chat_id, current_user['phone_number'])

    # Удаляем чат из списка покинутых
    left_chats = request.session.get("left_chats", [])
    if chat_id in left_chats:
        left_chats.remove(chat_id)
    request.session["left_chats"] = left_chats

    return RedirectResponse(f"/chat/{chat_id}", status_code=303)


# Vаршрут присоединения к чату
@app.post("/join_chat/{chat_id}")
async def join_chat(chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    query = ChatMembers.insert().values(chat_id=chat_id, user_phone_number=current_user.phone_number)
    await database.execute(query)

    return RedirectResponse(url=f"/chat/{chat_id}", status_code=status.HTTP_303_SEE_OTHER)


# БЛОК 3 КАНАЛ
# Функция, которая создает новый канал
async def create_new_channel(channel_name: str, owner_phone_number: str):
    try:
        query = channels.insert().values(name=channel_name, owner_phone_number=owner_phone_number)
        last_record_id = await database.execute(query)
        return last_record_id
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error creating new channel")


async def get_channel_messages(channel_id: int):
    query = channel_history.select().where(channel_history.c.channel_id == channel_id).order_by(
        channel_history.c.timestamp)
    messages = await database.fetch_all(query)
    return messages


@app.get("/create_channel", response_class=HTMLResponse)
async def create_channel_page(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    user_channels = await get_user_channels(current_user.phone_number)
    return templates.TemplateResponse("create_channel.html",
                                      {"request": request, "current_user": current_user, "channels": user_channels})


@app.post("/create_channel", response_class=HTMLResponse)
async def create_channel(request: Request, channel_name: str = Form(...),
                         current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    channel_id = await create_new_channel(channel_name, current_user.phone_number)
    return RedirectResponse(url=f"/channels/{channel_id}", status_code=303)


async def remove_user_from_channel(user_phone_number: str, channel_id: int):
    async with database.transaction():
        query = channel_members.delete().where(
            (channel_members.c.user_phone_number == user_phone_number) &
            (channel_members.c.channel_id == channel_id)
        )
        await database.execute(query)


async def get_channel_info(channel_id: int):
    stmt = select(channels).where(channels.c.id == channel_id)

    conn = engine.connect()  # Используем engine.connect() без контекстного менеджера
    result = conn.execute(stmt)

    channel_info = result.fetchone()

    return dict(channel_info)


@app.post("/channels/{channel_id}/subscribers/{subscriber_phone_number}/remove", response_class=RedirectResponse)
async def remove_subscriber(channel_id: int, subscriber_phone_number: str,
                            current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Получаем информацию о канале из БД
    channel_info = await get_channel_info(channel_id)

    # Если текущий пользователь не является админом канала, возвращаем ошибку
    if current_user["phone_number"] != channel_info["owner_phone_number"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    await remove_user_from_channel(subscriber_phone_number, channel_id)
    return RedirectResponse(f"/channels/{channel_id}/subscribers", status_code=303)


# Функция для отображения списка каналов созданных пользователем.
async def get_user_channels(user_phone_number: str):
    query = channels.select().where(channels.c.owner_phone_number == user_phone_number)
    owned_channels = await database.fetch_all(query)

    query = channel_members.select().where(channel_members.c.user_phone_number == user_phone_number)
    subscribed_channel_ids = await database.fetch_all(query)
    subscribed_channel_ids = [channel['channel_id'] for channel in subscribed_channel_ids]

    query = channels.select().where(channels.c.id.in_(subscribed_channel_ids))
    subscribed_channels = await database.fetch_all(query)

    # Initialize a list to store the channel info along with last message
    owned_channels_dicts = []
    subscribed_channels_dicts = []

    for channel in owned_channels:
        query = channel_history.select().where(and_(channel_history.c.channel_id == channel['id'],
                                                    channel_history.c.sender_phone_number == channel[
                                                        'owner_phone_number'])).order_by(
            channel_history.c.timestamp.desc())
        last_owner_message = await database.fetch_one(query)

        channel_dict = dict(channel)

        if last_owner_message:
            channel_dict['last_owner_message'] = last_owner_message['message']
            channel_dict['last_owner_message_timestamp'] = last_owner_message['timestamp']
            channel_dict['last_owner_message_file'] = last_owner_message['file_id']
            channel_dict['last_owner_message_file_name'] = last_owner_message['file_name']

        owned_channels_dicts.append(channel_dict)

    for channel in subscribed_channels:
        query = channel_history.select().where(channel_history.c.channel_id == channel['id']).order_by(
            channel_history.c.timestamp.desc())
        last_message = await database.fetch_one(query)

        channel_dict = dict(channel)

        if last_message:
            channel_dict['last_message'] = last_message['message']
            channel_dict['last_message_timestamp'] = last_message['timestamp']
            channel_dict['last_message_file'] = last_message['file_id']
            channel_dict['last_message_file_name'] = last_message['file_name']

        subscribed_channels_dicts.append(channel_dict)

    user_channels = owned_channels_dicts + subscribed_channels_dicts

    return user_channels


# Функция, которая добавляет пользователя в канал.
async def add_channel_member(channel_id: int, phone_number: str):
    try:
        query = channel_members.insert().values(channel_id=channel_id, user_phone_number=phone_number)
        result = await database.execute(query)  # store result of execution

        # Debug lines:
        print(f"Trying to add user {phone_number} to channel {channel_id}")
        print(f"Result of the operation: {result}")

    except SQLAlchemyError as e:
        print(f"Error occurred: {e}")  # Debug line to print the exception
        raise HTTPException(status_code=500, detail="Error adding channel member")


async def get_channel_subscribers(channel_id: int):
    query = select([users]).select_from(
        users.join(channel_members, users.c.phone_number == channel_members.c.user_phone_number)
    ).where(channel_members.c.channel_id == channel_id)

    subscribers = await database.fetch_all(query)
    return subscribers


async def search_subscribers(channel_id: int, search_user: str):
    query = select([users]).select_from(
        users.join(channel_members, users.c.phone_number == channel_members.c.user_phone_number)
    ).where(
        (channel_members.c.channel_id == channel_id) &
        (or_(
            users.c.first_name.ilike(f"%{search_user}%"),
            users.c.last_name.ilike(f"%{search_user}%"),
            users.c.phone_number.ilike(f"%{search_user}%")
        ))
    )

    search_results = await database.fetch_all(query)
    return search_results


@app.get("/channels/{channel_id}/subscribers", response_class=HTMLResponse)
async def view_subscribers(
        request: Request,
        channel_id: int,
        search_user: Optional[str] = None,
        current_user: Union[str, RedirectResponse] = Depends(get_current_user)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = channels.select().where(channels.c.id == channel_id)
    channel = await database.fetch_one(query)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if channel['owner_phone_number'] != current_user['phone_number']:
        raise HTTPException(status_code=403, detail="Forbidden")

    subscribers = await get_channel_subscribers(channel_id)
    search_results = []
    if search_user:
        search_results = await search_subscribers(channel_id, search_user)

    return templates.TemplateResponse(
        "subscribers.html",
        {"request": request, "channel": channel, "subscribers": subscribers, "search_results": search_results,
         "current_user": current_user}
    )


@app.post("/join_channel/{channel_id}", response_class=RedirectResponse)
async def join_channel(channel_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    print(f"User {current_user['phone_number']} is trying to join channel {channel_id}")  # Debug line
    await add_channel_member(channel_id, current_user['phone_number'])
    print(f"User {current_user['phone_number']} has been added to channel {channel_id}")  # Debug line
    return RedirectResponse(f"/channels/{channel_id}", status_code=303)


@app.get("/channels/{channel_id}", response_class=HTMLResponse)
async def view_channel_page(request: Request, channel_id: int,
                            current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = channels.select().where(channels.c.id == channel_id)
    channel = await database.fetch_one(query)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Считаем количество подписчиков
    count_query = select([func.count()]).select_from(channel_members).where(channel_members.c.channel_id == channel_id)
    subscribers_count = await database.fetch_val(count_query)

    # Проверяем, является ли текущий пользователь владельцем канала
    is_owner = current_user.phone_number == channel.owner_phone_number

    messages = await get_channel_messages(channel_id)
    return templates.TemplateResponse("channel.html", {"request": request, "channel": channel, "messages": messages,
                                                       "current_user": current_user,
                                                       "subscribers_count": subscribers_count, "is_owner": is_owner})


@app.post("/channels/{channel_id}", response_class=HTMLResponse)
async def update_channel(request: Request, channel_id: int, new_content: str = Form(...),
                         current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = channels.update().where(channels.c.id == channel_id).values(content=new_content)
    await database.execute(query)
    return RedirectResponse(url=f"/", status_code=303)


async def create_channel_message(channel_id: int, message_text: str, sender_phone_number: str, file_id: int = None,
                                 file_name: str = None):
    try:
        current_time = datetime.now(MSK_TZ)
        query = channel_history.insert().values(
            channel_id=channel_id,
            message=message_text,
            timestamp=current_time,
            sender_phone_number=sender_phone_number,
            file_id=file_id,
            file_name=file_name
        )
        await database.execute(query)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error creating message in channel")


@app.post("/channels/{channel_id}/send_message", response_class=HTMLResponse)
async def send_channel_message(request: Request, channel_id: int, message_text: str = Form(...),
                               file: UploadFile = File(None),
                               current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Определение комнаты для канала
    room = f"channel_{channel_id}"

    # Отправка сообщения в канал через вебсокет
    await manager.send_message_to_room(room,
                                       f"New message in channel {channel_id} from user {current_user.phone_number}: {message_text}")

    # Проверяем, является ли текущий пользователь владельцем канала
    query = channels.select().where(channels.c.id == channel_id)
    channel = await database.fetch_one(query)

    if channel['owner_phone_number'] != current_user.phone_number:
        raise HTTPException(status_code=403, detail="You are not authorized to send messages in this channel")

    file_id = None
    file_name = None

    # Обрабатываем прикрепленный файл, если он есть
    if file and file.filename:
        print(f"Uploaded file: {file.filename}")  # добавлено для отладки
        # Здесь код для обработки файла
        contents = await file.read()
        file_id = await save_file(current_user.phone_number, file.filename, contents, file.filename.split('.')[-1])
        file_name = file.filename
    else:
        print("No file uploaded")  # добавлено для отладки

    await create_channel_message(channel_id, message_text, current_user.phone_number, file_id, file_name)
    return RedirectResponse(url=f"/channels/{channel_id}", status_code=303)


# Для просмотра истории сообщений канала вам также может потребоваться функция, которая будет извлекать сообщения из channel_history вместо message_history. Возможно, это будет выглядеть примерно так:
@app.get("/channels/{channel_id}/history", response_class=HTMLResponse)
async def get_channel_history(request: Request, channel_id: int,
                              current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = channel_history.select().where(channel_history.c.channel_id == channel_id).order_by(
        desc(channel_history.c.timestamp))
    messages = await database.fetch_all(query)
    return templates.TemplateResponse("channel_history.html",
                                      {"request": request, "messages": messages, "current_user": current_user})


async def delete_channel(channel_id: int):
    try:
        # Remove channel messages
        query = channel_history.delete().where(channel_history.c.channel_id == channel_id)
        await database.execute(query)

        # Remove channel members
        query = channel_members.delete().where(channel_members.c.channel_id == channel_id)
        await database.execute(query)

        # Remove channel
        query = channels.delete().where(channels.c.id == channel_id)
        await database.execute(query)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error deleting the channel")


@app.post("/channels/{channel_id}/delete", response_class=RedirectResponse)
async def delete_channel_route(channel_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Check if current user is the owner of the channel
    query = channels.select().where(channels.c.id == channel_id)
    channel = await database.fetch_one(query)

    if channel['owner_phone_number'] != current_user.phone_number:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this channel")

    await delete_channel(channel_id)

    return RedirectResponse(url=f"/", status_code=303)


async def delete_channel_message(message_id: int):
    try:
        # Remove message from channel
        query = channel_history.delete().where(channel_history.c.id == message_id)
        await database.execute(query)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error deleting the message")


@app.post("/channels/{channel_id}/delete_message/{message_id}", response_class=RedirectResponse)
async def delete_message_route(channel_id: int, message_id: int,
                               current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Check if current user is the owner of the channel
    query = channels.select().where(channels.c.id == channel_id)
    channel = await database.fetch_one(query)

    if channel['owner_phone_number'] != current_user.phone_number:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this message")

    await delete_channel_message(message_id)

    return RedirectResponse(url=f"/channels/{channel_id}", status_code=303)


@app.post("/channels/{channel_id}/leave")
async def leave_channel(channel_id: int, request: Request):
    # Получить текущего пользователя
    user = await get_current_user(request)

    # Убедимся, что мы получили пользователя
    assert user, f"Пользователь не найден в сессии. Сессия: {request.session}"

    # Убедимся, что мы получили идентификатор канала
    assert channel_id, "ID канала не указан"

    # Удалить пользователя из списка подписчиков канала
    await remove_user_from_channel(user.phone_number,
                                   channel_id)  # Передайте номер телефона пользователя, а не объект пользователя

    # Перенаправить пользователя на домашнюю страницу, где он увидит обновленный список каналов
    return RedirectResponse(url='/home', status_code=303)


# БЛОК ПОИСК
# Функция для поиска по чатам и каналам
async def search_chats_and_channels(search_query: str):
    try:
        # Поиск по чатам
        query_chats = userchats.select().where(userchats.c.chat_name.ilike(f"%{search_query}%"))
        search_results_chats = await database.fetch_all(query_chats)

        # Поиск по каналам
        query_channels = channels.select().where(channels.c.name.ilike(f"%{search_query}%"))
        search_results_channels = await database.fetch_all(query_channels)

        return search_results_chats, search_results_channels
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error getting search results")


# БЛОК ДИАЛОГ
# Маршрут для создания нового диалога
@app.get("/create_dialog", response_class=HTMLResponse)
async def create_dialog_route(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    return templates.TemplateResponse("create_dialog.html", {
        "request": request,
        "current_user": current_user,
        "users": await get_all_users(),
        "search_results": [],
    })


# Метод служит для поиска диалога.
@app.post("/create_dialog", response_class=HTMLResponse)
async def search_dialog_route(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    form = await request.form()
    search_query = form.get("search_query", "").strip()
    search_results = []
    if search_query:
        search_results = await search_users(search_query)

    return templates.TemplateResponse("create_dialog.html", {
        "request": request,
        "current_user": current_user,
        "users": await get_all_users(),
        "search_results": search_results,
    })


# Cоздает новый диалог между двумя пользователями.
async def create_new_dialog(user1_id: int, user2_id: int) -> int:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    await cur.execute("INSERT INTO Dialogs (user1_id, user2_id) VALUES (%s, %s)", (user1_id, user2_id))
    dialog_id = cur.lastrowid

    await conn.commit()
    await cur.close()
    conn.close()

    return dialog_id


# Функция поиска пользователей по заданному запросу.
async def search_users(query: str) -> List[dict]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()
    query = '%' + query + '%'
    await cur.execute(
        "SELECT id, first_name, last_name, phone_number FROM Users WHERE first_name LIKE %s OR last_name LIKE %s OR nickname LIKE %s OR phone_number LIKE %s",
        (query, query, query, query),
    )
    result = []
    async for row in cur:
        result.append({"id": row[0], "first_name": row[1], "last_name": row[2], "phone_number": row[3]})

    print(f"Результаты поиска: {result}")  # Логируем результаты поиска

    await cur.close()
    conn.close()
    return result


# Возвращает информацию о диалоге по его идентификатору. Если диалог не найден, возникает исключение
async def get_dialog_by_id(dialog_id: int, current_user_id: int, check_user_deleted: bool = True) -> dict:
    # Get the dialog information
    query = dialogs.select().where(dialogs.c.id == dialog_id)
    row = await database.fetch_one(query)

    # Check if the dialog exists
    if row is None:
        raise HTTPException(status_code=404, detail="Dialog not found")

    # Check if the dialog was deleted by the user
    if check_user_deleted and ((current_user_id == row['user1_id'] and row['user1_deleted']) or (
            current_user_id == row['user2_id'] and row['user2_deleted'])):
        raise HTTPException(status_code=410, detail="Dialog was deleted by the user")

    # Get the interlocutor information
    interlocutor_id = row['user1_id'] if row['user2_id'] == current_user_id else row['user2_id']
    interlocutor_query = users.select().where(users.c.id == interlocutor_id)
    interlocutor_info = await database.fetch_one(interlocutor_query)

    # Format the 'last_online' datetime if it exists, else set it as 'нет данных'
    if interlocutor_info['last_online']:
        utc_last_online = interlocutor_info['last_online'].replace(
            tzinfo=pytz.utc)  # assuming the time is stored in UTC
        last_online = utc_last_online.astimezone(moscow_tz).strftime('%Y-%m-%d %H:%M:%S')
    else:
        last_online = 'нет данных'

    # Return the dialog information
    return {
        "id": row['id'],
        "user1_id": row['user1_id'],
        "user2_id": row['user2_id'],
        "interlocutor_phone_number": interlocutor_info['phone_number'],
        "last_online": last_online,  # Updated to pass the formatted 'last_online' or 'нет данных'
        "user1_deleted": row['user1_deleted'],
        "user2_deleted": row['user2_deleted']
    }


# Возвращает все сообщения из данного диалога.
async def get_messages_from_dialog(dialog_id: int, message_id: int = None) -> List[dict]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()
    if message_id:
        await cur.execute("SELECT * FROM DialogMessages WHERE dialog_id = %s AND id = %s", (dialog_id, message_id))
    else:
        await cur.execute("SELECT * FROM DialogMessages WHERE dialog_id = %s", (dialog_id,))
    result = []
    async for row in cur:
        result.append({
            "id": row[0],
            "dialog_id": row[1],
            "sender_id": row[2],
            "message": row[3],
            "timestamp": row[4].strftime("%Y-%m-%d %H:%M:%S") if row[4] else None,
            "delete_timestamp": row[5].strftime("%Y-%m-%d %H:%M:%S") if row[5] else None
        })
    await cur.close()
    conn.close()

    # Send the messages through WebSocket
    room = f"dialog_{dialog_id}"
    await manager.send_message_to_room(room, json.dumps({"type": "initial_messages", "messages": result}))

    return result


# Добавляет новое сообщение в базу данных
async def send_message(dialog_id: int, sender_id: int, message: str):
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()
    await cur.execute("INSERT INTO DialogMessages (dialog_id, sender_id, message) VALUES (%s, %s, %s)",
                      (dialog_id, sender_id, message))
    await conn.commit()
    await cur.close()
    conn.close()

    # Send the message through WebSocket
    room = f"dialog_{dialog_id}"
    new_message = {
        "dialog_id": dialog_id,
        "sender_id": sender_id,
        "message": message,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    await manager.send_message_to_room(room, json.dumps({"type": "new_message", "message": new_message}))


# Общая функция для получения данных о диалоге и сообщениях
async def get_dialog_and_messages(dialog_id: int, current_user):
    if isinstance(current_user, RedirectResponse):
        return current_user, None, None

    dialog = await get_dialog_by_id(dialog_id, current_user.id)
    messages = await get_messages_from_dialog(dialog_id)
    return None, dialog, messages


# Маршрут для страницы диалога
@app.get("/dialogs/{dialog_id}", response_class=HTMLResponse)
async def dialog_route(dialog_id: int, request: Request,
                       current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    redirect, dialog, messages = await get_dialog_and_messages(dialog_id, current_user)
    if redirect:
        return redirect

    return templates.TemplateResponse("dialogs.html", {
        "request": request,
        "current_user": current_user,
        "dialog": dialog,
        "messages": messages,
    })


# Маршрут для API диалога
@app.get("/api/dialogs/{dialog_id}", response_class=HTMLResponse)
async def api_dialog_route(dialog_id: int, request: Request,
                           current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    redirect, dialog, messages = await get_dialog_and_messages(dialog_id, current_user)
    if redirect:
        return redirect

    return templates.TemplateResponse("dialogs.html", {
        "request": request,
        "current_user": current_user,
        "dialog": dialog,
        "messages": messages,
    })


async def update_last_online(user_id: int):
    current_time = datetime.utcnow()
    query = users.update(). \
        where(users.c.id == user_id). \
        values(last_online=current_time)
    await database.execute(query)


# Обработчик отправки сообщения в диалог
@app.post("/dialogs/{dialog_id}/send_message")
async def send_message_to_dialog(dialog_id: int, message: str = Form(None), file: UploadFile = File(None), current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    sender_id = current_user.id
    dialog = await get_dialog_by_id(dialog_id, sender_id, check_user_deleted=False)

    # Добавил эту строку для определения room
    room = f"dialog_{dialog_id}"

    await manager.send_message_to_room(room, f"New message in dialog {dialog_id} from user {sender_id}: {message}")

    if sender_id not in [dialog['user1_id'], dialog['user2_id']]:
        raise HTTPException(status_code=400, detail="User not in this dialog")

    receiver_id = dialog['user1_id'] if sender_id == dialog['user2_id'] else dialog['user2_id']
    if receiver_id == dialog['user1_id']:
        await update_dialog_deleted_status(dialog_id, deleted_by_user1=False)
    else:
        await update_dialog_deleted_status(dialog_id, deleted_by_user2=False)

    file_id = None
    file_name = None

    if file and file.filename:
        file_content = await file.read()
        file_id = await save_file(current_user.id, file.filename, file_content, file.filename.split('.')[-1])
        file_name = file.filename

    if file_id and file_name:
        file_info = f' [[FILE]]File ID: {file_id}, File Name: {file_name}[[/FILE]]'
        message = file_info if message is None else message + file_info

    if message is None:
        raise HTTPException(status_code=400, detail="No message or file to send")

    await send_message(dialog_id, sender_id, message)
    participants = [sender_id, receiver_id]
    await manager.broadcast(f"New message in dialog {dialog_id} from user {sender_id}: {message}")

    new_message = {
        "dialog_id": dialog_id,
        "sender_id": sender_id,
        "message": message,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    print(f"Sending message to dialog {dialog_id} from user {sender_id}: {message}")

    websocket = manager.get_connection(current_user.id, room)  # Изменил на переменную room
    if websocket and isinstance(websocket, WebSocket) and websocket.client_state == WebSocketState.CONNECTED:
        await manager.send_message_to_room(room, json.dumps({"type": "new_message", "message": new_message}))  # Изменил на переменную room
    else:
        logging.warning(f"No active connections found for room {room}")  # Изменил на переменную room

    await update_last_online(sender_id)

    return JSONResponse(content={"message": "Message sent successfully", "dialog_id": dialog_id})

@app.get("/create_dialog/{user_id}")
@app.post("/create_dialog/{user_id}")
async def create_dialog_handler(user_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Используем .id вместо ['id']
    dialog_id = await check_dialog_exists(current_user.id, user_id)

    if dialog_id is None:
        # Если диалог не существует, создаем новый диалог
        dialog_id = await create_new_dialog(current_user.id, user_id)

    # Перенаправляем пользователя на страницу диалога (нового или уже существующего)
    return RedirectResponse(url=f"/dialogs/{dialog_id}", status_code=status.HTTP_303_SEE_OTHER)


# Удаление сообщения из диалога
@app.post("/dialogs/{dialog_id}/delete_message/{message_id}")
async def delete_message(
        dialog_id: int,
        message_id: int,
        current_user: User = Depends(get_current_user)
):
    messages = await get_messages_from_dialog(dialog_id, message_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Message not found")

    message = messages[0]

    # Проверяем, есть ли у пользователя права на удаление этого сообщения
    if message["sender_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this message")

    await delete_message_by_id(message_id)

    return RedirectResponse(url=f"/dialogs/{dialog_id}", status_code=303)


# Функция полностью удаляет сообщение из базы данных.
async def delete_message_by_id(message_id: int):
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    # Полностью удаляем сообщение из базы данных
    await cur.execute("""
        DELETE FROM DialogMessages
        WHERE id = %s
    """, (message_id,))

    await conn.commit()
    await cur.close()
    conn.close()


# Маршрут, который обрабатывает удаление диалога.
## Обработчик удаления диалога
@app.post("/dialogs/{dialog_id}/delete_post", response_class=RedirectResponse)
async def delete_dialog(dialog_id: int, current_user: User = Depends(get_current_user)):
    dialog = await get_dialog_by_id(dialog_id, current_user.id, check_user_deleted=False)

    if dialog is None:
        raise HTTPException(status_code=404, detail="Dialog not found")

    if dialog['user1_id'] != current_user.id and dialog['user2_id'] != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this dialog")

    # Обновляем статус удаления для пользователя
    if dialog['user1_id'] == current_user.id:
        query = dialogs.update(). \
            where(dialogs.c.id == dialog_id). \
            values(user1_deleted=True)
        await database.execute(query)
    else:
        query = dialogs.update(). \
            where(dialogs.c.id == dialog_id). \
            values(user2_deleted=True)
        await database.execute(query)

    return RedirectResponse("/home", status_code=303)


# Проверка наличия активного диалога между двумя пользователями
async def check_dialog_exists(user1_id: int, user2_id: int) -> Union[int, None]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    await cur.execute(
        """
        SELECT id FROM Dialogs 
        WHERE ((user1_id = %s AND user2_id = %s) OR (user1_id = %s AND user2_id = %s))
        AND (user1_deleted = 0 OR user2_deleted = 0)
        """,
        (user1_id, user2_id, user2_id, user1_id),
    )

    row = await cur.fetchone()
    await cur.close()
    conn.close()

    return row[0] if row else None


# Обновление статуса удаления диалога
async def update_dialog_deleted_status(dialog_id: int, deleted_by_user1: bool = False, deleted_by_user2: bool = False):
    try:
        conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
        cur = await conn.cursor()
        await cur.execute("UPDATE Dialogs SET user1_deleted = %s, user2_deleted = %s WHERE id = %s",
                          (deleted_by_user1, deleted_by_user2, dialog_id))
        await conn.commit()
    except Exception as e:
        logging.error(f"Error updating dialog deleted status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await cur.close()
        conn.close()


# Получение сообщений диалога
async def get_dialog_messages(dialog_id: int) -> List[dict]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    # Выполнение SQL запроса
    await cur.execute("""
        SELECT 
            DialogMessages.id,
            DialogMessages.dialog_id,
            DialogMessages.sender_id,
            DialogMessages.message,
            DialogMessages.timestamp,
            DialogMessages.delete_timestamp,
            Users.first_name,
            Users.last_name
        FROM DialogMessages
        JOIN Users ON DialogMessages.sender_id = Users.id
        WHERE DialogMessages.dialog_id = %s
        ORDER BY DialogMessages.timestamp ASC
    """, (dialog_id,))

    # Получение всех строк и преобразование их в список словарей
    rows = await cur.fetchall()
    messages = []
    for row in rows:
        messages.append({
            "id": row[0],
            "dialog_id": row[1],
            "sender_id": row[2],
            "message": row[3],
            "timestamp": row[4],
            "delete_timestamp": row[5],
            "sender_first_name": row[6],
            "sender_last_name": row[7],
        })

    await cur.close()
    conn.close()

    return messages

async def get_dialog_history(dialog_id: int, user_id: int) -> dict:
    redirect, dialog, messages = await get_dialog_and_messages(dialog_id, user_id)
    if redirect:
        return {"error": "Redirect or some other issue"}

    dialog_history = {
        "dialog": dialog,
        "messages": messages
    }
    return dialog_history


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self.global_active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, room: str, existing_token: Optional[str] = None):
        if user_id in self.active_connections and room in self.active_connections[user_id]:
            logging.warning(f"Already an active connection for user {user_id} in room {room}.")
            old_websocket = self.active_connections[user_id][room]['websocket']
            if old_websocket.client_state == WebSocketState.CONNECTED:
                await old_websocket.close()
            # или объедините новое и старое соединение

        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}

        self.active_connections[user_id][room] = {"websocket": websocket, "state": WebSocketState.CONNECTED}
        self.add_global_connection(room, websocket)
        logging.info(f"Successfully connected user {user_id} to room {room}.")

    # В методе disconnect добавляем проверки
    def disconnect(self, user_id: int, room: str):
        if user_id not in self.active_connections or room not in self.active_connections[user_id]:
            logging.warning(f"No active connection for user {user_id} in room {room}.")
            return

        self.active_connections[user_id][room]['state'] = WebSocketState.DISCONNECTED
        self.remove_global_connection(room, self.active_connections[user_id][room]['websocket'])
        del self.active_connections[user_id][room]
        if not self.active_connections[user_id]:
            del self.active_connections[user_id]

    async def send_message(self, message: str, user_id: int, room: str):
        logging.info(f"Function send_message has been called for user {user_id} and room {room}")

        # Валидация сообщения
        if not message or not isinstance(message, str):
            logging.warning(f"Invalid message for user {user_id} and room {room}")
            return

        connection = self.get_connection(user_id, room)
        if connection:
            websocket = connection['websocket']
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # Конвертируем сообщение в JSON
                    message_json = json.dumps({"action": "new_message", "message": message, "sender": user_id})
                except (TypeError, ValueError) as e:
                    logging.error(f"Failed to create JSON: {e}")
                    return

                try:
                    logging.info(f"Sending message for user {user_id} and room {room}: {message}")
                    await websocket.send_text(message_json)
                except RuntimeError as e:
                    logging.error(f"An error occurred: {e}")

    async def send_message_to_room(self, room: str, message: str):
        # Добавленное логирование
        logging.info(f"Sending message to room {room}: {message}")

        if room in self.global_active_connections:
            for websocket in self.global_active_connections[room]:
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_text(message)
                    except RuntimeError as e:
                        logging.error(f"An error occurred: {e}")

    async def broadcast(self, message: str):
        for user_rooms in self.active_connections.values():
            for data in user_rooms.values():
                websocket = data['websocket']
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_text(message)
                    except RuntimeError as e:
                        logging.error(f"An error occurred: {e}")

    def get_connection(self, user_id: int, room: str) -> Optional[Dict]:
        return self.active_connections.get(user_id, {}).get(room)

    def add_global_connection(self, room, websocket):
        if room not in self.global_active_connections:
            self.global_active_connections[room] = []
        self.global_active_connections[room].append(websocket)

    def remove_global_connection(self, room, websocket):
        if room in self.global_active_connections:
            self.global_active_connections[room].remove(websocket)
            if not self.global_active_connections[room]:
                del self.global_active_connections[room]

    async def auto_reconnect(self, user_id: int, room: str, max_retries=5):
        retries = 0
        websocket_info = self.get_connection(user_id, room)
        if not websocket_info:
            return

        # Удаляем старое соединение перед попыткой переподключения
        self.disconnect(user_id, room)

        websocket = websocket_info['websocket']
        while retries < max_retries:
            try:
                await websocket.connect()
                self.active_connections[user_id][room]['state'] = WebSocketState.CONNECTED
                break
            except Exception as e:
                await asyncio.sleep(5)
                retries += 1

    async def keep_alive(self):
        while True:
            await asyncio.sleep(30)
            for user_rooms in self.active_connections.values():
                for data in user_rooms.values():
                    websocket = data['websocket']
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(json.dumps({"action": "keep_alive"}))
                        logging.info("Keep-alive message sent.")

    async def send_token_refresh_command(self, user_id: int, room: str, new_token: str):
        connection = self.get_connection(user_id, room)
        if connection:
            websocket = connection['websocket']
            if websocket.client_state == WebSocketState.CONNECTED:
                message_json = json.dumps({"action": "refresh_token", "new_token": new_token})
                await websocket.send_text(message_json)


manager = ConnectionManager()
# Запуск метода keep_alive в фоне
asyncio.create_task(manager.keep_alive())
#Функция, которая будет отправлять обновленное число участников:
async def send_member_count_update(chat_id: int, count: int):
    room = f"chat_{chat_id}"
    message_data = {
        "action": "update_member_count",
        "count": count
    }
    await manager.send_message_to_room(room, json.dumps(message_data))

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    current_user = await get_current_user_from_websocket(websocket)
    if isinstance(current_user, RedirectResponse):
        logging.warning("RedirectResponse received instead of current_user.")
        return
    try:
        logging.info("WebSocket connection initiated for user_id: {}".format(user_id))

        # Пытаемся получить токен WebSocket
        access_token = await get_websocket_token(websocket)

        # Добавленное логирование для отладки
        if access_token:
            logging.info(f"Received token: {access_token}")
        else:
            logging.warning("No token received.")

        if access_token is None:
            logging.warning("Missing token. Closing the WebSocket.")
            await websocket.close(code=4000)
            return

        logging.info("Verifying access token for user_id: {}".format(user_id))

        # Проверка и валидация токена
        _, is_valid = await verify_and_validate_token(access_token)

        if not is_valid:
            logging.warning("Invalid access_token. Attempting to use refresh_token...")
            refresh_token = websocket._cookies.get("refresh_token")

            if refresh_token:
                _, is_valid = await verify_and_validate_token(refresh_token)

            if not is_valid:
                logging.warning("Invalid tokens. Closing the WebSocket.")
                await websocket.close(code=4001)
                return

        # Все проверки пройдены, принимаем соединение
        logging.info("All checks passed. Accepting the WebSocket connection.")

        # Получение текущего пользователя из WebSocket
        user = await get_current_user_from_websocket(websocket)

        if user is None:
            logging.warning("User not found. Closing the WebSocket.")
            await websocket.close(code=4003)
            return

        # Подключение к менеджеру
        await manager.connect(websocket, user_id, "some_room")


        # Основной цикл для приема и отправки сообщений
        while True:
            data = await websocket.receive_text()
            messageData = json.loads(data)
            action = messageData.get('action')
            logging.info(f"Received data from user {user_id}: {data}")

            if action == "get_dialog_history":  # Новый блок кода
                dialog_id = messageData.get("dialog_id")
                if dialog_id:
                    dialog_history = await get_dialog_history(dialog_id, user_id)  # предполагается, что эту функцию нужно реализовать
                    await websocket.send_json({"action": "dialog_history", "history": dialog_history})
            elif action == "get_initial_messages":
                dialog_id = messageData.get("dialog_id")
                if dialog_id:
                    messages = await get_messages_from_dialog(dialog_id)
                    await websocket.send_json({"action": "initial_messages", "messages": messages})
            else:
                await manager.send_message(f"User {user_id} said: {data}", user_id, "some_room")
    except WebSocketDisconnect:
        logging.info("WebSocket disconnected. Attempting to reconnect.")
        # Здесь должны быть определены `manager` и `room`, если вы их используете
        if manager.get_connection(user_id, room):
            await manager.auto_reconnect(user_id, room)
        manager.disconnect(user_id, room)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        await websocket.close(code=4002)

async def get_websocket_token(websocket: WebSocket, phone_number: Optional[str] = None):
    logging.info("=== Getting WebSocket Token ===")
    logging.info("Initiating process to get WebSocket token.")

    try:
        # Попытка извлечь токен из куки
        cookies = websocket._cookies
        logging.info(f"All received cookies: {cookies}")
        access_token = cookies.get("access_token")

        if access_token:
            logging.info(f"Successfully retrieved token from WebSocket cookies: {access_token}")
        else:
            logging.warning("Token is missing from WebSocket cookies.")

            # Если токен отсутствует в куки, попробуем извлечь его из базы данных
            if phone_number:
                access_token = await get_token_from_db_by_phone_number(phone_number)
            else:
                access_token = await get_token_from_db(access_token)

            if access_token:
                logging.info(f"Successfully retrieved token from database: {access_token}")
            else:
                logging.warning("Token is also missing from database.")
                await websocket.close(code=4000)  # Custom close code for "missing token"

        return access_token


    except Exception as e:
        logging.error(f"An error occurred while getting the WebSocket token: {e}")
        await websocket.close(code=4002)
        return None
#
#
#
async def handle_dialog_message(dialog_id: int, message_content: str, current_user: User):
    try:
        logging.info(f"Handling dialog message from user {current_user.id} in dialog {dialog_id}: {message_content}")

        # Получаем текущее время в формате строки
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Вставляем сообщение в базу данных
        query = dialog_messages.insert().values(
            dialog_id=dialog_id,
            sender_id=current_user.id,
            message=message_content,
            timestamp=current_time  # Убедитесь, что у вас есть поле timestamp в таблице dialog_messages
        )
        result = await database.execute(query)

        if result:
            logging.info(f"Message successfully saved in the database with result: {result}")
        else:
            logging.warning("Message was not saved in the database.")

        # Получаем информацию о диалоге
        dialog_query = dialogs.select().where(dialogs.c.id == dialog_id)
        dialog_data = await database.fetch_one(dialog_query)

        if dialog_data:
            recipient_id = dialog_data["user1_id"] if dialog_data["user2_id"] == current_user.id else dialog_data["user2_id"]
            room = f"dialog_{dialog_id}"

            # Формируем данные сообщения для отправки
            message_data = {
                "action": "new_message",
                "dialog_id": dialog_id,
                "message": message_content,
                "sender_id": current_user.id,
                "timestamp": current_time  # Добавляем время
            }

            # Отправляем сообщение
            await manager.send_message_to_room(f"user_{recipient_id}", json.dumps(message_data))
            await manager.send_message_to_room(f"user_{current_user.id}", json.dumps({
                "action": "new_message",
                "dialog_id": dialog_id,
                "timestamp": current_time  # Добавляем время
            }))

    except Exception as e:
        logging.error(f"An error occurred while handling dialog message: {e}")
        logging.exception(e)

async def handle_chat_message(chat_id: int, message_content: str, current_user: User):
    try:
        logging.info(f"Starting to handle chat message from user {current_user.phone_number} in chat {chat_id}.")
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        query = chatmessages.insert().values(
            chat_id=chat_id,
            sender_phone_number=current_user.phone_number,
            message=message_content,
            timestamp=current_time  # убедитесь, что у вас есть такое поле в базе данных
        )

        result = await database.execute(query)
        logging.info(f"Message saved to database with result: {result}")

        room = f"chat_{chat_id}"
        message_data = {
            "action": "new_message",
            "message": message_content,
            "sender_phone_number": current_user.phone_number,
            "timestamp": current_time  # добавляем время
        }

        await manager.send_message_to_room(room, json.dumps(message_data))
    except Exception as e:
        logging.error(f"An error occurred while handling chat message: {e}")


async def handle_heartbeat(websocket: WebSocket, last_heartbeat, interval=30):
    current_time = datetime.utcnow()
    if (current_time - last_heartbeat).seconds >= interval:
        await websocket.send_text("heartbeat")
        return current_time
    return last_heartbeat

# В этом методе добавим автоматическое обновление токенов
async def handle_token_refresh(websocket: WebSocket, user_id, last_token_refresh, interval=3600):
    current_time = datetime.utcnow()
    logging.info(f"Handling token refresh for user {user_id}. Last token refresh was at {last_token_refresh}.")

    if (current_time - last_token_refresh).seconds >= interval:
        new_token, is_valid = await validate_and_refresh_token(websocket, user_id)
        if is_valid:
            logging.info(f"Token successfully refreshed for user {user_id}. New token: {new_token}.")
            await websocket.send_text(json.dumps({"action": "token_refreshed", "new_token": new_token}))
            return current_time
        else:
            logging.warning(f"Failed to refresh token for user {user_id}. Closing WebSocket.")
            await websocket.close(code=4001)
            return last_token_refresh
    return last_token_refresh


async def common_websocket_endpoint_logic(websocket: WebSocket, room_name: str, user, manager: ConnectionManager):
    current_time = datetime.utcnow()
    last_heartbeat = current_time
    last_token_refresh = current_time
    HEARTBEAT_INTERVAL = 30  # в секундах

    access_token, is_valid = await validate_and_refresh_token(websocket, user.id)
    if not is_valid:
        logging.warning("WebSocket connection attempt failed: Invalid Token.")
        await websocket.close(code=status.HTTP_403_FORBIDDEN)
        return

    logging.info(f"WebSocket accepted for user {user.id} in room {room_name}")

    await manager.connect(websocket, user.id, room_name)

    try:
        while True:
            last_heartbeat = await handle_heartbeat(websocket, last_heartbeat)
            last_token_refresh = await handle_token_refresh(websocket, user.id, last_token_refresh)

            data = await websocket.receive_text()
            received_data = json.loads(data)
            action = received_data.get('action')

            if action == 'init_connection':
                logging.info(f"Initializing connection for room {room_name} and user {user.id}")

            elif action == 'send_message':
                message = received_data.get('message')
                logging.info(f"Received message from user {user.id}: {message}")

                if "dialog" in room_name:
                    dialog_id = int(room_name.split("_")[1])
                    await handle_dialog_message(dialog_id, message, user)

                elif "chat" in room_name:
                    chat_id = int(room_name.split("_")[1])
                    await handle_chat_message(chat_id, message, user)

                await manager.send_message_to_room(
                    room_name,
                    json.dumps({
                        "action": "new_message",
                        "message": message,
                        "sender_phone_number": user.phone_number,
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    })
                )
            else:
                logging.warning("Unsupported action or user is not the author or the chat admin")
    except WebSocketDisconnect:
        manager.disconnect(user.id, room_name)
        logging.warning(f"WebSocket disconnected for user {user.id}")


async def generic_websocket_endpoint(websocket: WebSocket, room_id: str, room_type: str):
    logging.info(f"=== WebSocket Endpoint: {room_type.capitalize()} ===")
    await websocket.accept()
    user = await get_current_user_from_websocket(websocket)
    room_name = f"{room_type}_{room_id}"

    if not user:
        logging.error("Failed to get the user from the websocket.")
        return

    logging.info(f"WebSocket accepted for user {user.id} in room {room_name}")
    await common_websocket_endpoint_logic(websocket, room_name, user, manager)

# Функция для чатов
@app.websocket("/ws/chats/{chat_id}/")
async def chat_websocket_endpoint(websocket: WebSocket, chat_id: str):
    await generic_websocket_endpoint(websocket, chat_id, "chat")

@app.websocket("/ws/dialogs/{dialog_id}/")
async def dialog_websocket_endpoint(websocket: WebSocket, dialog_id: str):
    await generic_websocket_endpoint(websocket, dialog_id, "dialog")

@app.websocket("/ws/main_page/{user_id}/")
async def main_page_websocket_endpoint(websocket: WebSocket, user_id: int):
    await generic_websocket_endpoint(websocket, user_id, "main_page")



# Обработчик ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)
