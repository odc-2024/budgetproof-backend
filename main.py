import os
from urllib.parse import urlencode
from flask import Flask, redirect, request
from dotenv import load_dotenv
import requests

load_dotenv()
app = Flask(__name__)

BASE_URL = os.environ.get('MYID_BASE_URL')

@app.get('/')
def myid_auth():
  print(request)
  params = {
    'client_id': os.environ.get('MYID_CLIENT_ID'),
    'response_type': 'code',
    'scope': 'address,contacts,doc_data,common_data',
    'method': 'strong',
    'state': 'blabla'
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
    return 'Code expired'
  return res.json()

@app.get('/personal-info')
def get_personal_info():
  url = BASE_URL + 'api/v1/users/me'
  res = requests.get(url, headers={
    'Authorization': 'Bearer ' + 'access_token'
  })
  print(res.text)
  if res.status_code != 200:
    return 'Unsuccessful response'
  return res.json()
