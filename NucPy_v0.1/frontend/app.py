import streamlit as st
import requests
import pandas as pd
import json
import io
import datetime
import pandas as pd
import numpy as np
import requests
import base64
import json
from calendar import monthrange
import pymongo
from mongoengine import StringField, ListField, DateTimeField, DictField
import matplotlib.pyplot as plt
from matplotlib.dates import MonthLocator



def mongo_unavs_call(user_input_start_date, user_input_end_date, user_input_past_date):
    print("Starting mongo_unavs_call")
    # Connect to the MongoDB database
    user = "dmarroquin"
    passw = "tN9XpCCQM2MtYDme"
    host = "nucmonitordata.xxcwx9k.mongodb.net"
    client = pymongo.MongoClient(
        f"mongodb+srv://{user}:{passw}@{host}/?retryWrites=true&w=majority"
    )

    db = client["data"]
    collection = db["unavs"]

    start_date = f"{user_input_start_date}T00:00:00"
    end_date = f"{user_input_end_date}T23:59:59"
    
    pipeline = [
        {
            "$unwind": "$results"
        },
        {
            "$unwind": "$results.generation_unavailabilities"
        },
        {
            "$match": {
                "results.generation_unavailabilities.production_type": "NUCLEAR",
                "results.generation_unavailabilities.start_date": {"$lte": end_date},
                "results.generation_unavailabilities.end_date": {"$gte": start_date},
                "results.generation_unavailabilities.updated_date": {"$lte": end_date}
            }
        },
        {
            "$project": {
                "_id": 0,
                "generation_unavailabilities": "$results.generation_unavailabilities"
            }
        }
    ]

    result = collection.aggregate(pipeline)

    return list(result)

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
def get_unavailabilities(usr_start_date, usr_end_date):
    oauth = get_oauth()
    print("Get Oauth done")
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
    usr_start_date = str(usr_start_date)
    usr_end_date = str(usr_end_date)
    start_date_obj = datetime.datetime.strptime(usr_start_date, "%Y-%m-%d").date()
    end_date_obj = datetime.datetime.strptime(usr_end_date, "%Y-%m-%d").date()
    # start_date_obj = usr_start_date
    # end_date_obj = usr_end_date
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
    # print(responses)
    return responses

# --------------------------------------------------------------------------------------- #


def nuc_monitor(usr_start_date, usr_end_date, past_date, mongo_db_data, rte_data):
    # # Slightly changed metadata to fit the data from the RTE API: ST-LAURENT B 2 --> ST LAURENT 2, ....

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

    # --------------------- INITIAL DATA CLEANING FOR RTE DATA ------------------------ #  
    # unav_API = rte_data.json()
    # rte_stuff = get_unavailabilities(usr_start_date, usr_end_date)
    # rte_stuff = get_rte_data(usr_start_date, usr_end_date)
    unav_API = rte_data
    # print(unav_API)
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

    # # Create a DataFrame
    # mongo_data = mongo_unavs_call(usr_start_date, usr_end_date, past_date)
    # mongo_data = get_mongodb_data(usr_start_date, usr_end_date, past_date)

    mongo_df = pd.DataFrame(mongo_db_data)

    # Unpack the dictionaries into separate columns
    mongo_df_unpacked = pd.json_normalize(mongo_df['generation_unavailabilities'])

    # Concatenate the unpacked columns with the original DataFrame
    mongo_df_result = pd.concat([mongo_df, mongo_df_unpacked], axis=1)

    # Drop the original column
    mongo_df_result.drop(columns=['generation_unavailabilities'], inplace=True)
    mongo_df_columns = mongo_df_result.columns

    mongo_df_result['start_date'] = mongo_df_result['values'].apply(lambda x: x[0]['start_date'])
    mongo_df_result['end_date'] = mongo_df_result['values'].apply(lambda x: x[0]['end_date'])
    mongo_df_result['available_capacity'] = mongo_df_result['values'].apply(lambda x: x[0]['available_capacity'])
    mongo_df_result['unavailable_capacity'] = mongo_df_result['values'].apply(lambda x: x[0]['unavailable_capacity'])
    # print(mongo_df_result)
    # print(mongo_df_result.columns)
    # Drop the original 'values' column
    mongo_df_result.drop('values', axis=1, inplace=True)
    mongo_df2 = mongo_df_result
    mongo_df2.rename(columns=lambda col: col.replace('unit.', ''), inplace=True)

    

    # --------------------- INITIAL DATA CLEANING FOR MONGO DATA ------------------------ #   

    # Make the two dataframes have the same columns
    mongo_unavs = mongo_df2.copy()
    mongo_unavs.drop(columns="type", inplace=True)

    rte_unavs = rte_nuclear_unav.copy()
    rte_unavs.drop(columns="type", inplace=True)

    # Merge dataframes
    column_order = mongo_unavs.columns
    # print(column_order)
    merged_df = pd.concat([mongo_unavs[column_order], rte_unavs[column_order]], ignore_index=True)
    # merged_df['updated_date'] = merged_df['updated_date'].astype(str)

