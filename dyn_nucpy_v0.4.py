"""
MVP of NucPy with gui and dynamic RTE, version 0.4.
Changelog:
v0.1
- Added RTE call to nucmonitor function

v0.2
- Removed ability to get database and collection
- Added datetime to file names
- Added database storage

v0.3
- Updated datetime translations to avoid future incompatibilities
- Removed unused imports
- Streamlined initial data cleaning

v0.4
- Removed time stuff

Future changes:
- Find a way to get the database collection faster
- Make it so that if the database has already called the connection, use the data already called instead of getting the data again

To run, install the dependencies and run the python file.
"""
# Get imports
import requests
import base64
import json
import datetime
from calendar import monthrange
import pymongo
from mongoengine import StringField, ListField, DateTimeField, DictField
import pandas as pd
from bson import json_util, ObjectId
from gridfs import GridFS, GridFSBucket
from tkinter import messagebox
from tkinter import simpledialog
import tkinter as tk
from tkinter import filedialog, simpledialog
from tkinter import simpledialog as sd

# --------------------------------------------------------------------------------------- #
# Create a function to create an excel of the output.
def get_excel_local(data, path, photo_date):
    """
    This function creates an excel of the output of nucmonitor(). It takes the data output of the nucmonitor,
    the path name for the excel defined in the get_excel_local(), and the boolean photo_date from the nucmonitor.
    """
    current_datetime = datetime.datetime.now()
    current_year = current_datetime.strftime('%Y')
    current_month = current_datetime.strftime('%m')
    current_day = current_datetime.strftime('%d')
    current_hour = current_datetime.strftime('%H')
    current_minute = current_datetime.strftime('%M')
    current_second = current_datetime.strftime('%S')
    data_df = pd.DataFrame(data)
    if photo_date:
        excel_file_path = f"photo_date_{current_year}-{current_month}-{current_day}-h{current_hour}m{current_minute}s{current_second}.xlsx"
    else:
        excel_file_path = f"filtered_unavailabilities_{current_year}-{current_month}-{current_day}-h{current_hour}m{current_minute}s{current_second}.xlsx"
    # Export the DataFrame to Excel with index
    data_df.to_excel(path + excel_file_path, index=True)

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

# Store data with more than 16MB in a collection using GridFS
def mongo_store_large_data(json_data, database_name, collection_name):
    # Credentials
    user = "dmarroquin"
    passw = "tN9XpCCQM2MtYDme"
    host = "nucmonitordata.xxcwx9k.mongodb.net"

    # Connect to the MongoDB database
    client = pymongo.MongoClient(
        "mongodb+srv://{0}:{1}@{2}/?retryWrites=true&w=majority&connectTimeoutMS=5000"
        .format(user, passw, host))
    db = client[database_name]
    fs = GridFS(db, collection_name)

    # Convert JSON data to string
    json_string = json.dumps(json_data)

    # Store the JSON data in GridFS as a single file
    file_id = fs.put(json_string.encode(), filename='data.json')

    # Close the database connection
    client.close()

    return file_id


# --------------------------------------------------------------------------------------- #

def merge_gridfs_files_to_json(database_name, collection_name):
    """
    This function retrieves the raw data from the database. More generally, it retrieves data from a GridFS collection 
    and outputs a json string.
    This function takes:
    - database_name, the name of the database, defined in the user input
    - collection_name, the name of the collection within the database, defined by user input.
    For now, user input must be:
    database_name = 'data'
    collection_name = 'raw' or 'clean_nuc'
    """
    # Connect to the MongoDB database
    user = "dmarroquin"
    passw = "tN9XpCCQM2MtYDme"
    host = "nucmonitordata.xxcwx9k.mongodb.net"
    client = pymongo.MongoClient(
        f"mongodb+srv://{user}:{passw}@{host}/?retryWrites=true&w=majority"
    )

    # Access the GridFS bucket
    db = client[database_name]
    fs = GridFS(db, collection=collection_name)

    # Retrieve all files from the GridFS bucket
    all_files = fs.find()

    # Create a list to store the contents of all files
    file_contents = []

    for file in all_files:
        content = file.read()
        content_str = content.decode('utf-8')  # Decode bytes to string
        file_contents.append(content_str)
            
    client.close()
    
    # Convert the list of file contents to a JSON string
    json_data = json.dumps(file_contents)
    
    return json_data

