# Встроенные модули Python
import asyncio
import io
import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from operator import and_
from typing import List, Optional, Dict, Tuple
from urllib.parse import quote, unquote

# Модули для работы с SQL базами данных
import aiomysql
import cur as cur
import jwt
from fastapi.params import Path, Body
from jose import JWTError
from sqlalchemy import create_engine, MetaData, Column, Integer, String, ForeignKey, PrimaryKeyConstraint, DateTime, \
    Table, func, LargeBinary, desc, or_, Boolean, BLOB, Text, Float, JSON
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.sync import update
from sqlalchemy.sql import select
from databases import Database
from pymysql.err import ProgrammingError

# Сторонние библиотеки для веб-фреймворков, безопасности и шаблонизации
from fastapi import FastAPI, WebSocket, HTTPException, Depends, status, Form, Cookie, logger, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

# Сторонние библиотеки для работы с файлами, датами и временем
from aiofile import async_open
from pytz import timezone
import pytz as pytz

# Сторонние библиотеки для безопасности и хеширования паролей
import bcrypt


# Другие сторонние библиотеки
from pydantic import BaseModel
from requests import Session

import mimetypes
from pydantic.json import Union

logging.basicConfig(level=logging.INFO)


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
    Column("user1_deleted", Boolean, default=False),  # Add this
    Column("user2_deleted", Boolean, default=False),  # Add this
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
    Column("delete_timestamp", DateTime),  # новый столбец
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

SECRET_KEY = "Bondar"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 3

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone_number: str = payload.get("sub")
        if phone_number is None:
            return None
        return phone_number
    except JWTError:
        return None

# Определяем модель пользователя
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    password = Column(String)

class MessageContent(BaseModel):
    message_text: str

# Папка, где будут храниться фотографии профиля
PROFILE_PICTURES_FOLDER = "C:/Users/Программист/PycharmProjects/fastApiSpiritChat/profile_pictures"

class MyJinja2Templates(Jinja2Templates):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env.globals["time"] = time

templates = MyJinja2Templates(directory="templates")

# На старте приложения подключаемся к базе данных
@app.on_event("startup")
async def startup():
    await database.connect()

# При остановке приложения отключаемся от базы данных
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# Зависимость для получения информации о текущем активном пользователе.
async def get_current_active_user(request: Request):
    phone_number = request.session.get("phone_number")
    if phone_number is None:
        raise HTTPException(status_code=403, detail="Not authenticated")
    user = await get_user_by_phone(phone_number)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # обновляем поле last_online в таблице пользователей
    query = (
        update(users).
        where(users.c.phone_number == phone_number).
        values(last_online=datetime.utcnow())
    )
    await database.execute(query)

    return user

# Извлекает информацию о пользователе из базы данных по номеру телефона.
async def get_user(phone_number: str):
    query = users.select().where(users.c.phone_number == phone_number)
    logging.info(f"Executing query: {query}")  # Debug info
    user = await database.fetch_one(query)
    logging.info(f"User from database in get_user function: {user}")  # Debug info
    return user

# Получает пользователя по номеру телефона.
async def get_user_by_phone(phone_number):
    query = users.select().where(users.c.phone_number == phone_number)
    logging.info(f"Executing query: {query}")  # Debug info
    result = await database.fetch_one(query)
    logging.info(f"Result: {result}")  # Debug info
    return result

#Проверяет, является ли хеш пароля действительным (соответствует формату bcrypt).
def is_password_hash_valid(password_hash: str):
    return password_hash.startswith(b'$2a$') or password_hash.startswith(b'$2b$') or password_hash.startswith(b'$2y$')

#Проверяет, соответствует ли введенный пароль хешу пароля пользователя.
def is_password_correct(password: str, password_hash: str):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash)

#Аутентифицирует пользователя, сравнивая введенный пароль с хешем пароля в базе данных.
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