# --------------------------- HERE IS THE CHANGE TO GET ONLY ACTIVE OR ACTIVE AND INACTIVE --------------------------- #
    # start_date_str = usr_start_date.strftime("%Y-%m-%d")
    start_date_str = str(usr_start_date)
    # end_date_str = usr_end_date.strftime("%Y-%m-%d")
    end_date_str = str(usr_end_date)
    current_datetime = datetime.datetime.now()
    past_date_str = str(past_date)
    current_datetime_str = current_datetime.strftime("%Y-%m-%d")

    nuclear_unav = merged_df.copy()[(merged_df.copy()["production_type"] == "NUCLEAR") & (merged_df.copy()["updated_date"] <= past_date_str)]

    # if photo_date == True:
    #     nuclear_unav = merged_df.copy()[(merged_df.copy()["production_type"] == "NUCLEAR") & (merged_df.copy()["updated_date"] <= past_date_str)]
    #     photo_date = True
    # else: # need to add updated_date as a conditional to get the newest for that day
    #     nuclear_unav = merged_df.copy()[(merged_df.copy()["production_type"] == "NUCLEAR") & (merged_df.copy()["updated_date"] <= end_date_str)]

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
    # print("Done")
    # print(results_plants)
    # Convert datetime key to string to store in mongodb
    output_results = {plant: {str(date): power for date, power in plant_data.items()} for plant, plant_data in output_results.items()}
    # print(output_results)
    # -------------------------------------------------

    json_data = json.dumps(output_results)
    # print(json_data)
    return json_data
    # -------------------------------------------------

@st.cache_data
def get_rte_data(start_date, end_date):
    rte_data = get_unavailabilities(start_date, end_date)
    print(rte_data)
    return rte_data
@st.cache_data
def get_mongodb_data(start_date, end_date, past_date):
    database_data = mongo_unavs_call(start_date, end_date, past_date)
    return database_data

@st.cache_data
def get_nucmonitor_data(start_date, end_date, past_date):
    mongo = get_mongodb_data(start_date, end_date, past_date)
    rte = get_rte_data(start_date, end_date)
    response_nucmonitor = nuc_monitor(start_date, end_date, past_date, mongo, rte)
    # nucmonitor_data = response_nucmonitor.json()
    # nucmonitor_json = json.loads(nucmonitor_data)
    print(response_nucmonitor)
    df = pd.read_json(response_nucmonitor)
    return df