# --------------------------------------------------------------------------------------- #

# Convert the dictionary of dictionaries to JSON
def convert_to_json(item):
    if isinstance(item, dict):
        return {str(k): convert_to_json(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [convert_to_json(i) for i in item]
    elif isinstance(item, ObjectId):
        return str(item)
    else:
        return item
# --------------------------------------------------------------------------------------- #

# The idea of this function is to sum the total availability for each day of interest
# This is already done in the Excel so it might be useful to check
# Function gives the total of the data. When printed as dataframe/excel,
# Will give a final row with the total for each plant and the total overall
def add_total(data):
    total_values = {}
    for key in data:
        daily_values = data[key]
        total = sum(daily_values.values())
        daily_values["Total"] = total
        for date, value in daily_values.items():
            if date not in total_values:
                total_values[date] = value
            else:
                total_values[date] += value
        
    data["Total"] = total_values

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
def get_unavailabilities(oauth, usr_start_date, usr_end_date):
    # This should be changed in the case of getting a past_photo because many of the rows that are relevant for that 
    # past photo will not be ACTIVE anymore.
    # unav_status = ['ACTIVE', 'INACTIVE']
    # This could also be changed. Currently it means that if we call the API with start_date=01/01/2023 and end_date=01/02/2023,
    # it will return all the records of unavailabilities that have been updated between the two dates.
    # date_type = 'UPDATED_DATE'
    # date_type APPLICATION_DATE gets all unavailabilities with predictions in the defined dates, so that 
    # we can get an unavailability that has updated_date outside the defined dates for start_date and end_date
    date_type = 'APPLICATION_DATE'
    
    # Current year/month/day/hour/minute/second is calculated for the last call to the API. For instance, if today is 05/05/2023,
    # the last call of the API will be from 01/05/2023 to 05/05/2023 (+current hour,minute,second). 
    current_datetime = datetime.datetime.now()
    current_year = current_datetime.strftime('%Y')
    current_month = current_datetime.strftime('%m')
    current_day = current_datetime.strftime('%d')
    current_hour = current_datetime.strftime('%H')
    current_minute = current_datetime.strftime('%M')
    current_second = current_datetime.strftime('%S')
    
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

    # --------------------------- HERE HAVE TO GET THE RANGE OF DATES FROM START AND END AND PUT THEM INTO LIST --------------------------- #
    # Convert start_date and end_date to datetime objects
    start_date_obj = usr_start_date
    end_date_obj = usr_end_date

    # Initialize lists to store years and months
    years = []
    months = []

    # Generate the range of years and months
    current_date = start_date_obj
    while current_date <= end_date_obj:
        years.append(current_date.year)
        months.append(current_date.month)
        current_date += datetime.timedelta(days=1)

    # Remove duplicates from the lists
    years = list(set(years))
    months = list(set(months))
    years.sort()
    months.sort()
    print(years)
    print(months)
   # --------------------------- HERE HAVE TO GET THE RANGE OF DATES FROM START AND END AND PUT THEM INTO LIST --------------------------- #

    # Loop to call the API all the necessary times.
    for i in range(len(years)):
        for j in range(len(months)): 
            # start_year and start_month of the current call to the API
            start_year = years[i]
            start_month = months[j]
            # start_date is constructed. Now we only need to construct the end_date.
            start_date = f'{start_year}-{start_month}-01T00:00:00%2B02:00'

            if True:
                # Calculate the number of days in the current month
                _, num_days = monthrange(int(start_year), int(start_month))
                end_date = f'{start_year}-{start_month}-{num_days}T23:59:59%2B02:00'
                    
                print(f'start date is {start_date}')
                print(f'end date is {end_date}')
                
                # Call to the API
                api_url = f'https://digital.iservices.rte-france.com/open_api/unavailability_additional_information/v4/generation_unavailabilities?date_type={date_type}&start_date={start_date}&end_date={end_date}'

                response = requests.get(api_url, headers=headers)
                json_response = response.json()
                responses["results"].append(json_response)

    # -----------------------------------NEED TO GET THE MONGO STUFF UP------------------------------------------ #

    # Store the responses in MongoDB
    database_name = "data"
    collection_name = "dynamic_nuc"
    mongo_store_large_data(responses, database_name, collection_name)
    print("Data stored in database")

    # -----------------------------------NEED TO GET THE MONGO STUFF UP------------------------------------------ #

    # path to store the results locally
    # file_path = '/Users/diegomarroquin/HayaEnergy/data/dynamic_unavailabilities_test.json'

    # with open(file_path, "w") as write_file:
    #     # Serialize responses using json_util
    #     serialized_responses = json.dumps(responses)
    #     write_file.write(serialized_responses)

    # print("Data stored locally")
    
    # user_input_excel = input("Would you like to get an excel of the RTE?: ")
    # if 'y' in user_input_excel.lower():
    #     get_excel_local(database_name, collection_name)
    #     print("Excel downloaded")
    #     return
    return responses

# --------------------------------------------------------------------------------------- #


# this function does the proper analysis of the data
# It takes the user, password, host, to connect to the mongodb database and get
# the data to clean from the database from database and collection
# Create a condition that makes it so it only takes the ACTIVE when nucmonitor, and 
# all (INACTIVE, ACTIVE) when photo_date
def nuc_monitor(user, passw, host, database, collection, usr_start_date, usr_end_date, path_to_store, first_loop_completed):
    # # Slightly changed metadata to fit the data from the RTE API: ST-LAURENT B 2 --> ST LAURENT 2, ....

    # --------------------------------------------- #
    photo_date = False

    # file_path = "/Users/diegomarroquin/HayaEnergy/data/plants_metadata.json"

    # with open(file_path, "r") as file:
    #     plants_metadata = json.load(file)
    plants_metadata = {"BELLEVILLE 1": 1310.0, "BELLEVILLE 2": 1310.0, "BLAYAIS 1": 910.0, "BLAYAIS 2": 910.0, 
                   "BLAYAIS 3": 910.0, "BLAYAIS 4": 910.0, "BUGEY 2": 910.0, "BUGEY 3": 910.0, "BUGEY 4": 880.0, 
                   "BUGEY 5": 880.0, "CATTENOM 1": 1300.0, "CATTENOM 2": 1300.0, "CATTENOM 3": 1300.0, 
                   "CATTENOM 4": 1300.0, "CHINON 1": 905.0, "CHINON 2": 905.0, "CHINON 3": 905.0, 
                   "CHINON 4": 905.0, "CHOOZ 1": 1500.0, "CHOOZ 2": 1500.0, "CIVAUX 1": 1495.0, 
                   "CIVAUX 2": 1495.0, "CRUAS 1": 915.0, "CRUAS 2": 915.0, "CRUAS 3": 915.0, "CRUAS 4": 915.0, 
                   "DAMPIERRE 1": 890.0, "DAMPIERRE 2": 890.0, "DAMPIERRE 3": 890.0, "DAMPIERRE 4": 890.0, 
                   "FLAMANVILLE 1": 1330.0, "FLAMANVILLE 2": 1330.0, "GOLFECH 1": 1310.0, "GOLFECH 2": 1310.0, 
                   "GRAVELINES 1": 910.0, "GRAVELINES 2": 910.0, "GRAVELINES 3": 910.0, "GRAVELINES 4": 910.0, 
                   "GRAVELINES 5": 910.0, "GRAVELINES 6": 910.0, "NOGENT 1": 1310.0, "NOGENT 2": 1310.0, 
                   "PALUEL 1": 1330.0, "PALUEL 2": 1330.0, "PALUEL 3": 1330.0, "PALUEL 4": 1330.0, "PENLY 1": 1330.0, 
                   "PENLY 2": 1330.0, "ST ALBAN 1": 1335.0, "ST ALBAN 2": 1335.0, "ST LAURENT 1": 915.0, 
                   "ST LAURENT 2": 915.0, "TRICASTIN 1": 915.0, "TRICASTIN 2": 915.0, "TRICASTIN 3": 915.0, 
                   "TRICASTIN 4": 915.0, "FESSENHEIM 1": 880.0, "FESSENHEIM 2": 880.0}


    # Get raw data from database and the RTE
    oauth = get_oauth()
    
    rte_data = get_unavailabilities(oauth, usr_start_date, usr_end_date)

    mongo_json_data = merge_gridfs_files_to_json(database, collection)

    
    # --------------------- INITIAL DATA CLEANING FOR RTE DATA ------------------------ #    
    unav_API = rte_data
    # Store the unavailabilities in a list
    unavailabilities = []
    print("Unav")
    for unavailabilities_API in unav_API['results']:
        try:
            unavailabilities.extend(unavailabilities_API.get('generation_unavailabilities', []))
        except:
            print('There was an error')
            # print(unavailabilities_API)
    rte_df = pd.DataFrame(unavailabilities)


    def unpack_values(row):
        if isinstance(row["values"], list):
            for key, value in row["values"][0].items():
                row[key] = value
        return row
    # Apply the function to each row in the DataFrame
    rte_df = rte_df.apply(unpack_values, axis=1)

    # Drop the original "values" column
    rte_df.drop("values", axis=1, inplace=True)

    # Unpack the unit column
    rte_df2 = pd.concat([rte_df, pd.json_normalize(rte_df['unit'])], axis=1)
    rte_df2.drop('unit', axis=1, inplace=True)


    rte_nuclear_unav = rte_df2[(rte_df2["production_type"] == "NUCLEAR")]

    # --------------------- INITIAL DATA CLEANING FOR RTE DATA ------------------------ #    


    # --------------------- INITIAL DATA CLEANING FOR MONGO DATA ------------------------ #    

    # Remove the outer square brackets from the JSON data
    mongo_data = mongo_json_data
    json_data = mongo_data.strip("[]")

    # Convert the JSON data into a list of dictionaries
    data_list = json.loads(json_data)

    # Convert the JSON data into a list of dictionaries
    mongo_df = pd.read_json(data_list)

    # --------------------- INITIAL DATA CLEANING FOR MONGO DATA ------------------------ #   

    # Make the two dataframes have the same columns
    mongo_unavs = mongo_df.copy()
    mongo_unavs.drop(columns="type", inplace=True)

    rte_unavs = rte_nuclear_unav.copy()
    rte_unavs.drop(columns="type", inplace=True)

    # Merge dataframes
    column_order = mongo_unavs.columns
    merged_df = pd.concat([mongo_unavs[column_order], rte_unavs[column_order]], ignore_index=True)

# --------------------------- HERE IS THE CHANGE TO GET ONLY ACTIVE OR ACTIVE AND INACTIVE --------------------------- #
    start_date_str = usr_start_date.strftime("%Y-%m-%d")
    end_date_str = usr_end_date.strftime("%Y-%m-%d")
    current_datetime = datetime.datetime.now()
    current_datetime_str = current_datetime.strftime("%Y-%m-%d")

    photo_date = False
    photo_date_input = messagebox.askquestion("Photo Date", "Would you like the photo date?")
    if photo_date_input == "yes":
        past_date = simpledialog.askstring("Past Date", "Enter the cutoff date (yyyy-mm-dd): ")
        nuclear_unav = merged_df.copy()[(merged_df.copy()["production_type"] == "NUCLEAR") & (merged_df.copy()["updated_date"] <= past_date)]
        photo_date = True
    else: # need to add updated_date as a conditional to get the newest for that day
        nuclear_unav = merged_df.copy()[(merged_df.copy()["production_type"] == "NUCLEAR") & (merged_df.copy()["updated_date"] <= end_date_str)]

    # return print(past_date)
    # print(nuclear_unav)
    # list_to_excel(nuclear_unav, "mongo_merged_photo_unavs.xlsx")
    # print("done")
    # return
# --------------------------- HERE IS THE CHANGE TO GET ONLY ACTIVE OR ACTIVE AND INACTIVE --------------------------- #

    # --------------------- SECOND DATA CLEANING ------------------------ #    
    # This filter should take only the most recent id and discard the rest

    # Sort by updated date
    sorted_df = nuclear_unav.copy().sort_values(by='updated_date')

    sorted_df = sorted_df.copy().reset_index(drop=True)

    # Filter to get identifiers
    filtered_id_df = sorted_df.copy()
    filtered_id_df.drop_duplicates(subset='identifier', keep='last', inplace=True)
    filtered_id_df = filtered_id_df.copy().reset_index(drop=True)


    # This filter should take all the dates with unavs that include days with unavs in the range of the start and end date

    filtered_df = filtered_id_df.copy()[(filtered_id_df.copy()['start_date'] <= end_date_str) & (filtered_id_df.copy()['end_date'] >= start_date_str)]

    # Standardize datetime in dataframe
    filtered_df2 = filtered_df.copy() # This code will just standardize datetime stuff
    filtered_df2['creation_date'] = pd.to_datetime(filtered_df2['creation_date'], utc=True)
    filtered_df2['updated_date'] = pd.to_datetime(filtered_df2['updated_date'], utc=True)
    filtered_df2['start_date'] = pd.to_datetime(filtered_df2['start_date'], utc=True)
    filtered_df2['end_date'] = pd.to_datetime(filtered_df2['end_date'], utc=True)

    # Drop the duplicates
    filtered_df3 = filtered_df2.copy().drop_duplicates()

    # start_date_datetime = pd.to_datetime(start_date_str, utc=True)  # Remove timezone info
    start_date_datetime = pd.Timestamp(start_date_str, tz='UTC')
    # end_date_datetime = pd.to_datetime(end_date_str, utc=True)
    end_date_datetime = pd.Timestamp(end_date_str, tz='UTC')

    # Turn df into dict for json processing
    filtered_unavs = filtered_df3.copy().to_dict(orient='records')

    results = {}

    for unav in filtered_unavs:
        plant_name = unav['name']
        if plant_name in results:
            # If the key is already in the dictionary, append unavailability to the list
            results[plant_name].append({'status': unav['status'],
                                        'id': unav['message_id'],
                                        'creation_date': unav['creation_date'],
                                        'updated_date': unav['updated_date'], 
                                        'start_date': unav['start_date'], 
                                        'end_date': unav['end_date'], 
                                        'available_capacity': unav['available_capacity']})
        else:
            # if the key of the plant is not there yet, create a new element of the dictionary

            # Get message_id instead of identifier, easier to identify stuff with it
            results[plant_name] = [{'status': unav['status'],
                                    'id': unav['message_id'],
                                    'creation_date': unav['creation_date'],
                                    'updated_date': unav['updated_date'], 
                                    'start_date': unav['start_date'], 
                                    'end_date': unav['end_date'], 
                                    'available_capacity': unav['available_capacity']}]
                        
    # Custom encoder to handle datetime objects
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, datetime.datetime):
                return o.isoformat()
            return super().default(o)

    results_holder = results

    # Create new dict with each plant only having start_date less than user_end_date and an end_date greater than user_start_date
    # should just be doing the same as above in the df for filtering only dates that inclued the start and end date
    start_date = start_date_datetime.date()
    end_date = end_date_datetime.date()
    results_filtered = results_holder
    for key, value in results_filtered.items():
        filtered_values = []
        for item in value:
            item_start_date = item['start_date'].date()
            item_end_date = item['end_date'].date()
            identifier = item['id']
            if item_start_date < end_date and item_end_date > start_date and identifier not in filtered_values:
                filtered_values.append(item)
        results_filtered[key] = filtered_values


    sorted_results = results_filtered
    # --------------------- SECOND DATA CLEANING ------------------------ #    

# --------------------------- HERE IS THE FINAL PROCESS --------------------------- #

    for key, value in sorted_results.items():
        sorted_results[key] = sorted(value, key=lambda x: x['updated_date'])

    results_sorted = sorted_results
 
    dates_of_interest = [start_date] # We are creating a list of dates ranging from user specified start and end dates
    date_plus_one = start_date

    while date_plus_one < end_date:
        date_plus_one = date_plus_one + datetime.timedelta(days=1)
        dates_of_interest.append(date_plus_one) 
        
    # This is to standardize the datetimes. Without this, the datetime calculations for each power plant will not work
    results_plants = {plant_name: {date: {"available_capacity": power, "updated_date": pd.to_datetime("1970-01-01", utc=True)} for date in dates_of_interest}
                    for plant_name, power in plants_metadata.items()}


    for plant, unavailabilities in results_sorted.items():

        original_power = plants_metadata[plant]
        # Get all the unavailabilities scheduled for the plant.
        results_current_plant = results_plants[plant] 
        
        for unavailability in unavailabilities:
            # For each unavailability, the resulting power, start and end datetime are collected. Need to collect updated_date
            power_unavailability = unavailability["available_capacity"]
            updated_date_unav = unavailability["updated_date"]
            # The date comes as a string
            start_datetime_unav = unavailability["start_date"]
            end_datetime_unav = unavailability["end_date"]
            start_date_unav = start_datetime_unav.date()  # Extract date part
            end_date_unav = end_datetime_unav.date()      # Extract date part
            
            # For the current unavailability, we want to find which days it affects
            for day in dates_of_interest: 

                start_hour = start_datetime_unav.hour
                start_minute = start_datetime_unav.minute
                end_hour = end_datetime_unav.hour
                end_minute = end_datetime_unav.minute

                if start_date_unav <= day <= end_date_unav:
                    # Check if the day is already updated with a later update_date
                    if day in results_current_plant and updated_date_unav <= results_current_plant[day]["updated_date"]:
                        continue  # Skip to the next loop if there is already information for a later update_date

                    # Calculate the % of the day that the plant is under maintenance
                    if start_date_unav == day and day == end_date_unav:
                        # The unavailability starts and ends on the same day
                        percentage_of_day = (end_hour * 60 + end_minute - start_hour * 60 - start_minute) / (24 * 60)
                    elif start_date_unav == day:
                        # The unavailability starts on the current day but ends on a later day
                        percentage_of_day = (24 * 60 - (start_hour * 60 + start_minute)) / (24 * 60)
                    elif day == end_date_unav:
                        # The unavailability starts on a previous day and ends on the current day
                        percentage_of_day = (end_hour * 60 + end_minute) / (24 * 60)
                    else:
                        # The unavailability covers the entire day
                        percentage_of_day = 1

                    # The average power of the day is calculated
                    power_of_day = percentage_of_day * power_unavailability + (1 - percentage_of_day) * original_power

                    # Update the available_capacity for the day only if it's not already updated with a later update_date
                    if day not in results_current_plant or updated_date_unav > results_current_plant[day]["updated_date"]:
                        results_current_plant[day] = {"available_capacity": power_of_day, "updated_date": updated_date_unav}


    output_results = {}
    for plant, plant_data in results_plants.items():
        available_capacity_per_day = {str(date): data["available_capacity"] for date, data in plant_data.items()}
        output_results[plant] = available_capacity_per_day

    # print(output_results)
    add_total(output_results)
    print("Done")
    # print(results_plants)
    # Convert datetime key to string to store in mongodb
    output_results = {plant: {str(date): power for date, power in plant_data.items()} for plant, plant_data in output_results.items()}

    # -------------------------------------------------
    if photo_date == False:
        # Store the results_plants in MongoDB
        database_name = "data"  # Specify your database name
        collection_name = "filtered"  # Specify your collection name
        mongo_store_data(output_results, database_name, collection_name)
        messagebox.showinfo("Success", "Nucmonitor results stored in database.")
        # mongo_replace_data(results_plants_total, database_name, "filtered_excel")
        # print("Data stored in database")
        # mongo_append_data(results_plants, database_name, collection_name)
        current_datetime = datetime.datetime.now()
        current_year = current_datetime.strftime('%Y')
        current_month = current_datetime.strftime('%m')
        current_day = current_datetime.strftime('%d')
        current_hour = current_datetime.strftime('%H')
        current_minute = current_datetime.strftime('%M')
        current_second = current_datetime.strftime('%S')

        json_file_path = path_to_store + f'filtered_unavailabilities_{current_year}-{current_month}-{current_day}h{current_hour}m{current_minute}s{current_second}.json'  
        
        json_data = json.dumps(convert_to_json(output_results))

        with open(json_file_path, "w") as results_file:
            json.dump(json_data, results_file)

        print("File stored in ", json_file_path)
        user_input_excel = messagebox.askquestion("Excel", "Would you like to get an excel of the NucMonitor?")
        if user_input_excel == "yes":
            get_excel_local(output_results, path_to_store, photo_date)
            messagebox.showinfo("Success", "Excel stored in " + path_to_store)
        return
    else:
        database_name = "data"  # Specify your database name
        collection_name = "photo_date"  # Specify your collection name
        mongo_store_data(output_results, database_name, collection_name)
        messagebox.showinfo("Success", "Photo Date results stored in database.")
        current_datetime = datetime.datetime.now()
        current_year = current_datetime.strftime('%Y')
        current_month = current_datetime.strftime('%m')
        current_day = current_datetime.strftime('%d')
        current_hour = current_datetime.strftime('%H')
        current_minute = current_datetime.strftime('%M')
        current_second = current_datetime.strftime('%S')

        json_file_path = path_to_store + f'photo_date_{current_year}-{current_month}-{current_day}h{current_hour}m{current_minute}s{current_second}.json'  
        json_data = json.dumps(convert_to_json(output_results))

        with open(json_file_path, "w") as results_file:
            json.dump(json_data, results_file)

        print("File stored in ", json_file_path)

        user_input_excel = messagebox.askquestion("Excel", "Would you like to get an excel of the Photo Date?")
        if user_input_excel == "yes":
            get_excel_local(output_results, path_to_store, photo_date)
            messagebox.showinfo("Success", "Excel stored in " + path_to_store)
        return
    # -------------------------------------------------
    return

def create_gui():
    # Initialize a flag to track if the first loop has completed
    first_loop_completed = False

    def browse_directory():
        directory = filedialog.askdirectory()
        directory_entry.delete(0, tk.END)
        directory_entry.insert(tk.END, directory)

    def submit_form():
        nonlocal first_loop_completed  # Use the flag from the outer function

        start_date = start_date_entry.get()
        end_date = end_date_entry.get()
        path_to_store = directory_entry.get()

        try:
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Please enter dates in YYYY-MM-DD format.")
            return

        if first_loop_completed:
            # Call the nuc_monitor function with True
            nuc_monitor("dmarroquin", "tN9XpCCQM2MtYDme", "nucmonitordata.xxcwx9k.mongodb.net",
                        "data", "clean_nuc", start_date, end_date, path_to_store, True)
        else:
            # Call the nuc_monitor function with False
            nuc_monitor("dmarroquin", "tN9XpCCQM2MtYDme", "nucmonitordata.xxcwx9k.mongodb.net",
                        "data", "clean_nuc", start_date, end_date, path_to_store, False)
            # Set the flag to True after the first loop completes
            first_loop_completed = True

        messagebox.showinfo("Success", "NucMonitor results generated successfully.")

    # Create the GUI window
    window = tk.Tk()
    window.title("NucMonitor GUI")

    # Create and arrange the form elements
    tk.Label(window, text="Start Date (yyyy-mm-dd):").grid(row=0, column=0, sticky=tk.E)
    tk.Label(window, text="End Date (yyyy-mm-dd):").grid(row=1, column=0, sticky=tk.E)
    tk.Label(window, text="Output Directory:").grid(row=2, column=0, sticky=tk.E)

    start_date_entry = tk.Entry(window)
    end_date_entry = tk.Entry(window)
    directory_entry = tk.Entry(window)

    start_date_entry.grid(row=0, column=1)
    end_date_entry.grid(row=1, column=1)
    directory_entry.grid(row=2, column=1)

    browse_button = tk.Button(window, text="Browse", command=browse_directory)
    browse_button.grid(row=2, column=2)

    submit_button = tk.Button(window, text="Submit", command=submit_form)
    submit_button.grid(row=3, column=1)

    # Start the GUI event loop
    window.mainloop()


if __name__ == "__main__":
    create_gui()