#Добавляет нового пользователя в базу данных.
async def add_user(gender, last_name, first_name, middle_name, nickname, phone_number, position, email, password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    query = users.insert().values(gender=gender, last_name=last_name, first_name=first_name, middle_name=middle_name, nickname=nickname,
                                  phone_number=phone_number, position=position, email=email, password=hashed_password)
    logging.info(f"Executing query: {query}")  # Debug info
    result = await database.execute(query)
    logging.info(f"Result: {result}")  # Debug info
    return result

#Извлекает текущего пользователя из сессии.
async def get_current_user(request: Request) -> User:
    if "phone_number" not in request.session:
        return RedirectResponse(url="/login")
    phone_number = request.session["phone_number"]
    print(f"Phone number from session: {phone_number}")  # line for debug
    user = await get_user(phone_number)
    print(f"User from database: {user}")  # line for debug
    return user

#Возвращает всех пользователей из базы данных.
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

#Получает все сообщения из указанного чата.
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
                updated_chat['last_message_sender_phone'] = last_message['sender_phone_number']  # добавляем номер отправителя последнего сообщения
                updated_chat['last_message_timestamp'] = last_message['timestamp']

            updated_user_chats.append(updated_chat)  # Добавляем обновленный чат в список

        return updated_user_chats
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error getting user chats")


#Получает чат по идентификатору.
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
async def read_chat_members(request: Request, chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    # Этот маршрут отображает всех участников конкретного чата
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    members = await get_chat_members(chat_id)
    members_info = [await get_user(member['user_phone_number']) for member in members]
    # Отсортировать список участников так, чтобы владелец был первым
    members_info.sort(key=lambda member: member['phone_number'] != chat['owner_phone_number'])
    return templates.TemplateResponse("chatmembers.html", {"request": request, "chat": chat, "members": members_info, "current_user": current_user})

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
async def invite_to_chat(request: Request, chat_id: int, search_query: Optional[str] = None, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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

    inviteable_users = [user for user in all_users if user['phone_number'] not in members_phone_numbers and user['phone_number'] != current_user['phone_number']]
    return templates.TemplateResponse("addtochat.html", {"request": request, "chat": chat, "users": inviteable_users, "current_user": current_user})

@app.post("/chat/{chat_id}/members/{phone_number}/add", response_class=RedirectResponse)
async def add_chat_member(request: Request, chat_id: int, phone_number: str, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    await add_chat_member_db(chat_id, phone_number)  # Исправленный вызов функции
    return RedirectResponse(url=f"/chat/{chat_id}/members", status_code=303)

@app.get("/chat/{chat_id}/members/search", response_class=HTMLResponse)
async def search_chat_members(request: Request, chat_id: int, search_user: str, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    members = await get_chat_members(chat_id)
    members_info = [await get_user(member['user_phone_number']) for member in members]

    search_results = None
    if search_user:  # Проверка, что поисковый запрос не пустой
        # Поиск среди участников чата
        search_results = list(filter(lambda member: search_user.lower() in member['first_name'].lower() or search_user.lower() in member['last_name'].lower() or search_user.lower() in member['nickname'].lower() or search_user in member['phone_number'], members_info))

    # Отсортировать список участников так, чтобы владелец был первым
    members_info.sort(key=lambda member: member['phone_number'] != chat['owner_phone_number'])

    # Возвращаем search_results только если поисковый запрос был выполнен
    return templates.TemplateResponse("chatmembers.html", {"request": request, "chat": chat, "members": members_info, "current_user": current_user, "search_results": search_results})

#Удаляет пользователя из чата.
async def delete_chat_member(chat_id: int, phone_number: str):
    try:
        query = ChatMembers.delete().where(and_(ChatMembers.c.chat_id == chat_id, ChatMembers.c.user_phone_number == phone_number))
        result = await database.execute(query)
        return result
    except SQLAlchemyError as e:
        print(str(e))  # line for debug
        raise HTTPException(status_code=500, detail="Error deleting chat member")

#Маршрут для удлаения частника из чата
@app.post("/chats/{chat_id}/members/{phone_number}/delete")
async def remove_chat_member(chat_id: int, phone_number: str, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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


#Создает новое сообщение в чате.
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

#Создает новый чат.
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
    query = files.select().where(files.c.id == file_id)
    result = await database.fetch_one(query)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

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

#Сохраняет файл в базу данных.
async def save_file(phone_number: str, file_path: str, file_content: bytes, file_extension: str):
    query = files.insert().values(phone_number=phone_number, file_path=file_path, file=file_content, file_extension=file_extension)
    file_id = await database.execute(query)
    return file_id

#БЛОК УДАЛЕНИЯ СООБЩЕНИЙ ИЗ ЧАТА
#Получает сообщение по его идентификатору.
async def get_message_by_id(message_id: int):
    query = chatmessages.select().where(chatmessages.c.id == message_id)
    result = await database.fetch_one(query)
    return result

#Удаляет сообщение из базы данных.
async def delete_message_from_db(message_id: int):
    query = chatmessages.delete().where(chatmessages.c.id == message_id)
    await database.execute(query)

#Удаляет сообщение из чата, если текущий пользователь является автором этого сообщения.
@app.post("/chats/{chat_id}/messages/{message_id}/delete")
async def delete_message(
    chat_id: int,
    message_id: int,
    current_user: Union[str, RedirectResponse] = Depends(get_current_user)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    message = await get_message_by_id(message_id)
    chat = await get_chat(chat_id)
    if message is None or message.chat_id != chat_id or (message.sender_phone_number != current_user.phone_number and chat['owner_phone_number'] != current_user.phone_number):
        raise HTTPException(status_code=404, detail="Message not found or user is not the author or the chat admin")

    # Если сообщение начинается с "Опрос: ", то это опрос
    if message.message.startswith("Опрос: "):
        poll_id = int(message.message[7:])
        poll = await get_poll(poll_id, current_user.phone_number)
        if poll is not None:
            # Если сообщение является опросом, то удаляем связанный опрос
            await delete_poll_data(poll_id)

    await delete_message_from_db(message_id)  # Удаляем сообщение из базы данных

    return RedirectResponse(url=f"/chats/{chat_id}", status_code=303)

#БЛОК МАРШРУТЫ
# Маршрут к главной странице
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return templates.TemplateResponse("login.html", {"request": request})
    else:
        return RedirectResponse(url="/home", status_code=303)

# Маршрут к странице входа в систему
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    # Этот маршрут отображает форму входа
    return templates.TemplateResponse('login.html', {"request": request})

# Маршрут для аутентификации пользователя
@app.post("/login")
async def login_user(request: Request,
                     phone_number: str = Form(...),
                     password: str = Form(...)):
    # Этот маршрут обрабатывает данные формы входа и осуществляет аутентификацию пользователя
    user = await authenticate_user(phone_number, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})
    response = RedirectResponse(url='/home', status_code=303)
    request.session["phone_number"] = user.phone_number
    return response

# Маршрут для выхода из системы
@app.get("/logout")
async def logout(request: Request):
    # Этот маршрут осуществляет выход из системы, очищая данные сессии
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

# Маршрут к странице регистрации
@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    # Этот маршрут отображает форму регистрации
    return templates.TemplateResponse("register.html", {"request": request})

# Маршрут для регистрации пользователя
@app.post("/register")
async def register_user(request: Request,
                        gender: str = Form(...),
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
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already registered"})
    if user_by_phone:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Phone number already registered"})
    await add_user(gender, last_name, first_name, middle_name, nickname, phone_number, position, email, password)
    # перенаправляем пользователя на его профиль после регистрации
    response = RedirectResponse(url=f'/profile/{phone_number}', status_code=303)
    request.session["phone_number"] = phone_number
    return response

@app.get("/profile", response_class=HTMLResponse)
async def user_profile(request: Request):
    phone_number = request.session.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=403, detail="You must be logged in to view the profile")

    # извлекаем информацию о пользователе из базы данных
    user = await get_user_by_phone(phone_number)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # передаем информацию о пользователе в шаблон
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
async def get_profile_picture(phone_number: str):
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
async def delete_profile_picture(request: Request):  # new
    phone_number = request.session.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=403, detail="You must be logged in to edit the profile")
    await update_user_profile_picture(phone_number, "images/default.jpg")  # new
    return RedirectResponse(url="/profile", status_code=303)

@app.post("/profile/update")
async def update_user_profile(request: Request,
                              nickname: str = Form(None),
                              status: str = Form(None),
                              profile_picture: UploadFile = File(None),
                              delete_picture: bool = Form(False)):
    phone_number = request.session.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=403, detail="You must be logged in to edit the profile")
    user = await get_user_by_phone(phone_number)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if nickname:
        await update_user_nickname(phone_number, nickname)
    await update_user_status(phone_number, status)  # removed 'if status:'
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
        query = dialog_messages.select().where(dialog_messages.c.dialog_id == dialog_id).order_by(dialog_messages.c.timestamp.desc()).limit(1)
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
async def main_page(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user),
                    search_query: str = None):
    if isinstance(current_user, RedirectResponse):
        return current_user

    search_results_chats = []
    search_results_channels = []
    user_chats = await get_user_chats(current_user.phone_number)
    user_channels = await get_user_channels(current_user.phone_number)
    subscribed_channels = await get_subscribed_channels(current_user.phone_number)
    if search_query and search_query.strip():
        search_results_chats, search_results_channels = await search_chats_and_channels(search_query)

        # Модифицированный код:
        for i, chat in enumerate(search_results_chats):
            chat_dict = dict(chat)  # преобразуем Row в словарь
            chat_dict['is_member'] = await is_member_of_chat(chat['id'], current_user.phone_number)
            search_results_chats[i] = chat_dict  # обновляем chat с новым словарем

    user_dialogs = await get_user_dialogs(current_user.id)
    return templates.TemplateResponse("chats.html", {
        "request": request,
        "chats": user_chats,
        "channels": user_channels,
        "current_user": current_user,
        "search_results_chats": search_results_chats,
        "search_results_channels": search_results_channels,
        "subscribed_channels": [channel['id'] for channel in subscribed_channels],
        "dialogs": user_dialogs,
        "search_query": search_query,
    })

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
    members = await get_chat_members(chat_id)
    return any(member['user_phone_number'] == phone_number for member in members)

@app.get("/chat/{chat_id}", response_class=HTMLResponse)
async def read_chat(request: Request, chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    messages = await get_chat_messages(chat_id)
    members = await get_chat_members(chat_id)  # получение списка участников
    is_member = await is_member_of_chat(chat_id, current_user['phone_number'])

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
                    user_voted = bool(await database.fetch_one(query="SELECT * FROM PollVotes WHERE poll_id = :poll_id AND voter_phone_number = :voter_phone_number",
                                                               values={"poll_id": poll_id, "voter_phone_number": current_user.phone_number}))

    return templates.TemplateResponse("chat.html", {"request": request, "chat": chat, "messages": messages, "polls": polls, "poll_results": poll_results, "user_voted": user_voted, "current_user": current_user})

# Маршрут к странице создания нового чата
@app.get("/create_chat", response_class=HTMLResponse)
async def create_chat_page(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    # Этот маршрут отображает страницу создания нового чата
    if isinstance(current_user, RedirectResponse):
        return current_user
    users = await get_all_users()
    return templates.TemplateResponse("create_chat.html", {"request": request, "users": users, "current_user": current_user})

# Маршрут для создания нового чата
@app.post("/create_chat", response_class=HTMLResponse)
async def create_chat(request: Request, chat_name: str = Form(...), user_phone: str = Form(...), current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    # Этот маршрут обрабатывает создание нового чата
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat_id = await create_new_chat(chat_name, current_user['phone_number'], user_phone)
    return RedirectResponse(url=f"/chat/{chat_id}", status_code=303)  # перенаправление на страницу чата

#Маршрут отображает страницу конкретного чата и форму отправки нового сообщения
@app.get("/chats/{chat_id}", response_class=HTMLResponse)
async def chat_page(request: Request, chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    chat = await get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = await get_chat_messages(chat_id)
    left_chats = request.session.get("left_chats", []) # Получаем список покинутых чатов
    return templates.TemplateResponse("chat.html", {"request": request, "chat": chat, "messages": messages, "current_user": current_user, "left_chats": left_chats})

# Маршрут для удаления чата
@app.post("/chats/{chat_id}/delete", response_class=HTMLResponse)
async def delete_chat(request: Request, chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Проверяем, является ли текущий пользователь владельцем чата
    chat = await get_chat(chat_id)
    if chat['owner_phone_number'] != current_user.phone_number:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this chat")

    # Удаляем чат, если текущий пользователь - владелец
    try:
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
async def send_message_to_chat(
        chat_id: int,
        message_text: str = Form(None),
        file: UploadFile = File(None),
        current_user: Union[str, RedirectResponse] = Depends(get_current_user)
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    file_id = None
    file_name = None

    # Обрабатываем прикрепленный файл, если он есть
    if file and file.filename:
        file_content = await file.read()
        file_id = await save_file(current_user.phone_number, file.filename, file_content, file.filename.split('.')[-1])
        file_name = file.filename

    # Преобразуем None в пустую строку, если пользователь не предоставил текст сообщения
    if message_text is None:
        message_text = ""

    try:
        # Если файл был загружен, добавьте информацию о файле в текст сообщения
        if file_id and file_name:
            message_text += f' [[FILE]]File ID: {file_id}, File Name: {file_name}[[/FILE]]'

        await create_message(chat_id, message_text, current_user.phone_number)
        participants = await get_chat_participants(chat_id)  # change here
        await manager.send_message(f"chat_{chat_id}", f"New message in chat {chat_id} from {current_user.phone_number}: {message_text}")

    except HTTPException:
        raise HTTPException(status_code=500, detail="Error sending message or uploading file")

    return RedirectResponse(url=f"/chats/{chat_id}", status_code=303)

# Этот маршрут обрабатывает действие "покинуть чат"
@app.post("/chats/{chat_id}/leave", response_class=RedirectResponse)
async def leave_chat(request: Request, chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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
async def return_to_chat(request: Request, chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    await add_chat_member(chat_id, current_user['phone_number'])

    # Удаляем чат из списка покинутых
    left_chats = request.session.get("left_chats", [])
    if chat_id in left_chats:
        left_chats.remove(chat_id)
    request.session["left_chats"] = left_chats

    return RedirectResponse(f"/chat/{chat_id}", status_code=303)

#Vаршрут присоединения к чату
@app.post("/join_chat/{chat_id}")
async def join_chat(chat_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    query = ChatMembers.insert().values(chat_id=chat_id, user_phone_number=current_user.phone_number)
    await database.execute(query)

    return RedirectResponse(url=f"/chat/{chat_id}", status_code=status.HTTP_303_SEE_OTHER)

#БЛОК 3 КАНАЛ
# Функция, которая создает новый канал
async def create_new_channel(channel_name: str, owner_phone_number: str):
    try:
        query = channels.insert().values(name=channel_name, owner_phone_number=owner_phone_number)
        last_record_id = await database.execute(query)
        return last_record_id
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error creating new channel")

async def get_channel_messages(channel_id: int):
    query = channel_history.select().where(channel_history.c.channel_id == channel_id).order_by(channel_history.c.timestamp)
    messages = await database.fetch_all(query)
    return messages

@app.get("/create_channel", response_class=HTMLResponse)
async def create_channel_page(request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    user_channels = await get_user_channels(current_user.phone_number)
    return templates.TemplateResponse("create_channel.html", {"request": request, "current_user": current_user, "channels": user_channels})

@app.post("/create_channel", response_class=HTMLResponse)
async def create_channel(request: Request, channel_name: str = Form(...), current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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

    conn = engine.connect() # Используем engine.connect() без контекстного менеджера
    result = conn.execute(stmt)

    channel_info = result.fetchone()

    return dict(channel_info)

@app.post("/channels/{channel_id}/subscribers/{subscriber_phone_number}/remove", response_class=RedirectResponse)
async def remove_subscriber(channel_id: int, subscriber_phone_number: str, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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
        {"request": request, "channel": channel, "subscribers": subscribers, "search_results": search_results, "current_user": current_user}
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
async def view_channel_page(request: Request, channel_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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
    return templates.TemplateResponse("channel.html", {"request": request, "channel": channel, "messages": messages, "current_user": current_user, "subscribers_count": subscribers_count, "is_owner": is_owner})

@app.post("/channels/{channel_id}", response_class=HTMLResponse)
async def update_channel(request: Request, channel_id: int, new_content: str = Form(...), current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = channels.update().where(channels.c.id == channel_id).values(content=new_content)
    await database.execute(query)
    return RedirectResponse(url=f"/", status_code=303)

async def create_channel_message(channel_id: int, message_text: str, sender_phone_number: str, file_id: int = None, file_name: str = None):
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
async def send_channel_message(request: Request, channel_id: int, message_text: str = Form(...), file: UploadFile = File(None), current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

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
async def get_channel_history(request: Request, channel_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user
    query = channel_history.select().where(channel_history.c.channel_id == channel_id).order_by(desc(channel_history.c.timestamp))
    messages = await database.fetch_all(query)
    return templates.TemplateResponse("channel_history.html", {"request": request, "messages": messages, "current_user": current_user})

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
async def delete_message_route(channel_id: int, message_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
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
    await remove_user_from_channel(user.phone_number, channel_id)  # Передайте номер телефона пользователя, а не объект пользователя

    # Перенаправить пользователя на домашнюю страницу, где он увидит обновленный список каналов
    return RedirectResponse(url='/home', status_code=303)

#БЛОК ПОИСК
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

#БЛОК ДИАЛОГ
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

#Cоздает новый диалог между двумя пользователями.
async def create_new_dialog(user1_id: int, user2_id: int) -> int:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    await cur.execute("INSERT INTO Dialogs (user1_id, user2_id) VALUES (%s, %s)", (user1_id, user2_id))
    dialog_id = cur.lastrowid

    await conn.commit()
    await cur.close()
    conn.close()

    return dialog_id

#Функция поиска пользователей по заданному запросу.
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
    if check_user_deleted and ((current_user_id == row['user1_id'] and row['user1_deleted']) or (current_user_id == row['user2_id'] and row['user2_deleted'])):
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

#Возвращает все сообщения из данного диалога.
async def get_messages_from_dialog(dialog_id: int, message_id: int = None) -> List[dict]:
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()

    if message_id:
        # Если задан message_id, получаем только это сообщение
        await cur.execute("SELECT * FROM DialogMessages WHERE dialog_id = %s AND id = %s", (dialog_id, message_id))
    else:
        # Если message_id не задан, получаем все сообщения диалога
        await cur.execute("SELECT * FROM DialogMessages WHERE dialog_id = %s", (dialog_id,))

    result = []
    async for row in cur:
        # Проверяем, было ли сообщение удалено
        if row[5] is not None:  # если delete_timestamp не None, значит, сообщение было удалено
            result.append(
                {"id": row[0], "dialog_id": row[1], "sender_id": row[2], "message": row[3], "timestamp": row[4],
                 "deleted_at": row[5].strftime("%Y-%m-%d %H:%M:%S")})
        else:
            result.append(
                {"id": row[0], "dialog_id": row[1], "sender_id": row[2], "message": row[3], "timestamp": row[4],
                 "delete_timestamp": row[5]})

    await cur.close()
    conn.close()

    return result

#Добавляет новое сообщение в базу данных
async def send_message(dialog_id: int, sender_id: int, message: str):
    conn = await aiomysql.connect(user='root', password='root', db='chat', host='localhost', port=3306)
    cur = await conn.cursor()
    await cur.execute("INSERT INTO DialogMessages (dialog_id, sender_id, message) VALUES (%s, %s, %s)", (dialog_id, sender_id, message))
    await conn.commit()
    await cur.close()
    conn.close()

#Метод возвращает страницу с конкретным диалогом и его сообщениями
@app.get("/dialogs/{dialog_id}", response_class=HTMLResponse)
async def dialog_route(dialog_id: int, request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Получаем информацию о диалоге
    dialog = await get_dialog_by_id(dialog_id, current_user['id'])

    # Получаем все сообщения из данного диалога
    messages = await get_messages_from_dialog(dialog_id)

    return templates.TemplateResponse("dialogs.html", {
        "request": request,
        "current_user": current_user,
        "dialog": dialog,
        "messages": messages,
    })

async def update_last_online(user_id: int):
    current_time = datetime.utcnow()
    query = users.update().\
        where(users.c.id == user_id).\
        values(last_online=current_time)
    await database.execute(query)

# Обработчик отправки сообщения в диалог
@app.post("/dialogs/{dialog_id}/send_message")
async def send_message_to_dialog(
    dialog_id: int,
    message: str = Form(None),
    file: UploadFile = File(None),
    current_user: Union[str, RedirectResponse] = Depends(get_current_user)
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    sender_id = current_user['id']
    dialog = await get_dialog_by_id(dialog_id, sender_id, check_user_deleted=False)

    if sender_id not in [dialog['user1_id'], dialog['user2_id']]:
        raise HTTPException(status_code=400, detail="User not in this dialog")

    # Изменяем статус удаления диалога на False для получателя, когда сообщение отправляется в диалог
    receiver_id = dialog['user1_id'] if sender_id == dialog['user2_id'] else dialog['user2_id']
    if receiver_id == dialog['user1_id']:
        await update_dialog_deleted_status(dialog_id, deleted_by_user1=False)
    else:
        await update_dialog_deleted_status(dialog_id, deleted_by_user2=False)

    file_id = None
    file_name = None

    # Обрабатываем прикрепленный файл, если он есть
    if file and file.filename:
        file_content = await file.read()
        file_id = await save_file(current_user['id'], file.filename, file_content, file.filename.split('.')[-1])
        file_name = file.filename

    # Если файл был загружен, добавьте информацию о файле в текст сообщения
    if file_id and file_name:
        file_info = f' [[FILE]]File ID: {file_id}, File Name: {file_name}[[/FILE]]'
        message = file_info if message is None else message + file_info

    # Проверяем, что у нас есть либо сообщение, либо файл
    if message is None:
        raise HTTPException(status_code=400, detail="No message or file to send")

    await send_message(dialog_id, sender_id, message)
    participants = [sender_id, receiver_id]
    await manager.send_message(f"dialog_{dialog_id}", f"New message in dialog {dialog_id} from user {sender_id}: {message}")

    # Обновляем время последнего онлайна после отправки сообщения
    await update_last_online(sender_id)

    return RedirectResponse(url=f"/dialogs/{dialog_id}", status_code=303)

#Обрабатывает создание диалога с определенным пользователем
@app.get("/create_dialog/{user_id}")
@app.post("/create_dialog/{user_id}")
async def create_dialog_handler(user_id: int, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Проверяем, существует ли уже диалог между текущим пользователем и выбранным пользователем
    dialog_id = await check_dialog_exists(current_user['id'], user_id)

    if dialog_id is None:
        # Если диалог не существует, создаем новый диалог
        dialog_id = await create_new_dialog(current_user['id'], user_id)

    # Перенаправляем пользователя на страницу диалога (нового или уже существующего)
    return RedirectResponse(url=f"/dialogs/{dialog_id}", status_code=status.HTTP_303_SEE_OTHER)

#Удаление сообщения из диалога
@app.post("/dialogs/{dialog_id}/delete_message/{message_id}")
async def delete_message(
        dialog_id: int,
        message_id: int,
        current_user: Union[str, RedirectResponse] = Depends(get_current_user)
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    messages = await get_messages_from_dialog(dialog_id, message_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Message not found")

    message = messages[0]  # Поскольку мы запрашиваем только одно сообщение, оно будет первым (и единственным) в списке

    # Проверяем, есть ли у пользователя права на удаление этого сообщения
    if message["sender_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this message")

    await delete_message_by_id(message_id)

    return RedirectResponse(url=f"/dialogs/{dialog_id}", status_code=303)

#Функция полностью удаляет сообщение из базы данных.
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
        query = dialogs.update().\
            where(dialogs.c.id == dialog_id).\
            values(user1_deleted=True)
        await database.execute(query)
    else:
        query = dialogs.update().\
            where(dialogs.c.id == dialog_id).\
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

# Получение диалога по его ID
@app.get("/dialogs/{dialog_id}", response_class=HTMLResponse)
async def get_dialog_route(dialog_id: int, request: Request, current_user: Union[str, RedirectResponse] = Depends(get_current_user)):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Получаем данные диалога
    dialog = await get_dialog_by_id(dialog_id, current_user['id'])

    # Получаем историю переписки
    messages = await get_dialog_messages(dialog_id)

    return templates.TemplateResponse("dialogs.html", {
        "request": request,
        "current_user": current_user,
        "dialog": dialog,
        "messages": messages,
    })

# БЛОК №4 СОКЕТЫ
import logging

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, room: str):
        logging.info(f"Connecting to room {room}")
        if room not in self.active_connections:
            self.active_connections[room] = []
        self.active_connections[room].append(websocket)
        await websocket.accept()
        logging.info(f"Connected to room {room}")

    async def disconnect(self, websocket: WebSocket, room: str):
        logging.info(f"Disconnecting from room {room}")
        if room in self.active_connections:
            self.active_connections[room].remove(websocket)
        logging.info(f"Disconnected from room {room}")

    async def send_message(self, room: str, message: str):
        logging.info(f"Sending message to room {room}")
        if room in self.active_connections:
            for connection in self.active_connections[room]:
                await connection.send_text(message)
                logging.info(f"Sent message to room {room}")

manager = WebSocketManager()


@app.websocket("/ws/chats/{chat_id}/")
async def chat_websocket_endpoint(websocket: WebSocket, chat_id: int, current_user_phone_number: str):
    room = f"chat_{chat_id}"

    # Log headers and cookies
    logging.info(f"Headers: {dict(websocket.headers)}")
    logging.info(f"Cookies: {dict(websocket.cookies)}")

    await manager.connect(websocket, room)
    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received data: {data}")
            await manager.send_message(room, data)
    except Exception as e:
        logging.error(f"Exception: {e}")
    finally:
        await manager.disconnect(websocket, room)


@app.websocket("/ws/dialogs/{dialog_id}/")
async def dialog_websocket_endpoint(websocket: WebSocket, dialog_id: int, current_user_phone_number: str):
    room = f"dialog_{dialog_id}"

    # Log headers and cookies
    logging.info(f"Headers: {dict(websocket.headers)}")
    logging.info(f"Cookies: {dict(websocket.cookies)}")

    await manager.connect(websocket, room)
    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received data: {data}")
            await manager.send_message(room, data)
    except Exception as e:
        logging.error(f"Exception: {e}")
    finally:
        await manager.disconnect(websocket, room)