def run_app():

    st.title("Nucmonitor App")

    # Get user input (e.g., dates)
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    past_date = st.date_input("Cutoff Date")
    # winter_date = st.date_input("Winter Cutoff Date")

    current_date = datetime.datetime.now()

    with st.form("nucmonitor_form"):
        submitted = st.form_submit_button("Get Nucmonitor")

    if not submitted:
        st.write("Form not submitted")

    else:
        st.write("Data received from Flask:")
        df_nucmonitor = get_nucmonitor_data(start_date, end_date, current_date)
        df_photo_date = get_nucmonitor_data(start_date, end_date, past_date)
        # df_winter_date = get_nucmonitor_data(start_date, end_date, winter_date)
        current_date_str = str(current_date.strftime('%Y-%m-%d'))
        past_date_str = str(past_date.strftime('%Y-%m-%d'))
        st.write("Nucmonitor")
        st.write(df_nucmonitor)  # Display DataFrame
        
        st.write("Photo Date")
        st.write(df_photo_date)

        # Get info on current forecast Nucmonitor
        st.title("Total Energy per Day at Current Forecast")
        
        # Remove the final row 'Total'
        df_nucmonitor_2 = df_nucmonitor.iloc[:-1, :]
        # Get the last column
        df_nucmonitor_2 = df_nucmonitor_2.iloc[:, -1]
        
        print(df_nucmonitor_2)

        st.write(df_nucmonitor_2)

        # Get info on past date forecast Nucmonitor
        st.title("Total Energy per Day at Past Date Forecast")
        
        # Remove the final row 'Total'
        df_photo_date_2 = df_photo_date.iloc[:-1, :]
        # Get the last column
        df_photo_date_2 = df_photo_date_2.iloc[:, -1]
        
        print(df_photo_date_2)

        st.write(df_photo_date_2)

# --------------------------------- AVERAGE EXPECTED AVAILABILITY M-1 M M+1 M+2 PIPELINE --------------------------------- #

        # Create a Table that displays the forecast of each dataframe total for two months before date and two months after
        # Filter dates for two months before and after the current date
        # Define date ranges
        two_months_before = (current_date - pd.DateOffset(months=2)).strftime('%Y-%m')
        one_month_before = (current_date - pd.DateOffset(months=1)).strftime('%Y-%m')
        one_month_after = (current_date + pd.DateOffset(months=1)).strftime('%Y-%m')
        two_months_after = (current_date + pd.DateOffset(months=2)).strftime('%Y-%m')

        # Assuming df is the DataFrame containing the date index and the 'Total' column

        # # Convert the index to datetime if it's not already
        # df_nucmonitor_2.index = pd.to_datetime(df_nucmonitor_2.index)
        # df_photo_date_2.index = pd.to_datetime(df_photo_date_2.index)

        # # Calculate monthly averages with date in yyyy-mm format
        # monthly_average_nucmonitor = df_nucmonitor_2.resample('M').mean()
        # monthly_average_photo_date = df_photo_date_2.resample('M').mean()

        # Convert the index to datetime if it's not already
        df_nucmonitor_2.index = pd.to_datetime(df_nucmonitor_2.index)
        df_photo_date_2.index = pd.to_datetime(df_photo_date_2.index)

        # Calculate monthly averages with date in yyyy-mm format
        monthly_average_nucmonitor = df_nucmonitor_2.resample('M').mean()
        monthly_average_nucmonitor.index = monthly_average_nucmonitor.index.strftime('%Y-%m')

        monthly_average_photo_date = df_photo_date_2.resample('M').mean()
        monthly_average_photo_date.index = monthly_average_photo_date.index.strftime('%Y-%m')


        print(monthly_average_nucmonitor)
        print(monthly_average_nucmonitor.index)
        print(len(monthly_average_nucmonitor.index) < 5)
        if len(monthly_average_nucmonitor.index) < 5 or two_months_before not in monthly_average_nucmonitor.index:
            df_display_normal_bool = False

        else:
            print(two_months_before, one_month_before, current_date.strftime('%Y-%m'), one_month_after, two_months_after)
            # Filter DataFrames based on date ranges
            df_nucmonitor_filtered = monthly_average_nucmonitor[
                (monthly_average_nucmonitor.index == two_months_before) |
                (monthly_average_nucmonitor.index == one_month_before) |
                (monthly_average_nucmonitor.index == current_date.strftime('%Y-%m')) |
                (monthly_average_nucmonitor.index == one_month_after) |
                (monthly_average_nucmonitor.index == two_months_after)
            ]

            df_photo_date_filtered = monthly_average_photo_date[
                (monthly_average_photo_date.index == two_months_before) |
                (monthly_average_photo_date.index == one_month_before) |
                (monthly_average_photo_date.index == current_date.strftime('%Y-%m')) |
                (monthly_average_photo_date.index == one_month_after) |
                (monthly_average_photo_date.index == two_months_after)
            ]

            # Display the filtered DataFrames
            st.write(f"Forecast update {current_date_str}")
            st.write(df_nucmonitor_filtered)
            st.write(f"Forecast update {past_date_str}")
            st.write(df_photo_date_filtered)

            current_forecast_update = df_nucmonitor_filtered.tolist()
            past_forecast_update = df_photo_date_filtered.tolist()
            delta = [current - past for current, past in zip(current_forecast_update, past_forecast_update)]

            print('Dates:', [two_months_before, one_month_before, current_date.strftime('%Y-%m'), one_month_after, two_months_after])
            print(f"Forecast update {current_date_str}", current_forecast_update)
            print(f"Forecast update {past_date_str}", past_forecast_update,)
            print('Delta', delta)

            # Create a DataFrame for display
            data_avg_expected_normal = {
                'Dates': [two_months_before, one_month_before, current_date.strftime('%Y-%m'), one_month_after, two_months_after],
                f"Forecast update {current_date_str}": current_forecast_update,
                f"Forecast update {past_date_str}": past_forecast_update,
                'Delta': delta
            }
            df_display_normal_bool = True

