# coding: utf-8
import json, time, datetime
import jwt
from flask import Blueprint, g
from flask import request,g,current_app,jsonify
from app.models import MyData
from app import db
from app.models import User, MyData
from app.auth import basic_auth, token_auth
from app.error import error_response, bad_request
from app.utils import action_lib_presets
from sqlalchemy import extract

EXPIRES_IN = 28800
bp = Blueprint('api', __name__)


@bp.route('/')
def hello_world():
    return 'Hello, World!'


@bp.route('/test', methods=['GET'])
def test():
    return 'test'


"""
    Users
"""

# get user
@bp.route('/users/<int:id>', methods=['GET'])
def get_user(id):
    user = User.query.get_or_404(id)
    resp = {
        username: user.username
    }
    return jsonify(resp)

# create user
@bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not data:
        return bad_request('bad request')
    if not username or not password:
        return bad_request('bad request')
    user = User.query.filter_by(username=username).first()
    if user is not None:
        return bad_request("user existed.")

    user = User()
    user.username = username
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return 'create success', 201


"""
    Training
"""

# get actions
@bp.route('/actions', methods=['GET'])
@token_auth.login_required
def get_action():
    date_time = request.args.get('datetime')
    user = g.current_user
    if date_time is None:
        return bad_request('args error.')
    if not user:
        return bad_request('Unauth...')

    action_lib_presets_dic = {}
    for action in action_lib_presets:
        name = action['name']
        label = action['label']
        action_lib_presets_dic[name] = label

    date_time_formatted = datetime.datetime.strptime(date_time, r'%Y-%m-%d')
    mydata = user.mydata.filter_by(timestamp=date_time_formatted).first_or_404()
    mydata_json = json.loads(mydata.data)
    for data in mydata_json:
        name = data.get('name')
        if name in action_lib_presets_dic:
            data['label'] = action_lib_presets_dic[name]

    message = {
        "mydata": mydata_json
    }
    return message


# append action cards
@bp.route('/actions', methods=['POST'])
@token_auth.login_required
def append_action():
    data = request.get_json()
    mydata_json = data.get('mydata')
    timestamp = data.get('timestamp')

    mydata_str = json.dumps(mydata_json)
    user = g.current_user
    user_id = user.id

    date_time = datetime.datetime.strptime(timestamp, r"%Y-%m-%d")

    mydata = MyData.query.filter_by(
        user=user,
        timestamp=date_time
    ).first()
    
    if mydata is None:
        db.session.add(MyData(user_id=user_id, timestamp=date_time, data=mydata_str))
        db.session.commit()
    else:
        mydata.data = mydata_str
        db.session.add(mydata)
        db.session.commit()

    return 'ok', 200

# get library
@bp.route('/actions-lib', methods=['GET'])
def get_actions_lib():
    return jsonify(action_lib_presets)

# get current month include actions (for calendar)
@bp.route('/days-have-actions', methods=['GET'])
@token_auth.login_required
def get_days_have_actions():
    month = request.args.get('date_month')
    if not month:
        return bad_request()
    response = []
    user = g.current_user
    if not user:
        return bad_request()
    data = MyData.query.filter(
        MyData.user==user,
        extract('month', MyData.timestamp) == int(month)
    ).all()
    for item in data:
        day = item.timestamp.day
        content = json.loads(item.data)
        if day not in response and len(content):
            response.append(day)
    # response = list(set([item.timestamp.day for item in data if item.data and len(item.data)]))
    return jsonify(response)

"""
    Data
"""
# get one year's all datas
@bp.route('/data-of-years', methods=['GET'])
@token_auth.login_required
def get_data_of_years():
    year = 2021
    current_user = g.current_user
    if not current_user:
        return error_response(401)

    mydatas = MyData.query.filter(
        MyData.user == current_user,
        extract('year', MyData.timestamp) == int(year)
    ).all()

    datetime_dic = {}
    for mydata in mydatas:
        data_json = json.loads(mydata.data)
        timestamp = mydata.timestamp
        month_day_str = datetime.datetime.strftime(timestamp, r'%m-%d')
        capacity = 0

        if not len(data_json):
            continue    

        for action in data_json:
            values = action['values']
            for value in values:
                capacity += value['numbers'] * value['weight']

        capacity /= (len(data_json) or 1)
        datetime_dic[month_day_str] = capacity

    response = []
    start_date_time = datetime.date(year, 1, 1)
    end_date_time = datetime.date(year, 12, 31)
    for i in range( (end_date_time - start_date_time).days + 1 ):
        year_month_day = start_date_time + datetime.timedelta(days=i)
        month_day_str = datetime.datetime.strftime(year_month_day, r'%m-%d')
        if month_day_str in datetime_dic:
            capacity = datetime_dic[month_day_str]
        else:
            capacity = 0
        response.append({
            'month_day': month_day_str,
            'capacity': capacity
        })

    print(response)

    return jsonify(response)



# Auth
@bp.route('/auth', methods=['POST'])
@basic_auth.login_required
def login_auth():
    user = g.current_user
    username = ''
    if user is not None:
        username = user.username
    response = {
        "username": username
    }
    return jsonify(response), 200

# Token
@bp.route('/tokens', methods=['POST'])
@basic_auth.login_required
def get_token():
    user = g.current_user
    if not user:
        return bad_request('Unauthorized...')
    now = datetime.datetime.utcnow()
    payload = {
        'user_id': user.id,
        'username': user.username,
        'exp': now + datetime.timedelta(seconds=EXPIRES_IN),
        'iat': now
    }
    token = jwt.encode(
        payload, current_app.config['SECRET_KEY'], algorithm='HS256'
    ).decode('utf-8')

    return jsonify({
        'token': token
    })

# Handle Error
@bp.app_errorhandler(404)
def not_found_error(error):
    return error_response(404)

@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return error_response(500)
