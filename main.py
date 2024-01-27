from datetime import datetime
import os
from secrets import token_hex
import typing
from urllib.parse import urlencode
from dotenv import load_dotenv
from flask import Flask, redirect, request
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import requests
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"


class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base, app=app)
migrate = Migrate(app=app, db=db)


class User(db.Model):
  __tablename__ = 'users'
  id: Mapped[int] = mapped_column(primary_key=True)
  pinfl: Mapped[str] = mapped_column()


class UserMyidCredential(db.Model):
  __tablename__ = 'user_myid_credentials'
  id: Mapped[int] = mapped_column(primary_key=True)
  user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
  access_token: Mapped[str] = mapped_column()
  refresh_token: Mapped[str] = mapped_column()
  scope: Mapped[str] = mapped_column()


class UserAccessToken(db.Model):
  __tablename__ = 'user_access_tokens'
  id: Mapped[int] = mapped_column(primary_key=True)
  user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
  access_token: Mapped[str] = mapped_column()

BASE_URL = os.environ.get('MYID_BASE_URL')

@app.get('/')
def myid_auth():
  params = {
    'client_id': os.environ.get('MYID_CLIENT_ID'),
    'response_type': 'code',
    'scope': 'address,contacts,doc_data,common_data',
    'method': 'strong',
    'state': datetime.now().utcnow()
  }
  url = BASE_URL + 'api/v1/oauth2/authorization' + '?' + urlencode(params)
  return redirect(url)

@app.get('/myid-redirect')
def myid_redirect():
  code = request.args.get('code')
  url = BASE_URL + 'api/v1/oauth2/access-token'
  data = {
    'grant_type': 'authorization_code',
    'code': code,
    'client_id': os.environ.get('MYID_CLIENT_ID'),
    'client_secret': os.environ.get('MYID_CLIENT_SECRET')
  }
  res = requests.post(url, data=data)

  if res.status_code != 200:
    return redirect('/')

  data = res.json()
  personal_info = get_myid_personal_info(data.get('access_token'))

  print(personal_info)

  user = get_or_create_user(personal_info['pinfl'])
  creds = create_myid_credentials(user.id, data)
  return ['ok']


@app.get('/user/<pinfl>')
def getuserpinfl(pinfl):
  user = get_or_create_user(pinfl)
  creds = get_myid_credentials(user.id)
  token = get_or_create_token(user.id)
  print(creds)
  try:
    personal_info = get_myid_personal_info(creds.access_token)
    minimal_info = get_myid_minimal_personal_info(personal_info)
    print(minimal_info)
    return [user.id, token.access_token, minimal_info]
  except Exception as e:
    print(e)
    return redirect('/')


def get_or_create_user(pinfl: str) -> User:
  user = db.session.execute(sa.select(User).where(User.pinfl == pinfl)).all()

  if len(user) > 0 and user[0][0] is not None:
    user = user[0][0]
  else:
    user = User(pinfl=pinfl)
    db.session.add(user)
    db.session.commit()
  return user

def get_or_create_token(user_id: int) -> UserAccessToken:
  token = db.session.execute(sa.select(UserAccessToken).where(UserAccessToken.user_id == user_id)).all()

  if len(token) > 0 and token[0][0] is not None:
    token = token[0][0]
  else:
    token = UserAccessToken(user_id=user_id, access_token=token_hex(32))
    db.session.add(token)
    db.session.commit()
  return token

def get_myid_credentials(user_id: int) -> typing.Optional[UserMyidCredential]:
  creds = db.session.execute(
    sa.select(UserMyidCredential).where(UserMyidCredential.user_id == user_id).order_by(sa.desc(UserMyidCredential.id))
  ).all()

  if (len(creds) == 0):
    return None

  return creds[0][0] if creds is not None else None

def create_myid_credentials(user_id: int, creds) -> UserMyidCredential:
  creds = UserMyidCredential(
    user_id=user_id,
    access_token=creds['access_token'],
    refresh_token=creds['refresh_token'],
    scope=creds['scope'],
  )
  db.session.add(creds)
  db.session.commit()
  return creds


def get_myid_personal_info(access_token):
  url = BASE_URL + 'api/v1/users/me'
  res = requests.get(url, headers={
    'Authorization': 'Bearer ' + access_token
  })

  if res.status_code != 200:
    raise Exception(res.text)
  return res.json()

def get_myid_minimal_personal_info(personal_info):
  return {
    'pinfl': personal_info['profile']['common_data']['pinfl'],
    'first_name': personal_info['profile']['common_data']['first_name'],
    'last_name': personal_info['profile']['common_data']['last_name'],
    'middle_name': personal_info['profile']['common_data']['middle_name'],
    'birth_date': personal_info['profile']['common_data']['birth_date'],
    'region': personal_info['profile']['address']['permanent_registration']['region'],
    'region_id': int(personal_info['profile']['address']['permanent_registration']['region_id']),
    'district': personal_info['profile']['address']['permanent_registration']['district'],
    'district_id': int(personal_info['profile']['address']['permanent_registration']['district_id']),
  }