# --------------------------------- AVERAGE EXPECTED AVAILABILITY M-1 M M+1 M+2 PIPELINE --------------------------------- #

# --------------------------------- AVERAGE EXPECTED AVAILABILITY WINTER PIPELINE --------------------------------- #
        # Create a Table that displays the forecast of each dataframe for the Winter months (Nov, Dec, Jan, Feb, Mar)

        # Create a table that gets the forecast for winter. This involves creating a new dataframe with
        # only the winter months with the total of each day, and another dataframe with the average of each month. Each month
        # included will only be 20xx-11, 12, and 20xx+1-01, 02, 03
        
        # Define date ranges for winter months
        winter_start_date = current_date.replace(month=11, day=1)
        winter_end_date = (current_date.replace(year=current_date.year+1, month=3, day=31))
        winter_start = f"{current_date.year}-11"
        winter_end = f"{current_date.year+1}-03"
        winter_start_str = str(winter_start)
        winter_end_str = str(winter_end)
        print("winter_start_str", winter_start)
        print("winter_end_str", winter_end)
        print("monthly_average_nucmonitor.index", monthly_average_nucmonitor.index)
        print(monthly_average_nucmonitor.index == winter_start)
        print(monthly_average_nucmonitor.index == winter_end)
        if monthly_average_nucmonitor.index.any() != winter_start or monthly_average_nucmonitor.index.an() != winter_end:
            df_display_winter_bool = False

        else:
            # Filter DataFrames based on winter date range
            df_nucmonitor_winter = monthly_average_nucmonitor[(monthly_average_nucmonitor.index >= winter_start_str) & (monthly_average_nucmonitor.index <= winter_end_str)]

            df_photo_date_winter = monthly_average_photo_date[(monthly_average_photo_date.index >= winter_start_str) & (monthly_average_photo_date.index <= winter_end_str)]

            # Display the forecast DataFrames for winter
            st.title("Forecast for Winter Months")
            st.write(f"Forecast for {current_date.year}-{current_date.year+1} (Nov, Dec, Jan, Feb, Mar)")
            st.write("Nucmonitor Forecast:")
            st.write(df_nucmonitor_winter)
            st.write("Photo Date Forecast:")
            st.write(df_photo_date_winter)
            
            current_winter_forecast_update = df_nucmonitor_winter.tolist()
            past_winter_forecast_update = df_photo_date_winter.tolist()
            winter_delta = [current - past for current, past in zip(current_winter_forecast_update, past_winter_forecast_update)]
            print("current_winter_forecast_update:", current_winter_forecast_update)
            print("past_winter_forecast_update:", past_winter_forecast_update)

            # Create a DataFrame for display
            data_avg_expected_winter = {
                'Dates': [f'Nov-{current_date.year}', f'Dec-{current_date.year}', f'Jan-{current_date.year+1}', f'Feb-{current_date.year+1}', f'Mar-{current_date.year+1}'],
                f"Forecast update {current_date_str}": current_winter_forecast_update,
                f"Forecast update {past_date_str}": past_winter_forecast_update,
                'Delta': winter_delta
            }
            print(data_avg_expected_winter)
            df_display_winter_bool = True

