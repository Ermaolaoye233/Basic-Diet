from flask import Blueprint, request, abort
from .db import get_db
from .jwt import get_userJWT
from .util import getUserRecCalories, getUserAge
from datetime import datetime
import json

class NestedBlueprint(object): # Object for creating nested blueprint
    def __init__(self, blueprint, prefix):
        super(NestedBlueprint, self).__init__()
        self.blueprint = blueprint
        self.prefix = '/' + prefix

    def route(self, rule, **options):
        rule = self.prefix + rule
        return self.blueprint.route(rule, **options)

bp = Blueprint('api', __name__, url_prefix='/api') # Setting up for the api blueprint
food = NestedBlueprint(bp, 'Food') # APIs about foods
user = NestedBlueprint(bp, 'User') # APIs about users
record = NestedBlueprint(bp, 'Record') # APIs about records

def query2Json(sql, para, abort400=False, returnNull=False):
    """
    Parameters:
    sql         The sql statement
    para        The parameter for the sql statement
    abort400    A boolean variable, if cannot find the corresponding item then abort HTTP 400 error.
    returnNull  Return -1 if cannot find the corresponding item.
                    - abort400 and returnNull cannot both be true at the same time
    """
    db = get_db()
    cursor = db.execute(sql % para)
    dictData = [dict(row) for row in cursor.fetchall()]
    if abort400 == True:
        if not dictData: # Empty dictionary evaluate to False in python
            abort(400)
    if returnNull == True:
        if not dictData:
            return -1
    return json.dumps(dictData)

def getUserID(para):
    """
    Parameters:
    para        Parameter for filtering the userID
                Parameter needs to contain \" when utilizing string data
    """
    db = get_db()
    cursor = db.execute("SELECT userID FROM Users WHERE %s" % para)
    dictData = [row[0] for row in cursor.fetchall()]
    userID = int(dictData[0])
    return userID

def JWTverification(JWT, userID):
    """
    Parameters:
    JWT         JWT input from the frontend
    userID      ID of the user for verificating its JWT
    """
    # Find the JWT stored in the server corresponding with the input
    sql = '''SELECT JWT FROM Users WHERE userID=%i''' % userID
    db = get_db()
    cursor = db.execute(sql)
    dictData = [row[0] for row in cursor.fetchall()]
    db_JWT = str(dictData[0])
    # Equal to frontend input then return True
    if db_JWT == JWT:
        return True
    else:
        return False

# - Foods
@food.route('/description/<int:food_id>', methods=('GET', 'POST'))
def get_food_description(food_id=1):
    """
    Parameter:
    food_id     The id of the description of the food that client is looking for
    """
    sql = """SELECT foodNameCHN, calories, carbohydrate, fat, protein, cholesterol 
    FROM Foods WHERE foodID = %i"""
    para = food_id
    json = query2Json(sql=sql, para=para, abort400=True)
    return json

@food.route('/list/<string:user_input>', methods=('GET','POST'))
def get_list_food(user_input):
    """
    Parameter:
    user_input  The user input of the name of food they're looking for
    """
    sql = """SELECT foodNameCHN FROM Foods WHERE foodNameCHN LIKE '%s'"""
    para = "%" + user_input + "%"
    json = query2Json(sql=sql, para=para, abort400=True)
    return json

# - Users
@user.route('/addUser', methods=('GET','POST'))
def user_register():
    """
    JSON Requirement
    userName    A string value that contains user name
    userGender  A string value that tells user gender
    password    A string value that contains SHA2 hashed value of password
    userEmail   A string value that contains user email
    userWeight  A integer value of the user's weight
    userBirthdayA string value of user's birthday in format yyyy-mm-dd
    """
    if request.method == 'POST':
        user = request.json
        # Insert the user information to database
        sql = '''INSERT INTO Users(userName, userGender, userEmail, userWeight, userHeight, userPassword, userBirthday) VALUES(\"%s\", \"%s\", \"%s\", %i, %i,\"%s\", \"%s\")''' % (user['userName'], user['userGender'], user['userEmail'], user['userWeight'], user['userHeight'],user['password'], user['userBirthday'])
        db = get_db()
        db.execute(sql)
        db.commit()
        # Get the corresponding JWT for user
        para = "userEmail == \"%s\"" % user['userEmail']
        JWT = get_userJWT(getUserID(para = para))
        # Get user recommend calories
        recCalories = getUserRecCalories(int(user['userWeight']),int(user['userHeight']),int(getUserAge(user['userBirthday'])),user['userGender'])
        # Update calories and jwt to database
        db.commit()
        db.execute('''UPDATE Users SET JWT=\"%s\", userCalories=%i WHERE userEmail=\"%s\"''' % (JWT, recCalories, user['userEmail']))
        db.commit()
        # Return JWT
        return JWT

