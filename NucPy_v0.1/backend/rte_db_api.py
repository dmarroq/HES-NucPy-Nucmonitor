# Get imports
import requests
import base64
import json
import datetime
import schedule
import time
from calendar import monthrange
import pymongo
from mongoengine import StringField, ListField, DateTimeField, DictField
import pandas as pd

# --------------------------------------------------------------------------------------- #

# Store normal size data
def mongo_store_data(data, database_name, collection_name):
    """
    This function stores the output of the nucmonitor in the database. It takes the data to be stored, the database name it will be stored
    in and the collection name. These are defined in the gui.
    For now, the database is not GridFS. This may change in future,
    since the function as it stands cannot store anything larger than 16MB. The data is stored as a JSON.
    """
    # Credentials
    user = "dmarroquin"
    passw = "tN9XpCCQM2MtYDme"
    host = "nucmonitordata.xxcwx9k.mongodb.net"

    # Connect to the MongoDB database
    client =  pymongo.MongoClient(
    "mongodb+srv://{0}:{1}@{2}/?retryWrites=true&w=majority&connectTimeoutMS=5000" \
    .format(user, passw, host))

    db = client[database_name]
    collection = db[collection_name]

    # Insert the data into the collection
    collection.insert_one(data)

    # Close the database connection
    client.close()

# --------------------------------------------------------------------------------------- #

# This file will simply connect to the rte and get the data directly from there

# Function to create an authentication token. This token is then used in the HTTP requests to the API for authentication.
# It is necessary to receive data from RTE.
def get_oauth():
    # ID from the user. This is encoded to base64 and sent in an HTTP request to receive the oauth token.
    # This ID is from my account (RMP). However, another account can be created in the RTE API portal and get another ID.
    joined_ID = '057e2984-edb3-4706-984b-9ea0176e74db:dc9df9f7-9f91-4c7a-910c-15c4832fb7bc'
    b64_ID = base64.b64encode(joined_ID.encode('utf-8'))
    b64_ID_decoded = b64_ID.decode('utf-8')
    
    # Headers for the HTTP request
    headers = {'Content-Type': 'application/x-www-form-urlencoded',
               'Authorization': f'Basic {b64_ID_decoded}'}
    api_url = 'https://digital.iservices.rte-france.com/token/oauth/'
    # Call to the API and if successful, the response will be 200.
    response = requests.post(api_url, headers=headers)
    
    # When positive response, the token is retrieved
    data = response.json()
    oauth = data['access_token']
    
    return(oauth)

# --------------------------------------------------------------------------------------- #

# This function does severall calls to the RTE API (because maximum time between start_date and end_date is 1 month) 
# the argument past_photo is a boolean (True, False) that indicates if we want to make a photo from the past or not
# However, the past_photo part and past_date is not yet implemented.
def get_unavailabilities(oauth):
    # This should be changed in the case of getting a past_photo because many of the rows that are relevant for that 
    # past photo will not be ACTIVE anymore.
    # unav_status = ['ACTIVE', 'INACTIVE']
    # This could also be changed. Currently it means that if we call the API with start_date=01/01/2023 and end_date=01/02/2023,
    # it will return all the records of unavailabilities that have been updated between the two dates.
    # date_type APPLICATION_DATE gets all unavailabilities with predictions in the defined dates, so that 
    # we can get an unavailability that has updated_date outside the defined dates for start_date and end_date
    date_type = 'UPDATED_DATE'
    
    # Current year/month/day/hour/minute/second is calculated for the last call to the API. 
    # For instance, if today is 05/05/2023, the last call of the API will be from 01/05/2023 to 05/05/2023 (+current hour,minute,second).
    current_datetime = datetime.datetime.now()
    previous_datetime = current_datetime - datetime.timedelta(days=1)

    # Set start_date to the beginning of the previous day
    start_date = previous_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date_formatted = start_date.strftime('%Y-%m-%dT%H:%M:%S%z')

    # Set end_date to the end of the previous day
    end_date = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date_formatted = end_date.strftime('%Y-%m-%dT%H:%M:%S%z')
    
    # Headers for the HTTP request
    headers = {'Host': 'digital.iservices.rte-france.com',
               'Authorization': f'Bearer {oauth}'
        }
    
    # the responses object is where we are going to store all the responses from the API.
    # Initially, current_datetime is included to know when we have called the API and all the
    # individual results of the API (because each call is Maz 1 month) are stored in responses["results"]
    responses = {"current_datetime": current_datetime.strftime("%m/%d/%Y, %H:%M:%S"),
                 "results":[]
        }
                
    # Call to the API
    api_url = f'https://digital.iservices.rte-france.com/open_api/unavailability_additional_information/v4/generation_unavailabilities?date_type={date_type}&start_date={start_date_formatted}%2B02:00&end_date={end_date_formatted}%2B02:00'
    print("Running request: ", api_url)
    response = requests.get(api_url, headers=headers)
    json_response = response.json()
    responses["results"].append(json_response)
    print("Response received:\n", responses)
    # -----------------------------------NEED TO GET THE MONGO STUFF UP------------------------------------------ #

    # Store the responses in MongoDB
    database_name = "data"
    collection_name = "unavs_update"
    mongo_store_data(responses, database_name, collection_name)
    print(f"Data stored in database {database_name} in collection {collection_name}")
    return

# Function to call get_unavailabilities and store the data
def call_and_store():
    oauth = get_oauth()
    get_unavailabilities(oauth)

# Schedule the function to run at 00:05
schedule.every().day.at("00:05").do(call_and_store)  # Adjust the time as needed

if __name__ == '__main__':
    # Run the scheduling loop
    while True:
        schedule.run_pending()
        time.sleep(1)