# --------------------------------- AVERAGE EXPECTED AVAILABILITY WINTER PIPELINE --------------------------------- #

# --------------------------------- VISUALIZE --------------------------------- #
        if df_display_normal_bool:
            df_display_normal = pd.DataFrame(data_avg_expected_normal)
            # Display the DataFrame as a horizontal table
            st.write("Table 1. Average expected availability on the French nuclear fleet (MW) - M-1, M, M+1, M+2, M+3")
            st.table(df_display_normal)
        
        if df_display_winter_bool:
            df_display_winter = pd.DataFrame(data_avg_expected_winter)
            st.write(f"Table 2. Average expected availability on the French nuclear fleet (MW) - Winter {winter_start}/{winter_end}")
            st.table(df_display_winter)

        # Line charts of the forecasts (need to combine them so they appear in the same chart)
        st.write("Current forecast")
        st.line_chart(df_nucmonitor_2)

        st.write("Previous forecast")
        st.line_chart(df_photo_date_2)
        # Create a new dataframe out of df_nucmonitor_2 call real_forecast that contains df_nucmonitor_2 up until current_date

        # Slice the DataFrame to include data up until current_date
        real_forecast = df_nucmonitor_2.loc[df_nucmonitor_2.index <= current_date_str]

        # Winter forecast still not the correct one, this is just a placeholder
        # winter_forecast = df_nucmonitor_2.loc[(df_nucmonitor_2.index >= winter_start_date) & (df_nucmonitor_2.index <= winter_end_date)]
        
        # Optionally, if you want to reset the index
        # real_forecast = real_forecast.reset_index()
        print(real_forecast)
        st.write("Real forecast")
        st.line_chart(real_forecast)

        # Combine dataframes
        # combined_df = pd.concat([df_nucmonitor_2, df_photo_date_2, real_forecast, winter_forecast], axis=1)
        combined_df = pd.concat([df_nucmonitor_2, df_photo_date_2, real_forecast], axis=1)

        # combined_df.columns = [f'Forecast {current_date_str}', f'Forecast {past_date_str}', 'Real Forecast', f'Winter forecast {winter_start}/{winter_end}']
        combined_df.columns = [f'Forecast {current_date_str}', f'Forecast {past_date_str}', 'Real Forecast']

        print(combined_df)
        st.write(f"Graph 1. {start_date} to {end_date}")
        st.line_chart(combined_df)

        # # Set Nucmonitor as a dotted line until the current date

        # fig, ax = plt.subplots(figsize=(10, 6))

        # plt.plot(combined_df.index, combined_df[f'Forecast {current_date_str}'], 'r--', label=f'Forecast {current_date_str}')
        # plt.plot(combined_df.index, combined_df[f'Forecast {past_date_str}'], 'b-', label=f'Forecast {past_date_str}')

        # plt.axvline(current_date_str, color='k', linestyle='--', linewidth=1, label='Current Date')

        # # Set the x-axis to show only the first day of every month
        # ax.xaxis.set_major_locator(MonthLocator(bymonthday=1))

        # plt.legend()

        # plt.xticks(rotation=45)

        # st.pyplot(fig)

        # For Historical Winter Availability, can just get the max and min of each month, store as list in a column, and try to graph that


        # Add a download button
        # Create a BytesIO object to hold the Excel data

        excel_buffer = io.BytesIO()

    
        current_datetime = datetime.datetime.now()
        current_year = current_datetime.strftime('%Y')
        current_month = current_datetime.strftime('%m')
        current_day = current_datetime.strftime('%d')
        current_hour = current_datetime.strftime('%H')
        current_minute = current_datetime.strftime('%M')
        current_second = current_datetime.strftime('%S')


        # Save the DataFrame to the BytesIO object as an Excel file
        df_nucmonitor.to_excel(excel_buffer, index=True)
        # Set the cursor position to the beginning of the BytesIO object
        excel_buffer.seek(0)

        # Provide the BytesIO object to the download button
        download_button = st.download_button(
            label="Download Excel",
            data=excel_buffer,
            file_name=f"nucmonitor_data_{current_year}-{current_month}-{current_day}-h{current_hour}m{current_minute}s{current_second}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == '__main__':
    run_app()