@user.route('/login', methods=('GET','POST'))
def user_login():
    """
    JSON Requirement
    userEmail   Email of the user
    password    Password input
    """
    if request.method == 'POST':
        user = request.json
        # GET the password's hashed value that stored in the database
        sql = '''SELECT userPassword FROM Users WHERE userEmail=\"%s\"''' % (user['userEmail'])
        db = get_db()
        cursor = db.execute(sql)
        dictData = [row[0] for row in cursor.fetchall()]
        db_userPassword = str(dictData[0])
        input_userPassword = str(user['password'])
        # When input password is the same as the password stored in the database
        if db_userPassword == input_userPassword:
            # Get corresponding userID and update user's JWT
            para = "userEmail == \"%s\"" % user['userEmail']
            JWT = get_userJWT(getUserID(para = para))
            db.commit()
            db.execute('''UPDATE Users SET JWT=\"%s\" WHERE userEmail=\"%s\"''' % (JWT, user['userEmail']))
            db.commit()
            # Return the new JWT
            return JWT 
        # Return error message when input is incorrect
        else:
            return "WrongInput"

@user.route('/description', methods=('GET','POST'))
def get_user_description():
    """
    JSON Requirement
    userJWT     JWT stored in the frontend
    userID      The ID of the user
    """
    if request.method == 'POST':
        user = request.json
        # JWT Verification
        if not JWTverification(JWT = str(user['userJWT']), userID = int(user['userID'])):
            abort(401)
        sql = '''SELECT userName, userEmail ,userWeight ,userHeight ,userCalories ,userBirthday ,userGender FROM Users WHERE userID = %i'''
        para = int(user['userID'])
        json = query2Json(sql=sql, para=para, abort400=False)
        return json

@user.route('/update', methods=('GET','POST'))
def update_user_profile():
    """
    JSON Requirement
    userJWT     JWT stored in the frontend
    userID      The ID of the user
    userName    New name of the user
    userGender  New gender of the user
    userEmail   New email of the user
    """
    if request.method == 'POST':
        user = request.json
        # JWT Verification
        if not JWTverification(JWT=user['userJWT'], userID=user['userID']):
            abort(401)
        # Update User Profile
        sql = '''UPDATE Users SET userName=\"%s\", userGender = \"%s\", userEmail=\"%s\" WHERE userID=%i''' % (user['userName'], user['userGender'], user['userEmail'], user['userID'])
        db = get_db()
        db.execute(sql)
        db.commit()
        return "Succeed"

@user.route('/updatePassword', methods=('GET','POST'))
def update_user_password():
    """
    JSON Requirement
    oriPassword Original Password stored in the database
    newPassword New Password that user want to set
    userID      The ID of the user
    """
    if request.method == 'POST':
        user = request.json
        # GET server password
        db = get_db()
        cursor = db.execute("SELECT userPassword FROM Users WHERE userID = %i" % user['userID'])
        dictData = [row[0] for row in cursor.fetchall()]
        db_userPassword = str(dictData[0])
        # Password Verification
        if db_userPassword != user['oriPassword']:
            return "Incorrect Input"
        db.commit()
        db.execute('''UPDATE Users SET userPassword=\"%s\" WHERE userID=%i''' % (user['newPassword'], user['userID']))
        db.commit()
        return 'succeed'

@user.route('/ratingFood', methods=('GET','POST'))
def addRating():
    """
    JSON Requirement
    userJWT     JWT stored in the frontend
    userID      ID of the user
    foodID      ID of the food that user want to rate
    rating      Score that food get
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=str(record['userJWT']), userID=record['userID']):
            abort(401)
        # Check IF foodID is exist in the database
        db = get_db()
        cursor = db.execute("SELECT foodID FROM Ratings WHERE userID = %i" % record['userID'])
        dictData = [row[0] for row in cursor.fetchall()]
        # IF Rating record already exist, update the record
        if record['foodID'] in dictData:
            sql = '''UPDATE Ratings SET rating=%i WHERE userID=%i AND foodID = %i''' % (record['rating'], record['userID'], record['foodID'])
        # IF does not exist, add the record
        else:
            sql = '''INSERT INTO Ratings(userID, foodID, rating) VALUES(%i, %i, %i)''' % (record['userID'], record['foodID'], record['rating'])
        db.execute(sql)
        db.commit()
        return "succeed"

@user.route('/getRating', methods=('GET', 'POST'))
def get_rating():
    """
    JSON Requirement
    userID      ID of the user
    userJWT     JWT stored in the frontend
    foodID      ID of the food
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=record['userJWT'], userID=record['userID']):
            abort(401)
        # Get corresponding rating
        sql = '''SELECT rating FROM Ratings WHERE userID = %i AND foodID = %i''' 
        para = (record['userID'], record['foodID'])
        json = query2Json(sql=sql, para=para, returnNull=True)
        return json

@user.route('/delRating', methods=('GET','POST'))
def del_rating():
    """
    JSON Requirement
    userID      ID of the user
    userJWT    JWT stored in the frontend
    foodID      ID of the food
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=str(record['userJWT']), userID=int(record['userID'])):
            abort(401)
        # Delete Ratings
        sql = '''DELETE FROM Ratings WHERE foodID=%i AND userID=%i''' % (record['foodID'],record['userID'])
        db = get_db()
        db.execute(sql)
        db.commit()
        return 'succeed'

@user.route('/addToFav', methods=('GET','POST'))
def add_fav():
    """
    JSON Requirement
    userID      ID of the user
    userJWT     JWT of the user
    foodID      ID of the food
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=str(record['userJWT']), userID=int(record['userID'])):
            abort(401)
        # Add to favourite
 

# - Records
@record.route('/addRecord', methods=('GET','POST'))
def record_register():
    """
    JSON Requirement
    userID      ID of the user
    userJWT     JWT stored in the frontend
    foodID      ID of the food
    quantity    Quantity of consumption
    unit        string value of unit
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=str(record['userJWT']), userID=int(record['userID'])):
            abort(401)
        # Get current time
        currentTime = datetime.now()
        str_currentTime = currentTime.strftime("%Y/%m/%d %H:%M:%S") # Format current time into string
        # Insert the data into the database
        sql = '''INSERT INTO Records(userID, foodID, date, quantity, unit) VALUES(%i, %i, \"%s\", %f, \"%s\")''' % (record['userID'], record['foodID'], str_currentTime, record['quantity'], record['unit'])
        # Return Succeed
        db = get_db()
        db.execute(sql)
        db.commit()
        # Return Succeed
        return 'succeed'

@record.route('/description', methods=('GET','POST'))
def get_record_description():
    """
    JSON Requirement
    userID      ID of the user
    userJWT     JWT of the user
    rangeType   Type of range of records: Day, Week, Month, ID
                    - Day: yyyy-mm-dd
                    - Week: yyyy-mm-dd of the start(Monday) of the week
                    - Month: yyyy-mm
                    - ID: id of the record 
    rangeVal    Value of the range
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=record['userJWT'], userID=record['userID']):
            abort(401)
        # When requesting for one day's record or one month's record
        if record['rangeType'] == 'Day' or record['rangeType'] == 'Month':
            # Query the database
            sql = """SELECT foodID, quantity, unit, date FROM Records WHERE date LIKE \"%s\""""
            para = record['rangeVal'] + "%"
            json = query2Json(sql=sql, para=para, abort400=True)
            return json
        # When requesting for one week's record
        elif record['rangeType'] == 'Week':
            # Week Start Date and Week End Date Calculation
            startDate = record['rangeVal']
            endDate = str(str(startDate[0:8]) + str(int(startDate[8:10])+6))
            # Query the database
            sql = """SELECT recordID, foodID, quantity, unit, date FROM Records WHERE date(date) BETWEEN date(\"%s\") AND date(\"%s\")"""
            para = (startDate, endDate)
            json = query2Json(sql=sql, para=para, abort400=True)
            return json
        elif record['rangeType'] == 'ID':
            sql = """SELECT recordID, foodID, quantity, unit, date FROM Records WHERE recordID = %i"""
            para = int(record['rangeVal'])
            json = query2Json(sql=sql, para=para, abort400=True)
            return json
        else:
            abort(400)

@record.route('/update', methods=('GET','POST'))
def update_record():
    """
    JSON Requirement
    userJWT     JWT stored in the frontend
    userID      The ID of the user
    recordID    The ID of the record
    newQuantity New value for quantity of that record, float number
    newDate     New value for the date of the record, format yyyy-mm-dd H:M:S
    newUnit     New value for the unit of the record
    """
    if request.method == 'POST':
        record = request.json
        # JWT verification
        if not JWTverification(JWT=record['userJWT'], userID=record['userID']):
            abort(401)
        # Update Records
        sql = '''UPDATE Records SET date=\"%s\", quantity=%f, unit=\"%s\" WHERE recordID = %i AND userID = %i''' % (record['newDate'], record['newQuantity'], record['newUnit'], record['recordID'], record['userID']) # make sure user can only update their own record
        db=get_db()
        db.execute(sql)
        db.commit()
        return "succeed"

@record.route('/delete', methods=('GET','POST'))
def del_record():
    """
    JSON Requirement
    userID      The ID of the user
    userJWT     The JWT of the user
    recordID    The ID of the record being deleted
    """
    if request.method == 'POST':
        record = request.json
        # JWT Verification
        if not JWTverification(JWT=record['userJWT'], userID=record['userID']):
            abort(401)
        # Delete from database
        sql = '''DELETE FROM Records WHERE recordID = %i AND userID= %i''' % (record['recordID'], record['userID'])
        db = get_db()
        db.execute(sql)
        db.commit()
        return 'succeed'
